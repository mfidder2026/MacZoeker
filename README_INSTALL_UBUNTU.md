# Mac Studio Beschikbaarheid Zoeker — Installatie & Handleiding (Ubuntu/Linux)

Deze handleiding is aangepast voor **Ubuntu (Linux)**. De app doorzoekt dagelijks heel Europa (EU + UK + CH) naar Apple Mac Studio's die **echt bestelbaar** zijn, verifieert elke pagina met een **LLM**, en stuurt een **Nederlandstalig rapport per e-mail**. Er is een dashboard met live scan-voortgang, filters en een e-mailpreview.

> **Verschillen met macOS-versie:**
> - LM Studio (macOS-only) → vervangen door **Ollama** (open-source LLM-server voor Linux)
> - Homebrew → vervangen door `apt`
> - MongoDB-installatie via `apt` in plaats van `brew`

---

## 1. Architectuur

| Laag        | Technologie                                   | Poort |
|-------------|-----------------------------------------------|-------|
| Frontend    | React (Create React App / CRACO) + Tailwind   | 3000  |
| Backend     | FastAPI (Python) + APScheduler                | 8001  |
| Database    | MongoDB                                        | 27017 |
| LLM         | **Ollama** (OpenAI-compatibele server)         | 11434 |

- Backend-routes zijn allemaal geprefixd met `/api`.
- De frontend praat met de backend via `REACT_APP_BACKEND_URL`.
- De scan draait op de achtergrond; een scheduler start hem dagelijks op een instelbaar tijdstip.

---

## 2. Vereisten (installeer eerst)

Op **Ubuntu 22.04+** (of Debian-gebaseerde distributies):

```bash
# Systeemvereisten en basisgereedschappen
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git python3 python3-pip python3-venv nodejs npm mongodb

# Yarn (voor frontend)
sudo npm install -g yarn

# Playwright (voor headless browser scraping)
sudo apt install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2
```

---

## 3. Ollama installeren (alternatief voor LM Studio)

Ollama is een open-source LLM-server die compatibel is met de OpenAI API. Het draait lokaal op Ubuntu en ondersteunt veel modellen.

### Installatie:

```bash
# Ollama installeren (eenmalig)
curl -fsSL https://ollama.com/install.sh | sh

# Ollama-server starten (in een aparte terminal of als service)
ollama serve &
```

### Model downloaden:

Kies een instruct-model dat goed is in **JSON-output** (bijv. voor prijsanalyse). Aanbevolen modellen:

```bash
# Aanbevolen modellen (kies één, afhankelijk van je RAM):
ollama pull qwen2.5:14b-instruct-q5_K_M   # Aanbevolen (goede JSON-output, 14B parameters)
ollama pull llama3.1:8b-instruct-q5_K_M   # Lichtgewicht alternatief
ollama pull mistral:7b-instruct-v0.3-q5_K_M
```

### Backend configureren voor Ollama:

