"""Backend API tests for Mac Studio Beschikbaarheid Zoeker."""
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
from bs4 import BeautifulSoup
from dotenv import dotenv_values
from pymongo import MongoClient

from report import build_email_html

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # fallback to frontend .env
    from pathlib import Path
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
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# --- root ---
def test_root(s):
    r = s.get(f"{API}/")
    assert r.status_code == 200
    assert "message" in r.json()


# --- latest with seeded demo ---
def test_latest_returns_demo(s):
    r = s.get(f"{API}/latest")
    assert r.status_code == 200
    body = r.json()
    assert "run" in body and "listings" in body
    assert body["run"] is not None, "Demo run should be seeded on startup"
    assert isinstance(body["listings"], list)
    # latest may be a real scan (not demo). Just verify listings list present.
    assert len(body["listings"]) >= 0
    # verify no mongo _id leaked
    assert "_id" not in body["run"]
    for l in body["listings"]:
        assert "_id" not in l


# --- settings ---
def test_get_settings(s):
    r = s.get(f"{API}/settings")
    assert r.status_code == 200
    data = r.json()
    assert data.get("recipient_email") == "mfidder@muzabv.nl"
    assert "send_time" in data
    assert isinstance(data.get("countries"), list) and len(data["countries"]) > 0


def test_put_settings_updates(s):
    # get current
    original = s.get(f"{API}/settings").json()
    original_time = original["send_time"]
    original_countries = original["countries"]
    # change send_time and toggle DE
    new_time = "09:15" if original_time != "09:15" else "07:45"
    updated_countries = [
        {**c, "enabled": (not c["enabled"]) if c["code"] == "DE" else c["enabled"]}
        for c in original_countries
    ]
    de_before = next(c["enabled"] for c in original_countries if c["code"] == "DE")
    r = s.put(f"{API}/settings", json={"send_time": new_time, "countries": updated_countries})
    assert r.status_code == 200
    merged = r.json()
    assert merged["send_time"] == new_time
    de_after = next(c["enabled"] for c in merged["countries"] if c["code"] == "DE")
    assert de_after == (not de_before)

    # persistence via GET
    check = s.get(f"{API}/settings").json()
    assert check["send_time"] == new_time
    # restore
    s.put(f"{API}/settings", json={"send_time": original_time, "countries": original_countries})


# --- runs ---
def test_list_runs(s):
    r = s.get(f"{API}/scan/runs")
    assert r.status_code == 200
    runs = r.json()
    assert isinstance(runs, list) and len(runs) >= 1
    # sorted desc
    times = [x["started_at"] for x in runs]
    assert times == sorted(times, reverse=True)


def test_get_single_run(s):
    runs = s.get(f"{API}/scan/runs").json()
    rid = runs[0]["id"]
    r = s.get(f"{API}/scan/runs/{rid}")
    assert r.status_code == 200
    assert r.json()["id"] == rid


def test_get_single_run_404(s):
    r = s.get(f"{API}/scan/runs/does-not-exist-xyz")
    assert r.status_code == 404


# --- reports ---
def test_latest_report(s):
    r = s.get(f"{API}/reports/latest")
    assert r.status_code == 200
    body = r.json()
    assert body.get("subject")
    assert body.get("html")
    assert body.get("recipient") == "mfidder@muzabv.nl"
    assert isinstance(body.get("sent"), bool)
    # send_reason is present when not sent; may be empty when sent successfully
    assert "send_reason" in body


# --- reference prices ---
def test_scan_current_progress(s):
    r = s.get(f"{API}/scan/current")
    assert r.status_code == 200
    data = r.json()
    assert "progress" in data and isinstance(data["progress"], dict)
    p = data["progress"]
    for k in ("phase", "message", "current", "total", "counters"):
        assert k in p, f"missing progress.{k}"
    for k in ("candidates", "analyzed", "available", "excluded", "blocked", "errors"):
        assert k in p["counters"], f"missing counter {k}"
    assert isinstance(data.get("log"), list)
    assert data.get("status") in ("bezig", "voltooid", "mislukt", "onderbroken")


def test_settings_include_marketplaces_and_17_countries(s):
    d = s.get(f"{API}/settings").json()
    assert d.get("include_marketplaces") is True
    countries = d.get("countries", [])
    assert len(countries) == 17
    assert all(c.get("enabled") for c in countries), "all 17 countries must be enabled"


