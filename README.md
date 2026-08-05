# MacZoeker - Network Device Discovery Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**MacZoeker** is een krachtige netwerkscan-tool die automatisch apparaten in je lokale netwerk detecteert en identificeert. Het systeem scant regelmatig je netwerk, houdt wijzigingen bij en kan je waarschuwen wanneer nieuwe of onbekende apparaten worden gedetecteerd.

![MacZoeker Dashboard](https://via.placeholder.com/800x400/0078d7/ffffff?text=MacZoeker+Dashboard) *Voorbeeld van het MacZoeker dashboard*

## 🚀 Features

✅ **Automatische netwerkscans** - Regelmatige scans van je lokale netwerk
✅ **Apparaatdetectie** - Identificeert apparaten op basis van MAC-adressen en hostnamen
✅ **Wijzigingsdetectie** - Houdt bij wanneer apparaten verschijnen of verdwijnen
✅ **Webinterface** - Gebruiksvriendelijke dashboard om apparaten te bekijken
✅ **Rapportage** - Gedetailleerde rapporten van netwerkactiviteit
✅ **Waarschuwingen** - Optionele e-mailmeldingen bij nieuwe apparaten
✅ **Multi-platform** - Werkt op Windows, Linux en macOS via WSL

## 📋 Systeemvereisten

- **Besturingssysteem**: Windows 10/11 met WSL2, Linux of macOS
- **Python**: 3.8+ (voor backend)
- **Node.js**: 16+ (voor frontend)
- **Netwerk**: Lokale netwerktoegang

## 🛠️ Installatie

### 1. Repository clonen
```bash
git clone https://github.com/mfidder2026/MacZoeker.git
cd MacZoeker
```

### 2. Backend installeren
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS/WSL
# of .venv\Scripts\activate op Windows
pip install -r requirements.txt
```

### 3. Frontend installeren
```bash
cd ../frontend
yarn install
```

### 4. Configuratie
Kopieer de voorbeeldconfiguratiebestanden:
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Pas de `.env` bestanden aan met je eigen instellingen.

### 5. Services starten
```bash
# Voor Linux/macOS/WSL
./reboot.sh

# Voor Windows
cd backend
start.sh
cd ../frontend
start.sh
```

## 🖥️ Gebruik

Na het starten van de services kun je MacZoeker benaderen via:

- **Frontend**: http://localhost:3000
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

## 📊 Dashboard Overzicht

Het MacZoeker dashboard biedt:
- **Realtime netwerkstatus** - Huidige apparaten in je netwerk
- **Scan geschiedenis** - Overzicht van eerdere scans
- **Wijzigingsdetectie** - Nieuwe en verdwenen apparaten
- **Rapport generatie** - Exporteerbare rapporten
- **Instellingen** - Configureer scanintervallen en meldingen

## 🔧 Configuratieopties

### Backend (.env)
```
# Scan instellingen
SCAN_INTERVAL_MINUTES=60
NETWORK_INTERFACE=eth0

# E-mail meldingen
EMAIL_ENABLED=true
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=user@example.com
SMTP_PASSWORD=yourpassword
EMAIL_FROM=noreply@maczoeker.example.com
EMAIL_TO=admin@example.com
```

### Frontend (.env)
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

## 📬 Meldingen

MacZoeker kan e-mailmeldingen sturen wanneer:
- Nieuwe apparaten worden gedetecteerd
- Bekende apparaten verdwijnen uit het netwerk
- Er wijzigingen zijn in het netwerk

Configureer de SMTP-instellingen in het `.env` bestand van de backend.

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

---
💡 **Tip**: MacZoeker werkt het beste in combinatie met WSL2 op Windows voor optimale netwerkscanmogelijkheden!
