"""Mock VirtualBox VM creation and failure paths; never touch real VMs."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from leskdoo import provision


def test_worker_success_no_real_virtualbox(monkeypatch, tmp_path):
    events = []
    def fake_vbox(*args):
        events.append(args)
        if args[0] == "createvm":
            return "Virtual machine created.\nUUID: 12345678-1234-1234-1234-123456789abc\n"
        return ""
    image = tmp_path / "cache-image.vmdk"
    image.write_bytes(b"simulated")
    monkeypatch.setattr(provision, "download_image", lambda path: image)
    monkeypatch.setattr(provision, "run_vbox", fake_vbox)
    monkeypatch.setattr(provision, "seed_iso", lambda path, *args: Path(path).write_bytes(b"seed"))
    states = []
    monkeypatch.setattr(provision, "update", lambda *args: states.append(args))
    provision.worker("job", {
        "name": "leskdoo-test", "directory": str(tmp_path),
        "ram_gb": 8, "vcpus": 4, "disk_gb": 60,
        "username": "aray", "ssh_key": "ssh-ed25519 AAAA",
        "ssh_port": 2222,
    })
    commands = [command[0] for command in events]
    assert "clonemedium" in commands
    assert "modifymedium" in commands
    assert "createvm" in commands
    assert "startvm" in commands
    assert states[-1][1] == "created"
    assert states[-1][3] == "12345678-1234-1234-1234-123456789abc"


def test_worker_existing_directory_rejected(monkeypatch, tmp_path):
    (tmp_path / "already").mkdir()
    statuses = []
    monkeypatch.setattr(provision, "update", lambda *args: statuses.append(args))
    provision.worker("job", {"name": "already", "directory": str(tmp_path)})
    assert statuses[-1][1] == "error"
    assert "já existe" in statuses[-1][2]


@pytest.fixture
def job_db(monkeypatch):
    engine = create_engine("sqlite://")
    provision.Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    monkeypatch.setattr(provision, "session_factory", lambda: factory)
    return factory


def test_update_and_jobs(job_db):
    with job_db() as session:
        session.add(provision.Job(id="abc", vm_name="leskdoo", state="queued"))
        session.commit()
    provision.update("abc", "running", "download", "12345678-1234-1234-1234-123456789abc")
    provision.update("missing", "running", "ignored")
    items = provision.jobs()
    assert len(items) == 1
    assert items[0]["state"] == "running"
    assert items[0]["uuid"] == "12345678-1234-1234-1234-123456789abc"


def test_start_services_rejects_unregistered(job_db):
    with pytest.raises(ValueError, match="não encontrado"):
        provision.start_services("missing", {})


def test_start_services_rejects_queued_job(job_db):
    with job_db() as session:
        session.add(provision.Job(id="abc", vm_name="ubuntu", state="queued"))
        session.commit()
    with pytest.raises(ValueError, match="precisa estar criada"):
        provision.start_services("abc", {})


def test_start_services_rejects_stopped_vm(job_db, monkeypatch):
    with job_db() as session:
        session.add(provision.Job(id="abc", vm_name="ubuntu", state="created"))
        session.commit()
    monkeypatch.setattr(provision, "virtual_machines", lambda: [
        {"name": "ubuntu", "state": "stopped"}
    ])
    with pytest.raises(ValueError, match="não está ligada"):
        provision.start_services("abc", {})


def test_start_services_rejects_ssh_parameters(job_db, monkeypatch, tmp_path):
    with job_db() as session:
        session.add(provision.Job(id="abc", vm_name="ubuntu", state="created"))
        session.commit()
    monkeypatch.setattr(provision, "virtual_machines", lambda: [
        {"name": "ubuntu", "state": "running"}
    ])
    with pytest.raises(ValueError, match="Usuário/porta"):
        provision.start_services("abc", {"username": "INVALID", "ssh_port": 22})


def test_start_services_rejects_key_file(job_db, monkeypatch, tmp_path):
    with job_db() as session:
        session.add(provision.Job(id="abc", vm_name="ubuntu", state="created"))
        session.commit()
    monkeypatch.setattr(provision, "virtual_machines", lambda: [
        {"name": "ubuntu", "state": "running"}
    ])
    from leskdoo import guest
    monkeypatch.setattr(guest, "validate_ssh_key_path", lambda p: (_ for _ in ()).throw(ValueError("invalid key")))
    with pytest.raises(ValueError, match="invalid key"):
        provision.start_services("abc", {"username": "aray", "ssh_port": 2222, "private_key_path": "missing", "vm_directory": str(tmp_path)})
