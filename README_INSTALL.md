# Mac Studio Beschikbaarheid Zoeker — Installatie & Handleiding

Deze app doorzoekt dagelijks heel Europa (EU + UK + CH) naar Apple Mac Studio's die **echt bestelbaar** zijn,
verifieert elke pagina met een **LLM**, en stuurt een **Nederlandstalig rapport per e-mail**. Er is een
dashboard met live scan-voortgang, filters en een e-mailpreview.

> Deze handleiding is geschreven voor een AI-developer / ontwikkelaar die de app lokaal op een **Mac Studio**
> installeert met **lokale LM Studio** (in plaats van een cloud-LLM) en **VS Code**.

---

## 1. Architectuur

| Laag        | Technologie                                   | Poort |
|-------------|-----------------------------------------------|-------|
| Frontend    | React (Create React App / CRACO) + Tailwind   | 3000  |
| Backend     | FastAPI (Python) + APScheduler                | 8001  |
| Database    | MongoDB                                        | 27017 |
| LLM         | **LM Studio** (OpenAI-compatibele server)      | 1234  |

- Backend-routes zijn allemaal geprefixd met `/api`.
- De frontend praat met de backend via `REACT_APP_BACKEND_URL`.
- De scan draait op de achtergrond; een scheduler start hem dagelijks op een instelbaar tijdstip.

---

## 2. Vereisten (installeer eerst)

