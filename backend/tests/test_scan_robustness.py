"""Unit-tests voor foutclassificatie, seed-URL's en parallelle scan (zonder netwerk/MongoDB)."""
import asyncio
import socket
import ssl
from urllib.parse import urlparse

import httpx
import pytest

import scanner

NL = {"code": "NL", "name": "Nederland", "currency": "EUR", "term": "Mac Studio", "enabled": True}
DE = {"code": "DE", "name": "Duitsland", "currency": "EUR", "term": "Mac Studio", "enabled": True}


@pytest.fixture(autouse=True)
def _geen_wachten_of_browser(monkeypatch):
    """Geen echte sleeps (extended retries) en geen Selenium in tests."""
    sleeps = []
    real_sleep = asyncio.sleep

    async def fake_sleep(sec, *a, **k):
        sleeps.append(sec)
        await real_sleep(0)

    monkeypatch.setattr(scanner.asyncio, "sleep", fake_sleep)
    monkeypatch.setenv("USE_SELENIUM", "false")
    return sleeps


def _fetch(handler):
    """Voert fetch_page uit tegen een nep-transport; geeft (resultaat, aantal requests)."""
    calls = []

    def wrapped(request):
        calls.append(request.url)
        return handler(request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(wrapped)) as client:
            return await scanner.fetch_page(client, "https://www.winkel.test/mac-studio", "NL")

    return asyncio.run(run()), len(calls)


def _raise(exc):
    def handler(request):
        raise exc
    return handler


# ---------------------------------------------------------------------------
# fetch_page: juiste reden per mislukte pagina
# ---------------------------------------------------------------------------
def test_404_is_niet_gevonden_zonder_retries(_geen_wachten_of_browser):
    (status, data), n = _fetch(lambda r: httpx.Response(404, text="Not found"))
    assert (status, data) == ("not_found", None)
    assert n == 1
    assert _geen_wachten_of_browser == []  # geen extended retries (2+4+6+8 s)


def test_410_is_niet_gevonden():
    (status, _), n = _fetch(lambda r: httpx.Response(410))
    assert status == "not_found" and n == 1


def test_ssl_fout_zonder_retries():
    exc = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
                             "certificate has expired (_ssl.c:1006)")
    (status, _), n = _fetch(_raise(exc))
    assert status == "ssl" and n == 1


def test_dns_fout_zonder_retries():
    (status, _), n = _fetch(_raise(httpx.ConnectError("[Errno -2] Name or service not known")))
    assert status == "dns" and n == 1


def test_connect_timeout_is_netwerkfout_zonder_retries():
    (status, _), n = _fetch(_raise(httpx.ConnectTimeout("timed out")))
    assert status == "network" and n == 1


def test_read_timeout_krijgt_wel_retries():
    (status, _), n = _fetch(_raise(httpx.ReadTimeout("read timed out")))
    assert status == "network"
    assert n == 1 + len(scanner.UA_POOL)


def test_403_overal_is_anti_bot():
    (status, _), n = _fetch(lambda r: httpx.Response(403, text="Forbidden"))
    assert status == "blocked"
    assert n == 1 + len(scanner.UA_POOL)


def test_challenge_pagina_is_anti_bot():
    html = "<html><head><title>Just a moment...</title></head><body>Checking</body></html>"
    (status, _), _ = _fetch(lambda r: httpx.Response(200, text=html))
    assert status == "blocked"


def test_serverfout_is_http_fout_geen_anti_bot():
    (status, _), _ = _fetch(lambda r: httpx.Response(500, text="Internal error"))
    assert status == "http_error"


def test_403_daarna_404_in_retry_is_niet_gevonden():
    codes = iter([403, 404])
    (status, _), n = _fetch(lambda r: httpx.Response(next(codes)))
    assert status == "not_found" and n == 2


def test_classify_error_volgt_exceptieketen():
    def chained(inner):
        try:
            try:
                raise inner
            except Exception as e:
                raise httpx.ConnectError("verbinding mislukt") from e
        except httpx.ConnectError as outer:
            return outer

    assert scanner._classify_error(chained(socket.gaierror(8, "nodename nor servname"))) == "dns"
    assert scanner._classify_error(chained(ssl.SSLCertVerificationError("bad cert"))) == "ssl"
    assert scanner._classify_error(httpx.ReadTimeout("x")) == "network"