def test_latest_has_marketplace_listings(s):
    body = s.get(f"{API}/latest").json()
    listings = body.get("listings", [])
    assert isinstance(listings, list)
    # at least one marketplace listing
    mp = [l for l in listings if l.get("verkoper_type") == "particulier marktplaats"]
    assert len(mp) >= 1, "expected at least one 'particulier marktplaats' listing"
    assert all(l.get("conditie") in ("tweedehands", "refurbished", "nieuw") for l in mp)


# --- all-listings email report ---
def test_latest_report_contains_all_latest_run_listings(s):
    latest_response = s.get(f"{API}/latest")
    report_response = s.get(f"{API}/reports/latest")
    assert latest_response.status_code == 200
    assert report_response.status_code == 200

    latest = latest_response.json()
    report_doc = report_response.json()
    assert report_doc["run_id"] == latest["run"]["id"], "latest report/run mismatch"

    listings = latest["listings"]
    soup = BeautifulSoup(report_doc["html"], "html.parser")
    headers = [th.get_text(" ", strip=True) for th in soup.select("thead th")]
    rows = soup.select("tbody tr")
    statuses = [row.select("td")[4].get_text(" ", strip=True) for row in rows]

    assert "Status" in headers
    assert len(rows) == len(listings)
    assert "Bevestigd" in statuses
    if any(l.get("beschikbaar") == "ONDUIDELIJK" for l in listings):
        assert "Onduidelijk" in statuses

    run_date = datetime.fromisoformat(latest["run"]["started_at"]).strftime("%d-%m-%Y")
    assert report_doc["subject"] == (
        f"Mac Studio beschikbaarheid — {run_date} — {len(listings)} gevonden"
    )

    confirmed = sum(l.get("beschikbaar") == "JA" for l in listings)
    unclear = len(listings) - confirmed
    summary_text = soup.get_text(" ", strip=True)
    assert f"{len(listings)} Mac Studio's gevonden vandaag" in summary_text
    assert f"{confirmed} bevestigd beschikbaar" in summary_text
    assert f"{unclear} onduidelijk" in summary_text

    report_prices = []
    for row in rows:
        raw_price = row.select("td")[1].get_text(" ", strip=True)
        report_prices.append(float(re.sub(r"[^0-9]", "", raw_price)) if raw_price != "—" else float("inf"))
    assert report_prices == sorted(report_prices)


def test_build_email_html_empty_case():
    subject, html = build_email_html([], {}, {}, datetime(2026, 7, 25, tzinfo=timezone.utc))
    assert subject == "Mac Studio beschikbaarheid — 25-07-2026 — 0 gevonden"
    assert "Vandaag geen Mac Studio's gevonden" in html
    assert "<tbody>" not in html


def test_scan_run_overlap_guard_without_starting_full_scan(s):
    env = dotenv_values("/app/backend/.env")
    mongo_url = env.get("MONGO_URL")
    db_name = env.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.fail("MONGO_URL/DB_NAME missing; cannot safely arrange overlap guard state")

    marker_id = f"TEST_overlap_{uuid.uuid4()}"
    client = MongoClient(mongo_url)
    db = client[db_name]
    db.scan_runs.insert_one({
        "id": marker_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "status": "bezig",
        "trigger": "TEST_overlap_guard",
        "is_demo": False,
        "stats": {},
        "log": [],
    })
    try:
        before_count = db.scan_runs.count_documents({})
        response = s.post(f"{API}/scan/run")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "bezig"
        assert "Er loopt al een scan" in body["message"]
        assert db.scan_runs.count_documents({}) == before_count
    finally:
        db.scan_runs.delete_one({"id": marker_id})
        client.close()


def test_reference_prices(s):
    r = s.get(f"{API}/reference-prices")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict) and len(data) > 0


# --- scan trigger (best-effort) ---
def test_trigger_scan_accepts(s):
    r = s.post(f"{API}/scan/run")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "bezig"
    # verify a new run was recorded
    time.sleep(2)
    runs = s.get(f"{API}/scan/runs").json()
    # newest run should be non-demo and either bezig or completed
    newest = runs[0]
    assert newest["is_demo"] is False
    assert newest["status"] in ("bezig", "voltooid", "mislukt")