Op macOS met [Homebrew](https://brew.sh):

```bash
# Python 3.11+ en Node 18+
brew install python@3.11 node yarn

# MongoDB (community edition)
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community   # start MongoDB als service

# (optioneel) MongoDB Compass voor een GUI:  https://www.mongodb.com/products/compass
```

- **LM Studio**: download van https://lmstudio.ai
- **VS Code**: https://code.visualstudio.com

---

## 3. LM Studio klaarzetten (lokale LLM)

1. Open LM Studio → tab **Discover** → download een instruct-model dat goed is in JSON.
   Aanbevolen (kies naar rato van je RAM):
   - `Qwen2.5-14B-Instruct` (aanrader, goede JSON-output)
   - `Meta-Llama-3.1-8B-Instruct`
   - `Mistral-Small-Instruct`
2. Ga naar de tab **Developer / Local Server** → laad het model → klik **Start Server**.
3. De server draait nu op `http://localhost:1234/v1` (OpenAI-compatibel).
4. Noteer de **exacte modelnaam** zoals LM Studio die toont (bijv. `qwen2.5-14b-instruct`);
   die zet je straks in `backend/.env` als `LMSTUDIO_MODEL`.

> Tip: een groter/slimmer model geeft betrouwbaardere beschikbaarheids-analyses en nettere JSON.

---

## 3b. Anti-bot / JS-pagina's met Playwright (aanbevolen lokaal)

Veel grote winkels (MediaMarkt, Fnac, bol.com, Coolblue) en marktplaatsen laden hun prijzen/voorraad
pas via JavaScript of blokkeren simpele requests. Met **Playwright** haalt de app zulke pagina's op
met een echte (headless) browser — veel hogere slagingskans.

Eenmalig installeren (in de backend-venv):

```bash
pip install playwright
playwright install chromium
```

Zet daarna in `backend/.env`:

```ini
USE_PLAYWRIGHT=true
```

De app probeert een pagina eerst snel via HTTP; lukt dat niet (geblokkeerd/JS), dan pas met de browser.
Playwright accepteert automatisch cookie-meldingen en scrollt om lazy-loaded content te laden.

> Zonder Playwright werkt de app ook, maar dan worden JS-/anti-bot-sites overgeslagen (geteld als
> "geblokkeerd"). **Let op bij marktplaatsen:** zoekpagina's tonen vaak alleen accessoires/diensten of
> "Zie omschrijving" i.p.v. een prijs; individuele advertenties (zoals een eigen M3-listing) zijn daardoor
> niet altijd terug te vinden — marktplaatsen zijn de minst betrouwbare bron. Winkelpagina's zijn dat wél.

---

## 3c. Snelstart met Makefile (aanbevolen)

Een `Makefile` is toegevoegd voor eenvoudige installatie en start:

```bash
# Controleer status van alle diensten
make check-status

# Installeer alles in één keer
make install-all

# Start backend en frontend
make start-backend    # in terminal 1
make start-frontend   # in terminal 2

# Of gebruik de scripts direct:
./backend/start.sh    # in terminal 1
./frontend/start.sh   # in terminal 2

# Tests uitvoeren
make test-backend
make test-frontend

# MongoDB setup
make setup-mongo
make setup-playwright

# Demo-data resetten
make reset-demo

# Opruimen
make clean
```

---

## 4. Backend installeren

```bash
cd backend

# virtuele omgeving
python3.11 -m venv .venv
source .venv/bin/activate

# dependencies
pip install -r requirements.txt

# configuratie
cp .env.example .env
```

Bewerk `backend/.env`:

```ini
MONGO_URL=mongodb://localhost:27017
DB_NAME=mac_studio_zoeker
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
API_TOKEN=

LLM_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_MODEL=qwen2.5-14b-instruct      # <-- exact zoals in LM Studio
LMSTUDIO_API_KEY=lm-studio

# optioneel voor e-mail:
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
```

Start de backend:

```bash
uvicorn server:app --host 127.0.0.1 --port 8001 --reload
```

Test: open http://localhost:8001/api/  → je ziet een JSON-bericht.

> **Let op:** `emergentintegrations` staat in `requirements.txt` maar wordt lokaal **niet** gebruikt
> (die is voor het Emergent-platform). Zolang `LLM_PROVIDER=lmstudio` gebruikt de app LM Studio.
> Mocht `pip install` op dat pakket vastlopen, verwijder dan de regel `emergentintegrations...`
> uit `requirements.txt` — lokaal heb je het niet nodig.

---

## 5. Frontend installeren

Open een **tweede terminal**:

```bash
cd frontend
yarn install
cp .env.example .env      # REACT_APP_BACKEND_URL=http://localhost:8001
yarn start
```

De app opent op http://localhost:3000

---

## 6. Eerste start (seeding & migratie — automatisch)

Er zijn **geen losse migratiescripts** nodig. Bij de eerste start van de backend gebeurt automatisch:

1. **Instellingen** worden aangemaakt in de collectie `settings` (met alle 17 landen aan,
   marktplaatsen aan, ontvanger-e-mail, verzendtijd 08:00, referentieprijzen, enz.).
   Er zit een ingebouwd **versie-migratiesysteem** (`config_version`) in `get_settings_full()`
   dat oude instellingen automatisch bijwerkt.
2. Een **demo-run** met voorbeelddata wordt geseed (collectie `scan_runs` + `listings`), zodat het
   dashboard meteen gevuld is. Deze is duidelijk gelabeld als DEMO.
3. Onderbroken runs (door herstart) worden netjes op `onderbroken` gezet.

MongoDB-collecties die de app zelf aanmaakt/gebruikt:
`settings`, `scan_runs`, `listings`, `email_reports`.

> Wil je opnieuw beginnen? Leeg de database:
> ```bash
> mongosh mac_studio_zoeker --eval "db.dropDatabase()"
> ```
> Bij de volgende backend-start wordt alles opnieuw geseed.

---

## 7. De app gebruiken

- **Scan nu** (rechtsboven): start een live scan. Je ziet real-time de fase (zoeken → analyseren),
  het huidige land/winkel, live tellers (kandidaten / geanalyseerd / beschikbaar / uitgesloten /
  geblokkeerd / fouten) en een meelopend logboek.
- **E-mail preview**: bekijk het Nederlandstalige rapport met **alle** gevonden aanbiedingen
  (Bevestigd + Onduidelijk), gesorteerd op prijs.
- **Instellingen**: landen aan/uit, marktplaatsen aan/uit, aantal resultaten, ontvanger-e-mail,
  verzendtijd en **SMTP-gegevens** (+ knop "Verstuur testrapport nu").

### Bronnen
- Vaste winkellijst per land (`SEED_URLS` in `backend/scanner.py`) — ~80 Europese winkels.
- Tweedehands-marktplaatsen per land (`MARKETPLACE_SEED_URLS`) — Marktplaats, 2dehands, Kleinanzeigen,
  Leboncoin, Wallapop, Subito, Tradera, Blocket, DBA, Ricardo, Finn, Tori, OLX, Gumtree, Willhaben, …
- Live zoekresultaten via DuckDuckGo (`ddgs`, geen API-key nodig), landspecifiek.

Je kunt eenvoudig meer winkels toevoegen: bewerk `SEED_URLS` / `MARKETPLACE_SEED_URLS` in
`backend/scanner.py` en herstart de backend.

---

## 8. Configuratie-overzicht (backend/.env)

| Variabele          | Betekenis                                                        |
|--------------------|------------------------------------------------------------------|
| `MONGO_URL`        | MongoDB-connectiestring                                          |
| `DB_NAME`          | Databasenaam                                                     |
| `CORS_ORIGINS`     | Toegestane frontend-adressen (standaard `http://localhost:3000`)                         |
| `LLM_PROVIDER`     | `lmstudio` (lokaal) of `emergent` (Emergent-platform)            |
| `LMSTUDIO_BASE_URL`| OpenAI-compatibele endpoint van LM Studio                        |
| `LMSTUDIO_MODEL`   | Exacte modelnaam in LM Studio                                    |
| `LMSTUDIO_API_KEY` | Willekeurig (LM Studio negeert de waarde), bv. `lm-studio`       |
| `USE_PLAYWRIGHT`   | `true` = echte browser-fallback voor JS/anti-bot-pagina's        |
| `SMTP_*`           | Optionele e-mailverzending                                       |

---

## 9. API Endpoints

### Health & Status
| Endpoint | Methode | Beschrijving |
|----------|---------|--------------|
| `/api/` | GET | API root — bevestiging dat de API draait |
| `/api/settings` | GET | Haal instellingen op (wachtwoord gemaskeerd) |
| `/api/settings` | PUT | Werk instellingen bij |
| `/api/scan/run` | POST | Start een handmatige scan |
| `/api/scan/current` | GET | Huidige/laatste scan voortgang |
| `/api/scan/runs` | GET | Lijst van alle scans |
| `/api/scan/runs/{id}` | GET | Details van een specifieke scan |
| `/api/latest` | GET | Laatste resultaten + listings |
| `/api/reports/latest` | GET | Laatste e-mailrapport |
| `/api/reports/{id}` | GET | Specifiek rapport |
| `/api/email/test` | POST | Verstuur een testmail |
| `/api/reference-prices` | GET | Referentieprijzen per chip |

### Frontend Health Check (dev mode)
Als `ENABLE_HEALTH_CHECK=true` in `frontend/.env`:
| Endpoint | Methode | Beschrijving |
|----------|---------|--------------|
| `/health` | GET | Uitgebreide health status (compilatie, uptime, geheugen) |

---

## 10. Problemen oplossen

- **Geen resultaten / veel "geblokkeerd"**: normaal — veel grote winkels (MediaMarkt, Fnac) zitten
  achter anti-bot-CDN's en laden alleen in een echte browser. De scan slaat die netjes over.
  Kleinere resellers en marktplaatsen leveren wel data.
- **LLM-fouten / lege JSON**: kies in LM Studio een groter/instruct-model; zet temperatuur laag
  (de app stuurt `temperature=0`). Controleer dat de server op poort 1234 draait en
  `LMSTUDIO_MODEL` exact klopt.
- **Backend start niet**: draait MongoDB? (`brew services list`). Klopt `MONGO_URL`?
- **Frontend bereikt backend niet**: staat `REACT_APP_BACKEND_URL=http://localhost:8001` in
  `frontend/.env`? Herstart `yarn start` na wijziging.
- **CORS-fout**: voeg het adres van je frontend toe aan `CORS_ORIGINS` in `backend/.env`.
- **Scan duurt lang**: normaal 5–8 min voor 17 landen (elke pagina = 1 LLM-call). Verlaag
  `max_pages_per_run` / aantal landen in Instellingen voor een snellere run.

---

## 11. VS Code tips

Aanbevolen extensies:
- **Python** (Microsoft) + **Pylance**
- **ESLint** en **Prettier**
- **Tailwind CSS IntelliSense**
- **MongoDB for VS Code**

Twee terminals openen (backend + frontend), of gebruik de VS Code "Run and Debug"/tasks.

---

## 12. Mappen

```
backend/
  server.py          # FastAPI app, routes, scheduler, seeding/migratie
  scanner.py         # zoeken (ddgs) + scrapen + LLM-analyse + winkellijsten
  report.py          # Nederlandstalig e-mailrapport + SMTP-verzending
  requirements.txt
  .env.example
  start.sh           # start script met venv auto-setup
frontend/
  src/pages/Dashboard.jsx   # het dashboard (live voortgang, tabel, instellingen)
  src/lib/api.js
  src/App.js
  package.json
  .env.example
  start.sh           # start script met yarn auto-setup
Makefile             # installatie, start, tests, status checks
README_INSTALL.md    # dit bestand
```

Veel plezier! Pas gerust `SEED_URLS` aan om nog meer winkels toe te voegen.
