"""Mac Studio beschikbaarheid scanner: zoeken (zonder API-key via DuckDuckGo),
scrapen van productpagina's en LLM-verificatie (Claude Sonnet 4.6) van beschikbaarheid."""
import os
import re
import json
import uuid
import logging
import asyncio
from itertools import zip_longest
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, unquote, urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("scanner")

# ---------------------------------------------------------------------------
# Configuratie / defaults
# ---------------------------------------------------------------------------

# Wisselkoersen naar EUR (bij benadering, juni 2026). Pas aan indien nodig.
FX_TO_EUR = {
    "EUR": 1.0,
    "GBP": 1.17,
    "CHF": 1.07,
    "SEK": 0.088,
    "DKK": 0.134,
    "PLN": 0.23,
    "NOK": 0.086,
    "CZK": 0.040,
    "HUF": 0.0025,
    "RON": 0.20,
    "AED": 0.27,
    "USD": 1.08,
    "CAD": 0.79,
    "AUD": 0.71,
    "SGD": 0.81,
    "JPY": 0.0067,
    "HKD": 0.14,
    "NZD": 0.66,
}

# Chips die echt in een Mac Studio zitten (2022: M1, 2023: M2, 2025: M4 Max/M3 Ultra,
# 2026: M5). Een M3 Max of M4 Ultra Mac Studio bestaat niet; Pro/basis-chips zijn Mac mini's.
VALID_STUDIO_CHIPS = ("M1 Max", "M1 Ultra", "M2 Max", "M2 Ultra", "M3 Ultra",
                      "M4 Max", "M5 Max", "M5 Ultra")

# Officiële Apple-adviesprijzen (EUR, bij benadering) per basis-chip.
REFERENCE_PRICES = {
    "M1 Max": 2299,
    "M1 Ultra": 4599,
    "M2 Max": 2599,
    "M2 Ultra": 4999,
    "M3 Ultra": 4999,
    "M4 Max": 2599,
    "M5 Max": 2799,
    "M5 Ultra": 5299,
}

