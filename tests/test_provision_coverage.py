"""Provisioning unit coverage for image verification, restart recovery and submit validation."""
import hashlib
import io
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from leskdoo import provision, inventory, planner


def test_session_factory_missing_url(monkeypatch):
    monkeypatch.setattr(provision, "_engine", None)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        provision.session_factory()


def test_session_factory_recovery(monkeypatch, tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path/"recovery.sqlite"))
    provision.Base.metadata.create_all(engine)
    with sessionmaker(engine)() as session:
        session.add_all([
            provision.Job(id="waiting", vm_name="test1", state="queued"),
            provision.Job(id="inflight", vm_name="test2", state="running"),
            provision.Job(id="complete", vm_name="test3", state="created"),
        ])
        session.commit()
    monkeypatch.setattr(provision, "_engine", None)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setattr(provision, "create_engine", lambda *a, **kw: engine)
    factory = provision.session_factory()
    with factory() as session:
        assert session.get(provision.Job, "waiting").state == "interrupted"
        assert session.get(provision.Job, "inflight").state == "interrupted"
        assert session.get(provision.Job, "complete").state == "created"
    monkeypatch.setattr(provision, "_engine", None)


def test_run_vbox_wrapper(monkeypatch):
    monkeypatch.setattr(provision, "vbox", lambda args: args)
    assert provision.run_vbox("list", "vms") == ["list", "vms"]


def test_download_verified_mismatch_then_ok(monkeypatch, tmp_path):
    payload = b"ubuntu-image"
    checksum = hashlib.sha256(payload).hexdigest()
    manifest = (checksum + "  noble-server-cloudimg-amd64.vmdk\n").encode()
    class Response:
        def __init__(self, value):
            self.file = io.BytesIO(value)
        def read(self, size=-1):
            return self.file.read(size)
        def __enter__(self):return self
        def __exit__(self,*args):return False
    def download(url, **kwargs):
        if isinstance(url, str):return Response(manifest)
        return Response(payload)
    monkeypatch.setattr(provision.urllib.request, "urlopen", download)
    path = provision.download_image(tmp_path)
    assert path.read_bytes() == payload
    assert provision.download_image(tmp_path) == path


def test_download_rejects_corrupted_image(monkeypatch, tmp_path):
    digest = hashlib.sha256(b"correct").hexdigest()
    manifest = (digest + "  noble-server-cloudimg-amd64.vmdk\n").encode()
    class Response:
        def __init__(self, value):self.value=io.BytesIO(value)
        def read(self,size=-1):return self.value.read(size)
        def __enter__(self):return self
        def __exit__(self,*a):return False
    monkeypatch.setattr(provision.urllib.request,"urlopen",
                        lambda target,**kw:Response(manifest if isinstance(target,str) else b"bad"))
    with pytest.raises(RuntimeError,match="integridade"):
        provision.download_image(tmp_path)
    assert not (tmp_path/"noble-server-cloudimg-amd64.partial").exists()


class FakePath:
    def __init__(self, raw):
        self.raw=str(raw)
        self.drive = "C:"
        self.parents = (FakeParent("C:/"),)
    def expanduser(self):return self
    def resolve(self):return self
    def is_absolute(self):return True
    def __eq__(self,other):return self.raw == str(getattr(other,"raw",other))
    def __str__(self):return self.raw


class FakeParent:
    def __init__(self,raw):self.raw=raw
    def __eq__(self,other):return self.raw==str(getattr(other,"raw",other))


@pytest.fixture
def submit_env(monkeypatch, tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path/"jobs.sqlite"))
    provision.Base.metadata.create_all(engine)
    factory=sessionmaker(engine)
    monkeypatch.setattr(provision,"session_factory",lambda:factory)
    monkeypatch.setattr(provision,"vbox_executable",lambda:"VBoxManage")
    monkeypatch.setattr(inventory,"host_inventory",lambda:{
        "disks":[{"mount":"C:/","free_gb":1000}],
        "ram_available_gb":24, "cpu_logical":16,
    })
    monkeypatch.setattr(planner,"recommend",lambda host:{
        "eligible":True,"ram_gb":16,"vcpus":8,
    })
    monkeypatch.setattr(inventory,"virtual_machines",lambda:[])
    monkeypatch.setattr(provision, "Path", FakePath)
    class FreeSocket:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def connect_ex(self,*a):return 0 if busy[0] else 1
    busy=[False]
    import socket
    monkeypatch.setattr(socket,"socket",lambda:FreeSocket())
    starts=[]
    class FakeThread:
        def __init__(self, target, args, daemon):
            self.args=args
        def start(self):starts.append(self.args)
    monkeypatch.setattr(provision.threading,"Thread",FakeThread)
    config={"name":"valid-vm","username":"aray",
            "ssh_key":"ssh-ed25519 AAAA","ram_gb":8,"vcpus":4,
            "disk_gb":60,"ssh_port":2222,"directory":"C:/LeskDoo"}
    return config,busy,starts,factory


def test_submit_success(submit_env):
    config,busy,starts,factory=submit_env
    job_id=provision.submit(config)
    assert len(job_id)==24
    assert starts and starts[0][0]==job_id
    with factory() as s:
        assert s.get(provision.Job,job_id).state=="queued"


@pytest.mark.parametrize("field,value,message",[
    ("name","x","Nome"),("username","INVALID","Usuário"),
    ("ssh_key","not-a-key","chave pública"),("ram_gb",1,"ram_gb"),
    ("ram_gb",True,"ram_gb"),("vcpus",15,"vcpus"),
    ("disk_gb",10,"disk_gb"),("ssh_port",80,"Porta SSH"),
])
def test_submit_invalid_fields(submit_env,field,value,message):
    config,busy,starts,factory=submit_env
    config[field]=value
    with pytest.raises(ValueError,match=message):
        provision.submit(config)
    assert not starts


def test_submit_busy_port(submit_env):
    config,busy,starts,factory=submit_env
    busy[0]=True
    with pytest.raises(ValueError, match="já está em uso"):
        provision.submit(config)


def test_submit_duplicate_name(submit_env,monkeypatch):
    config,busy,starts,factory=submit_env
    monkeypatch.setattr(inventory,"virtual_machines",lambda:[{"name":"VALID-VM"}])
    with pytest.raises(ValueError,match="Já existe"):
        provision.submit(config)


def test_submit_ineligible(submit_env,monkeypatch):
    config,busy,starts,factory=submit_env
    monkeypatch.setattr(planner,"recommend",lambda h:{"eligible":False})
    with pytest.raises(ValueError,match="insuficiente"):
        provision.submit(config)


def test_submit_no_virtualbox(submit_env,monkeypatch):
    config,busy,starts,factory=submit_env
    monkeypatch.setattr(provision,"vbox_executable",lambda:None)
    with pytest.raises(ValueError,match="VirtualBox"):
        provision.submit(config)


def test_submit_disallowed_disk(submit_env,monkeypatch):
    config,busy,starts,factory=submit_env
    monkeypatch.setattr(inventory,"host_inventory",lambda:{"disks":[{"mount":"D:/","free_gb":1}]})
    with pytest.raises(ValueError,match="espaço"):
        provision.submit(config)