def test_elke_status_heeft_een_reden():
    for status in ("blocked", "empty", "not_found", "dns", "network", "ssl", "http_error"):
        assert scanner.FETCH_REASONS[status]
    assert "anti-bot" in scanner.FETCH_REASONS["blocked"].lower()
    assert "anti-bot" not in scanner.FETCH_REASONS["not_found"].lower()


# ---------------------------------------------------------------------------
# Seed-URL's
# ---------------------------------------------------------------------------
DODE_DOMEINEN = (
    "bhphotofinding.com", "johnibuilders.com", "riga24.lv", "havells.com", "stuff.co.nz",
    "noa.ae", "compub.com", "magnus.com", "miraclesignals.com", "dubzz.com", "dubai-sell.com",
    "hudsons.com", "kojincomputer.jp", "goodmall.cy", "iway.com.mt", "ingressa.hr",
    "plivnica.hr", "bolt.si", "imaginatio.bg", "tirgus360.lv", "techfinder.at",
    "stormfront.co.uk", "mac-center.nl", "jumia.ae", "extraclear.com.sg", "invertor.hu",
)


def _alle_seeds():
    for bron in (scanner.SEED_URLS, scanner.MARKETPLACE_SEED_URLS):
        for land, urls in bron.items():
            for u in urls:
                yield land, u


def test_seeds_bevatten_geen_dode_of_verzonnen_domeinen():
    fout = [(land, u) for land, u in _alle_seeds()
            if any(urlparse(u).netloc.endswith(d) for d in DODE_DOMEINEN)]
    assert fout == []


def test_seeds_geldig_en_zonder_dubbels():
    for bron in (scanner.SEED_URLS, scanner.MARKETPLACE_SEED_URLS):
        for land, urls in bron.items():
            assert len(urls) == len(set(urls)), land
            for u in urls:
                p = urlparse(u)
                assert p.scheme == "https" and "." in p.netloc, u


def test_geen_buitenlandse_winkels_in_verkeerd_land():
    assert not any("currys.co.uk" in u for u in scanner.SEED_URLS["AE"])
    assert not any("digitec.ch" in u for u in scanner.SEED_URLS["DE"])


def test_geen_apple_store_voor_landen_zonder_online_store():
    zonder_store = ("BG", "CY", "EE", "HR", "LT", "LV", "MT", "RO", "SI", "SK")
    for land in zonder_store:
        assert not any("apple.com/" in u for u in scanner.SEED_URLS.get(land, [])), land


# ---------------------------------------------------------------------------
# Zoeken
# ---------------------------------------------------------------------------
def test_ddgs_gebruikt_vaste_backend_en_korte_timeout(monkeypatch):
    import ddgs

    gebruikt = {}

    class FakeDDGS:
        def __init__(self, timeout=None, **k):
            gebruikt["timeout"] = timeout

        def text(self, term, region=None, max_results=None, backend="auto"):
            gebruikt["backend"] = backend
            return [{"href": "https://www.amac.nl/mac-studio"}]

    monkeypatch.setattr(ddgs, "DDGS", FakeDDGS)
    assert scanner._ddgs_search("Mac Studio", "nl-nl", 5) == ["https://www.amac.nl/mac-studio"]
    assert "wikipedia" not in gebruikt["backend"] and "mojeek" not in gebruikt["backend"]
    assert gebruikt["backend"] != "auto"
    assert gebruikt["timeout"] == scanner.DDGS_TIMEOUT


# ---------------------------------------------------------------------------
# perform_scan: redenen, parallelle verwerking en annuleren
# ---------------------------------------------------------------------------
class _Coll:
    def __init__(self):
        self.docs = []

    async def update_one(self, *a, **k):
        return None

    async def insert_one(self, doc):
        self.docs.append(doc)


class _DB:
    def __init__(self):
        self.scan_runs = _Coll()
        self.listings = _Coll()


