"""Tests for provisioning input and Linux installation specifications.
These do not replace a Windows 11/VirtualBox integration test.
"""
from leskdoo.provision import safe_name
from leskdoo.guest import COMPOSE, SCRIPT

def test_vm_name_validation():
    assert safe_name("leskdoo-zabbix-ai")
    assert not safe_name("../../outside")
    assert not safe_name("a")
    assert not safe_name("vm with space")

def test_compose_has_full_stack():
    for component in ("zabbix-db:", "zabbix-server:", "zabbix-web:",
                      "zabbix-agent:", "ollama:", "chat:"):
        assert component in COMPOSE

def test_compose_requires_secrets():
    assert "ZABBIX_DB_PASSWORD:?required" in COMPOSE
    assert "WEBUI_SECRET_KEY:?required" in COMPOSE

def test_guest_installer_checks_compose():
    assert "config -q" in SCRIPT
    assert "up -d" in SCRIPT
