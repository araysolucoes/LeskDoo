"""Additional provision branches with isolated in-memory state."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import pytest
from leskdoo import provision, guest


def test_worker_uuid_fallback(monkeypatch, tmp_path):
    events=[]
    monkeypatch.setattr(provision,"update",lambda *args:events.append(args))
    monkeypatch.setattr(provision,"download_image",lambda folder:tmp_path/"fake.vmdk")
    monkeypatch.setattr(provision,"seed_iso",lambda *args:None)
    monkeypatch.setattr(provision,"run_vbox",lambda *args:"")
    provision.worker("id",{"name":"valid-vm","directory":str(tmp_path),"ram_gb":8,
                         "vcpus":4,"disk_gb":60,"username":"aray",
                         "ssh_key":"ssh-ed25519 AAAA","ssh_port":2222})
    assert events[-1][1]=="created"
    assert len(events[-1])==4
    assert events[-1][3] is None


@pytest.fixture
def stages(monkeypatch,tmp_path):
    engine=create_engine("sqlite:///"+str(tmp_path/"job.sqlite"))
    provision.Base.metadata.create_all(engine)
    factory=sessionmaker(engine)
    monkeypatch.setattr(provision,"session_factory",lambda:factory)
    monkeypatch.setattr(provision,"virtual_machines",
                        lambda:[{"name":"vm-test","state":"running"}])
    with factory() as s:
        s.add(provision.Job(id="job",vm_name="vm-test",state="services_error"))
        s.commit()
    monkeypatch.setattr(guest,"validate_ssh_key_path",lambda path:path)
    class Thread:
        def __init__(self,target,daemon):self.target=target
        def start(self):pass
    monkeypatch.setattr(provision.threading,"Thread",Thread)
    return factory,tmp_path


def test_retry_install_from_services_error(stages,monkeypatch):
    factory,tmp_path=stages
    assert provision.start_services("job",{
        "username":"aray","ssh_port":2222,
        "private_key_path":"mykey","vm_directory":str(tmp_path)
    })=="job"
    with factory() as s:
        assert s.get(provision.Job,"job").state=="services_queued"


def test_services_missing_private_key(stages):
    factory,tmp_path=stages
    with pytest.raises(ValueError,match="Dados SSH obrigatórios"):
        provision.start_services("job",{
            "username":"aray","ssh_port":2222,"vm_directory":str(tmp_path)
        })
    with factory() as s:
        assert s.get(provision.Job,"job").state=="created"
