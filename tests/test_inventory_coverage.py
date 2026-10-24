"""Cover the host inventory adapters, VirtualBox command handling and PowerShell parsing.

No commands or disk queries reach the host.
"""
from types import SimpleNamespace
import subprocess
import pytest
from leskdoo import inventory


def test_command_success_and_error(monkeypatch):
    calls=[]
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="vm-output", stderr="")
    monkeypatch.setattr(inventory.subprocess,"run",run)
    assert inventory.command(["VBoxManage","list","vms"])=="vm-output"
    assert calls[0][1]["shell"] is False
    monkeypatch.setattr(inventory.subprocess,"run",
                        lambda *a,**kw:SimpleNamespace(returncode=1, stdout="fallback", stderr="error message"))
    with pytest.raises(RuntimeError,match="error message"):
        inventory.command(["invalid"])


def test_vbox_discovery_on_path_and_standard_install(monkeypatch,tmp_path):
    standard=tmp_path/"Oracle"/"VirtualBox"/"VBoxManage.exe"
    standard.parent.mkdir(parents=True)
    standard.touch()
    monkeypatch.setenv("ProgramFiles",str(tmp_path))
    monkeypatch.setattr(inventory.shutil,"which",lambda name:None)
    assert inventory.vbox_executable()==str(standard)
    monkeypatch.setattr(inventory.shutil,"which",lambda name:"D:/tools/VBoxManage.exe")
    assert inventory.vbox_executable()=="D:/tools/VBoxManage.exe"


def test_vbox_missing_and_success(monkeypatch):
    monkeypatch.setattr(inventory,"vbox_executable",lambda:None)
    with pytest.raises(RuntimeError,match="não encontrado"):
        inventory.vbox(["list","vms"])
    monkeypatch.setattr(inventory,"vbox_executable",lambda:"VBoxManage")
    calls=[]
    monkeypatch.setattr(inventory,"command",lambda args:calls.append(args) or "ok")
    assert inventory.vbox(["list","runningvms"])=="ok"
    assert calls==[["VBoxManage","list","runningvms"]]


@pytest.mark.parametrize("raw,expected",[
    ('[{"Name":"eth0"},{"Name":"eth1"}]',[{"Name":"eth0"},{"Name":"eth1"}]),
    ('{"Name":"single"}',[{"Name":"single"}]),
    ("null",[]),
])
def test_powershell_normalized(monkeypatch,raw,expected):
    monkeypatch.setattr(inventory.shutil,"which",lambda name:"pwsh")
    monkeypatch.setattr(inventory,"command",lambda args:raw)
    assert inventory.powershell_json("Get-NetAdapter")==expected


def test_powershell_unavailable_and_errors(monkeypatch):
    monkeypatch.setattr(inventory.shutil,"which",lambda name:None)
    assert inventory.powershell_json("Get-NetAdapter")==[]
    monkeypatch.setattr(inventory.shutil,"which",lambda name:"powershell.exe")
    def fail(args):
        raise subprocess.TimeoutExpired(args,5)
    monkeypatch.setattr(inventory,"command",fail)
    assert inventory.powershell_json("Get-NetAdapter")==[]


def test_host_inventory_with_disk_errors_and_missing_cpu(monkeypatch):
    giga=2**30
    monkeypatch.setattr(inventory.psutil,"virtual_memory",
                        lambda:SimpleNamespace(total=32*giga,available=18*giga))
    monkeypatch.setattr(inventory.psutil,"cpu_count",lambda logical:None)
    monkeypatch.setattr(inventory.psutil,"cpu_percent",lambda interval:12.5)
    monkeypatch.setattr(inventory.psutil,"disk_partitions",lambda all:[
        SimpleNamespace(device="C:",mountpoint="C:/"),
        SimpleNamespace(device="D:",mountpoint="D:/"),
        SimpleNamespace(device="E:",mountpoint="E:/"),
    ])
    def usage(path):
        if path=="D:/":raise PermissionError("denied")
        if path=="E:/":raise OSError("disconnected")
        return SimpleNamespace(free=100*giga,total=200*giga)
    monkeypatch.setattr(inventory.psutil,"disk_usage",usage)
    monkeypatch.setattr(inventory,"powershell_json",lambda script:[{"Name":"mock"}])
    monkeypatch.setattr(inventory,"vbox_executable",lambda:"VBoxManage")
    data=inventory.host_inventory()
    assert data["cpu_logical"]==1
    assert data["cpu_physical"]==1
    assert data["cpu_usage_pct"]==12.5
    assert data["ram_total_gb"]==32.0
    assert data["ram_available_gb"]==18.0
    assert data["disks"]==[{"device":"C:","mount":"C:/","free_gb":100.0,"total_gb":200.0}]
    assert data["virtualbox_installed"] is True
    assert data["adapters"]==[{"Name":"mock"}]


def test_vbox_discovery_no_executable(monkeypatch,tmp_path):
    monkeypatch.setenv("ProgramFiles",str(tmp_path))
    monkeypatch.setattr(inventory.shutil,"which",lambda name:None)
    assert inventory.vbox_executable() is None