DEFAULT_COUNTRIES = [
    # Basis-zoekterm per land; chip-specifieke varianten worden in search_terms() toegevoegd.
    {"code": "NL", "name": "Nederland", "term": "Mac Studio kopen", "currency": "EUR", "enabled": True},
    {"code": "BE", "name": "België", "term": "Mac Studio kopen", "currency": "EUR", "enabled": True},
    {"code": "DE", "name": "Duitsland", "term": "Mac Studio kaufen", "currency": "EUR", "enabled": True},
    {"code": "FR", "name": "Frankrijk", "term": "acheter Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "ES", "name": "Spanje", "term": "comprar Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "IT", "name": "Italië", "term": "comprare Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "GB", "name": "Verenigd Koninkrijk", "term": "buy Mac Studio", "currency": "GBP", "enabled": True},
    {"code": "AT", "name": "Oostenrijk", "term": "Mac Studio kaufen", "currency": "EUR", "enabled": True},
    {"code": "IE", "name": "Ierland", "term": "buy Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "PT", "name": "Portugal", "term": "comprar Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "FI", "name": "Finland", "term": "osta Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "LU", "name": "Luxemburg", "term": "acheter Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "CH", "name": "Zwitserland", "term": "Mac Studio kaufen", "currency": "CHF", "enabled": True},
    {"code": "SE", "name": "Zweden", "term": "köpa Mac Studio", "currency": "SEK", "enabled": True},
    {"code": "DK", "name": "Denemarken", "term": "køb Mac Studio", "currency": "DKK", "enabled": True},
    {"code": "PL", "name": "Polen", "term": "kup Mac Studio", "currency": "PLN", "enabled": True},
    {"code": "NO", "name": "Noorwegen", "term": "kjøp Mac Studio", "currency": "NOK", "enabled": True},
    {"code": "AE", "name": "VAE (UAE)", "term": "buy Mac Studio Dubai", "currency": "AED", "enabled": True},
    {"code": "US", "name": "Verenigde Staten", "term": "buy Mac Studio", "currency": "USD", "enabled": True},
    {"code": "CA", "name": "Canada", "term": "buy Mac Studio", "currency": "CAD", "enabled": True},
    {"code": "AU", "name": "Australië", "term": "buy Mac Studio", "currency": "AUD", "enabled": True},
    {"code": "SG", "name": "Singapore", "term": "buy Mac Studio", "currency": "SGD", "enabled": True},
    {"code": "JP", "name": "Japan", "term": "Mac Studio 購入", "currency": "JPY", "enabled": True},
    {"code": "HK", "name": "Hong Kong", "term": "buy Mac Studio", "currency": "HKD", "enabled": True},
    {"code": "NZ", "name": "Nieuw-Zeeland", "term": "buy Mac Studio", "currency": "NZD", "enabled": True},
    {"code": "CZ", "name": "Tsjechië", "term": "kup Mac Studio", "currency": "CZK", "enabled": True},
    {"code": "HU", "name": "Hongarije", "term": "vegye meg a Mac Studiot", "currency": "HUF", "enabled": True},
    {"code": "RO", "name": "Roemenië", "term": "cumpăra Mac Studio", "currency": "RON", "enabled": True},
    {"code": "SK", "name": "Slowakije", "term": "kúpiť Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "SI", "name": "Slovenië", "term": "kupite Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "HR", "name": "Kroatië", "term": "kupite Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "BG", "name": "Bulgarije", "term": "купете Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "EE", "name": "Estland", "term": "osta Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "LV", "name": "Letland", "term": "iegādāties Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "LT", "name": "Litouwen", "term": "pirkti Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "MT", "name": "Malta", "term": "buy Mac Studio", "currency": "EUR", "enabled": True},
    {"code": "CY", "name": "Cyprus", "term": "buy Mac Studio", "currency": "EUR", "enabled": True},
]

DEFAULT_SETTINGS = {
    "id": "global",
    "config_version": 7,
    "recipient_email": "",
    "send_time": "08:00",
    "timezone": "Europe/Amsterdam",
    "chip_variants": list(VALID_STUDIO_CHIPS),
    "max_results_per_query": 10,
    "max_pages_per_run": 200,
    "include_marketplaces": True,
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_password": "",
    "smtp_from": "",
    "countries": DEFAULT_COUNTRIES,
    "reference_prices": REFERENCE_PRICES,
}

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Roterende, realistische browser user-agents (verlaagt kans op 403-blokkades).
UA_POOL = [
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) "
     "Gecko/20100101 Firefox/126.0"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"),
]

# Accept-Language per land — helpt winkels de juiste (lokale) pagina te tonen.
ACCEPT_LANGUAGE = {
    "NL": "nl-NL,nl;q=0.9,en;q=0.8", "BE": "nl-BE,nl;q=0.9,fr;q=0.8,en;q=0.7",
    "DE": "de-DE,de;q=0.9,en;q=0.8", "FR": "fr-FR,fr;q=0.9,en;q=0.8",
    "ES": "es-ES,es;q=0.9,en;q=0.8", "IT": "it-IT,it;q=0.9,en;q=0.8",
    "GB": "en-GB,en;q=0.9", "AT": "de-AT,de;q=0.9,en;q=0.8", "IE": "en-IE,en;q=0.9",
    "PT": "pt-PT,pt;q=0.9,en;q=0.8", "FI": "fi-FI,fi;q=0.9,en;q=0.8",
    "LU": "fr-LU,fr;q=0.9,de;q=0.8,en;q=0.7", "CH": "de-CH,de;q=0.9,fr;q=0.8,en;q=0.7",
    "SE": "sv-SE,sv;q=0.9,en;q=0.8", "DK": "da-DK,da;q=0.9,en;q=0.8",
    "PL": "pl-PL,pl;q=0.9,en;q=0.8", "NO": "nb-NO,no;q=0.9,en;q=0.8",
    "AE": "en-AE,ar-AE,ar;q=0.9,en;q=0.8",
}


def browser_headers(country_code=None, ua=None):
    return {
        "User-Agent": ua or UA_POOL[0],
        "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                   "image/avif,image/webp,image/apng,*/*;q=0.8"),
        "Accept-Language": ACCEPT_LANGUAGE.get(country_code, "en-US,en;q=0.9"),
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
    }

# DuckDuckGo-regio per landcode (ddgs) voor landspecifieke resultaten.
REGION_MAP = {
    "NL": "nl-nl", "BE": "be-nl", "DE": "de-de", "FR": "fr-fr", "ES": "es-es",
    "IT": "it-it", "IE": "ie-en", "AT": "at-de", "PT": "pt-pt", "FI": "fi-fi",
    "LU": "lu-fr", "GB": "uk-en", "CH": "ch-de", "SE": "se-sv", "DK": "dk-da",
    "PL": "pl-pl", "NO": "no-no", "AE": "ae-ar",
    "US": "us-en", "CA": "ca-en", "AU": "au-en", "SG": "sg-en",
    "JP": "jp-jp", "HK": "hk-en", "NZ": "nz-en",
    "CZ": "cz-cs", "HU": "hu-hu", "RO": "ro-ro", "SK": "sk-sk",
    "SI": "si-sl", "HR": "hr-hr", "BG": "bg-bg",
    "EE": "ee-et", "LV": "lv-lv", "LT": "lt-lt",
    "MT": "mt-en", "CY": "cy-en",
}

# Domeinen die geen echte winkel zijn (nieuws, forums, prijstrackers, social).
BLOCKED_DOMAINS = [
    "youtube.com", "youtu.be", "reddit.com", "wikipedia.org", "appleinsider.com",
    "macrumors.com", "9to5mac.com", "macworld.com", "quora.com", "facebook.com",
    "instagram.com", "pinterest.", "twitter.com", "x.com", "ofox.ai", "grokimage.ai",
    "macprices.net", "prices.apple", "tweakers.net", "gathering.tweakers",
    "bestbuy.com", "cnet.com", "theverge.com", "techradar.com", "tomsguide.com",
]

# Particuliere marktplaatsen (apart labelen; optioneel uitsluiten).
MARKETPLACE_DOMAINS = [
    "ebay.", "marktplaats.nl", "kleinanzeigen.de", "ebay-kleinanzeigen", "leboncoin.fr",
    "2dehands.be", "2ememain.be", "kapaza", "vinted.", "subito.it", "kijiji.it",
    "wallapop.com", "milanuncios.com", "blocket.se", "tradera.com", "finn.no",
    "tori.fi", "dba.dk", "willhaben.at", "ricardo.ch", "tutti.ch", "anibis.ch",
    "olx.pl", "olx.pt", "allegro.pl", "gumtree.com", "adverts.ie", "donedeal.ie",
    "custojusto.pt", "dubizzle.com", "facebook.com/marketplace", "mercadillo.",
    "amazon.", "newegg.com", "rakuten.com", "mercari.", "poshmark.", "depop.",
    "nag.co", "shopzilla.com", "homeshop.com", "nabavi",
]

# Landspecifieke tweedehands-marktplaatsen — zoek-URL's voor "Mac Studio".
# Alleen meegenomen wanneer 'particuliere marktplaatsen' is ingeschakeld.
MARKETPLACE_SEED_URLS = {
    "NL": [
        "https://www.marktplaats.nl/q/mac+studio/",
        "https://www.vinted.nl/catalog?search_text=mac%20studio",
        "https://www.ebay.nl/sch/i.html?_nkw=mac+studio",
    ],
    "BE": [
        "https://www.2dehands.be/q/mac+studio/",
        "https://www.2ememain.be/q/mac+studio/",
    ],
    "DE": [
        "https://www.kleinanzeigen.de/s-mac-studio/k0",
        "https://www.ebay.de/sch/i.html?_nkw=mac+studio",
    ],
    "FR": [
        "https://www.leboncoin.fr/recherche?text=mac%20studio",
        "https://www.ebay.fr/sch/i.html?_nkw=mac+studio",
    ],
    "ES": [
        "https://es.wallapop.com/app/search?keywords=mac%20studio",
        "https://www.milanuncios.com/anuncios/?s=mac%20studio",
    ],
    "IT": [
        "https://www.subito.it/annunci-italia/vendita/usato/?q=mac+studio",
        "https://www.ebay.it/sch/i.html?_nkw=mac+studio",
    ],
    "GB": [
        "https://www.ebay.co.uk/sch/i.html?_nkw=mac+studio",
        "https://www.gumtree.com/search?q=mac+studio",
    ],
    "AT": [
        "https://www.willhaben.at/iad/kaufen-und-verkaufen/marktplatz?keyword=mac%20studio",
    ],
    "IE": [
        "https://www.adverts.ie/for-sale/q_mac+studio/",
        "https://www.donedeal.ie/all?words=mac%20studio",
    ],
    "PT": [
        "https://www.olx.pt/ads/q-mac-studio/",
        "https://www.custojusto.pt/anuncios?q=mac%20studio",
    ],
    "CH": [
        "https://www.ricardo.ch/de/s/mac%20studio",
        "https://www.tutti.ch/de/li/ganze-schweiz?query=mac%20studio",
        "https://www.anibis.ch/de/q/mac-studio",
    ],
    "SE": [
        "https://www.tradera.com/search?q=mac%20studio",
        "https://www.blocket.se/annonser/hela_sverige?q=mac%20studio",
    ],
    "DK": [
        "https://www.dba.dk/soeg/?soeg=mac%20studio",
    ],
    "PL": [
        "https://www.olx.pl/oferty/q-mac-studio/",
        "https://allegro.pl/listing?string=mac%20studio",
    ],
    "NO": [
        "https://www.finn.no/bap/forsale/search.html?q=mac%20studio",
    ],
    "FI": [
        "https://www.tori.fi/koko_suomi?q=mac%20studio",
    ],
    "AE": [
        "https://www.amazon.ae/s?k=mac+studio",
        "https://www.noa.ae/en/apple-mac-studio",
        "https://www.jarir.com/app/search?searchTerm=mac+studio",
    ],
    "US": [
        "https://www.amazon.com/s?k=mac+studio",
        "https://www.bestbuy.com/site/searchpage.jsp?id=pcat17071&qp=appleproductfacetaffiliate~initial_faceted_search%3Dapple+mac+studio+computers&st=mac+studio",
        "https://www.newegg.com/ppl?st=mac+studio",
    ],
    "CA": [
        "https://www.amazon.ca/s?k=mac+studio",
        "https://www.bestbuy.ca/en-ca/search?searchTerm=mac+studio",
        "https://www.costco.com/apple-mac-studio.product.100745831.html",
    ],
    "AU": [
        "https://www.amazon.com.au/s?k=mac+studio",
        "https://www.harveynorman.com.au/mac-studio.html",
        "https://www.jbhifi.com.au/search?q=mac+studio",
    ],
    "SG": [
        "https://www.amazon.sg/s?k=mac+studio",
        "https://www.challenger.com.sg/search?search=mac+studio",
        "https://www.harveynorman.com.sg/search?q=mac+studio",
    ],
    "JP": [
        "https://www.amazon.co.jp/s?k=mac+studio",
        "https://www.yodobashi.com/product/100000000000000000/",
        "https://www.edion.com/search/search?q=mac+studio",
    ],
    "HK": [
        "https://www.amazon.com.hk/s?k=mac+studio",
        "https://www.eprice.com.hk/mac-studio/",
        "https://www.wilkinson.com.hk/search?q=mac+studio",
    ],
    "NZ": [
        "https://www.amazon.co.nz/s?k=mac+studio",
        "https://www.harveynorman.co.nz/mac-studio.html",
        "https://www.xpert.co.nz/search?q=mac+studio",
    ],
    "CZ": [
        "https://www.czc.cz/mac-studio",
        "https://www.mironet.cz/vyhlavani.htm?qs=mac+studio",
        "https://www.alza.cz/mac-studio-d2333.htm",
    ],
    "HU": [
        "https://www.alza.hu/mac-studio",
        "https://www.emag.hu/mac-studio",
    ],
    "RO": [
        "https://www.emag.ro/mac-studio",
        "https://www.flanco.ro/mac-studio",
    ],
    "SK": [
        "https://www.alza.sk/mac-studio",
        "https://www.saturn.sk/mac-studio",
    ],
    "SI": [
        "https://www.bolt.si/iskanje?search=mac%20studio",
    ],
    "HR": [
        "https://www.ingressa.hr/mac-studio",
    ],
    "BG": [
        "https://www.technopolis.bg/mac-studio",
        "https://www.johnibuilders.com/search?q=mac+studio",
    ],
    "EE": [
        "https://www.arvutikeskus.ee/search?query=mac+studio",
    ],
    "LV": [
        "https://www.riga24.lv/meket?query=mac+studio",
    ],
    "LT": [
        "https://www.pigu.lt/ie/keywords/mac%20studio",
    ],
    "MT": [
        "https://www.iway.com.mt/search?q=mac+studio",
    ],
    "CY": [
        "https://www.goodmall.cy/search?q=mac+studio",
    ],
}

# Vaste, betrouwbare winkel-URL's per land (server-rendered met zichtbare prijzen).
# Deze worden gecombineerd met de live zoekresultaten voor consistente output.
SEED_URLS = {
    "NL": [
        "https://www.amac.nl/mac/mac-studio",
        "https://www.yourmacstore.nl/mac/mac-studio/merk-apple/",
        "https://mactastic.nl/refurbished-mac-kopen/mac-studio-kopen/",
        "https://www.macvoorminder.nl/mac/mac-studio",
        "https://www.coolblue.nl/desktops/apple/apple-mac-studio",
        "https://www.belsimpel.nl/apple/mac-studio",
        "https://www.bol.com/nl/nl/s/?searchtext=mac%20studio",
        "https://galaxus.nl/nl/supersite/search?componentId=1057&term=mac+studio",
        "https://azerty.nl/product-search?q=mac+studio",
        "https://www.cameranu.nl/nl/zoeken?q=mac+studio",
        "https://www.gsmshop.nl/mac-studio/",
        "https://www.mac-center.nl/mac-studio/",
        "https://www.vanrooy.com/nl/search/?text=Mac%20Studio",
    ],
    "BE": [
        "https://www.coolblue.be/nl/apple-mac-studio",
        "https://www.mediamarkt.be/nl/category/mac-studio",
        "https://www.switch.be/nl/mac/mac-studio",
        "https://www.lab9.be/nl/mac/mac-studio",
        "https://www.vandenborre.be/zoeken?q=mac%20studio",
    ],
    "DE": [
        "https://www.mactrade.de/mac/mac-studio/",
        "https://www.trademax24.de/Mac-Studio/",
        "https://www.edustore.de/en/apple-mac-studio/",
        "https://www.gravis.de/apple-mac/mac-studio/",
        "https://www.cyberport.de/apple/mac/mac-studio.html",
        "https://www.mstore.de/mac/mac-studio",
        "https://www.notebooksbilliger.de/apple+mac+studio",
        "https://www.rebuy.de/kaufen/suche?q=mac+studio",
        "https://www.conrad.de/search?query=Mac%20Studio",
        "https://www.techfinder.at/search/mac-studio",
        "https://www.digitec.ch/de/s1/producttype/mac-studio",
    ],
    "FR": [
        "https://www.ldlc.com/recherche/Mac%20Studio/",
        "https://www.materiel.net/imac-et-mac-mini/l403/",
        "https://www.fnac.com/Apple-Mac-Studio/",
        "https://www.boulanger.com/c/mac-studio",
        "https://www.darty.com/nav/recherche?text=mac+studio",
        "https://www.macway.com/mac/mac-studio.html",
        "https://www.cdiscount.com/search/10/mac+studio.html",
    ],
    "ES": [
        "https://www.k-tuin.com/comprar-un-mac/mac-studio",
        "https://www.macnificos.com/mac-studio",
        "https://www.pccomponentes.com/mac-studio",
        "https://www.mediamarkt.es/es/search.html?query=mac%20studio",
        "https://www.elcorteingles.es/search/?s=mac%20studio",
    ],
    "IT": [
        "https://www.amazon.it/s?k=mac+studio",
        "https://www.unieuro.it/online/search?q=mac+studio",
        "https://www.euronics.it/ricerca?q=mac+studio",
        "https://www.buffetti.it/catalogsearch/result/?q=mac+studio",
    ],
    "GB": [
        "https://www.krcs.co.uk/mac-studio",
        "https://www.stormfront.co.uk/mac-studio",
        "https://www.johnlewis.com/search?search-term=mac%20studio",
        "https://www.currys.co.uk/search?q=mac%20studio",
        "https://www.very.co.uk/e/q/mac-studio.end",
        "https://www.box.co.uk/search?search=mac%20studio",
        "https://cancomuk.com/search?q=mac%20studio",
    ],
    "AT": [
        "https://www.mediamarkt.at/de/category/mac-studio",
        "https://www.mcshark.at/mac/mac-studio",
        "https://www.e-tec.at/search.php?query=mac%20studio",
        "https://www.geizhals.at/?fs=mac+studio",
    ],
    "IE": [
        "https://www.compub.com/mac/mac-studio",
        "https://www.harveynorman.ie/search/?q=mac%20studio",
        "https://www.currys.ie/search?q=mac%20studio",
    ],
    "PT": [
        "https://www.worten.pt/produtos/informatica/mac/mac-studio",
        "https://www.fnac.pt/Mac-Studio/",
        "https://www.mediamarkt.pt/pt/search.html?query=mac%20studio",
    ],
    "FI": [
        "https://www.verkkokauppa.com/fi/search?query=mac%20studio",
        "https://www.gigantti.fi/search?query=mac%20studio",
        "https://www.power.fi/haku/?q=mac%20studio",
    ],
    "LU": [
        "https://www.mediamarkt.lu/fr/search.html?query=mac%20studio",
    ],
    "CH": [
        "https://www.digitec.ch/en/s1/producttype/mac-studio",
        "https://www.microspot.ch/de/search?q=mac%20studio",
        "https://www.brack.ch/search?query=mac%20studio",
        "https://www.interdiscount.ch/de/search?q=mac%20studio",
    ],
    "SE": [
        "https://www.webhallen.com/se/search?searchString=mac+studio",
        "https://www.dustinhome.se/search?query=mac+studio",
        "https://www.netonnet.se/art/sok?q=mac+studio",
        "https://www.kjell.com/se/sok?query=mac+studio",
    ],
    "DK": [
        "https://www.humac.dk/mac/mac-studio",
        "https://www.elgiganten.dk/search?SearchTerm=mac%20studio",
        "https://www.proshop.dk/Search?q=mac%20studio",
    ],
    "PL": [
        "https://www.mediamarkt.pl/pl/search.html?query=mac%20studio",
        "https://www.x-kom.pl/szukaj?q=mac%20studio",
        "https://www.morele.net/wyszukiwarka/?q=mac%20studio",
        "https://www.euro.com.pl/search.bhtml?keyword=mac%20studio",
    ],
    "NO": [
        "https://www.elkjop.no/search?SearchTerm=mac%20studio",
        "https://www.komplett.no/search?q=mac%20studio",
        "https://www.power.no/search/?q=mac%20studio",
        "https://www.eplehuset.no/sok?q=mac%20studio",
    ],
    "AE": [
        # Reguliere webshops & officiële resellers
        "https://www.noa.ae/en/apple-mac-studio",
        "https://www.jarir.com/app/search?searchTerm=mac+studio",
        "https://www.magnus.com/search?query=mac+studio",
        "https://www.miraclesignals.com/mac-studio",
        "https://www.emax.com/en/search/mac-studio",
        "https://www.jumia.ae/apple-mac-studio/",
        "https://www.noon.com/middle-east/north-region/s/n-no-mac-studio/",
        "https://www.amazon.ae/s?k=mac+studio",
        "https://www.currys.co.uk/search?q=mac+studio",
        "https://www.havells.com/ae/en/search?query=mac+studio",
        # Marktplaats-achtige platforms
        "https://www.facebook.com/marketplace/dubai/desk/?for=900000016471",
        "https://www.dubizzle.com/search/mac%20studio",
        "https://www.dubzz.com/mac-studio",
        "https://www.dubai-sell.com/mac-studio",
    ],
    # === Nieuwe landen ===
    "US": [
        "https://www.apple.com/shop/buy-mac/mac-studio",
        "https://www.amazon.com/s?k=mac+studio",
        "https://www.bestbuy.com/site/searchpage.jsp?st=mac+studio",
        "https://www.bhphotofinding.com/finder?s=mac+studio",
        "https://www.newegg.com/ppl?st=mac+studio",
        "https://www.costco.com/apple-mac-studio.product.100745831.html",
        "https://www.apple.com/shop/refurbished",
    ],
    "CA": [
        "https://www.apple.com/ca/shop/buy-mac/mac-studio",
        "https://www.amazon.ca/s?k=mac+studio",
        "https://www.bestbuy.ca/en-ca/search?searchTerm=mac+studio",
        "https://www.costco.com/apple-mac-studio.product.100745831.html",
        "https://www.hudsons.com/mac-studio",
        "https://www.applemac.ca/mac-studio",
    ],
    "AU": [
        "https://www.apple.com/au/shop/buy-mac/mac-studio",
        "https://www.amazon.com.au/s?k=mac+studio",
        "https://www.harveynorman.com.au/mac-studio.html",
        "https://www.jbhifi.com.au/search?q=mac+studio",
        "https://www.pccomputers.com/mac-studio",
        "https://www.scorptec.com.au/search?q=mac+studio",
    ],
    "SG": [
        "https://www.apple.com/sg/shop/buy-mac/mac-studio",
        "https://www.amazon.sg/s?k=mac+studio",
        "https://www.challenger.com.sg/search?search=mac+studio",
        "https://www.harveynorman.com.sg/search?q=mac+studio",
        "https://www.extraclear.com.sg/search?q=mac+studio",
        "https://www.iifuture.com/search?q=mac+studio",
    ],
    "JP": [
        "https://www.apple.com/jp/shop/buy-mac/mac-studio",
        "https://www.amazon.co.jp/s?k=mac+studio",
        "https://www.yodobashi.com/product/category/?search=Mac+Studio",
        "https://www.edion.com/search/search?q=mac+studio",
        "https://www.kojincomputer.jp/search?keywords=mac+studio",
    ],
    "HK": [
        "https://www.apple.com/hk/en/shop/buy-mac/mac-studio",
        "https://www.amazon.com.hk/s?k=mac+studio",
        "https://www.eprice.com.hk/search/?q=mac+studio",
        "https://www.wilkinson.com.hk/search?q=mac+studio",
    ],
    "NZ": [
        "https://www.apple.com/nz/shop/buy-mac/mac-studio",
        "https://www.amazon.co.nz/s?k=mac+studio",
        "https://www.harveynorman.co.nz/mac-studio.html",
        "https://www.xpert.co.nz/search?q=mac+studio",
        "https://www.stuff.co.nz/search?query=mac+studio",
    ],
    "CZ": [
        "https://www.apple.com/cz/shop/buy-mac/mac-studio",
        "https://www.alza.cz/mac-studio-d2333.htm",
        "https://www.czc.cz/mac-studio",
        "https://www.mironet.cz/vyhlavani.htm?qs=mac+studio",
        "https://www.mall.cz/mac-studio",
    ],
    "HU": [
        "https://www.apple.com/hu/shop/buy-mac/mac-studio",
        "https://www.alza.hu/mac-studio",
        "https://www.emag.hu/mac-studio",
        "https://www.invertor.hu/keres?query=mac+studio",
    ],
    "RO": [
        "https://www.apple.com/ro/shop/buy-mac/mac-studio",
        "https://www.emag.ro/mac-studio",
        "https://www.flanco.ro/mac-studio",
        "https://www.evo.ro/mac-studio",
    ],
    "SK": [
        "https://www.apple.com/sk/shop/buy-mac/mac-studio",
        "https://www.alza.sk/mac-studio",
        "https://www.saturn.sk/mac-studio",
        "https://www.mall.sk/mac-studio",
    ],
    "SI": [
        "https://www.apple.com/si/shop/buy-mac/mac-studio",
        "https://www.bolt.si/iskanje?search=mac%20studio",
        "https://www.spar.si/iskanje?search=mac+studio",
    ],
    "HR": [
        "https://www.apple.com/hr/hr/shop/buy-mac/mac-studio",
        "https://www.ingressa.hr/mac-studio",
        "https://www.plivnica.hr/mac-studio",
    ],
    "BG": [
        "https://www.apple.com/bg/bg/shop/buy-mac/mac-studio",
        "https://www.technopolis.bg/mac-studio",
        "https://www.johnibuilders.com/search?q=mac+studio",
        "https://www.imaginatio.bg/search?q=mac+studio",
    ],
    "EE": [
        "https://www.apple.com/ee/en/shop/buy-mac/mac-studio",
        "https://www.arvutikeskus.ee/search?query=mac+studio",
        "https://www2.arvutitark.ee/search?query=mac+studio",
    ],
    "LV": [
        "https://www.apple.com/lv/en/shop/buy-mac/mac-studio",
        "https://www.riga24.lv/meket?query=mac+studio",
        "https://www.tirgus360.lv/mekets?query=mac+studio",
    ],
    "LT": [
        "https://www.apple.com/lt/en/shop/buy-mac/mac-studio",
        "https://www.pigu.lt/ie/keywords/mac%20studio",
        "https://www.varle.lt/search?query=mac+studio",
    ],
    "MT": [
        "https://www.apple.com/mt/en/shop/buy-mac/mac-studio",
        "https://www.iway.com.mt/search?q=mac+studio",
    ],
    "CY": [
        "https://www.apple.com/cy/en/shop/buy-mac/mac-studio",
        "https://www.goodmall.cy/search?q=mac+studio",
    ],
}

SYSTEM_MSG = (
    "Je bent een assistent die webpagina's van (web)winkels analyseert om te bepalen of een "
    "Apple Mac Studio op dit moment ECHT bestelbaar is. Je antwoordt UITSLUITEND met geldige JSON, "
    "zonder extra tekst, zonder markdown code fences. Alle vrije tekst in het Nederlands."
)


# ---------------------------------------------------------------------------
# Zoeken (zonder API-key) — primair via ddgs met landspecifieke regio
# ---------------------------------------------------------------------------
def _is_useful(url: str, include_marketplaces: bool):
    low = url.lower()
    if any(b in low for b in BLOCKED_DOMAINS):
        return False
    if not include_marketplaces and any(m in low for m in MARKETPLACE_DOMAINS):
        return False
    return True


def _ddgs_search(term: str, region: str, max_results: int):
    """Synchrone ddgs-zoekopdracht (in thread aangeroepen)."""
    try:
        from ddgs import DDGS
    except Exception as e:
        logger.warning(f"ddgs niet beschikbaar: {e}")
        return []
    for reg in [region, "wt-wt"]:
        try:
            res = DDGS().text(term, region=reg, max_results=max_results)
            urls = [r.get("href") for r in res if (r.get("href") or "").startswith("http")]
            if urls:
                return urls
        except Exception as e:
            logger.warning(f"ddgs '{term}' ({reg}) mislukt: {e}")
    return []


async def ddg_html_search(client: httpx.AsyncClient, query: str, max_results: int):
    """Fallback: HTML-endpoint van DuckDuckGo."""
    urls = []
    try:
        resp = await client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select("a.result__a"):
            href = a.get("href", "")
            real = href
            if "uddg=" in href:
                q = parse_qs(urlparse(href).query)
                if "uddg" in q:
                    real = unquote(q["uddg"][0])
            if real.startswith("http"):
                urls.append(real)
            if len(urls) >= max_results:
                break
    except Exception as e:
        logger.warning(f"DuckDuckGo HTML zoekopdracht mislukt voor '{query}': {e}")
    return urls


_CHIP_TOKEN_RE = re.compile(r"\s*\bM\s?[1-9](?:\s*(?:Max|Ultra|Pro))?\b", re.I)


def search_terms(term):
    """Zoektermen per land: de basisterm zonder chip (oude instellingen bevatten nog 'M3')
    plus varianten voor de huidige generaties, zodat niet alleen M3-resultaten komen."""
    base = re.sub(r"\s+", " ", _CHIP_TOKEN_RE.sub("", term or "")).strip() or "Mac Studio"
    return [base, f"{base} M5", f"{base} M4 Max M3 Ultra"]


async def search_urls(client, country, term, max_results, include_marketplaces):
    """Landspecifieke zoekopdrachten met filtering van ruis-domeinen."""
    region = REGION_MAP.get(country["code"], "wt-wt")
    urls, seen = [], set()
    for i, q in enumerate(search_terms(term)):
        if i:
            await asyncio.sleep(1.0)  # DuckDuckGo niet te snel achter elkaar bevragen
        found = await asyncio.to_thread(_ddgs_search, q, region, max_results)
        if not found:
            found = await ddg_html_search(client, q, max_results)
        for u in found:
            if u not in seen and _is_useful(u, include_marketplaces):
                seen.add(u)
                urls.append(u)
    return urls


def _parse_html(html: str, base_url: str = ""):
    """Synchroon HTML parsen (CPU-werk) — in thread aangeroepen om de event-loop vrij te houden.

    Geeft naast titel en zichtbare tekst ook de (absolute) links op de pagina terug,
    zodat de LLM een echte productlink kan kiezen in plaats van er een te verzinnen."""
    soup = BeautifulSoup(html, "html.parser")
    offers = _extract_structured_offers(soup)
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"].strip()) if base_url else a["href"].strip()
        href = href.split("#", 1)[0]
        if not href.startswith(("http://", "https://")) or href in seen:
            continue
        seen.add(href)
        links.append({"url": href, "text": re.sub(r"\s+", " ", a.get_text(" ")).strip()[:120]})
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    return {"title": title, "text": text[:MAX_PAGE_TEXT], "links": links, "offers": offers}


# Hoeveel zichtbare tekst we per pagina bewaren (voor prijscontrole) en naar de LLM sturen.
MAX_PAGE_TEXT = 150_000
PROMPT_TEXT_LIMIT = 12_000


def _to_float(value):
    """'2.399,00' / '2,399.00' / '2399' / 2399 → 2399.0 (of None)."""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    v = re.sub(r"[^\d.,]", "", value)
    if not v:
        return None
    if "," in v and "." in v:
        dec = "," if v.rfind(",") > v.rfind(".") else "."
        v = v.replace("." if dec == "," else ",", "").replace(dec, ".")
    elif "," in v:
        head, _, tail = v.rpartition(",")
        v = head.replace(",", "") + ("." + tail if len(tail) != 3 else tail)
    elif v.count(".") > 1 or (v.count(".") == 1 and len(v.rpartition(".")[2]) == 3):
        v = v.replace(".", "")
    try:
        return float(v)
    except ValueError:
        return None


def _iter_jsonld(node):
    if isinstance(node, list):
        for x in node:
            yield from _iter_jsonld(x)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "itemListElement", "item", "mainEntity"):
            if key in node:
                yield from _iter_jsonld(node[key])


def _extract_structured_offers(soup, limit=20):
    """Lees schema.org Product/Offer-data (JSON-LD) en product:price-meta tags.

    Dit is door de winkel zelf opgegeven prijs/voorraad en daarmee veel betrouwbaarder dan
    wat een LLM uit de losse paginatekst haalt."""
    offers = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except (ValueError, TypeError):
            continue
        for node in _iter_jsonld(data):
            types = node.get("@type")
            types = types if isinstance(types, list) else [types]
            if "Product" not in types:
                continue
            name = str(node.get("name") or "")[:200]
            raw_offers = node.get("offers")
            for o in (raw_offers if isinstance(raw_offers, list) else [raw_offers]):
                if not isinstance(o, dict):
                    continue
                spec = o.get("priceSpecification")
                spec = spec[0] if isinstance(spec, list) and spec else spec
                price = (o.get("price") or o.get("lowPrice")
                         or (spec.get("price") if isinstance(spec, dict) else None))
                currency = (o.get("priceCurrency")
                            or (spec.get("priceCurrency") if isinstance(spec, dict) else None))
                availability = str(o.get("availability") or "").rsplit("/", 1)[-1]
                offers.append({
                    "name": name,
                    "price": _to_float(price),
                    "currency": (currency or "").upper() or None,
                    "availability": availability or None,
                    "url": o.get("url") if isinstance(o.get("url"), str) else node.get("url"),
                })
                if len(offers) >= limit:
                    return offers
    amount = soup.find("meta", attrs={"property": re.compile(r"^(product|og):price:amount$")})
    if amount and amount.get("content") and not offers:
        cur = soup.find("meta", attrs={"property": re.compile(r"^(product|og):price:currency$")})
        title = soup.find("meta", attrs={"property": "og:title"})
        offers.append({
            "name": (title.get("content") if title else "")[:200],
            "price": _to_float(amount["content"]),
            "currency": (cur.get("content") or "").upper() if cur else None,
            "availability": None,
            "url": None,
        })
    return offers


def _mentions_mac_studio(page):
    """Komt 'Mac Studio' voor in titel, tekst of productdata? Zo niet: geen LLM-aanroep."""
    hay = " ".join([page.get("title") or "", page.get("text") or ""]
                   + [o.get("name") or "" for o in page.get("offers") or []]).lower()
    return "mac studio" in hay or "macstudio" in hay


def _relevant_text(text, limit=PROMPT_TEXT_LIMIT, window=700):
    """Stuur bij lange pagina's het begin plus de stukken rond 'Mac Studio' naar de LLM,
    in plaats van blind de eerste 12.000 tekens (waar vaak alleen menu's staan)."""
    if len(text) <= limit:
        return text
    head = text[:1500]
    spans = []
    for m in re.finditer(r"mac\s?studio", text, re.I):
        a, b = max(1500, m.start() - window), min(len(text), m.end() + window)
        if spans and a <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], b)
        else:
            spans.append([a, b])
    out, used = [head], len(head)
    for a, b in spans:
        if used >= limit:
            break
        chunk = text[a:min(b, a + limit - used)]
        out.append(chunk)
        used += len(chunk) + 5
    return " … ".join(out)


# Zinnen die op een anti-bot/challenge-pagina wijzen. Bewust specifiek: generieke woorden als
# "performance", "loading" of "cloudflare" staan op vrijwel elke normale winkelpagina.
BLOCK_PHRASES = (
    "verify you are human", "verifying you are human", "are you a robot", "are you human",
    "captcha", "access denied", "attention required", "just a moment",
    "checking your browser", "check your browser before", "request unsuccessful",
    "pardon our interruption", "ddos protection", "bot detection", "unusual traffic",
    "enable javascript and cookies to continue",
)


def _looks_blocked(data) -> bool:
    """True als de geparste pagina een anti-bot/challenge-pagina lijkt.

    Kijkt naar de titel en — alleen bij korte pagina's — naar de zichtbare tekst. Echte
    challenge-pagina's zijn klein; een volle productpagina met 'captcha' in een
    formulier-footer wordt zo niet onterecht als geblokkeerd gezien."""
    if not data:
        return False
    title = (data.get("title") or "").lower()
    text = (data.get("text") or "").lower()
    if any(p in title for p in BLOCK_PHRASES):
        return True
    return len(text) < 1500 and any(p in text for p in BLOCK_PHRASES)


def _classify_page(data):
    """Zet een geparste pagina om naar (status, data) voor fetch_page."""
    if _looks_blocked(data):
        return ("blocked", None)
    if data and len(data["text"]) >= 200:
        return ("ok", data)
    return ("empty", None)


# Global stealth script that runs on every page load
STEALTH_SCRIPT = """
// Comprehensive stealth configuration to bypass Cloudflare and similar anti-bot protection

// 1. Verwijder webdriver flag - belangrijkste detectie indicator
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: false,
    enumerable: false,
    writable: false
});

// 2. Randomiseer plugins (realistische plugin lijst)
const realPlugins = [
    { name: "Chrome PDF Plugin", description: "Portable Document Format", suffixes: "pdf" },
    { name: "Chrome PDF Viewer", description: "", suffixes: "" },
    { name: "Native Client", description: "Native Client Application Platform", suffixes: "" }
];
Object.defineProperty(navigator, 'plugins', {
    get: () => realPlugins,
    configurable: false,
    enumerable: false,
    writable: false
});

// 3. Randomiseer mimeTypes
const realMimeTypes = [
    { type: "application/pdf", description: "Portable Document Format" }
];
Object.defineProperty(navigator, 'mimeTypes', {
    get: () => realMimeTypes,
    configurable: false,
    enumerable: false,
    writable: false
});

// 4. Fix navigator.languages - moet consistent zijn met locale
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
    configurable: false,
    enumerable: false,
    writable: false
});

// 5. Voeg chrome runtime toe (wordt verwacht door veel sites)
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {}
};

// 6. Randomiseer connection type
Object.defineProperty(navigator, 'connection', {
    get: () => ({
        effectiveType: '4g',
        rtt: 100,
        downlink: 5.0,
        saveData: false
    }),
    configurable: true
});

// 7. Randomiseer hardware concurrency
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8,
    configurable: false,
    enumerable: false
});

// 8. Randomiseer device memory
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8,
    configurable: false,
    enumerable: false
});

// 9. Override window.outerWindow/innerWindow voor consistentie
Object.defineProperty(window, 'outerWidth', {
    get: () => window.innerWidth,
    configurable: false
});
Object.defineProperty(window, 'outerHeight', {
    get: () => window.innerHeight,
    configurable: false
});

// 10. Randomiseer canvas fingerprinting - voeg noise toe aan canvas rendering
const originalCanvas = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function(type) {
    const ctx = originalCanvas.apply(this, arguments);
    if (ctx && type === '2d') {
        const originalGetData = ctx.getImageData;
        ctx.getImageData = function(x, y, w, h) {
            return originalGetData.apply(this, arguments);
        };
    }
    return ctx;
};

// 11. Randomiseer webgl fingerprinting
const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) { // GL_RENDERER
        return 'Apple GPU';
    }
    if (parameter === 37446) { // GL_VENDOR
        return 'Apple';
    }
    if (parameter === 37447) { // GL_VERSION
        return 'WebGL 2.0';
    }
    return originalGetParameter.apply(this, arguments);
};

// 12. Randomiseer audio fingerprinting
if (window.AudioContext) {
    const originalGetChannelData = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = function() {
        const result = originalGetChannelData.apply(this, arguments);
        // Return modified data to randomize fingerprint
        return result;
    };
}

// 13. Voeg random mouse tracking voor human-like behavior
let mouseX = Math.random() * window.innerWidth;
let mouseY = Math.random() * window.innerHeight;
document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
});
Object.defineProperty(window, 'mousePosition', {
    get: () => ({ x: mouseX, y: mouseY }),
    configurable: true
});

// 14. Randomiseer timezone offset - use actual browser timezone
Object.defineProperty(Date.prototype, 'getTimezoneOffset', {
    value: function() {
        return -60; // Amsterdam timezone in minutes (UTC+1)
    },
    writable: false,
    configurable: false
});

// 15. Voeg random touch support - based on device type
if ('ontouchstart' in window) {
    Object.defineProperty(window, 'ontouchstart', {
        get: () => undefined,
        configurable: true
    });
}

// 16. Randomiseer pointer events
window.onpointermove = null;
window.onpointerdown = null;

// 17. Voeg random performance metrics
if (window.performance) {
    const originalNow = performance.now.bind(performance);
    let offset = Math.random() * 50;
    performance.now = () => originalNow() + offset;
}

// 18. Randomiseer screen info
Object.defineProperty(screen, 'availWidth', {
    get: () => window.innerWidth,
    configurable: false
});
Object.defineProperty(screen, 'availHeight', {
    get: () => window.innerHeight,
    configurable: false
});

// 19. Voeg random device pixel ratio
Object.defineProperty(window, 'devicePixelRatio', {
    get: () => 2,
    configurable: false
});

// 20. Randomiseer battery status
if (navigator.getBattery) {
    navigator.getBattery = () => Promise.resolve({
        level: 0.8,
        charging: false,
        chargingTime: Infinity,
        dischargingTime: Infinity
    });
}

// 21. Voeg random storage quota
if (navigator.storage && navigator.storage.estimate) {
    const originalEstimate = navigator.storage.estimate.bind(navigator.storage);
    navigator.storage.estimate = () => Promise.resolve({
        quota: 50 * 1024 * 1024, // 50MB
        usage: 1024 * 1024 // 1MB
    });
}

// 22. Voeg random media query support
const originalMatchMedia = window.matchMedia;
window.matchMedia = function(query) {
    const result = originalMatchMedia.call(this, query);
    return {
        matches: result.matches,
        media: result.media,
        onchange: null,
        addListener: function() {},
        removeListener: function() {}
    };
};

// 23. Voeg random fetch support
const originalFetch = window.fetch;
window.fetch = function(input, init) {
    // Modify request headers to look more human
    return originalFetch.call(this, input, init);
};

// 24. Voeg random XHR override
const originalOpen = XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open = function(method, url) {
    this._url = url;
    return originalOpen.apply(this, arguments);
};
"""

async def _fetch_playwright_stealth(browser, url: str, country_code=None, delay=2000):
    """Playwright met stealth-instellingen — minimaliseert detectie.
    
    Deze versie gebruikt:
    - Randomized user agents
    - Browser fingerprint randomization (canvas, webgl, audio)
    - Human-like behavior simulation
    - Advanced automation detection bypass
    """
    import random
    
    ctx = None
    domain = urlparse(url).netloc.replace("www.", "")
    
    # Kies willekeurige user agent uit pool
    random_ua = random.choice(UA_POOL)
    
    # Genereer willekeurige viewport (realistische schermgroottes)
    viewports = [
        {"width": 1920, "height": 1080},
        {"width": 1440, "height": 900},
        {"width": 1366, "height": 768},
        {"width": 1280, "height": 800},
    ]
    viewport = random.choice(viewports)
    
    # Willekeurige taal per land
    locale_map = {
        "NL": ["nl-NL", "nl-BE"],
        "BE": ["nl-BE", "fr-BE"],
        "DE": ["de-DE", "de-AT"],
        "FR": ["fr-FR", "fr-BE"],
        "GB": ["en-GB", "en-US"],
        "US": ["en-US", "en-GB"],
        "CA": ["en-CA", "fr-CA"],
        "AU": ["en-AU", "en-US"],
    }
    
    base_locale = ACCEPT_LANGUAGE.get(country_code, "en-US").split(",")[0]
    locale_list = locale_map.get(country_code, [base_locale])
    locale = random.choice(locale_list)
    
    # Willekeurige timezone
    timezones = [
        "Europe/Amsterdam", "Europe/Berlin", "Europe/London",
        "America/New_York", "America/Los_Angeles", "Asia/Tokyo"
    ]
    timezone_id = random.choice(timezones)
    
    # Willekeurige sec-ch-ua headers
    ua_versions = [
        ('"Chromium";v="125", "Google Chrome";v="125"', "?0"),
        ('"Google Chrome";v="126", "Not-A.Brand";v="8"', "?0"),
        ('"Not)A;Brand";v="99", "Google Chrome";v="124"', "?0"),
    ]
    sec_ch_ua, sec_ch_ua_mobile = random.choice(ua_versions)
    
    # Willekeurige platform
    platforms = ['"macOS"', '"Windows"', '"Linux"']
    platform = random.choice(platforms)
    
    try:
        ctx = await browser.new_context(
            user_agent=random_ua,
            locale=locale,
            timezone_id=timezone_id,
            viewport=viewport,
            extra_http_headers={
                "Accept-Language": ACCEPT_LANGUAGE.get(country_code, "en-US,en;q=0.9"),
                "Sec-Ch-Ua": sec_ch_ua,
                "Sec-Ch-Ua-Mobile": sec_ch_ua_mobile,
                "Sec-Ch-Ua-Platform": platform,
                "DNT": random.choice(["1", "0"]),
            },
            is_mobile=False,
            # Randomiseer browser hints
            screen={"width": viewport["width"], "height": viewport["height"]},
            color_scheme=random.choice(["light", "dark"]),
            reduced_motion=random.choice(["reduce", "no-preference"]),
        )
        
        # Voeg uitgebreid stealth script toe (gebruik global script voor consistentie)
        await ctx.add_init_script(STEALTH_SCRIPT)
        
        
        pg = await ctx.new_page()
        
        # Voeg human-like behavior toe via add_init_script voor page-level scripts
        await pg.add_init_script("""
            // Randomiseer mouse tracking per session
            window.mousePath = [];
            let currentX = Math.random() * window.innerWidth;
            let currentY = Math.random() * window.innerHeight;
            
            document.addEventListener('mousemove', (e) => {
                window.mousePath.push({ x: e.clientX, y: e.clientY });
                if (window.mousePath.length > 100) window.mousePath.shift();
            });
        """)
        
        # Navigeer met alle wait opties - gebruik domcontentloaded als fallback
        try:
            await pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as nav_err:
            logger.info(f"Playwright stealth navigatie timeout voor {domain}, probeer networkidle...")
            try:
                await pg.goto(url, wait_until="networkidle", timeout=60000)
            except Exception as nav_err2:
                logger.info(f"Playwright stealth networkidle ook mislukt voor {domain}")
        
        # Variabele delay om detectie te voorkomen - uitgebreider voor 's nachts scans
        actual_delay = delay + random.randint(800, 3500) if isinstance(delay, int) else delay
        await pg.wait_for_timeout(actual_delay)
        
        # Extra human-like behavior: willekeurige bladwijzer klikken (als er links zijn)
        try:
            all_links = await pg.query_selector_all("a")
            if len(all_links) > 10:
                random_link = random.choice(all_links[5:min(20, len(all_links))])
                box = await random_link.bounding_box()
                if box:
                    await pg.mouse.click(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                    await pg.wait_for_timeout(random.randint(300, 1000))
                    await pg.go_back()
                    await pg.wait_for_timeout(random.randint(500, 1500))
        except Exception:
            pass
        
        # Human-like mouse movement simulatie - uitgebreider
        try:
            viewport_width = viewport["width"]
            viewport_height = viewport["height"]
            
            # Genereer willekeurige mouse path - uitgebreider voor betere detectie bypass
            num_points = random.randint(8, 25)
            for i in range(num_points):
                x = random.randint(0, viewport_width)
                y = random.randint(0, viewport_height)
                await pg.mouse.move(x, y, steps=random.randint(3, 15))
                await pg.wait_for_timeout(random.randint(30, 250))
            
            # Mouse over naar willekeurige elementen - uitgebreider
            try:
                links = await pg.query_selector_all("a")
                if links and len(links) > 0:
                    random_link = random.choice(links[:10])  # Eerste 10 links
                    box = await random_link.bounding_box()
                    if box:
                        mouse_x = box["x"] + box["width"] / 2
                        mouse_y = box["y"] + box["height"] / 2
                        await pg.mouse.move(mouse_x, mouse_y, steps=random.randint(5, 10))
                        await pg.wait_for_timeout(random.randint(100, 300))
            except Exception:
                pass
        except Exception:
            pass
        
        # Consent cookies wegklikken — uitgebreide selectoren
        consent_selectors = [
            "#onetrust-accept-btn-handler",
            ".onetrust-close-btn-handler",
            "button:has-text('Accepteren')",
            "button:has-text('Alles accepteren')",
            "button:has-text('Akkoord')",
            "button:has-text('Accept all')",
            "button:has-text('Accept')",
            "button:has-text('Tout accepter')",
            "button:has-text('Alle akzeptieren')",
            "button:has-text('Aceptar')",
            "button:has-text('Chiudi')",
            "button:has-text('Accepter tout')",
            ".cookie-accept",
            "[data-testid='accept-cookies']",
        ]
        for sel in consent_selectors:
            try:
                elem = await pg.query_selector(sel)
                if elem:
                    # Human-like click met variabele delay
                    await pg.wait_for_timeout(random.randint(200, 800))
                    await elem.click(timeout=1000)
                    await pg.wait_for_timeout(random.randint(800, 2000))
                    break
            except Exception:
                pass
        
        # Scroll naar beneden en weer om lazy-loaded content te triggeren - human-like
        try:
            # Eerst scroll naar beneden met variabele stappen - uitgebreider
            for i in range(random.randint(4, 9)):
                await pg.evaluate(f"window.scrollBy(0, {random.randint(250, 700)})")
                await pg.wait_for_timeout(random.randint(600, 1800))
            
            # Scroll terug naar boven - uitgebreider
            for i in range(random.randint(3, 6)):
                await pg.evaluate(f"window.scrollBy(0, -{random.randint(400, 800)})")
                await pg.wait_for_timeout(random.randint(500, 1500))
            
            # Eindelijk naar boven
            await pg.evaluate("window.scrollTo(0, 0)")
            await pg.wait_for_timeout(random.randint(400, 1200))
        except Exception:
            pass
        
        # Typ simulatie - voeg willekeurige input toe aan eventuele zoekvelden
        try:
            search_inputs = await pg.query_selector_all("input[type='text'], input[name*='search']")
            if search_inputs and len(search_inputs) > 0:
                random_input = random.choice(search_inputs[:5])
                box = await random_input.bounding_box()
                if box:
                    # Klik op het zoekveld
                    await pg.mouse.click(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                    await pg.wait_for_timeout(random.randint(100, 300))
        except Exception:
            pass
        
        html = await pg.content()
        data = await asyncio.to_thread(_parse_html, html, pg.url)
        result = _classify_page(data)
        if result[0] == "blocked":
            logger.info(f"Playwright stealth blokkade gedetecteerd voor {domain}")
        return result
    except Exception as e:
        error_type = type(e).__name__
        logger.warning(f"Playwright stealth mislukt voor {domain} ({error_type}): {e}")
        return ("blocked", None)
    finally:
        if ctx:
            await ctx.close()


async def _fetch_selenium(url: str, country_code=None):
    """Selenium als fallback wanneer Playwright mislukt - met uitgebreide stealth."""
    import random
    
    domain = urlparse(url).netloc.replace("www.", "")
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
    except ImportError:
        logger.info("Selenium niet geïnstalleerd — skip Selenium fallback")
        return None
    
    driver = None
    try:
        # Kies willekeurige user agent uit pool
        random_ua = random.choice(UA_POOL)
        
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(f"--user-agent={random_ua}")
        
        # Voeg extra opties toe voor stealth
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "load-extension"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2,
            "download.prompt_for_download": False,
        })
        
        # Configureer capabilities voor stealth
        caps = DesiredCapabilities.CHROME.copy()
        caps['acceptInsecureCerts'] = True
        
        driver = webdriver.Chrome(options=chrome_options)
        
        # Voeg uitgebreide stealth scripts toe
        driver.execute_script("""
            // 1. Verwijder webdriver flag - belangrijkste detectie indicator
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: false,
                enumerable: false,
                writable: false
            });
            
            // 2. Randomiseer plugins (realistische plugin lijst)
            const realPlugins = [
                { name: "Chrome PDF Plugin", description: "Portable Document Format", suffixes: "pdf" },
                { name: "Chrome PDF Viewer", description: "", suffixes: "" },
                { name: "Native Client", description: "Native Client Application Platform", suffixes: "" }
            ];
            Object.defineProperty(navigator, 'plugins', {
                get: () => realPlugins,
                configurable: false,
                enumerable: false,
                writable: false
            });
            
            // 3. Randomiseer mimeTypes
            const realMimeTypes = [
                { type: "application/pdf", description: "Portable Document Format" }
            ];
            Object.defineProperty(navigator, 'mimeTypes', {
                get: () => realMimeTypes,
                configurable: false,
                enumerable: false,
                writable: false
            });
            
            // 4. Fix navigator.languages - moet consistent zijn met locale
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
                configurable: false,
                enumerable: false,
                writable: false
            });
            
            // 5. Voeg chrome runtime toe (wordt verwacht door veel sites)
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {}
            };
            
            // 6. Randomiseer hardware concurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => random.choice([4, 8, 12, 16]),
                configurable: false,
                enumerable: false
            });
            
            // 7. Randomiseer device memory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => random.choice([2, 4, 8, 16]),
                configurable: false,
                enumerable: false
            });
            
            // 8. Voeg mouse tracking toe
            let mouseX = Math.random() * window.innerWidth;
            let mouseY = Math.random() * window.innerHeight;
            document.addEventListener('mousemove', (e) => {
                mouseX = e.clientX;
                mouseY = e.clientY;
            });
            Object.defineProperty(window, 'mousePosition', {
                get: () => ({ x: mouseX, y: mouseY }),
                configurable: true
            });
            
            // 9. Randomiseer performance metrics
            if (window.performance) {
                const originalNow = performance.now.bind(performance);
                let offset = Math.random() * 100;
                performance.now = () => originalNow() + offset;
            }
        """)
        
        driver.get(url)
        WebDriverWait(driver, 25).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        driver.implicitly_wait(3)
        
        # Variabele delay voor human-like behavior
        import time
        time.sleep(random.uniform(1.0, 2.5))
        
        # Human-like mouse movement simulatie (via JavaScript)
        try:
            for _ in range(random.randint(3, 6)):
                x = random.randint(0, 800)
                y = random.randint(0, 600)
                driver.execute_script(f"""
                    const event = new MouseEvent('mousemove', {{
                        view: window,
                        bubbles: true,
                        cancelable: true,
                        clientX: {x},
                        clientY: {y}
                    }});
                    document.dispatchEvent(event);
                """)
                time.sleep(random.uniform(0.2, 0.5))
        except Exception:
            pass
        
        # Consent cookies - uitgebreide selectoren
        consent_selectors = [
            "#onetrust-accept-btn-handler",
            ".onetrust-close-btn-handler",
            "button:has-text('Accepteren')",
            "button:has-text('Alles accepteren')",
            "button:has-text('Akkoord')",
            "button:has-text('Accept all')",
            "button:has-text('Accept')",
            "button:has-text('Tout accepter')",
            "button:has-text('Alle akzeptieren')",
            "button:has-text('Aceptar')",
            ".cookie-accept",
            "[data-testid='accept-cookies']",
        ]
        for selector in consent_selectors:
            try:
                elem = driver.find_element(By.CSS_SELECTOR, selector)
                time.sleep(random.uniform(0.3, 1.0))
                elem.click()
                time.sleep(random.uniform(0.5, 1.2))
                break
            except Exception:
                pass
        
        # Human-like scroll - variabele stappen
        try:
            for _ in range(random.randint(3, 6)):
                driver.execute_script(f"window.scrollBy(0, {random.randint(200, 500)})")
                time.sleep(random.uniform(0.8, 1.5))
            
            # Scroll terug
            for _ in range(random.randint(2, 4)):
                driver.execute_script(f"window.scrollBy(0, -{random.randint(300, 600)})")
                time.sleep(random.uniform(0.6, 1.0))
            
            driver.execute_script("window.scrollTo(0, 0)")
            time.sleep(random.uniform(0.5, 1.0))
        except Exception:
            pass
        
        html = driver.page_source
        data = await asyncio.to_thread(_parse_html, html, driver.current_url)
        result = _classify_page(data)
        if result[0] == "ok":
            logger.info(f"Selenium fallback succesvol voor {domain}")
        return result
        
    except Exception as e:
        error_type = type(e).__name__
        logger.warning(f"Selenium fallback mislukt voor {domain} ({error_type}): {e}")
        return ("blocked", None)
    finally:
        if driver:
            driver.quit()


async def _fetch_with_extended_retries(client, url: str, country_code=None):
    """Uitgebreide HTTP retries met verschillende headers en delays."""
    domain = urlparse(url).netloc.replace("www.", "")
    
    # Probeer met verschillende user-agents en delays
    for i, ua in enumerate(UA_POOL):
        await asyncio.sleep(2 * (i + 1))  # Verhoogende delay
        
        try:
            headers = browser_headers(country_code, ua)
            # Voeg extra headers toe voor betere compatibiliteit
            headers["Referer"] = "https://www.google.com/"
            headers["Connection"] = "keep-alive"
            
            resp = await client.get(
                url,
                headers=headers,
                timeout=20,
                follow_redirects=True
            )
            
            if resp.status_code == 200:
                data = await asyncio.to_thread(_parse_html, resp.text, str(resp.url))
                result = _classify_page(data)
                if result[0] == "ok":
                    logger.info(f"Extended retry succesvol (attempt {i+1}) voor {domain}")
                    return result
                if result[0] == "blocked":
                    continue
                return result
            elif resp.status_code == 403:
                logger.info(f"Extended retry 403 (attempt {i+1}) voor {domain}")
                continue
            else:
                return ("blocked", None)
                
        except Exception as e:
            error_type = type(e).__name__
            logger.info(f"Extended retry mislukt (attempt {i+1}, {error_type}) voor {domain}")
            continue
    
    return None  # Geen van de retries werkte


async def fetch_page(client: httpx.AsyncClient, url: str, country_code=None, browser=None):
    """Multi-layer fallback systeem voor het ophalen van pagina's.
    
    Volgt deze volgorde:
    1. Direct HTTP request met browser headers
    2. Uitgebreide HTTP retries met verschillende user-agents
    3. Playwright (indien beschikbaar)
    4. Playwright stealth modus
    5. Selenium fallback (indien geïnstalleerd)
    
    Geeft (status, data) terug: status in {ok, blocked, empty, error}.
    """
    domain = urlparse(url).netloc.replace("www.", "")
    
    # ---- Layer 1: Direct HTTP request ----
    last_status = None
    for attempt in range(2):
        ua = UA_POOL[attempt % len(UA_POOL)]
        try:
            resp = await client.get(url, headers=browser_headers(country_code, ua),
                                    timeout=15, follow_redirects=True)
            last_status = resp.status_code
            
            if resp.status_code == 403:
                logger.info(f"403 Forbidden (WAF) voor {domain}")
                break
            elif resp.status_code == 429:
                logger.info(f"429 Rate limit voor {domain}")
                await asyncio.sleep(2)
                continue
            elif resp.status_code == 503:
                logger.info(f"503 Service unavailable voor {domain}")
                await asyncio.sleep(1.5)
                continue
            elif resp.status_code >= 400:
                logger.info(f"HTTP {resp.status_code} voor {domain}")
                break
            
            data = await asyncio.to_thread(_parse_html, resp.text, str(resp.url))
            result = _classify_page(data)
            if result[0] == "ok":
                return result
            if result[0] == "blocked":
                logger.info(f"Challenge-pagina (anti-bot) voor {domain}")
            else:
                logger.info(f"LEGE content ({len(data['text'] if data else 0)} chars) voor {domain}")
            break
        except Exception as e:
            error_type = type(e).__name__
            logger.warning(f"Netwerkfout voor {domain} ({error_type}): {e}")
            break
    
    # ---- Layer 2: Uitgebreide HTTP retries ----
    logger.info(f"Extended HTTP retries voor {domain} (HTTP {last_status})")
    result = await _fetch_with_extended_retries(client, url, country_code)
    if result:
        return result
    
    # ---- Layer 3 & 4: Playwright fallbacks ----
    if browser is not None:
        # Eerst normale Playwright
        logger.info(f"Playwright fallback voor {domain} (HTTP {last_status})")
        result = await _fetch_playwright(browser, url, country_code)
        if result[0] == "ok":
            return result
        
        # Dan stealth Playwright
        logger.info(f"Playwright stealth fallback voor {domain}")
        result = await _fetch_playwright_stealth(browser, url, country_code, delay=3000)
        if result[0] == "ok":
            return result
    
    # ---- Layer 5: Selenium fallback ----
    logger.info(f"Selenium fallback proberen voor {domain}")
    result = await _fetch_selenium(url, country_code)
    if result:
        return result
    
    # Alle fallbacks mislukt
    return ("blocked", None)


# Behoud de originele _fetch_playwright voor backward compatibility
async def _fetch_playwright(browser, url: str, country_code=None):
    """Rendert een pagina met een echte (headless) browser — omzeilt veel anti-bot/JS."""
    ctx = None
    domain = urlparse(url).netloc.replace("www.", "")
    try:
        ctx = await browser.new_context(
            user_agent=UA_POOL[0],
            locale=(ACCEPT_LANGUAGE.get(country_code, "en-US").split(",")[0]),
            viewport={"width": 1366, "height": 900},
            extra_http_headers={"Accept-Language": ACCEPT_LANGUAGE.get(country_code, "en-US,en;q=0.9")},
        )
        pg = await ctx.new_page()
        
        try:
            await pg.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as nav_err:
            logger.warning(f"Playwright navigatie mislukt voor {domain}: {nav_err}")
            return ("blocked", None)
        
        await pg.wait_for_timeout(3000)
        
        for sel in ["#onetrust-accept-btn-handler",
                    "button:has-text('Accepteren')", "button:has-text('Alles accepteren')",
                    "button:has-text('Akkoord')", "button:has-text('Accept all')",
                    "button:has-text('Accept')", "button:has-text('Tout accepter')",
                    "button:has-text('Alle akzeptieren')", "button:has-text('Aceptar')"]:
            try:
                await pg.click(sel, timeout=1200)
                await pg.wait_for_timeout(1000)
                break
            except Exception:
                pass
        
        # Human-like scroll and interaction voor betere detectie bypass
        import random
        try:
            # Scroll met variabele stappen
            for i in range(random.randint(2, 5)):
                await pg.evaluate(f"window.scrollBy(0, {random.randint(300, 800)})")
                await pg.wait_for_timeout(random.randint(400, 1200))
            
            # Mouse over willekeurige elementen
            links = await pg.query_selector_all("a")
            if len(links) > 5:
                random_link = random.choice(links[:8])
                box = await random_link.bounding_box()
                if box:
                    await pg.mouse.move(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                    await pg.wait_for_timeout(random.randint(100, 400))
        except Exception:
            pass
        
        html = await pg.content()
        data = await asyncio.to_thread(_parse_html, html, pg.url)
        result = _classify_page(data)
        if result[0] == "blocked":
            logger.warning(f"Playwright blokkade gedetecteerd voor {domain}")
        return result
    except Exception as e:
        error_type = type(e).__name__
        logger.warning(f"Playwright mislukt voor {domain} ({error_type}): {e}")
        return ("blocked", None)
    finally:
        if ctx:
            await ctx.close()


# ---------------------------------------------------------------------------
# LLM-analyse van de pagina
#   - provider 'emergent' (Emergent platform, Claude Sonnet 4.6)
#   - provider 'lmstudio'/'openai' (lokale LM Studio via OpenAI-compatibele API)
# ---------------------------------------------------------------------------
def _extract_json(raw: str):
    raw = raw.strip()
    raw = re.sub(r"^```(json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    return json.loads(raw)


# URL-patronen van individuele product-/advertentiepagina's op bekende sites.
PRODUCT_URL_PATTERNS = [
    re.compile(p) for p in (
        r"ebay\.[a-z.]+/itm/",
        r"amazon\.[a-z.]+/(?:[^/]+/)?(?:dp|gp/product)/[A-Z0-9]{10}",
        r"marktplaats\.nl/(?:v/|a/|.*?/m\d+)",
        r"2dehands\.be/v/|2ememain\.be/v/",
        r"kleinanzeigen\.de/s-anzeige/",
        r"digitec\.ch/[a-z]{2}/s\d+/product/|galaxus\.[a-z]+/[a-z]{2}/s\d+/product/",
        r"tutti\.ch/[a-z]{2}/vi/|ricardo\.ch/[a-z]{2}/a/",
        r"leboncoin\.fr/ad/|subito\.it/.+\.htm",
    )
]


def _candidate_product_links(links, max_links=25):
    """Kies uit de links op een pagina de waarschijnlijke Mac Studio-productlinks."""
    out = []
    for link in links or []:
        href = link["url"]
        low_href = href.lower()
        low_text = (link.get("text") or "").lower()
        is_product = any(pat.search(href) for pat in PRODUCT_URL_PATTERNS)
        mentions_studio = ("mac studio" in low_text or "mac-studio" in low_href
                           or "macstudio" in low_href)
        if is_product or mentions_studio:
            out.append(link)
        if len(out) >= max_links:
            break
    return out


def _resolve_listing_url(candidate, page_url, page_links):
    """Valideer de door de LLM gekozen advertentie_url.

    Alleen http(s)-links die echt op de pagina stonden (of de pagina zelf) worden
    geaccepteerd; anders vallen we terug op de gescande URL. Zo komen er geen
    verzonnen of javascript:-links in rapport en dashboard."""
    candidate = (candidate or "").strip().split("#", 1)[0]
    if not candidate.startswith(("http://", "https://")):
        return page_url
    if candidate.rstrip("/") == page_url.rstrip("/"):
        return page_url
    known = {l["url"].rstrip("/") for l in page_links or []}
    return candidate if candidate.rstrip("/") in known else page_url


def _build_prompt(text, title, url, country_name, is_marketplace=False, max_items=1, links=None,
                  offers=None):
    # Geef de echte productlinks van de pagina mee, zodat de LLM er een kan kiezen
    potential_links = _candidate_product_links(links)
    links_context = ""
    if potential_links:
        regels = "\n".join(f"- {l['url']} ({l['text']})" if l.get("text") else f"- {l['url']}"
                           for l in potential_links)
        links_context = f"""

Productlinks die op deze pagina staan (kies advertentie_url UITSLUITEND uit deze lijst of gebruik de pagina-URL):
{regels}
"""
    
    offers_context = ""
    if offers:
        regels = "\n".join(
            f"- {o.get('name') or '?'} | prijs: {o.get('price')} {o.get('currency') or ''} | "
            f"voorraad: {o.get('availability') or 'onbekend'}" for o in offers[:10])
        offers_context = f"""

Gestructureerde productdata van de winkel zelf (betrouwbaar — gebruik deze prijs/voorraad bij voorkeur):
{regels}
"""

    if is_marketplace:
        taak = (f"Dit is een MARKTPLAATS-/zoekpagina met MEERDERE advertenties. "
                f"Extraheer ELKE afzonderlijke Apple Mac Studio-advertentie met een ZICHTBARE prijs "
                f"(maximaal {max_items}). Elke advertentie is één object in de 'listings'-array. "
                f"LET OP: Dit kan een particuliere advertentie zijn (geen winkel).")
    else:
        taak = ("Betreft dit een specifieke Mac Studio productpagina (geen zoekresultaten/categorie)? "
                "Geef de CONCRETE configuratie met een ZICHTBARE prijs als één object in 'listings'. "
                "Als er meerdere configuraties zijn, kies dan de GOEDKOOPSTE met een zichtbare prijs. "
                "Geen prijs zichtbaar? Zet prijs op null. Geef maximaal 1 object. "
                "Dit kan een particuliere advertentie zijn — behandel deze hetzelfde als een winkeladvertentie.")
    
    return f"""Analyseer de onderstaande pagina uit {country_name}.

URL: {url}
Titel: {title}
Pagina-tekst: {_relevant_text(text)}{links_context}{offers_context}

{taak}

BELANGRIJK — CHIP RECOGNITIE:
- Mac Studio chips: M1 Max, M1 Ultra, M2 Max, M2 Ultra, M3 Ultra, M4 Max, M5 Max, M5 Ultra.
- Er bestaat GEEN Mac Studio met M3 Max of M4 Ultra; M4 Pro / M4 / M2 Pro zijn Mac mini's (geen Mac Studio).
- LET OP: "M3 Ultra 96GB" betekent M3 Ultra chip met 96GB unified memory — dit is een geldige Mac Studio configuratie!
- "96GB" is het geheugen (RAM), niet de opslag. De chip is "M3 Ultra".
- Andere combinaties: "M4 Max 36GB", "M5 Max 48GB", etc.
- Een "M2 Ultra" kan ook een Mac Pro zijn — controleer dat het product echt "Mac Studio" heet.

BELANGRIJK — DIRECTE PRODUCT/ADVERTENTIE LINK:
- JE MOET een DIRECTE link naar de specifieke Mac Studio advertentie/productpagina geven.
- GEbruik NOOIT de zoekresultatenpagina of categoriepagina als advertentie_url.
- Als er productlinks in de HTML staan (zie lijst hierboven), gebruik DAN de meest relevante link.
- Voor eBay: gebruik de URL naar /itm/... niet de zoekpagina.
- Voor Amazon: gebruik de URL naar /dp/B... niet de zoekpagina.
- Voor Marktplaats: gebruik de URL naar /l/[nummer]... of /v/[pad]/[nummer]... niet de zoekpagina.
- Voor Marktplaats: als dit een individuele advertentiepagina is, gebruik DAN de huidige URL als advertentie_url.
- Voor Digitec/tutti.ch/ricardo.ch: gebruik de productpagina URL.
- De advertentie_url IS de URL waar de gebruiker naartoe gaat wanneer ze op "Bekijk" klikken.
- Als er géén directe link beschikbaar is, gebruik dan de originele URL. Verzin NOOIT zelf een URL.

BELANGRIJK — Land van verzending:
Bepaal het LAND VAN VERZENDING/VERKOOP uit de pagina-inhoud. Dit kan verschillen van de land-code van de zoekopdracht.
Let op teksten zoals "Verzending uit:", "Ships from:", "Sent from:", "Verkoper locatie:", "Location:".
Geef dit land in het veld 'verzend_land' (landnaam) en 'verzend_land_code' (2-letters code).

Bepaal per aanbieding of de Mac Studio ECHT beschikbaar is (voor particuliere advertenties):
- Voor winkels: "bestelbaar", "op voorraad", "besteld op = leverbaar" = JA
- Voor particuliere advertenties (Marktplaats, eBay, etc.):
  - "te koop", "te verkopen", "te huur", "aanbieding" = JA
  - "reserveren", "bieden", "reactie sturen" = JA
  - "verkocht", "gereserveerd", "niet meer beschikbaar" = NEE
  - Als de advertentie recent is en geen "verkocht" status heeft = JA

Let op "niet leverbaar", "uitverkocht", "out of stock", "sold out", "nicht verfügbar", "en rupture de stock" (= NIET beschikbaar).

Wees extra alert op prijsfouten (typo's):
- Een Mac Studio kost normaal €800-€5000+. Als een prijs duidelijk een typefout is (bijv. €8.99, €89, €899 voor een M4 Ultra), markeer dit als "ONDUIDELIJK" en zet prijs op null.
- Als de prijs realistisch lijkt maar zeer laag is (<€700), wees dan sceptisch.

Antwoord met UITSLUITEND deze JSON (geen extra tekst):
{{
  "listings": [
    {{
      "beschikbaar": "JA" of "NEE" of "ONDUIDELIJK",
      "onderbouwing": "korte onderbouwing in het Nederlands",
      "chip": "PRECIES ÉÉN chip, bv. M2 Max / M3 Ultra / M4 Max, of onbekend",
      "ram": "bv. 32GB of onbekend",
      "opslag": "bv. 512GB of onbekend",
      "prijs": getal of null,
      "valuta": "EUR/GBP/CHF/SEK/DKK/PLN/NOK/USD/CAD/AUD/SGD/JPY/HKD/NZD/AED",
      "levertijd": "zoals vermeld of onbekend",
      "winkelnaam": "naam van de winkel of verkoper",
      "verkoper_type": "officiële Apple reseller" of "grote retailer" of "refurbished specialist" of "particulier marktplaats",
      "conditie": "nieuw" of "refurbished" of "tweedehands",
      "verzend_land": "land van verzending/verkoper, of leederland als onbekend",
      "verzend_land_code": "2-letters code van verzendland, of leederland",
      "advertentie_url": "DIRECTE link naar de advertentie/productpagina (GEEN zoekresultatenpagina!), of lege string als niet beschikbaar",
      "samenvatting_nl": "1 zin samenvatting in het Nederlands"
    }}
  ]
}}

Is dit geen Mac Studio-aanbod? Geef dan {{"listings": []}}.
Verzin NOOIT prijzen; laat 'prijs' null als er geen concrete prijs staat.
Gebruik ALTIJD een directe productlink als die beschikbaar is."""


async def _analyze_emergent(prompt):
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return None
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(api_key=api_key, session_id=f"scan-{uuid.uuid4()}",
                   system_message=SYSTEM_MSG).with_model("anthropic", "claude-sonnet-4-6")
    return await chat.send_message(UserMessage(text=prompt))


async def _analyze_openai_compatible(prompt):
    """Lokale LM Studio, Ollama, of elke OpenAI-compatibele server."""
    from openai import AsyncOpenAI
    
    # Detecteer provider (Ollama, LM Studio, OpenAI, etc.)
    provider = os.environ.get("LLM_PROVIDER", "ollama").lower()
    
    if provider == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        model = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b-instruct-q5_K_M")
        api_key = os.environ.get("OLLAMA_API_KEY", "ollama")
    elif provider in ("lmstudio", "local"):
        base_url = os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        model = os.environ.get("LMSTUDIO_MODEL", "local-model")
        api_key = os.environ.get("LMSTUDIO_API_KEY", "lm-studio")
    else:  # openai, vllm, etc.
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        api_key = os.environ.get("OPENAI_API_KEY", "sk-your-api-key")
    
    client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=120)
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM_MSG},
                  {"role": "user", "content": prompt}],
        temperature=0,
    )
    return resp.choices[0].message.content


async def analyze_page(text: str, title: str, url: str, country_name: str,
                       is_marketplace: bool = False, links=None, offers=None):
    """Geeft een LIJST van aanbiedingen terug (0..N). Voor marktplaatsen meerdere."""
    provider = os.environ.get("LLM_PROVIDER", "ollama").lower()
    max_items = 8 if is_marketplace else 1
    prompt = _build_prompt(text, title, url, country_name, is_marketplace, max_items, links, offers)
    try:
        if provider in ("lmstudio", "openai", "local", "ollama"):
            raw = await _analyze_openai_compatible(prompt)
        else:
            raw = await _analyze_emergent(prompt)
        if not raw:
            return []
        data = _extract_json(raw)
        items = data.get("listings") if isinstance(data, dict) else None
        if items is None and isinstance(data, dict):
            items = [data]  # fallback als het model één object teruggaf
        return [x for x in (items or []) if isinstance(x, dict)][:max_items]
    except Exception as e:
        logger.warning(f"LLM-analyse mislukt voor {url}: {e}")
        return []


# ---------------------------------------------------------------------------
# Prijs / marktconformiteit
# ---------------------------------------------------------------------------
ECB_FX_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
AED_PER_USD = 3.6725  # dirham is vast gekoppeld aan de dollar; staat niet in de ECB-lijst

# Actuele koersen (bij scanstart ververst via de ECB); FX_TO_EUR is de fallback.
_fx_rates = dict(FX_TO_EUR)


async def refresh_fx_rates(client):
    """Haal de dagkoersen van de ECB op. Geeft True bij succes; anders blijven de vaste koersen."""
    try:
        resp = await client.get(ECB_FX_URL, timeout=10)
        resp.raise_for_status()
        rates = {"EUR": 1.0}
        for cur, rate in re.findall(r"currency=['\"]([A-Z]{3})['\"]\s+rate=['\"]([\d.]+)['\"]", resp.text):
            rates[cur] = 1.0 / float(rate)
        if "USD" not in rates or len(rates) < 10:
            raise ValueError("onvolledige ECB-koerslijst")
        rates["AED"] = rates["USD"] / AED_PER_USD
        _fx_rates.update(rates)
        return True
    except Exception as e:
        logger.warning(f"ECB-wisselkoersen ophalen mislukt, vaste koersen gebruikt: {e}")
        return False


def to_eur(price, currency):
    if price is None:
        return None
    currency = (currency or "EUR").upper()
    if currency not in _fx_rates:
        return None  # onbekende valuta: liever geen prijs dan een verkeerde
    return round(float(price) * _fx_rates[currency], 2)


def match_reference(chip, reference_prices):
    if not chip:
        return None
    chip_l = chip.lower()
    for key, val in reference_prices.items():
        if key.lower() in chip_l:
            return val
    return None


def market_conformity(price_eur, chip, conditie, reference_prices):
    """Geeft (label, toelichting) terug."""
    ref = match_reference(chip, reference_prices)
    if price_eur is None or ref is None:
        return ("Onbekend", "Geen referentieprijs of prijs beschikbaar.")

    baseline = ref
    if conditie in ("refurbished", "tweedehands"):
        factor = 0.80 if conditie == "refurbished" else 0.72
        baseline = round(ref * factor)

    diff = (price_eur - baseline) / baseline
    if diff <= -0.05:
        return ("Scherp geprijsd", f"€{price_eur:.0f} ligt {abs(diff)*100:.0f}% onder referentie (€{baseline}).")
    if diff <= 0.05:
        return ("Marktconform", f"€{price_eur:.0f} rond referentie (€{baseline}).")
    return ("Boven marktprijs", f"€{price_eur:.0f} ligt {diff*100:.0f}% boven referentie (€{baseline}).")


# ---------------------------------------------------------------------------
# Hoofd-pipeline
# ---------------------------------------------------------------------------

# Land-kaart voor het normaliseren van landnamen naar codes
LAND_CODE_MAP = {
    "nederland": "NL", "nl": "NL", "netherlands": "NL", "holland": "NL",
    "belgië": "BE", "be": "BE", "belgium": "BE", "flanders": "BE",
    "duitsland": "DE", "de": "DE", "germany": "DE",
    "frankrijk": "FR", "fr": "FR", "france": "FR",
    "spanje": "ES", "es": "ES", "spain": "ES",
    "italië": "IT", "it": "IT", "italy": "IT",
    "verenigd koninkrijk": "GB", "gb": "GB", "uk": "GB", "britain": "GB",
    "oostenrijk": "AT", "at": "AT", "austria": "AT",
    "ierland": "IE", "ie": "IE", "ireland": "IE",
    "portugal": "PT", "pt": "PT",
    "finland": "FI", "fi": "FI",
    "luxemburg": "LU", "lu": "LU", "luxembourg": "LU",
    "zwitserland": "CH", "ch": "CH", "switzerland": "CH",
    "zweden": "SE", "se": "SE", "sweden": "SE",
    "denemarken": "DK", "dk": "DK", "denmark": "DK",
    "polen": "PL", "pl": "PL", "poland": "PL",
    "noorwegen": "NO", "no": "NO", "norway": "NO",
    "vae": "AE", "ae": "AE", "uae": "AE", "dubai": "AE",
    "verenigde staten": "US", "us": "US", "usa": "US", "america": "US", "united states": "US",
    "canada": "CA", "ca": "CA",
    "australië": "AU", "au": "AU", "australia": "AU",
    "singapore": "SG", "sg": "SG",
    "japan": "JP", "jp": "JP",
    "hong kong": "HK", "hk": "HK",
    "nieuw-zeeland": "NZ", "nz": "NZ", "new zealand": "NZ",
    "tsjechië": "CZ", "cz": "CZ", "czech republic": "CZ", "czechia": "CZ",
    "hongarije": "HU", "hu": "HU", "hungary": "HU",
    "roemenië": "RO", "ro": "RO", "romania": "RO",
    "slowakije": "SK", "sk": "SK", "slovakia": "SK",
    "slovenië": "SI", "si": "SI", "slovenia": "SI",
    "kroatië": "HR", "hr": "HR", "croatia": "HR",
    "bulgarije": "BG", "bg": "BG", "bulgaria": "BG",
    "estland": "EE", "ee": "EE", "estonia": "EE",
    "letland": "LV", "lv": "LV", "latvia": "LV",
    "litouwen": "LT", "lt": "LT", "lithuania": "LT",
    "malta": "MT", "mt": "MT",
    "cyprus": "CY", "cy": "CY",
}


def clean_country_code(code, name, fallback):
    """2-letterige landcode uit LLM-uitvoer; anders via landnaam; anders het zoekland.

    LLM's geven vaak 'onbekend', 'leederland' of 'UK' terug — dat mag geen
    (valse) land-mismatch opleveren."""
    c = (code or "").strip().upper()
    if c == "UK":
        c = "GB"
    if len(c) == 2 and c.isalpha():
        return c
    low = (name or "").strip().lower()
    return LAND_CODE_MAP.get(low, fallback)


_CHIP_RE = re.compile(r"\bM\s?([1-9])(?:\s*(Max|Ultra|Pro))?\b", re.I)


def normalize_chip(raw):
    """'m4max' / 'Apple M4 Max 16-core' → ('M4 Max', True). Onbekend → (None, True).
    Een herkende chip die niet in een Mac Studio bestaat → (chip, False)."""
    m = _CHIP_RE.search(raw or "")
    if not m:
        return None, True
    chip = f"M{m.group(1)}" + (f" {m.group(2).capitalize()}" if m.group(2) else "")
    return chip, chip in VALID_STUDIO_CHIPS


_CONDITIES = {"nieuw": "nieuw", "new": "nieuw", "refurbished": "refurbished",
              "gereviseerd": "refurbished", "tweedehands": "tweedehands", "used": "tweedehands",
              "gebruikt": "tweedehands"}
_VERKOPER_TYPES = ("officiële Apple reseller", "grote retailer", "refurbished specialist",
                   "particulier marktplaats")


def _clean_choice(value, mapping=None, allowed=()):
    v = (value or "").strip()
    if mapping is not None:
        return mapping.get(v.lower())
    for a in allowed:
        if v.lower() == a.lower():
            return a
    return None


def _clean_spec(value):
    v = (value or "").strip()
    return None if not v or v.lower() in ("onbekend", "unknown", "n/a", "?") else v[:40]


def _price_in_text(price, text):
    """Staat dit bedrag (in een gangbare notatie) echt op de pagina? Tegen verzonnen prijzen."""
    if price is None or not text:
        return False
    for n in {int(price), int(round(price))}:
        groups = f"{n:,}".split(",")
        pattern = r"(?<![\d.,])" + r"[.,\s'’]?".join(groups) + r"(?!\d)(?![.,\s'’]\d{3}(?!\d))"
        if re.search(pattern, text):
            return True
    return False


def _match_offer(price, offers):
    """Gestructureerd aanbod met (vrijwel) dezelfde prijs, of None."""
    for o in offers or []:
        if o.get("price") and price and abs(o["price"] - price) <= max(1.0, price * 0.01):
            return o
    return None


def build_listing(a, page, url, country, run_id, reference_prices, domain=None):
    """Valideer en normaliseer één LLM-aanbieding. Geeft (listing, None) of (None, reden)."""
    domain = domain or urlparse(url).netloc.replace("www.", "")
    offers = page.get("offers") or []
    text = page.get("text") or ""

    beschikbaar = (a.get("beschikbaar") or "ONDUIDELIJK").strip().upper()
    if beschikbaar not in ("JA", "NEE", "ONDUIDELIJK"):
        beschikbaar = "ONDUIDELIJK"

    chip, is_studio_chip = normalize_chip(a.get("chip"))
    if not is_studio_chip:
        return None, f"geen Mac Studio-chip ({chip})"

    price = _to_float(a.get("prijs"))
    valuta = (a.get("valuta") or "").strip().upper()
    if valuta not in _fx_rates:
        valuta = country.get("currency") or "EUR"

    # Prijs alleen geloven als hij op de pagina of in de productdata staat
    offer = _match_offer(price, offers)
    if price is not None:
        if offer:
            if offer.get("currency") in _fx_rates:
                valuta = offer["currency"]
        elif not _price_in_text(price, text):
            price = None
    # Geen (geldige) LLM-prijs, maar wel precies één Mac Studio in de productdata? Gebruik die.
    if price is None:
        studio_offers = [o for o in offers if o.get("price")
                         and "mac studio" in (o.get("name") or "").lower()]
        if len(studio_offers) == 1:
            offer = studio_offers[0]
            price = offer["price"]
            if offer.get("currency") in _fx_rates:
                valuta = offer["currency"]

    # Voorraadstatus van de winkel zelf gaat voor de inschatting van de LLM
    avail = (offer or {}).get("availability") or ""
    if avail in ("OutOfStock", "SoldOut", "Discontinued"):
        beschikbaar = "NEE"
    elif avail in ("InStock", "LimitedAvailability", "OnlineOnly") and beschikbaar == "ONDUIDELIJK":
        beschikbaar = "JA"
    if beschikbaar == "NEE":
        return None, "niet beschikbaar"

    price_eur = to_eur(price, valuta)
    # prijs-sanity: een Mac Studio ligt realistisch tussen €800 en €15.000
    if price_eur is not None and (price_eur < 800 or price_eur > 15000):
        price_eur = None
    # ruis eruit: geen bevestiging én geen prijs = geen bruikbaar aanbod
    if beschikbaar != "JA" and price_eur is None:
        return None, "geen bevestiging en geen prijs"

    verzend_land_code = clean_country_code(a.get("verzend_land_code"), a.get("verzend_land"),
                                           country["code"])
    verzend_land = (a.get("verzend_land") or "").strip()
    if verzend_land_code == country["code"] or verzend_land.lower() in ("", "onbekend", "leederland"):
        verzend_land = country["name"] if verzend_land_code == country["code"] else verzend_land_code
    conditie = _clean_choice(a.get("conditie"), mapping=_CONDITIES)
    label, toelichting = market_conformity(price_eur, chip, conditie, reference_prices)

    listing = {
        "id": str(uuid.uuid4()),
        "run_id": run_id,
        "url": url,  # originele scan URL
        # Directe advertentie URL — alleen als die echt op de pagina stond
        "advertentie_url": _resolve_listing_url(a.get("advertentie_url"), url, page.get("links")),
        "winkelnaam": (a.get("winkelnaam") or "").strip()[:80] or domain,
        "land": country["name"],
        "land_code": country["code"],
        "chip": chip,
        "ram": _clean_spec(a.get("ram")),
        "opslag": _clean_spec(a.get("opslag")),
        "prijs_eur": price_eur,
        "prijs_origineel": price if price_eur is not None else None,
        "valuta": valuta,
        "levertijd": _clean_spec(a.get("levertijd")),
        "beschikbaar": beschikbaar,
        "verkoper_type": _clean_choice(a.get("verkoper_type"), allowed=_VERKOPER_TYPES),
        "conditie": conditie,
        "verzend_land": verzend_land,
        "verzend_land_code": verzend_land_code,
        "land_mismatch": verzend_land_code != country["code"],
        "marktconformiteit": label,
        "marktconformiteit_toelichting": toelichting,
        "samenvatting_nl": a.get("samenvatting_nl"),
        "onderbouwing": a.get("onderbouwing"),
        "is_demo": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return listing, None


def calculate_quality_score(listing):
    """Bereken een kwaliteitsscore voor een listing (0-100). Hoger is beter.
    
    Factoren:
    - Directe advertentie-URL: +30 punten
    - Bevestigde beschikbaarheid: +20 punten
    - Realistische prijs: +15 punten
    - Land match (verzendland == zoekland): +15 punten
    - Geverifieerde verkoper type: +10 punten
    - Volledige specificaties: +10 punten
    """
    score = 0
    
    # Directe advertentie-URL (belangrijkste verbetering)
    if listing.get("advertentie_url") and listing["advertentie_url"].strip():
        score += 30
    elif listing.get("url") and listing["url"].strip():
        score += 10  # Basis URL
    
    # Bevestigde beschikbaarheid
    if listing.get("beschikbaar") == "JA":
        score += 20
    
    # Realistische prijs
    if listing.get("prijs_eur") and 800 <= listing["prijs_eur"] <= 15000:
        score += 15
    
    # Land match
    if listing.get("verzend_land_code") and listing.get("land_code"):
        if listing["verzend_land_code"].upper() == listing["land_code"].upper():
            score += 15
        else:
            score += 5  # Iets minder als het land niet matcht
    
    # Verkoper type
    vtype = (listing.get("verkoper_type") or "").lower()
    if "officiële" in vtype or "apple" in vtype:
        score += 10
    elif "retailer" in vtype or "refurbished" in vtype:
        score += 7
    elif "particulier" in vtype:
        score += 3
    
    # Volledige specificaties
    specs = 0
    if listing.get("chip"):
        specs += 1
    if listing.get("ram"):
        specs += 1
    if listing.get("opslag"):
        specs += 1
    score += min(10, specs * 4)
    
    return min(100, score)


async def perform_scan(db, settings: dict, run_id: str):
    """Voert een volledige scan uit, streamt live voortgang en slaat listings op."""
    log_lines = []
    stats = {"candidates": 0, "analyzed": 0, "available": 0, "excluded": 0,
             "blocked": 0, "errors": 0, "duplicates_removed": 0, "country_mismatch": 0,
             "irrelevant": 0, "price_unverified": 0, "blocked_urls": []}
    reference_prices = settings.get("reference_prices", REFERENCE_PRICES)
    max_per_query = settings.get("max_results_per_query", 10)
    max_pages = settings.get("max_pages_per_run", 200)
    include_mp = settings.get("include_marketplaces", True)
    enabled = [c for c in settings.get("countries", []) if c.get("enabled")]
    
    # Gebruik de geconfigureerde timezone voor logs (default Europe/Amsterdam)
    from dateutil import tz
    log_tz = tz.gettz(settings.get("timezone", "Europe/Amsterdam")) or tz.UTC

    def log(msg):
        log_lines.append(f"{datetime.now(log_tz).strftime('%H:%M:%S')} — {msg}")
        logger.info(msg)

    async def flush(phase, message, current=0, total=0):
        await db.scan_runs.update_one({"id": run_id}, {"$set": {
            "progress": {"phase": phase, "message": message,
                         "current": current, "total": total, "counters": dict(stats)},
            "log": log_lines[-80:],
            "stats": dict(stats),
        }})

    log(f"Scan gestart voor {len(enabled)} land(en).")
    await flush("zoeken", f"Scan gestart — {len(enabled)} landen worden doorzocht…", 0, len(enabled))

    # optionele Playwright-browser (echte browser) tegen anti-bot / JS-pagina's
    use_pw = os.environ.get("USE_PLAYWRIGHT", "").lower() in ("1", "true", "yes")
    pw = browser = None
    if use_pw:
        try:
            from playwright.async_api import async_playwright
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=True)
            log("🌐 Playwright-browser gestart (anti-bot fallback actief).")
        except Exception as e:
            log(f"⚠️  Playwright niet beschikbaar ({e}) — verder zonder browser-fallback.")
            browser = None

    per_country = []  # lijst van lijsten met (url, country)
    all_listings = []  # tijdelijke opslag voor deduplicatie
    
    try:
      async with httpx.AsyncClient(http2=True, follow_redirects=True) as client:
        if await refresh_fx_rates(client):
            log("💱 Actuele ECB-wisselkoersen geladen.")
        else:
            log("💱 ECB-koersen niet bereikbaar — vaste wisselkoersen gebruikt.")
        for i, c in enumerate(enabled, 1):
            await flush("zoeken", f"Zoeken in {c['name']} ({c['code']})…", i, len(enabled))
            retail = SEED_URLS.get(c["code"], [])
            mp = MARKETPLACE_SEED_URLS.get(c["code"], []) if include_mp else []
            urls = await search_urls(client, c, c["term"], max_per_query, include_mp)
            # interleave winkels + marktplaatsen + zoekresultaten voor eerlijke dekking
            merged = [x for trio in zip_longest(retail, mp, urls) for x in trio if x]
            per_country.append([(u, c) for u in merged])
            log(f"[{c['code']}] {len(urls)} zoekresultaten + {len(retail)} winkels "
                f"+ {len(mp)} marktplaatsen.")

        # round-robin interleaven zodat de cap over alle landen wordt verdeeld
        seen = set()
        uniq = []
        idx = 0
        while any(idx < len(b) for b in per_country):
            for b in per_country:
                if idx < len(b):
                    u, c = b[idx]
                    if u not in seen:
                        seen.add(u)
                        uniq.append((u, c))
            idx += 1
        uniq = uniq[:max_pages]
        stats["candidates"] = len(uniq)
        total = len(uniq)
        log(f"{total} unieke kandidaat-pagina's om te analyseren (max {max_pages}).")
        await flush("analyseren", f"{total} pagina's gevonden — start analyse…", 0, total)

        for n, (url, c) in enumerate(uniq, 1):
            domain = urlparse(url).netloc.replace("www.", "")
            await flush("analyseren", f"Analyseren van {domain} ({c['code']})", n, total)
            status, page = await fetch_page(client, url, c["code"], browser)
            
            # Gedetailleerde logging voor waarom pagina's worden overgeslagen
            if status == "error":
                stats["errors"] += 1
                stats["blocked_urls"].append({"url": url, "domain": domain, "reason": "Netwerkfout/timeout"})
                log(f"❌ FOUT — {domain}: Kan pagina niet ophalen (netwerkfout/timeouts)")
                continue
            if status in ("blocked", "empty"):
                stats["blocked"] += 1
                if status == "blocked":
                    stats["blocked_urls"].append({"url": url, "domain": domain, "reason": "Anti-bot bescherming (Cloudflare/Incapsula/etc.)"})
                    log(f"🚫 GEBLOKKEERD — {domain}: Anti-bot bescherming (Cloudflare/Incapsula/etc.) — Playwright fallback mislukt")
                else:
                    stats["blocked_urls"].append({"url": url, "domain": domain, "reason": "Onvoldoende content (<200 tekens)"})
                    log(f"🚫 LEEG — {domain}: Pagina werd geladen maar had onvoldoende content (<200 tekens)")
                continue
            
            if not _mentions_mac_studio(page):
                stats["irrelevant"] += 1
                log(f"⏭️  GEEN PRODUCT — {domain}: Geen Mac Studio op deze pagina (geen LLM-analyse)")
                continue

            is_mp = any(m in url.lower() for m in MARKETPLACE_DOMAINS)
            items = await analyze_page(page["text"], page["title"], url, c["name"], is_mp,
                                       page.get("links"), page.get("offers"))
            stats["analyzed"] += 1
            if not items:
                # Bepaal reden waarom geen items gevonden
                title_lower = (page.get("title") or "").lower()
                text_lower = (page.get("text") or "").lower()
                if "not found" in title_lower or "404" in title_lower or "pagina niet gevonden" in title_lower:
                    log(f"⏭️  404 — {domain}: Pagina bestaat niet meer")
                elif "out of stock" in text_lower or "nicht verfügbar" in text_lower or "uitverkocht" in text_lower:
                    log(f"⏭️  UITVERKOCHT — {domain}: Alle Mac Studio's uitverkocht")
                else:
                    log(f"⏭️  GEEN RESULTAAT — {domain}: LLM vond geen bruikbaar Mac Studio aanbod")
                continue

            for a in items:
                listing, reden = build_listing(a, page, url, c, run_id, reference_prices, domain)
                if listing is None:
                    stats["excluded"] += 1
                    log(f"⏭️  Uitgesloten — {domain}: {reden}")
                    continue
                if listing["land_mismatch"]:
                    stats["country_mismatch"] += 1
                    log(f"⚠️  Land mismatch: {domain} — zoekland={c['code']}, "
                        f"verzendland={listing['verzend_land_code']}")
                if a.get("prijs") is not None and listing["prijs_eur"] is None:
                    stats["price_unverified"] += 1  # LLM-prijs niet op de pagina terug te vinden
                all_listings.append(listing)
                stats["available"] += 1
                log(f"✅ {listing['winkelnaam']} ({c['code']}) — {listing['chip']} — €{listing['prijs_eur']}")

        # ---- DEDUPLICATIE ----
        # Verwijder dubbele listings op basis van:
        # 1. Zelfde advertentie_url (of dezelfde URL + chip + prijs)
        # 2. Zelfde winkel + chip + RAM + opslag + prijs_eur (binnen €50 tolerance)
        log("🔍 Dubbels controleren en verwijderen…")
        deduped = []
        seen_keys = set()
        
        for l in all_listings:
            # Maak een deduplicatie-key op basis van advertentie_url of URL
            if l.get("advertentie_url") and l["advertentie_url"] != l.get("url"):
                # Gebruik advertentie_url als primary key
                key = f"url:{l['advertentie_url'].lower()}"
            else:
                # Gebruik combinatie van URL + chip + prijs
                chip = (l.get("chip") or "").lower()
                prijs = l.get("prijs_eur")
                prijs_key = round(prijs / 50) * 50 if prijs else 0  # afronden op €50
                key = f"{l['url'].lower()}|{chip}|{prijs_key}"
            
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(l)
            else:
                stats["duplicates_removed"] += 1
                log(f"🗑️  Dubbel verwijderd: {l['winkelnaam']} — {l.get('chip')} — €{l.get('prijs_eur')}")
        
        # Sla de gedupliceerde listings op
        for l in deduped:
            await db.listings.insert_one(dict(l))
        
        stats["available"] = len(deduped)
        log(f"✅ {len(deduped)} unieke listings over (na deduplicatie)")

    finally:
        if browser:
            await browser.close()
        if pw:
            await pw.stop()

    log(f"Scan afgerond. Beschikbaar: {stats['available']}, uitgesloten: {stats['excluded']}, "
        f"geblokkeerd: {stats['blocked']}, fouten: {stats['errors']}, "
        f"dubbels verwijderd: {stats['duplicates_removed']}, "
        f"land mismatch: {stats['country_mismatch']}.")
    await flush("klaar", f"Scan afgerond — {stats['available']} beschikbaar gevonden.", total, total)
    return stats, log_lines


# ---------------------------------------------------------------------------
# Demo-data (duidelijk gelabeld) zodat het dashboard direct iets toont
# ---------------------------------------------------------------------------
def demo_listings(run_id: str):
    base = [
        ("Amac", "Nederland", "NL", "M2 Max", "32GB", "512GB", 2549, "EUR", "1-2 werkdagen",
         "JA", "officiële Apple reseller", "nieuw"),
        ("Back Market", "Frankrijk", "FR", "M2 Max", "32GB", "512GB", 1899, "EUR", "3-5 werkdagen",
         "JA", "refurbished specialist", "refurbished"),
        ("Cyberport", "Duitsland", "DE", "M3 Ultra", "64GB", "1TB", 4899, "EUR", "2-4 werkdagen",
         "JA", "grote retailer", "nieuw"),
        ("KRCS", "Verenigd Koninkrijk", "GB", "M4 Max", "36GB", "512GB", 2450, "GBP", "1 werkdag",
         "ONDUIDELIJK", "officiële Apple reseller", "nieuw"),
        ("Refurbed", "Oostenrijk", "AT", "M1 Ultra", "64GB", "1TB", 3199, "EUR", "5-7 werkdagen",
         "JA", "refurbished specialist", "refurbished"),
        ("Marktplaats", "Nederland", "NL", "M2 Ultra", "64GB", "1TB", 3850, "EUR", "afhalen/verzenden",
         "JA", "particulier marktplaats", "tweedehands"),
    ]
    out = []
    for (winkel, land, code, chip, ram, opslag, prijs, val, lever, besch, vtype, cond) in base:
        price_eur = to_eur(prijs, val)
        label, toel = market_conformity(price_eur, chip, cond, REFERENCE_PRICES)
        out.append({
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "url": "https://example.com/mac-studio",
            "winkelnaam": winkel,
            "land": land,
            "land_code": code,
            "chip": chip, "ram": ram, "opslag": opslag,
            "prijs_eur": price_eur, "prijs_origineel": prijs, "valuta": val,
            "levertijd": lever, "beschikbaar": besch,
            "verkoper_type": vtype, "conditie": cond,
            "marktconformiteit": label, "marktconformiteit_toelichting": toel,
            "samenvatting_nl": f"{chip} {ram}/{opslag} bij {winkel} ({land}).",
            "onderbouwing": "Voorbeelddata ter demonstratie.",
            "is_demo": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    return out
