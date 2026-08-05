"""Backend tests for SMTP settings + /api/email/test endpoint."""
import os
import pytest
import requests
from pathlib import Path

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = (BASE_URL or "").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    yield sess
    # cleanup: leave smtp_host empty so scheduled scans don't attempt bad SMTP
    sess.put(f"{API}/settings", json={
        "smtp_host": "", "smtp_user": "", "smtp_from": "", "smtp_port": "587"
    })


def test_get_settings_smtp_fields_present(s):
    r = s.get(f"{API}/settings")
    assert r.status_code == 200
    d = r.json()
    for k in ("smtp_host", "smtp_port", "smtp_user", "smtp_from"):
        assert k in d, f"missing {k}"
    # password always masked to empty string
    assert d.get("smtp_password") == ""
    assert "smtp_password_set" in d
    assert isinstance(d["smtp_password_set"], bool)


def test_email_test_without_smtp_configured(s):
    # ensure host empty first
    s.put(f"{API}/settings", json={"smtp_host": ""})
    r = s.post(f"{API}/email/test")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("sent") is False
    assert "SMTP niet geconfigureerd" in body.get("reason", "")


def test_put_smtp_password_and_preserve_on_empty(s):
    # 1) Set a password + host
    r = s.put(f"{API}/settings", json={
        "smtp_host": "smtp.invalid.example.com",
        "smtp_port": "587",
        "smtp_user": "test@example.com",
        "smtp_from": "test@example.com",
        "smtp_password": "supersecret123",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["smtp_host"] == "smtp.invalid.example.com"
    assert d["smtp_user"] == "test@example.com"
    assert d["smtp_password"] == ""  # masked
    assert d["smtp_password_set"] is True

    # 2) GET confirms masked + password_set true
    g = s.get(f"{API}/settings").json()
    assert g["smtp_password"] == ""
    assert g["smtp_password_set"] is True
    assert g["smtp_host"] == "smtp.invalid.example.com"

    # 3) PUT with empty password should PRESERVE
    r2 = s.put(f"{API}/settings", json={"smtp_password": "", "smtp_user": "test2@example.com"})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["smtp_password_set"] is True, "empty password must preserve existing"
    assert d2["smtp_user"] == "test2@example.com"

    # 4) GET again → still set
    g2 = s.get(f"{API}/settings").json()
    assert g2["smtp_password_set"] is True


def test_email_test_with_invalid_smtp_host_returns_smtp_fout(s):
    # host is already configured to invalid one from prev test
    r = s.post(f"{API}/email/test")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("sent") is False
    reason = body.get("reason", "")
    assert reason.startswith("SMTP-fout"), f"expected SMTP-fout prefix, got: {reason}"


def test_cleanup_smtp(s):
    """Reset smtp_host to empty so scheduled runs don't attempt bad SMTP."""
    r = s.put(f"{API}/settings", json={
        "smtp_host": "", "smtp_user": "", "smtp_from": ""
    })
    assert r.status_code == 200
    d = r.json()
    assert d["smtp_host"] == ""
    # password_set remains true (empty preserves) — acceptable, host is what gates sending
    # verify email/test now returns "niet geconfigureerd"
    t = s.post(f"{API}/email/test").json()
    assert t["sent"] is False
    assert "SMTP niet geconfigureerd" in t["reason"]
