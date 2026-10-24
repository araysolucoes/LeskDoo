"""Remaining service-stage branches: mocks never connect to an actual guest."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from leskdoo import provision, guest


@pytest.fixture
def stage(monkeypatch,tmp_path):
    engine=create_engine("sqlite:///"+str(tmp_path/"jobs.sqlite"))
    provision.Base.metadata.create_all(engine)
    factory=sessionmaker(engine)
    monkeypatch.setattr(provision,"session_factory",lambda:factory)
    monkeypatch.setattr(provision,"virtual_machines",lambda:[{"name":"testvm","state":"running"}])
    with factory() as session:
        session.add(provision.Job(id="abc",vm_name="testvm",state="created"))
        session.commit()
    monkeypatch.setattr(guest,"validate_ssh_key_path",lambda value:tmp_path/"key")
    started=[]
    class Thread:
        def __init__(self,target,daemon):self.target=target
        def start(self):started.append(self.target)
    monkeypatch.setattr(provision.threading,"Thread",Thread)
    payload={"username":"aray","ssh_port":2222,"private_key_path":"key","vm_directory":str(tmp_path)}
    return factory,started,payload,tmp_path


def test_missing_ssh_fields(stage):
    factory,started,payload,folder=stage
    del payload["vm_directory"]
    with pytest.raises(ValueError,match="Dados SSH obrigatórios"):
        provision.start_services("abc",payload)
    assert not started


def test_missing_vm_folder(stage):
    factory,started,payload,folder=stage
    payload["vm_directory"]=str(folder/"unknown")
    with pytest.raises(ValueError,match="Pasta da VM"):
        provision.start_services("abc",payload)
    assert not started


def test_service_install_success(stage,monkeypatch):
    factory,started,payload,folder=stage
    activity=[]
    monkeypatch.setattr(guest,"deploy",lambda *args:activity.append(args))
    assert provision.start_services("abc",payload)=="abc"
    assert len(started)==1
    started[0]()
    assert len(activity)==1
    with factory() as s:
        assert s.get(provision.Job,"abc").state=="services_queued"


def test_service_install_failure_reported(stage,monkeypatch):
    factory,started,payload,folder=stage
    def fail(*args):raise RuntimeError("SSH connection interrupted")
    monkeypatch.setattr(guest,"deploy",fail)
    provision.start_services("abc",payload)
    started[0]()
    with factory() as s:
        j=s.get(provision.Job,"abc")
        assert j.state=="services_error"
        assert "SSH connection interrupted" in j.detail
