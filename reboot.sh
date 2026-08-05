#!/usr/bin/env bash
# reboot.sh — Stop en start alle services (frontend + backend)
# Gebruik: ./reboot.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Kleuren en symbols
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=================================================="
echo "  MacZoeker Reboot Script"
echo "=================================================="
echo ""

# ---------------------------------------------------
# Stap 1: Stop alle bestaande services
# ---------------------------------------------------
echo -e "${YELLOW}🛑 Stap 1: Bestaande services stoppen${NC}"
echo "--------------------------------------------------"

# Stop backend (port 8001)
BACKEND_PID=$(lsof -ti :8001 2>/dev/null || true)
if [ -n "$BACKEND_PID" ]; then
    echo -e "  ${YELLOW}Backend (port 8001) stoppen (PID: $BACKEND_PID)...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    sleep 1
    # Force kill als het nog draait
    if lsof -ti :8001 >/dev/null 2>&1; then
        kill -9 $BACKEND_PID 2>/dev/null || true
    fi
    echo -e "  ${GREEN}✅ Backend gestopt${NC}"
else
    echo -e "  ${GREEN}✅ Backend was niet actief${NC}"
fi

# Stop frontend (port 3000)
FRONTEND_PID=$(lsof -ti :3000 2>/dev/null || true)
if [ -n "$FRONTEND_PID" ]; then
    echo -e "  ${YELLOW}Frontend (port 3000) stoppen (PID: $FRONTEND_PID)...${NC}"
    kill $FRONTEND_PID 2>/dev/null || true
    sleep 1
    # Force kill als het nog draait
    if lsof -ti :3000 >/dev/null 2>&1; then
        kill -9 $FRONTEND_PID 2>/dev/null || true
    fi
    echo -e "  ${GREEN}✅ Frontend gestopt${NC}"
else
    echo -e "  ${GREEN}✅ Frontend was niet actief${NC}"
fi

echo ""

# ---------------------------------------------------
# Stap 2: Start backend
# ---------------------------------------------------
echo -e "${BLUE}🚀 Stap 2: Backend starten${NC}"
echo "--------------------------------------------------"

cd "$SCRIPT_DIR/backend"

# Controleer .env
if [ ! -f ".env" ]; then
    echo -e "  ⚠️  .env niet gevonden. .env.example kopiëren..."
    cp .env.example .env
    echo -e "  ${GREEN}✅ .env aangemaakt.${NC}"
fi

# Controleer .venv
if [ ! -d ".venv" ]; then
    echo "  📦 Virtuele omgeving aanmaken..."
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
    echo -e "  ${GREEN}✅ Virtuele omgeving aangemaakt.${NC}"
fi

# Activeer virtuele omgeving en start backend
source .venv/bin/activate

echo -e "  ${GREEN}🚀 Backend starten op http://0.0.0.0:8001${NC}"
echo "     API: http://localhost:8001/api/"
echo ""

# Start backend in achtergrond en sla PID op
uvicorn server:app --host 0.0.0.0 --port 8001 --reload > /tmp/maczoeker-backend.log 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# Wacht tot backend klaar is (max 10 seconden)
echo -n "  Wachten op backend"
for i in {1..10}; do
    sleep 1
    echo -n "."
    if curl -s http://localhost:8001/api/health >/dev/null 2>&1; then
        echo ""
        echo -e "  ${GREEN}✅ Backend is ready (http://localhost:8001)${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo ""
        echo -e "  ${RED}❌ Backend start niet (timeout)${NC}"
        echo "  Bekijk log: cat /tmp/maczoeker-backend.log"
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
done

echo ""

# ---------------------------------------------------
# Stap 3: Start frontend
# ---------------------------------------------------
echo -e "${BLUE}🚀 Stap 3: Frontend starten${NC}"
echo "--------------------------------------------------"

cd "$SCRIPT_DIR/frontend"

# Controleer .env
if [ ! -f ".env" ]; then
    echo -e "  ⚠️  .env niet gevonden. .env.example kopiëren..."
    cp .env.example .env
    echo -e "  ${GREEN}✅ .env aangemaakt.${NC}"
fi

# Controleer node_modules
if [ ! -d "node_modules" ]; then
    echo "  📦 Dependencies installeren..."
    yarn install --silent
    echo -e "  ${GREEN}✅ Dependencies geïnstalleerd.${NC}"
fi

echo -e "  ${GREEN}🚀 Frontend starten op http://localhost:3000${NC}"
echo ""

# Start frontend in achtergrond en sla PID op
yarn start > /tmp/maczoeker-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

# Wacht tot frontend klaar is (max 30 seconden)
echo -n "  Wachten op frontend"
for i in {1..30}; do
    sleep 1
    echo -n "."
    if curl -s http://localhost:3000 >/dev/null 2>&1; then
        echo ""
        echo -e "  ${GREEN}✅ Frontend is ready (http://localhost:3000)${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo ""
        echo -e "  ${RED}❌ Frontend start niet (timeout)${NC}"
        echo "  Bekijk log: cat /tmp/maczoeker-frontend.log"
        kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
        exit 1
    fi
done

echo ""

# ---------------------------------------------------
# Stap 4: Rapport
# ---------------------------------------------------
echo "=================================================="
echo "  ✅ MacZoeker Reboot Complete"
echo "=================================================="
echo ""
echo "  Services:"
echo "    - Backend:  http://localhost:8001  (PID: $BACKEND_PID)"
echo "    - Frontend: http://localhost:3000  (PID: $FRONTEND_PID)"
echo ""
echo "  Logs:"
echo "    - Backend:  cat /tmp/maczoeker-backend.log"
echo "    - Frontend: cat /tmp/maczoeker-frontend.log"
echo ""
echo "  Stop alle services:"
echo "    kill $BACKEND_PID $FRONTEND_PID"
echo ""
echo "  ${YELLOW}Druck Ctrl+C niet om te stoppen - services draaien op de achtergrond${NC}"
echo ""
