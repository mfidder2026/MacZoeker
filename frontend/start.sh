#!/usr/bin/env bash
# start.sh — Start de frontend development server.
# Gebruik: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Controleer .env
if [ ! -f ".env" ]; then
    echo "⚠️  .env niet gevonden. .env.example kopiëren..."
    cp .env.example .env
    echo "✅ .env aangemaakt."
fi

# Controleer node_modules
if [ ! -d "node_modules" ]; then
    echo "📦 Dependencies installeren..."
    yarn install
    echo "✅ Dependencies geïnstalleerd."
fi

echo "🚀 Frontend starten op http://localhost:3000"
echo "   Ctrl+C om te stoppen"
echo ""

exec yarn start
