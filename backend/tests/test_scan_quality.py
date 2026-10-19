"""Unit-tests voor API-beveiliging en scan-kwaliteit (zonder draaiende server/MongoDB)."""
import asyncio
import os

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "maczoeker_unittest")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import scanner  # noqa: E402
import server  # noqa: E402

NL = {"code": "NL", "name": "Nederland", "currency": "EUR"}
GB = {"code": "GB", "name": "Verenigd Koninkrijk", "currency": "GBP"}


# ---------------------------------------------------------------------------
# API-beveiliging
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    return TestClient(server.app)  # zonder 'with' → geen startup-hooks/MongoDB


def test_api_open_without_token(client, monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    assert client.get("/api/").status_code == 200


def test_api_requires_token_when_set(client, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "geheim-123")
    assert client.get("/api/").status_code == 401
    assert client.get("/api/", headers={"X-API-Key": "fout"}).status_code == 401
    assert client.get("/api/", headers={"X-API-Key": "geheim-123"}).status_code == 200
    assert client.get("/api/health").status_code == 200  # healthcheck blijft open


@pytest.mark.parametrize("payload", [
    {"send_time": "25:00"},
    {"send_time": "8"},
    {"recipient_email": "geen-email"},
    {"max_pages_per_run": 0},
    {"smtp_port": "abc"},
    {"smtp_from": "a@b.nl\r\nBcc: x@y.nl"},
    {"countries": [{"code": "nederland", "name": "NL", "term": "x", "currency": "EUR"}]},
    {"onbekend_veld": 1},
])
def test_invalid_settings_rejected(client, monkeypatch, payload):
    monkeypatch.delenv("API_TOKEN", raising=False)
    assert client.put("/api/settings", json=payload).status_code == 422


def test_cors_only_allows_local_frontend(client):
    r = client.options("/api/", headers={"Origin": "https://evil.example",
                                         "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") != "https://evil.example"
    r = client.options("/api/", headers={"Origin": "http://localhost:3000",
                                         "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


# ---------------------------------------------------------------------------
# Zoektermen
# ---------------------------------------------------------------------------
def test_search_terms_strip_old_chip_and_add_generations():
    terms = scanner.search_terms("Mac Studio kopen M3")
    assert terms[0] == "Mac Studio kopen"
    assert any("M5" in t for t in terms) and any("M4 Max" in t for t in terms)


# ---------------------------------------------------------------------------
# Structured data
# ---------------------------------------------------------------------------
JSONLD_PAGE = """<html><head><title>Apple Mac Studio M4 Max</title>
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[{"@type":"Product","name":"Apple Mac Studio M4 Max 36GB 512GB",
 "offers":{"@type":"Offer","price":"2399.00","priceCurrency":"EUR",
 "availability":"https://schema.org/InStock"}}]}
</script></head><body>""" + "<p>Bestel vandaag.</p>" * 30 + "</body></html>"


def test_structured_offer_extracted():
    page = scanner._parse_html(JSONLD_PAGE, "https://shop.example/p")
    assert page["offers"] == [{"name": "Apple Mac Studio M4 Max 36GB 512GB", "price": 2399.0,
                               "currency": "EUR", "availability": "InStock", "url": None}]
    assert scanner._mentions_mac_studio(page)


@pytest.mark.parametrize("raw,expected", [
    ("2.399,00", 2399.0), ("2,399.00", 2399.0), ("2399", 2399.0), ("€ 2.399", 2399.0),
    ("1.234.567", 1234567.0), ("49,95", 49.95), (2399, 2399.0), ("", None), (None, None),
])
def test_to_float(raw, expected):
    assert scanner._to_float(raw) == expected


def test_relevant_text_keeps_mac_studio_section():
    text = "menu " * 5000 + "Apple Mac Studio M4 Max voor € 2.399" + " footer" * 5000
    out = scanner._relevant_text(text)
    assert len(out) <= scanner.PROMPT_TEXT_LIMIT + 50
    assert "Mac Studio M4 Max voor € 2.399" in out


# ---------------------------------------------------------------------------
# Normalisatie / validatie van LLM-uitvoer
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("M4 Max", ("M4 Max", True)), ("apple m3ultra 28-core", ("M3 Ultra", True)),
    ("M3 Max", ("M3 Max", False)), ("M4 Ultra", ("M4 Ultra", False)),
    ("M4 Pro", ("M4 Pro", False)), ("onbekend", (None, True)), (None, (None, True)),
])
def test_normalize_chip(raw, expected):
    assert scanner.normalize_chip(raw) == expected


@pytest.mark.parametrize("code,name,expected", [
    ("de", "Duitsland", "DE"), ("UK", "", "GB"), ("leederland", "", "NL"),
    ("", "onbekend", "NL"), ("", "germany", "DE"),
])
def test_clean_country_code(code, name, expected):
    assert scanner.clean_country_code(code, name, "NL") == expected


@pytest.mark.parametrize("price,text,expected", [
    (2399, "Nu voor € 2.399,00 bij ons", True),
    (2399, "Now £2,399 only", True),
    (2399, "Prijs 2 399 kr", True),
    (2399, "Prijs € 12.399", False),
    (2399, "Prijs € 2.3990", False),
    (2399, "Prijs € 2.399.000", False),
    (2399, "Geen prijs hier", False),
])
def test_price_in_text(price, text, expected):
    assert scanner._price_in_text(price, text) is expected


def _page(text="Apple Mac Studio " * 20, offers=None):
    return {"title": "Mac Studio", "text": text, "links": [], "offers": offers or []}


def test_build_listing_rejects_non_studio_chip():
    a = {"beschikbaar": "JA", "chip": "M4 Pro", "prijs": 1499, "valuta": "EUR"}
    listing, reden = scanner.build_listing(a, _page("Mac mini M4 Pro € 1.499"), "https://x.nl", NL, "r", {})
    assert listing is None and "chip" in reden


def test_build_listing_drops_hallucinated_price():
    a = {"beschikbaar": "JA", "chip": "M4 Max", "prijs": 1999, "valuta": "EUR"}
    listing, _ = scanner.build_listing(a, _page("Mac Studio M4 Max, op voorraad"), "https://x.nl",
                                       NL, "r", scanner.REFERENCE_PRICES)
    assert listing is not None and listing["prijs_eur"] is None


def test_build_listing_uses_structured_price_and_availability():
    offers = [{"name": "Apple Mac Studio M4 Max", "price": 2399.0, "currency": "EUR",
               "availability": "InStock", "url": None}]
    a = {"beschikbaar": "ONDUIDELIJK", "chip": "M4 Max", "prijs": None,
         "verzend_land_code": "leederland", "conditie": "New"}
    listing, _ = scanner.build_listing(a, _page(offers=offers), "https://x.nl", NL, "r",
                                       scanner.REFERENCE_PRICES)
    assert listing["prijs_eur"] == 2399.0
    assert listing["beschikbaar"] == "JA"
    assert listing["land_mismatch"] is False
    assert listing["conditie"] == "nieuw"


def test_build_listing_out_of_stock_excluded():
    offers = [{"name": "Mac Studio", "price": 2399.0, "currency": "EUR",
               "availability": "OutOfStock", "url": None}]
    a = {"beschikbaar": "JA", "chip": "M4 Max", "prijs": 2399}
    listing, reden = scanner.build_listing(a, _page(offers=offers), "https://x.nl", NL, "r", {})
    assert listing is None and reden == "niet beschikbaar"


def test_build_listing_defaults_currency_to_country():
    a = {"beschikbaar": "JA", "chip": "M4 Max", "prijs": 2099, "valuta": ""}
    listing, _ = scanner.build_listing(a, _page("Mac Studio M4 Max £2,099"), "https://x.co.uk",
                                       GB, "r", scanner.REFERENCE_PRICES)
    assert listing["valuta"] == "GBP"
    assert listing["prijs_eur"] == round(2099 * scanner._fx_rates["GBP"], 2)


# ---------------------------------------------------------------------------
# Wisselkoersen
# ---------------------------------------------------------------------------
class _Resp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class _Client:
    def __init__(self, text):
        self._text = text

    async def get(self, *a, **k):
        return _Resp(self._text)


def test_refresh_fx_rates_parses_ecb(monkeypatch):
    monkeypatch.setattr(scanner, "_fx_rates", dict(scanner.FX_TO_EUR))
    cubes = "".join(f"<Cube currency='{c}' rate='{r}'/>" for c, r in [
        ("USD", "1.25"), ("JPY", "160"), ("GBP", "0.8"), ("CHF", "0.95"), ("SEK", "11"),
        ("DKK", "7.46"), ("PLN", "4.3"), ("NOK", "11.5"), ("CZK", "25"), ("HUF", "390")])
    assert asyncio.run(scanner.refresh_fx_rates(_Client(cubes))) is True
    assert scanner._fx_rates["USD"] == pytest.approx(0.8)
    assert scanner._fx_rates["AED"] == pytest.approx(0.8 / scanner.AED_PER_USD)


def test_refresh_fx_rates_keeps_fallback_on_garbage(monkeypatch):
    monkeypatch.setattr(scanner, "_fx_rates", dict(scanner.FX_TO_EUR))
    assert asyncio.run(scanner.refresh_fx_rates(_Client("<html>storing</html>"))) is False
    assert scanner._fx_rates == scanner.FX_TO_EUR


# ---------------------------------------------------------------------------
# Instellingen: meerdere ontvangers, tijd met seconden, duidelijke fouten
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("a@b.nl", "a@b.nl"),
    ("a@b.nl, c@d.nl", "a@b.nl, c@d.nl"),
    ("a@b.nl;c@d.nl;", "a@b.nl, c@d.nl"),
    ("", ""),
])
def test_recipients_accepted_and_normalized(raw, expected):
    assert server.SettingsUpdate(recipient_email=raw).recipient_email == expected


def test_invalid_recipient_names_the_address():
    with pytest.raises(Exception) as exc:
        server.SettingsUpdate(recipient_email="a@b.nl, fout-adres")
    assert "fout-adres" in str(exc.value)


@pytest.mark.parametrize("raw,expected", [("08:00", "08:00"), ("8:05", "08:05"), ("08:00:00", "08:00")])
def test_send_time_normalized(raw, expected):
    assert server.SettingsUpdate(send_time=raw).send_time == expected


def test_send_email_to_multiple_recipients(monkeypatch):
    import report
    sent = {}

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def ehlo(self): pass
        def starttls(self, **k): pass
        def login(self, *a): pass
        def sendmail(self, frm, to, msg): sent["to"] = to

    monkeypatch.setattr(report.smtplib, "SMTP", FakeSMTP)
    res = report.send_email("s", "<p>x</p>", "a@b.nl; c@d.nl",
                            {"smtp_host": "smtp.example", "smtp_port": "587", "smtp_from": "x@y.nl"})
    assert res["sent"] is True
    assert sent["to"] == ["a@b.nl", "c@d.nl"]
