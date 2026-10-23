"""More API error and happy-path contracts with injected service mocks."""
import pytest
from leskdoo import app as mod


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LESDKOO_ALLOW_MUTATIONS","true")
    app=mod.create_app()
    app.config["TESTING"]=True
    return app.test_client()


def test_jobs_success(client,monkeypatch):
    from leskdoo import provision
    monkeypatch.setattr(provision,"jobs",lambda:[{"id":"abc","state":"queued"}])
    assert client.get("/api/jobs").json["jobs"][0]["id"]=="abc"


def test_jobs_error_returns_503(client,monkeypatch):
    from leskdoo import provision
    def failure():raise RuntimeError("database unavailable")
    monkeypatch.setattr(provision,"jobs",failure)
    res=client.get("/api/jobs")
    assert res.status_code==503
    assert "database unavailable" in res.json["error"]


def test_create_job_valid_payload(client,monkeypatch):
    from leskdoo import provision
    monkeypatch.setattr(provision,"submit",lambda d:"a"*24)
    res=client.post("/api/jobs",json={"name":"leskdoo"})
    assert res.status_code==202
    assert res.json["id"]=="a"*24


@pytest.mark.parametrize("value,expected",[(None,400),({"name":"vm"},202)])
def test_create_payload_validation(client,monkeypatch,value,expected):
    from leskdoo import provision
    monkeypatch.setattr(provision,"submit",lambda d:"a"*24)
    res=client.post("/api/jobs",json=value)
    assert res.status_code==expected


def test_create_job_rejected_parameter(client,monkeypatch):
    from leskdoo import provision
    def reject(_):raise ValueError("invalid input")
    monkeypatch.setattr(provision,"submit",reject)
    res=client.post("/api/jobs",json={})
    assert res.status_code==422


def test_create_job_service_down(client,monkeypatch):
    from leskdoo import provision
    def fail(_):raise RuntimeError("db offline")
    monkeypatch.setattr(provision,"submit",fail)
    res=client.post("/api/jobs",json={})
    assert res.status_code==503


def test_services_happy_path(client,monkeypatch):
    from leskdoo import provision
    monkeypatch.setattr(provision,"start_services",lambda job,payload:job)
    res=client.post("/api/jobs/"+"a"*24+"/services",json={"username":"aray"})
    assert res.status_code==202


def test_services_invalid_job_id(client):
    assert client.post("/api/jobs/bad-id/services",json={}).status_code==400


def test_services_invalid_payload(client):
    assert client.post("/api/jobs/"+"a"*24+"/services",json=[]).status_code==400


def test_services_value_error(client,monkeypatch):
    from leskdoo import provision
    def fail(*a):raise ValueError("bad SSH")
    monkeypatch.setattr(provision,"start_services",fail)
    res=client.post("/api/jobs/"+"a"*24+"/services",json={})
    assert res.status_code==422


def test_services_runtime_error(client,monkeypatch):
    from leskdoo import provision
    def fail(*a):raise RuntimeError("no PostgreSQL")
    monkeypatch.setattr(provision,"start_services",fail)
    res=client.post("/api/jobs/"+"a"*24+"/services",json={})
    assert res.status_code==503


def test_power_unknown_vm(client,monkeypatch):
    monkeypatch.setattr(mod,"virtual_machines",lambda:[])
    res=client.post("/api/vms/"+"a"*36+"/power",json={"action":"start"})
    assert res.status_code==404


def test_power_bad_action(client):
    res=client.post("/api/vms/"+"a"*36+"/power",json={"action":"delete"})
    assert res.status_code==400


def test_power_bad_uuid(client):
    res=client.post("/api/vms/bad/power",json={"action":"start"})
    assert res.status_code==400


def test_power_acpi_shutdown(client,monkeypatch):
    from leskdoo import provision
    uid="12345678-1234-1234-1234-123456789abc"
    monkeypatch.setattr(mod,"virtual_machines",lambda:[{"uuid":uid,"name":"vm","state":"running"}])
    monkeypatch.setattr(provision,"jobs",lambda:[{"uuid":uid}])
    calls=[]
    monkeypatch.setattr(mod,"vbox",lambda args:calls.append(args))
    res=client.post(f"/api/vms/{uid}/power",json={"action":"acpi_shutdown"})
    assert res.status_code==200
    assert calls==[["controlvm",uid,"acpipowerbutton"]]


def test_power_conflict(client,monkeypatch):
    from leskdoo import provision
    uid="12345678-1234-1234-1234-123456789abc"
    monkeypatch.setattr(mod,"virtual_machines",lambda:[{"uuid":uid,"name":"vm","state":"running"}])
    monkeypatch.setattr(provision,"jobs",lambda:[{"uuid":uid}])
    assert client.post(f"/api/vms/{uid}/power",json={"action":"start"}).status_code==409
