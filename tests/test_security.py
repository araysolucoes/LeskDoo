"""Safety contracts: localhost-only operations and foreign-VM isolation."""
import pytest
from leskdoo import app as app_module


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv('LESDKOO_ALLOW_MUTATIONS', 'true')
    app = app_module.create_app()
    app.config['TESTING'] = True
    return app.test_client()


def test_external_origin_cannot_create_vm(client):
    res = client.post('/api/jobs', json={}, headers={'Origin': 'https://untrusted.example'})
    assert res.status_code == 403
    assert 'Origem' in res.json['error']


def test_remote_cannot_access_management_api(client):
    res = client.get('/api/status', environ_overrides={'REMOTE_ADDR': '192.168.1.5'})
    assert res.status_code == 403


def test_unmanaged_vm_cannot_be_started(client, monkeypatch):
    uuid = '12345678-1234-1234-1234-123456789abc'
    monkeypatch.setattr(app_module, 'virtual_machines',
        lambda: [{'name': 'pfSense', 'uuid': uuid, 'state': 'stopped'}])
    from leskdoo import provision
    monkeypatch.setattr(provision, 'jobs', lambda: [])
    invoked = []
    monkeypatch.setattr(app_module, 'vbox', lambda args: invoked.append(args))
    res = client.post('/api/vms/' + uuid + '/power', json={'action': 'start'})
    assert res.status_code == 403
    assert invoked == []


def test_managed_vm_power_is_allowed(client, monkeypatch):
    uuid = '12345678-1234-1234-1234-123456789abc'
    monkeypatch.setattr(app_module, 'virtual_machines',
        lambda: [{'name': 'leskdoo-test', 'uuid': uuid, 'state': 'stopped'}])
    from leskdoo import provision
    monkeypatch.setattr(provision, 'jobs', lambda: [{'uuid': uuid, 'name': 'leskdoo-test'}])
    invoked = []
    monkeypatch.setattr(app_module, 'vbox', lambda args: invoked.append(args))
    res = client.post('/api/vms/' + uuid + '/power', json={'action': 'start'})
    assert res.status_code == 200
    assert invoked == [['startvm', uuid, '--type', 'headless']]
