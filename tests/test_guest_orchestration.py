"""Unit tests for SSH command execution and deployment orchestration.

All SSH clients, remote files and Docker actions are mocks.
"""
import io
import pytest
from leskdoo import guest


class Channel:
    def __init__(self, rc=0):
        self.rc = rc
        self.combined = False

    def set_combine_stderr(self, enabled):
        self.combined = enabled

    def recv_exit_status(self):
        return self.rc


class Output:
    def __init__(self, result, rc=0):
        self.result = result
        self.channel = Channel(rc)

    def read(self):
        return self.result


class FakeFile:
    def __init__(self, store, path):
        self.store = store
        self.path = path
        self.buffer = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.store[self.path] = "".join(self.buffer)

    def write(self, data):
        self.buffer.append(data)


class FakeSFTP:
    def __init__(self):
        self.files = {}
        self.closed = False

    def file(self, path, mode):
        assert mode == "w"
        return FakeFile(self.files, path)

    def close(self):
        self.closed = True


class FakeClient:
    def __init__(self, failure=None):
        self.failure = failure
        self.commands = []
        self.sftp = FakeSFTP()
        self.closed = False

    def exec_command(self, command, timeout):
        self.commands.append((command, timeout))
        if self.failure and self.failure in command:
            raise RuntimeError("remote unavailable")
        return None, Output(b"ok"), None

    def open_sftp(self):
        return self.sftp

    def close(self):
        self.closed = True


@pytest.mark.parametrize("exit_code,expected", [(0, "hello"), (2, None)])
def test_exec_checked_exit_code(exit_code, expected):
    class Client:
        def exec_command(self, command, timeout):
            assert command == "whoami"
            assert timeout == 20
            return None, Output(b"hello", exit_code), None
    if expected:
        assert guest.exec_checked(Client(), "whoami", timeout=20) == expected
    else:
        with pytest.raises(RuntimeError, match="Etapa Linux falhou"):
            guest.exec_checked(Client(), "whoami", timeout=20)


def test_ssh_session_first_connection(monkeypatch, tmp_path):
    events = []
    class FakeSSH:
        def set_missing_host_key_policy(self, policy):
            events.append(type(policy).__name__)
        def connect(self, *args, **kwargs):
            events.append(kwargs)
        def save_host_keys(self, value):
            events.append(("save", value))
    ssh = FakeSSH()
    monkeypatch.setattr(guest.paramiko, "SSHClient", lambda: ssh)
    key = tmp_path / "private"
    key.write_text("test")
    hostfile = tmp_path / "subdir" / "known_hosts"
    assert guest.ssh_session("aray", 2222, key, hostfile) is ssh
    assert events[0] == "AutoAddPolicy"
    assert events[1]["allow_agent"] is False
    assert events[1]["look_for_keys"] is False
    assert events[-1] == ("save", str(hostfile))


def test_ssh_session_known_host(monkeypatch, tmp_path):
    events = []
    class FakeSSH:
        def load_host_keys(self, value):
            events.append(("load", value))
        def set_missing_host_key_policy(self, policy):
            events.append(type(policy).__name__)
        def connect(self, *args, **kwargs):
            pass
    monkeypatch.setattr(guest.paramiko, "SSHClient", lambda: FakeSSH())
    hostfile = tmp_path / "known_hosts"
    hostfile.write_text("host key")
    guest.ssh_session("aray", 2222, tmp_path / "key", hostfile)
    assert events == [("load", str(hostfile)), "RejectPolicy"]


def test_guest_deploy_full_orchestration(monkeypatch, tmp_path):
    ssh = FakeClient()
    steps = []
    key = tmp_path / "key"
    key.write_text("private")
    monkeypatch.setattr(guest, "validate_ssh_key_path", lambda path: key)
    monkeypatch.setattr(guest, "wait_ssh", lambda port: steps.append(("port", port)))
    monkeypatch.setattr(guest, "ssh_session", lambda *args: ssh)
    result = guest.deploy("aray", 2222, str(key), str(tmp_path), lambda *x: steps.append(x))
    assert result == "ok"
    assert ssh.closed
    assert ssh.sftp.closed
    assert "zabbix-server" in ssh.sftp.files["/tmp/leskdoo-compose.yml"]
    assert "ZABBIX_DB_PASSWORD=" in ssh.sftp.files["/tmp/leskdoo.env"]
    assert "WEBUI_SECRET_KEY=" in ssh.sftp.files["/tmp/leskdoo.env"]
    assert ("port", 2222) in steps
    assert steps[-1][0] == "services_started"
    assert any("cloud-init status --wait" in cmd for cmd, _ in ssh.commands)
    assert any("ollama pull" in cmd for cmd, _ in ssh.commands)


def test_guest_deploy_closes_on_error(monkeypatch, tmp_path):
    ssh = FakeClient(failure="cloud-init status")
    monkeypatch.setattr(guest, "validate_ssh_key_path", lambda path: tmp_path / "key")
    monkeypatch.setattr(guest, "wait_ssh", lambda port: None)
    monkeypatch.setattr(guest, "ssh_session", lambda *args: ssh)
    with pytest.raises(RuntimeError, match="remote unavailable"):
        guest.deploy("aray", 2222, "key", str(tmp_path), lambda *x: None)
    assert ssh.closed