def _scan_setup(monkeypatch, fetch, countries=(NL, DE)):
    async def no_fx(client):
        return False

    async def no_search(client, country, term, max_results, include_mp):
        await asyncio.sleep(0)
        return []

    async def no_items(*a, **k):
        return []

    monkeypatch.setattr(scanner, "refresh_fx_rates", no_fx)
    monkeypatch.setattr(scanner, "search_urls", no_search)
    monkeypatch.setattr(scanner, "analyze_page", no_items)
    monkeypatch.setattr(scanner, "fetch_page", fetch)
    monkeypatch.delenv("USE_PLAYWRIGHT", raising=False)
    settings = {"countries": [dict(c) for c in countries], "include_marketplaces": False,
                "max_pages_per_run": 50}
    return settings


def test_perform_scan_rapporteert_juiste_reden(monkeypatch):
    statussen = {
        "https://a.test/": "not_found", "https://b.test/": "ssl", "https://c.test/": "network",
        "https://d.test/": "blocked", "https://e.test/": "dns",
    }
    monkeypatch.setattr(scanner, "SEED_URLS", {"NL": list(statussen), "DE": []})

    async def fetch(client, url, cc, browser=None):
        return (statussen[url], None)

    settings = _scan_setup(monkeypatch, fetch)
    stats, log = asyncio.run(scanner.perform_scan(_DB(), settings, "run-1"))

    redenen = {b["url"]: b["reason"] for b in stats["blocked_urls"]}
    assert redenen == {u: scanner.FETCH_REASONS[s] for u, s in statussen.items()}
    assert stats["blocked"] == 1  # alleen de echte anti-bot pagina
    assert stats["errors"] == 4
    assert sum("Anti-bot" in regel for regel in log) == 1


def test_perform_scan_verwerkt_paginas_parallel_met_limiet(monkeypatch):
    urls = [f"https://w{i}.test/" for i in range(12)]
    monkeypatch.setattr(scanner, "SEED_URLS", {"NL": urls[:6], "DE": urls[6:]})
    actief = {"nu": 0, "max": 0}

    async def fetch(client, url, cc, browser=None):
        actief["nu"] += 1
        actief["max"] = max(actief["max"], actief["nu"])
        for _ in range(5):
            await asyncio.sleep(0)
        actief["nu"] -= 1
        return ("not_found", None)

    settings = _scan_setup(monkeypatch, fetch)
    stats, _ = asyncio.run(scanner.perform_scan(_DB(), settings, "run-2"))
    assert stats["candidates"] == 12
    assert len(stats["blocked_urls"]) == 12
    assert 1 < actief["max"] <= scanner.PAGE_CONCURRENCY


def test_perform_scan_overleeft_exceptie_in_een_pagina(monkeypatch):
    monkeypatch.setattr(scanner, "SEED_URLS", {"NL": ["https://kapot.test/", "https://ok.test/"]})

    async def fetch(client, url, cc, browser=None):
        if "kapot" in url:
            raise RuntimeError("boem")
        return ("not_found", None)

    settings = _scan_setup(monkeypatch, fetch, countries=(NL,))
    stats, _ = asyncio.run(scanner.perform_scan(_DB(), settings, "run-3"))
    assert stats["errors"] == 2
    assert [b["url"] for b in stats["blocked_urls"]] == ["https://ok.test/"]


def test_annuleren_stopt_alle_lopende_paginas(monkeypatch):
    monkeypatch.setattr(scanner, "SEED_URLS", {"NL": [f"https://w{i}.test/" for i in range(8)]})
    gestart, geannuleerd = [], []

    async def fetch(client, url, cc, browser=None):
        gestart.append(url)
        try:
            await asyncio.Event().wait()  # blijft hangen tot annulering
        except asyncio.CancelledError:
            geannuleerd.append(url)
            raise

    settings = _scan_setup(monkeypatch, fetch, countries=(NL,))

    async def run():
        task = asyncio.create_task(scanner.perform_scan(_DB(), settings, "run-4"))
        while len(gestart) < scanner.PAGE_CONCURRENCY:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert len(gestart) == scanner.PAGE_CONCURRENCY  # semafoor houdt de rest tegen
    assert sorted(geannuleerd) == sorted(gestart)
