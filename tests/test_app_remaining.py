"""Complete remaining uncovered error branches for the dashboard API."""
from leskdoo import app as app_module


def test_status_handles_inventory_backend_failures(monkeypatch):
    sample = {
        "ram_total_gb": 32, "ram_available_gb": 20,
        "cpu_logical": 16, "cpu_physical": 8,
        "disks": [{"mount": "C:/", "total_gb": 500, "free_gb": 300}],
        "virtualbox_installed": True, "gpus": [],
    }
    monkeypatch.setattr(app_module, "host_inventory", lambda: sample)
    def vms_error():
        raise RuntimeError("VirtualBox indisponível")
    def net_error():
        raise RuntimeError("Interfaces indisponíveis")
    monkeypatch.setattr(app_module, "virtual_machines", vms_error)
    monkeypatch.setattr(app_module, "network_interfaces", net_error)
    client = app_module.create_app().test_client()
    response = client.get("/api/status")
    assert response.status_code == 200
    assert response.json["vms"] == []
    assert response.json["bridged_interfaces"] == []
    assert response.json["warnings"] == ["VirtualBox indisponível", "Interfaces indisponíveis"]
