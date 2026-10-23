"""Cover SSH socket retry and failure path without actual connections."""
import pytest
from leskdoo import guest


def test_wait_ssh_retries_before_success(monkeypatch):
    calls = []
    class FakeSocket:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    def connect(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionRefusedError("initial boot")
        return FakeSocket()
    monkeypatch.setattr(guest.socket, "create_connection", connect)
    monkeypatch.setattr(guest.time, "sleep", lambda seconds: calls.append("slept"))
    guest.wait_ssh(2222, timeout=30)
    assert calls == [1, "slept", 1]
