"""Provisioning error paths without disk downloads or real VirtualBox calls."""
import hashlib
import io
from pathlib import Path
import pytest
from leskdoo import provision


def test_safe_name_boundaries():
    assert provision.safe_name("server-123")
    for value in ("vm","/root","vm name","vm_name","a"*41):
        assert not provision.safe_name(value)


def test_sha256(tmp_path):
    target=tmp_path/"sample.bin"
    target.write_bytes(b"leskdoo")
    assert provision.sha256(target)==hashlib.sha256(b"leskdoo").hexdigest()


def test_download_uses_verified_cache(tmp_path,monkeypatch):
    content=b"verified ubuntu image bytes"
    digest=hashlib.sha256(content).hexdigest()
    target=tmp_path/"noble-server-cloudimg-amd64.vmdk"
    target.write_bytes(content)
    class FakeResponse:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return (digest+"  noble-server-cloudimg-amd64.vmdk\n").encode()
    calls=[]
    def response(url,timeout=0):
        calls.append(url)
        return FakeResponse()
    monkeypatch.setattr(provision.urllib.request,"urlopen",response)
    assert provision.download_image(tmp_path)==target
    assert len(calls)==1


def test_download_rejects_missing_checksum(tmp_path,monkeypatch):
    class FakeResponse:
        def read(self):return b"invalid manifest"
    monkeypatch.setattr(provision.urllib.request,"urlopen",lambda *a,**k:FakeResponse())
    with pytest.raises(RuntimeError,match="SHA256SUMS"):
        provision.download_image(tmp_path)


def test_job_worker_error_recorded(tmp_path,monkeypatch):
    transitions=[]
    monkeypatch.setattr(provision,"update",lambda *args:transitions.append(args))
    monkeypatch.setattr(provision,"download_image",lambda *args: (_ for _ in ()).throw(RuntimeError("download failed")))
    provision.worker("testjob",{"name":"vm-test","directory":str(tmp_path)})
    assert transitions[-1][1]=="error"
    assert "download failed" in transitions[-1][2]


def test_seed_iso_can_be_opened(tmp_path):
    import pycdlib
    path=tmp_path/"seed.iso"
    provision.seed_iso(path,"aray","ssh-ed25519 AAAABBBB comment","leskdoo-test")
    assert path.exists()
    image=pycdlib.PyCdlib()
    image.open(str(path))
    buffer=io.BytesIO()
    image.get_file_from_iso_fp(buffer,rr_path="/user-data")
    assert b"ssh-ed25519" in buffer.getvalue()
    image.close()
