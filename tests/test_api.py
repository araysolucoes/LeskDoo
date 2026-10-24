"""HTTP contract and default read-only protection, no VirtualBox required."""
import pytest

from leskdoo import app as app_module


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("LESDKOO_ALLOW_MUTATIONS", raising=False)
    app = app_module.create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_dashboard(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"LeskDoo" in res.data


def test_provision_denied_by_default(client):
    res = client.post("/api/jobs", json={"name": "example"})
    assert res.status_code == 403


def test_services_denied_by_default(client):
    res = client.post("/api/jobs/" + "a" * 24 + "/services", json={})
    assert res.status_code == 403


def test_vm_mutation_denied_by_default(client):
    res = client.post("/api/vms/" + "a" * 36 + "/power", json={"action": "start"})
    assert res.status_code == 403


def test_status_inventory_mocked(client, monkeypatch):
    fake = {
        "ram_available_gb": 20,
        "ram_total_gb": 32,
        "cpu_physical": 8,
        "cpu_logical": 16,
        "disks": [{"mount": "C:/", "free_gb": 300, "total_gb": 500}],
        "gpus": [],
        "adapters": [],
        "virtualbox_installed": True,
    }
    monkeypatch.setattr(app_module, "host_inventory", lambda: fake)
    monkeypatch.setattr(app_module, "virtual_machines", lambda: [])
    monkeypatch.setattr(app_module, "network_interfaces", lambda: [])
    res = client.get("/api/status")
    assert res.status_code == 200
    assert res.json["host"]["cpu_physical"] == 8
    assert res.json["recommendation"]["eligible"] is True
    assert res.json["vms"] == []
