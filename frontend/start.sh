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

# Zorg ervoor dat de backend URL correct is ingesteld voor WSL naar Windows communicatie
if ! grep -q "REACT_APP_BACKEND_URL=" ".env"; then
    echo "🔧 Backend URL configureren voor WSL naar Windows communicatie..."
    # Gebruik het Windows host IP (via /etc/resolv.conf) zodat frontend in Windows de backend kan bereiken
    WIN_HOST_IP=$(grep nameserver /etc/resolv.conf | awk '{print $2}')
    echo "REACT_APP_BACKEND_URL=http://$WIN_HOST_IP:8001" >> .env
    echo "✅ Backend URL ingesteld: http://$WIN_HOST_IP:8001"
else
    # Update bestaande .env als het een WSL IP is (oude configuratie)
    CURRENT_BACKEND_URL=$(grep "REACT_APP_BACKEND_URL=" .env | cut -d'=' -f2)
    if [[ "$CURRENT_BACKEND_URL" == http://172.*:* ]]; then
        echo "🔄 Bijwerken van oude WSL IP configuratie..."
        WIN_HOST_IP=$(grep nameserver /etc/resolv.conf | awk '{print $2}')
        sed -i "s|REACT_APP_BACKEND_URL=.*|REACT_APP_BACKEND_URL=http://$WIN_HOST_IP:8001|" .env
        echo "✅ Backend URL bijgewerkt: http://$WIN_HOST_IP:8001"
    else
        echo "✅ Backend URL al geconfigureerd in .env"
    fi
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

# Start de frontend (geen HOST nodig, draait op localhost)
exec yarn start
