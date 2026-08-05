# MacZoeker - Global Mac Studio Availability Scanner

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![AI Powered](https://img.shields.io/badge/AI-Powered-blue.svg)](https://github.com/openai)
[![Daily Reports](https://img.shields.io/badge/Reports-Daily-green.svg)]()

**MacZoeker** is een geavanceerde wereldwijde beschikbaarheids-scanner voor Mac Studio computers. Het systeem doorzoekt dagelijks 30+ landen naar beschikbare voorraad bij webshops en marktplaatsen, verifieert beschikbaarheid met AI en stuurt gedetailleerde rapporten per e-mail.

🌍 **30+ landen** | 🛒 **Webshops & marktplaatsen** | 🤖 **AI-verificatie** | 💰 **Kostenefficiënt** | 📧 **Dagelijkke rapportage**

![MacZoeker Dashboard](https://via.placeholder.com/800x400/0078d7/ffffff?text=MacZoeker+Dashboard) *Voorbeeld van het MacZoeker dashboard met wereldwijde beschikbaarheid*

## 🚀 Wat maakt MacZoeker uniek?

✅ **Wereldwijde dekking** - Zoekt in 30+ landen naar Mac Studio's via DuckDuckGo
✅ **AI-gedreven verificatie** - Gebruikt OpenAI-compatible AI (Claude, LM Studio, Ollama, etc.) om beschikbaarheid kostenefficiënt te controleren
✅ **Dagelijkse rapportage** - Ontvang automatisch e-mails met nieuwe aanbiedingen
✅ **Prijsvergelijking** - Vergelijkt prijzen met officiële Apple adviesprijzen
✅ **Land mismatch detectie** - Identificeert importmogelijkheden (bijv. US → EU)
✅ **Marktplaatsondersteuning** - Doorzoekt zowel officiële winkels als particuliere marktplaatsen
✅ **Automatische valuta conversie** - Alle prijzen worden omgerekend naar EUR voor vergelijking
✅ **Slimme filtering** - Blokkeert nieuwsites, forums en andere niet-relevante bronnen

## 🌍 Landendekking

MacZoeker doorzoekt dagelijks de volgende landen:

**Europa**: Nederland, België, Duitsland, Frankrijk, Spanje, Italië, Verenigd Koninkrijk, Oostenrijk, Ierland, Portugal, Finland, Luxemburg, Zwitserland, Zweden, Denemarken, Polen, Noorwegen, Tsjechië, Hongarije, Roemenië, Slowakije, Slovenië, Kroatië, Bulgarije, Estland, Letland, Litouwen, Malta, Cyprus

**Wereldwijd**: Verenigde Arabische Emiraten, Verenigde Staten, Canada, Australië, Singapore, Japan, Hong Kong, Nieuw-Zeeland

## 🤖 Hoe werkt het?

1. **Zoeken**: MacZoeker gebruikt DuckDuckGo om landspecifiek te zoeken naar Mac Studio aanbiedingen
2. **Scrapen**: Productpagina's worden gedownload en geanalyseerd
3. **AI-verificatie**: OpenAI-compatible AI (Claude, LM Studio, Ollama, etc.) controleert of de Mac Studio daadwerkelijk beschikbaar is
4. **Prijsanalyse**: Prijzen worden vergeleken met officiële Apple adviesprijzen
5. **Rapportage**: Dagelijks e-mailrapport met alle gevonden aanbiedingen
6. **Dashboard**: Webinterface om historische data en trends te bekijken

## 📊 Rapportage features

- **Bevestigde beschikbaarheid**: Aanbiedingen die geverifieerd beschikbaar zijn
- **Onduidelijke beschikbaarheid**: Aanbiedingen die handmatige controle vereisen
- **Land mismatches**: Producten die vanuit een ander land worden verzonden
- **Prijsvergelijking**: Huidige prijs vs. Apple adviesprijs
- **Marktconformiteit**: Scherp geprijsd, marktconform of boven marktprijs
- **Levertijd informatie**: Wanneer wordt het product geleverd?
- **Verkopertypes**: Officiële winkels vs. particuliere marktplaatsen

## 🛠️ Installatie

### Vereisten
- Python 3.8+ (voor backend)
- Node.js 16+ (voor frontend)
- WSL2 (voor Windows gebruikers)
- GitHub account (voor AI API toegang)

### Stappen

1. **Repository clonen**
```bash
git clone https://github.com/mfidder2026/MacZoeker.git
cd MacZoeker
```

2. **Backend installeren**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS/WSL
# of .venv\Scripts\activate op Windows
pip install -r requirements.txt
```

3. **Frontend installeren**
```bash
cd ../frontend
yarn install
```

4. **Configuratie**
```bash
# Kopieer voorbeeldconfiguratiebestanden
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Configureer je instellingen in backend/.env
# Voeg je Anthropic API sleutel toe voor AI-verificatie
```

5. **Services starten**
```bash
# Voor Linux/macOS/WSL
./reboot.sh

# Voor Windows
cd backend
start.sh
cd ../frontend
start.sh
```

## ⚙️ Configuratie

### Backend (.env)
```ini
# AI configuratie (kies één van de opties)
# Optie 1: Anthropic Claude (betaald)
ANTHROPIC_API_KEY=your_api_key_here

# Optie 2: OpenAI-compatible API (bijv. LM Studio, Ollama)
OPENAI_API_KEY=sk-1234567890  # Kan willekeurig zijn voor lokale servers
OPENAI_API_BASE=http://localhost:1234/v1  # URL van je lokale AI server

# Scan instellingen
SCAN_INTERVAL_HOURS=24
MAX_RESULTS_PER_QUERY=10
INCLUDE_MARKETPLACES=true

# E-mail meldingen
EMAIL_ENABLED=true
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=user@example.com
SMTP_PASSWORD=yourpassword
EMAIL_FROM=noreply@maczoeker.example.com
EMAIL_TO=your@email.com

# Landen en zoektermen (kan aangepast worden)
ENABLED_COUNTRIES=NL,BE,DE,FR,GB,US
```

### Frontend (.env)
```ini
REACT_APP_BACKEND_URL=http://localhost:8001
```

## 🖥️ Gebruik

Na het starten van de services kun je MacZoeker benaderen via:

- **Frontend dashboard**: http://localhost:3000
- **Backend API**: http://localhost:8001

### Belangrijke commando's
```bash
# Alle services stoppen en starten
./reboot.sh

# Alleen backend starten
cd backend && ./start.sh

# Alleen frontend starten
cd frontend && ./start.sh
```

## 📈 Dashboard Overzicht

Het MacZoeker dashboard biedt:
- **Realtime beschikbaarheid** - Huidige Mac Studio aanbiedingen wereldwijd
- **Scan geschiedenis** - Overzicht van eerdere scans
- **Prijsontwikkeling** - Trends in Mac Studio prijzen
- **Landanalyse** - Waar zijn Mac Studio's beschikbaar?
- **Rapport generatie** - Exporteerbare rapporten
- **Instellingen** - Configureer scanparameters en meldingen

## 📬 Voorbeeld e-mailrapport

Dagelijks ontvang je een e-mail met:
- Totaal aantal gevonden aanbiedingen
- Bevestigd beschikbare Mac Studio's
- Onduidelijke beschikbaarheid (handmatige controle nodig)
- Land mismatches (mogelijke importkansen)
- Prijsvergelijking met Apple adviesprijzen
- Directe links naar de aanbiedingen

![Voorbeeld e-mail](https://via.placeholder.com/600x400/f0f0f0/333333?text=MacZoeker+Email+Report) *Voorbeeld van een MacZoeker e-mailrapport*

## 🔧 Geavanceerde opties

### Landen aanpassen
Je kunt landen toevoegen, verwijderen of uitschakelen in de configuratie. Elk land heeft:
- Landcode (bijv. NL, BE, DE)
- Zoekterm (bijv. "Mac Studio kopen M3")
- Valuta (voor prijsconversie)
- Taalinstellingen (voor lokale zoekresultaten)

### AI-configuratie
MacZoeker ondersteunt OpenAI-compatible AI agents:
- **Claude Sonnet** (standaard, vereist API sleutel)
- **LM Studio** (lokaal, gratis, geen API kosten)
- **Ollama** (lokaal, gratis, geen API kosten)
- **Andere OpenAI-compatible API's**

De AI wordt gebruikt voor:
- Beschikbaarheid verifiëren
- Productconfiguraties controleren
- Valse positieve resultaten filteren
- Leveringsvoorwaarden analyseren

### Marktplaatsfilter
Je kunt kiezen om:
- Alleen officiële winkels te doorzoeken
- Ook particuliere marktplaatsen (eBay, Marktplaats, etc.) mee te nemen
- Specifieke marktplaatsen uit te sluiten

## 🤝 Bijdragen

Bijdragen aan MacZoeker zijn welkom! Volg deze stappen:

1. Fork de repository
2. Maak een feature branch (`git checkout -b feature/geweldige-functie`)
3. Commit je wijzigingen (`git commit -m 'Voeg geweldige functie toe'`)
4. Push naar de branch (`git push origin feature/geweldige-functie`)
5. Open een Pull Request

## 📜 Licentie

Dit project is gelicentieerd onder de **MIT License** - zie het [LICENSE](LICENSE) bestand voor details.

## 📞 Ondersteuning

Voor vragen of ondersteuning:
- Open een issue in deze repository
- Neem contact op via GitHub

## 🤖 Lokale AI-instellingen

Voor kostenefficiënte AI-verificatie kun je lokale AI-servers gebruiken:

### LM Studio
1. Download en installeer LM Studio van [lmstudio.ai](https://lmstudio.ai)
2. Kies een geschikt model (bijv. llama3, mistral, etc.)
3. Start de lokale server op `http://localhost:1234`
4. Configureer in `.env`:
```ini
OPENAI_API_KEY=sk-1234567890
OPENAI_API_BASE=http://localhost:1234/v1
```

### Ollama
1. Installeer Ollama van [ollama.ai](https://ollama.ai)
2. Download een model: `ollama pull llama3`
3. Start de server: `ollama serve`
4. Configureer in `.env`:
```ini
OPENAI_API_KEY=ollama
OPENAI_API_BASE=http://localhost:11434/v1
```

---
💡 **Tip**: MacZoeker werkt het beste met een OpenAI-compatible AI voor beschikbaarheidsverificatie. Voor kostenefficiëntie kun je lokale AI-servers zoals LM Studio of Ollama gebruiken.