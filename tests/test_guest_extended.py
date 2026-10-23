"""Guest SSH guards and readiness failures; no SSH connections are made."""
from pathlib import Path
import pytest
from leskdoo import guest


def test_ssh_key_must_be_under_home(monkeypatch,tmp_path):
    home=tmp_path/"home"
    home.mkdir()
    monkeypatch.setattr(guest.Path,"home",lambda:home)
    outside=tmp_path/"elsewhere"
    outside.write_text("private key")
    with pytest.raises(ValueError,match="pasta do usuário"):
        guest.validate_ssh_key_path(str(outside))
    authorized=home/".ssh"
    authorized.mkdir()
    key=authorized/"test_ed25519"
    key.write_text("private key")
    assert guest.validate_ssh_key_path(str(key))==key


def test_ssh_port_timeout(monkeypatch):
    class Clock:
        count=0
        def monotonic(self):
            self.count+=10
            return self.count
    clock=Clock()
    monkeypatch.setattr(guest.time,"monotonic",clock.monotonic)
    monkeypatch.setattr(guest.socket,"create_connection",
        lambda *args,**kwargs: (_ for _ in ()).throw(OSError("unreachable")))
    with pytest.raises(TimeoutError,match="SSH"):
        guest.wait_ssh(2222,timeout=1)


def test_ssh_readiness_succeeds(monkeypatch):
    class Sock:
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(guest.socket,"create_connection",lambda *a,**k:Sock())
    guest.wait_ssh(2222,timeout=1)


def test_compose_defines_services():
    for component in ("zabbix-db:","zabbix-server:","zabbix-agent:","ollama:","chat:"):
        assert component in guest.COMPOSE
    assert "docker compose" in guest.SCRIPT
