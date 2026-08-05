#!/usr/bin/env bash
# start.sh — Start de backend met virtuele omgeving en uvicorn.
# Gebruik: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Controleer of de virtuele omgeving bestaat
if [ ! -d ".venv" ]; then
    echo "⚠️  Virtuele omgeving niet gevonden. Aan het maken..."
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    echo "✅ Virtuele omgeving gemaakt."
fi

# Activeer virtuele omgeving
source .venv/bin/activate

# Controleer .env
if [ ! -f ".env" ]; then
    echo "⚠️  .env niet gevonden. .env.example kopiëren..."
    cp .env.example .env
    echo "✅ .env aangemaakt. Pas de waarden aan (vooral OLLAMA_MODEL)."
fi

echo "🚀 Backend starten op http://0.0.0.0:8001"
echo "   API: http://localhost:8001/api/"
echo "   Ctrl+C om te stoppen"
echo ""

exec uvicorn server:app --host 0.0.0.0 --port 8001 --reload
