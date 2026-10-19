"""Unit-tests (zonder draaiende server/MongoDB) voor scan-annuleren, blokkade-detectie,
productlink-extractie en HTML-escaping van het rapport."""
import asyncio
import os
from datetime import datetime, timezone

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "maczoeker_unittest")

import report  # noqa: E402
import scanner  # noqa: E402


# ---------------------------------------------------------------------------
# Blokkade-detectie
# ---------------------------------------------------------------------------
NORMAL_SHOP = """<html><head><title>Mac Studio kopen | Winkel</title>
<script src="https://cdnjs.cloudflare.com/x.js"></script></head><body>
<p>Loading… Top performance met de M4 Max. Protected by onze garantie.</p>
<a href="/mac-studio-m4-max-36gb">Apple Mac Studio M4 Max 36GB 512GB</a>
<a href="https://www.ebay.de/itm/1234567890">eBay listing</a>
<a href="javascript:alert(1)">kwaad</a>
<a href="/over-ons">Over ons</a>
""" + "<p>Op voorraad, morgen in huis. Prijs € 2.399,00.</p>" * 20 + "</body></html>"

CHALLENGE = """<html><head><title>Just a moment...</title></head>
<body><p>Checking your browser before accessing the site. Ray ID: 123abc</p></body></html>"""


def test_normal_page_with_generic_words_is_not_blocked():
    data = scanner._parse_html(NORMAL_SHOP, "https://shop.example/mac")
    assert scanner._classify_page(data)[0] == "ok"


def test_challenge_page_is_blocked():
    data = scanner._parse_html(CHALLENGE, "https://shop.example/mac")
    assert scanner._classify_page(data) == ("blocked", None)


def test_short_page_without_block_phrases_is_empty():
    data = scanner._parse_html("<html><body>Hallo</body></html>")
    assert scanner._classify_page(data) == ("empty", None)


# ---------------------------------------------------------------------------
# Productlinks
# ---------------------------------------------------------------------------
def test_parse_html_returns_absolute_http_links_only():
    data = scanner._parse_html(NORMAL_SHOP, "https://shop.example/mac")
    urls = [l["url"] for l in data["links"]]
    assert "https://shop.example/mac-studio-m4-max-36gb" in urls
    assert "https://www.ebay.de/itm/1234567890" in urls
    assert not any(u.startswith("javascript:") for u in urls)


def test_candidate_product_links_returns_full_urls():
    data = scanner._parse_html(NORMAL_SHOP, "https://shop.example/mac")
    cands = [l["url"] for l in scanner._candidate_product_links(data["links"])]
    assert "https://shop.example/mac-studio-m4-max-36gb" in cands
    assert "https://www.ebay.de/itm/1234567890" in cands
    assert "https://shop.example/over-ons" not in cands


def test_prompt_contains_real_links():
    data = scanner._parse_html(NORMAL_SHOP, "https://shop.example/mac")
    prompt = scanner._build_prompt(data["text"], data["title"], "https://shop.example/mac",
                                   "Nederland", links=data["links"])
    assert "https://www.ebay.de/itm/1234567890" in prompt


def test_resolve_listing_url_rejects_unknown_and_unsafe_urls():
    links = [{"url": "https://shop.example/mac-studio-m4", "text": ""}]
    page = "https://shop.example/mac"
    assert scanner._resolve_listing_url("https://shop.example/mac-studio-m4", page, links) \
        == "https://shop.example/mac-studio-m4"
    assert scanner._resolve_listing_url("https://verzonnen.example/x", page, links) == page
    assert scanner._resolve_listing_url("javascript:alert(1)", page, links) == page
    assert scanner._resolve_listing_url("", page, links) == page


# ---------------------------------------------------------------------------
# HTML-escaping in rapport
# ---------------------------------------------------------------------------
def test_report_escapes_scraped_values_and_unsafe_links():
    evil = '<script>alert("x")</script>'
    listing = {
        "id": "1", "land": "Nederland", "land_code": "NL", "winkelnaam": evil,
        "chip": "M4 Max", "ram": "36GB", "opslag": "512GB", "prijs_eur": 2399.0,
        "beschikbaar": "JA", "advertentie_url": "javascript:alert(1)",
        "levertijd": '<img src=x onerror=alert(1)>', "marktconformiteit": "Marktconform",
    }
    stats = {"blocked_urls": [{"url": "javascript:alert(2)", "domain": evil, "reason": evil}]}
    _, html = report.build_email_html([listing], stats, {}, datetime.now(timezone.utc))
    assert "<script>" not in html
    assert "<img src=x" not in html
    assert "javascript:" not in html
    assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# Scan annuleren
# ---------------------------------------------------------------------------
class _Cursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *a, **k):
        return self

    async def to_list(self, n):
        return self.docs[:n]


class _Coll:
    def __init__(self):
        self.docs = []

    def _match(self, doc, flt):
        return all(doc.get(k) == v for k, v in (flt or {}).items())

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def count_documents(self, flt):
        return sum(self._match(d, flt) for d in self.docs)

    async def find_one(self, flt=None, *a, **k):
        return next((dict(d) for d in self.docs if self._match(d, flt)), None)

    def find(self, flt=None, *a, **k):
        return _Cursor([dict(d) for d in self.docs if self._match(d, flt)])

    async def update_one(self, flt, upd, upsert=False):
        for d in self.docs:
            if self._match(d, flt):
                d.update(upd.get("$set", {}))
                for k, v in upd.get("$push", {}).items():
                    d.setdefault(k, []).append(v)
                return


class _DB:
    def __init__(self):
        self.scan_runs, self.listings, self.email_reports, self.settings = _Coll(), _Coll(), _Coll(), _Coll()


def test_cancel_stops_running_scan_without_report(monkeypatch):
    import server

    db = _DB()
    monkeypatch.setattr(server, "db", db)
    started = asyncio.Event()
    finished_normally = []

    async def slow_scan(_db, _settings, _run_id):
        started.set()
        await asyncio.sleep(3600)
        finished_normally.append(True)
        return {}, []

    monkeypatch.setattr(server.scanner, "perform_scan", slow_scan)

    async def scenario():
        job = asyncio.ensure_future(server.run_scan_job("test"))
        await asyncio.wait_for(started.wait(), 5)
        res = await server.cancel_scan_job()
        await asyncio.wait_for(job, 5)
        return res

    res = asyncio.run(scenario())
    assert res["status"] == "onderbroken"
    assert not finished_normally
    run = db.scan_runs.docs[0]
    assert run["status"] == "onderbroken"
    assert db.email_reports.docs == []
    assert not server._scan_is_running()
