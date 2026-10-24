"""Administrative authentication is mandatory in non-test deployments."""
import base64
import pytest
from leskdoo.app import create_app


def auth(password, username="admin"):
    token=base64.b64encode((username+":"+password).encode()).decode()
    return {"Authorization":"Basic "+token}


def test_mutations_fail_closed_without_password(monkeypatch):
    monkeypatch.setenv("LESDKOO_ALLOW_MUTATIONS","true")
    monkeypatch.delenv("LESDKOO_ADMIN_PASSWORD",raising=False)
    app=create_app()
    app.config["TESTING"]=False
    client=app.test_client()
    response=client.get("/")
    assert response.status_code==503
    assert "LESDKOO_ADMIN_PASSWORD" in response.json["error"]


def test_admin_challenge_and_credentials(monkeypatch):
    monkeypatch.setenv("LESDKOO_ALLOW_MUTATIONS","true")
    monkeypatch.setenv("LESDKOO_ADMIN_PASSWORD","a-long-test-secret")
    app=create_app()
    app.config["TESTING"]=False
    client=app.test_client()
    for header in (None,auth("incorrect"),auth("a-long-test-secret","guest")):
        result=client.get("/",headers=header)
        assert result.status_code==401
        assert result.headers["WWW-Authenticate"].startswith("Basic")
    ok=client.get("/",headers=auth("a-long-test-secret"))
    assert ok.status_code==200


def test_read_only_dashboard_needs_no_password(monkeypatch):
    monkeypatch.setenv("LESDKOO_ALLOW_MUTATIONS","false")
    monkeypatch.delenv("LESDKOO_ADMIN_PASSWORD",raising=False)
    app=create_app()
    assert app.test_client().get("/").status_code==200
