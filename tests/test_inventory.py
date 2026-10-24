"""VirtualBox inventory parser tests run without an installed hypervisor."""
from leskdoo import inventory


def test_vms_active_and_inactive(monkeypatch):
    uid1 = '12345678-1234-1234-1234-123456789abc'
    uid2 = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
    monkeypatch.setattr(inventory, 'vbox_executable', lambda: 'VBoxManage')
    def simulated(args):
        if args == ['list', 'vms']:
            return f'"pfSense" {{{uid1}}}\n"Ubuntu-server" {{{uid2}}}\n'
        if args == ['list', 'runningvms']:
            return f'"Ubuntu-server" {{{uid2}}}\n'
        raise AssertionError(args)
    monkeypatch.setattr(inventory, 'vbox', simulated)
    result = inventory.virtual_machines()
    assert result == [
        {'name': 'pfSense', 'uuid': uid1, 'state': 'stopped'},
        {'name': 'Ubuntu-server', 'uuid': uid2, 'state': 'running'}
    ]


def test_vms_when_virtualbox_absent(monkeypatch):
    monkeypatch.setattr(inventory, 'vbox_executable', lambda: None)
    assert inventory.virtual_machines() == []
    assert inventory.network_interfaces() == []


def test_bridged_adapter_names(monkeypatch):
    monkeypatch.setattr(inventory, 'vbox_executable', lambda: 'VBoxManage')
    monkeypatch.setattr(inventory, 'vbox', lambda args:
        'Name:            Realtek Gaming 2.5GbE Family Controller\n'
        'Status:          Up\n'
        'Name:            Wi-Fi\n')
    assert inventory.network_interfaces() == [
        'Realtek Gaming 2.5GbE Family Controller', 'Wi-Fi'
    ]


def test_powershell_invalid_output_returns_empty(monkeypatch):
    monkeypatch.setattr(inventory.shutil, 'which', lambda exe: 'powershell.exe')
    monkeypatch.setattr(inventory, 'command', lambda cmd: 'INVALID JSON')
    assert inventory.powershell_json('Get-NetAdapter') == []