Bewerk `backend/.env` (zie [Backend installeren](#4-backend-installeren)) en gebruik:

```ini
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:14b-instruct-q5_K_M   # Moet exact overeenkomen met `ollama list`
OLLAMA_API_KEY=ollama
```

> **Tip:** Grotere modellen geven betrouwbaardere analyses. Zet temperatuur laag (`temperature=0`) voor consistente JSON-output.

---

## 3b. Anti-bot / JS-pagina's met Playwright (aanbevolen)

Veel grote winkels (MediaMarkt, Fnac, bol.com, Coolblue) en marktplaatsen laden hun prijzen/voorraad pas via JavaScript of blokkeren simpele requests. Met **Playwright** haalt de app zulke pagina's op met een echte (headless) browser — veel hogere slagingskans.

### Installatie:

```bash
# Playwright installeren (in de backend-venv)
pip install playwright
playwright install chromium
```

### Configuratie:

Zet in `backend/.env`:

```ini
USE_PLAYWRIGHT=true
```

De app probeert een pagina eerst snel via HTTP; lukt dat niet (geblokkeerd/JS), dan pas met de browser. Playwright accepteert automatisch cookie-meldingen en scrollt om lazy-loaded content te laden.

> **Zonder Playwright** werkt de app ook, maar dan worden JS-/anti-bot-sites overgeslagen (geteld als "geblokkeerd").

---

## 3c. Snelstart met Makefile (Ubuntu-versie)

Gebruik het **Ubuntu-specifieke Makefile** (`Makefile.ubuntu`) voor eenvoudige installatie en start:

```bash
# Controleer status van alle diensten
make -f Makefile.ubuntu check-status

# Installeer alles in één keer
make -f Makefile.ubuntu install-all

# Start backend en frontend (in aparte terminals)
make -f Makefile.ubuntu start-backend    # Terminal 1
make -f Makefile.ubuntu start-frontend   # Terminal 2

# Of gebruik de scripts direct:
./backend/start.sh    # Terminal 1
./frontend/start.sh   # Terminal 2

# Tests uitvoeren
make -f Makefile.ubuntu test-backend
make -f Makefile.ubuntu test-frontend

# MongoDB setup
make -f Makefile.ubuntu setup-mongo
make -f Makefile.ubuntu setup-playwright

# Demo-data resetten
make -f Makefile.ubuntu reset-demo

# Opruimen
make -f Makefile.ubuntu clean
```

---

## 4. Backend installeren

```bash
cd backend

# Virtuele omgeving
python3 -m venv .venv
source .venv/bin/activate

# Dependencies
pip install -r requirements.txt

# Configuratie (gebruik Ollama in plaats van LM Studio)
cp .env.example .env
```

Bewerk `backend/.env`:

```ini
MONGO_URL=mongodb://localhost:27017
DB_NAME=mac_studio_zoeker
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
API_TOKEN=

# Ollama-configuratie (in plaats van LM Studio)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:14b-instruct-q5_K_M   # Exacte modelnaam uit `ollama list`
OLLAMA_API_KEY=ollama

# Optioneel voor e-mail:
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=

# Playwright (aanbevolen)
USE_PLAYWRIGHT=true
```

Start de backend:

```bash
uvicorn server:app --host 127.0.0.1 --port 8001 --reload
```

Test: open [http://localhost:8001/api/](http://localhost:8001/api/) → je ziet een JSON-bericht.

> **Let op:** `emergentintegrations` in `requirements.txt` is voor het Emergent-platform en wordt **lokaal niet gebruikt**. 
> Verwijder de regel `emergentintegrations...` uit `requirements.txt` als `pip install` vastloopt.

---

## 5. Frontend installeren

Open een **tweede terminal**:

```bash
cd frontend

# Dependencies
yarn install

# Configuratie
cp .env.example .env
```

Bewerk `frontend/.env` (standaardwaarden zijn prima voor lokale ontwikkeling):

```ini
REACT_APP_BACKEND_URL=http://localhost:8001
```

Start de frontend:

```bash
yarn start
```

De app opent op [http://localhost:3000](http://localhost:3000).

---

## 6. Eerste start (seeding & migratie — automatisch)

Bij de eerste start van de backend gebeurt automatisch:

1. **Instellingen** worden aangemaakt in de collectie `settings` (met alle 17 landen aan, marktplaatsen aan, ontvanger-e-mail, verzendtijd 08:00, referentieprijzen, enz.).
2. Een **demo-run** met voorbeelddata wordt geseed (collectie `scan_runs` + `listings`), zodat het dashboard meteen gevuld is.
3. Onderbroken runs (door herstart) worden netjes op `onderbroken` gezet.

MongoDB-collecties die de app zelf aanmaakt/gebruikt:
`settings`, `scan_runs`, `listings`, `email_reports`.

> **Opnieuw beginnen?** Leeg de database:
> ```bash
> mongosh mac_studio_zoeker --eval "db.dropDatabase()"
> ```
> Bij de volgende backend-start wordt alles opnieuw geseed.

---

## 7. De app gebruiken

- **Scan nu** (rechtsboven): start een live scan. Je ziet real-time de fase (zoeken → analyseren), het huidige land/winkel, live tellers (kandidaten / geanalyseerd / beschikbaar / uitgesloten / geblokkeerd / fouten) en een meelopend logboek.
- **E-mail preview**: bekijk het Nederlandstalige rapport met **alle** gevonden aanbiedingen (Bevestigd + Onduidelijk), gesorteerd op prijs.
- **Instellingen**: landen aan/uit, marktplaatsen aan/uit, aantal resultaten, ontvanger-e-mail, verzendtijd en **SMTP-gegevens** (+ knop "Verstuur testrapport nu").

---

## 8. Configuratie-overzicht (backend/.env)

| Variabele          | Betekenis                                                        |
|--------------------|------------------------------------------------------------------|
| `MONGO_URL`        | MongoDB-connectiestring (`mongodb://localhost:27017`)            |
| `DB_NAME`          | Databasenaam (`mac_studio_zoeker`)                                |
| `CORS_ORIGINS`     | Toegestane frontend-adressen (standaard `http://localhost:3000`)                         |
| `LLM_PROVIDER`     | `ollama` (lokaal) of `emergent` (Emergent-platform)              |
| `OLLAMA_BASE_URL`  | OpenAI-compatibele endpoint van Ollama (`http://localhost:11434/v1`) |
| `OLLAMA_MODEL`     | Exacte modelnaam in Ollama (bijv. `qwen2.5:14b-instruct-q5_K_M`) |
| `OLLAMA_API_KEY`   | Willekeurig (Ollama negeert de waarde), bv. `ollama`             |
| `USE_PLAYWRIGHT`   | `true` = echte browser-fallback voor JS/anti-bot-pagina's        |
| `SMTP_*`           | Optionele e-mailverzending                                       |

---

## 9. Problemen oplossen

- **Geen resultaten / veel "geblokkeerd"**: Normaal — veel grote winkels (MediaMarkt, Fnac) zitten achter anti-bot-CDN's en laden alleen in een echte browser. De scan slaat die netjes over. Kleinere resellers en marktplaatsen leveren wel data.
- **LLM-fouten / lege JSON**: Kies in Ollama een groter/instruct-model; zet temperatuur laag (de app stuurt `temperature=0`). Controleer dat Ollama draait (`ollama serve`) en `OLLAMA_MODEL` exact klopt.
- **Backend start niet**: Draait MongoDB? (`sudo systemctl status mongodb`). Klopt `MONGO_URL`?
- **Frontend bereikt backend niet**: Staat `REACT_APP_BACKEND_URL=http://localhost:8001` in `frontend/.env`? Herstart `yarn start` na wijziging.
- **CORS-fout**: Voeg het adres van je frontend toe aan `CORS_ORIGINS` in `backend/.env`.
- **Scan duurt lang**: Normaal 5–8 min voor 17 landen (elke pagina = 1 LLM-call). Verlaag `max_pages_per_run` / aantal landen in Instellingen voor een snellere run.

---

## 10. VS Code tips (zelfde als macOS)

Aanbevolen extensies:
- **Python** (Microsoft) + **Pylance**
- **ESLint** en **Prettier**
- **Tailwind CSS IntelliSense**
- **MongoDB for VS Code**

Twee terminals openen (backend + frontend), of gebruik de VS Code "Run and Debug"/tasks.

---

## 11. Mappen (zelfde als macOS)

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
Makefile.ubuntu     # Ubuntu-specifiek Makefile
README_INSTALL_UBUNTU.md  # Deze handleiding
```

---

## 12. Alternatieve LLM-opties (voor gevorderden)

### Optie 1: **Ollama (aanbevolen)**
- **Voordelen**: Open-source, lokaal draaien, geen API-kosten, veel modellen beschikbaar.
- **Nadelen**: Vereist voldoende RAM (14B-model: ~10GB RAM).
- **Installatie**: Zie [hierboven](#3-ollama-installeren-alternatief-voor-lm-studio).

### Optie 2: **Lokale API met vLLM of Text Generation WebUI**
- **vLLM**: Snellere inferentie voor grote modellen.
  ```bash
  pip install vllm
  python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-14B-Instruct --dtype auto --api-key token-abc123 --port 8000
  ```
  Configureer in `backend/.env`:
  ```ini
  LLM_PROVIDER=openai
  OPENAI_BASE_URL=http://localhost:8000/v1
  OPENAI_MODEL=Qwen/Qwen2.5-14B-Instruct
  OPENAI_API_KEY=token-abc123
  ```

### Optie 3: **Cloud-LLM (betaald)**
- **Providers**: OpenAI, Mistral AI, Groq, Fireworks AI.
- Configureer in `backend/.env`:
  ```ini
  LLM_PROVIDER=openai
  OPENAI_BASE_URL=https://api.openai.com/v1
  OPENAI_MODEL=gpt-4o-mini
  OPENAI_API_KEY=sk-your-api-key
  ```

---

Veel plezier! Pas gerust `SEED_URLS` in `backend/scanner.py` aan om meer winkels toe te voegen.