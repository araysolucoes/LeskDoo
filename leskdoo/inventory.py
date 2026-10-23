"""Read-only host and VirtualBox inventory."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import psutil


def command(args, timeout=20):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                            shell=False, check=False, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip()[:500])
    return result.stdout


def vbox_executable():
    standard = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Oracle/VirtualBox/VBoxManage.exe"
    return shutil.which("VBoxManage") or (str(standard) if standard.exists() else None)


def vbox(args):
    executable = vbox_executable()
    if not executable:
        raise RuntimeError("VirtualBox não encontrado")
    return command([executable, *args])


def powershell_json(script):
    exe = shutil.which("powershell.exe") or shutil.which("pwsh")
    if not exe:
        return []
    try:
        data = json.loads(command([exe, "-NoProfile", "-NonInteractive", "-Command", script]))
        return data if isinstance(data, list) else ([data] if data else [])
    except (ValueError, RuntimeError, subprocess.TimeoutExpired):
        return []


def host_inventory():
    ram = psutil.virtual_memory()
    cpu = psutil.cpu_count(logical=True) or 1
    disks = []
    for disk in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(disk.mountpoint)
        except (PermissionError, OSError):
            continue
        disks.append({"device":disk.device,"mount":disk.mountpoint,
                      "free_gb":round(usage.free / 2**30, 1),"total_gb":round(usage.total / 2**30, 1)})
    physical = powershell_json("Get-PhysicalDisk | Select-Object FriendlyName,MediaType,Size | ConvertTo-Json -Compress")
    gpus = powershell_json("Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json -Compress")
    adapters = powershell_json("Get-NetAdapter | Select-Object Name,InterfaceDescription,Status,LinkSpeed | ConvertTo-Json -Compress")
    return {"ram_total_gb":round(ram.total/2**30,1),"ram_available_gb":round(ram.available/2**30,1),
            "cpu_logical":cpu,"cpu_physical":psutil.cpu_count(logical=False) or cpu,
            "cpu_usage_pct":psutil.cpu_percent(interval=0.1), "disks":disks,
            "physical_disks":physical,"gpus":gpus,"adapters":adapters,
            "virtualbox_installed":bool(vbox_executable())}


def virtual_machines():
    if not vbox_executable():
        return []
    all_vms = vbox(["list", "vms"])
    running = vbox(["list", "runningvms"])
    expression = re.compile(r'^"(.*)"\s+\{([0-9a-fA-F-]{36})\}$')
    active = {m.group(2) for line in running.splitlines() if (m:=expression.match(line))}
    return [{"name":m.group(1),"uuid":m.group(2),"state":"running" if m.group(2) in active else "stopped"}
            for line in all_vms.splitlines() if (m:=expression.match(line))]


def network_interfaces():
    if not vbox_executable():
        return []
    raw = vbox(["list", "bridgedifs"])
    return [line.split(":",1)[1].strip() for line in raw.splitlines() if line.startswith("Name:")]
