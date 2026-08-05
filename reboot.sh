#!/usr/bin/env bash
# reboot.sh — Stop en start alle services (frontend + backend)
# Gebruik: ./reboot.sh   of   bash reboot.sh
#
# Robuust: werkt met zowel bash als sh, controleert dependencies,
#          schrijft REACT_APP_BACKEND_URL naar de frontend .env,
#          en stopt alle processen op de juiste poorten.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Kleuren en symbols
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CHECK_MARK="${GREEN}✓${NC}"
CROSS_MARK="${RED}✗${NC}"
ARROW="${BLUE}→${NC}"

# ---------------------------------------------------------------------------
# Helper: stop alle processen op een poort (werkt met fuser én lsof als fallback)
# ---------------------------------------------------------------------------
kill_port() {
    local port="$1"
    local label="$2"
    local pids

    # Probeer fuser eerst (betrouwbaarder, psmisc package)
    if command -v fuser &>/dev/null; then
        pids=$(fuser "$port/tcp" 2>/dev/null || true)
    fi

    # Fallback naar lsof als fuser niets vond of niet bestaat
    if [ -z "$pids" ] && command -v lsof &>/dev/null; then
        pids=$(lsof -ti ":$port" 2>/dev/null || true)
    fi

    # Fallback naar ss + awk als laatste redmiddel
    if [ -z "$pids" ] && command -v ss &>/dev/null; then
        pids=$(ss -tlnp "sport = :$port" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || true)
    fi

    if [ -z "$pids" ]; then
        echo -e "  ${GREEN}✅ $label was niet actief${NC}"
        return 0
    fi

    echo -e "  ${YELLOW}$label (poort $port) stoppen (PID: $(echo $pids | tr '\n' ' '))...${NC}"

    # Eerst SIGTERM naar alle PIDs
    for pid in $pids; do
        kill "$pid" 2>/dev/null || true
    done
    sleep 1

    # Check of er nog iets draait en forceer met SIGKILL
    local remaining
    if command -v fuser &>/dev/null; then
        remaining=$(fuser "$port/tcp" 2>/dev/null || true)
    else
        remaining=$(lsof -ti ":$port" 2>/dev/null || true)
    fi

    if [ -n "$remaining" ]; then
        for pid in $remaining; do
            kill -9 "$pid" 2>/dev/null || true
        done
        sleep 1
    fi

    echo -e "  ${GREEN}✅ $label gestopt${NC}"
}

# ---------------------------------------------------------------------------
# Helper: bepaal het WSL host IP (Windows host)
# ---------------------------------------------------------------------------
get_wsl_host_ip() {
    # In WSL2 staat het Windows host IP in /etc/resolv.conf als nameserver
    grep nameserver /etc/resolv.conf 2>/dev/null | awk '{print $2}' | head -1
}

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
check_deps() {
    local missing=""

    for cmd in python3 node curl; do
        if ! command -v "$cmd" &>/dev/null; then
            missing="$missing  - $cmd\n"
        fi
    done

    if ! command -v yarn &>/dev/null && ! command -v npm &>/dev/null; then
        missing="$missing  - yarn of npm\n"
    fi

    if [ -n "$missing" ]; then
        echo -e "${RED}❌ Ontbrekende dependencies:${NC}"
        echo -e "$missing"
        echo "Installeer deze eerst en probeer opnieuw."
        exit 1
    fi
}

echo "=================================================="
echo "  MacZoeker Reboot Script"
echo "=================================================="
echo ""

check_deps

# ---------------------------------------------------
# Stap 1: Stop alle bestaande services
# ---------------------------------------------------
echo -e "${YELLOW}🛑 Stap 1: Bestaande services stoppen${NC}"
echo "--------------------------------------------------"

kill_port 8001 "Backend"
kill_port 3000 "Frontend"

echo ""

# ---------------------------------------------------
# Stap 2: Start backend
# ---------------------------------------------------
echo -e "${BLUE}🚀 Stap 2: Backend starten${NC}"
echo "--------------------------------------------------"

cd "$SCRIPT_DIR/backend"

# Controleer .env — maak aan indien nodig
if [ ! -f ".env" ]; then
    echo -e "  ⚠️  .env niet gevonden."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "  ${CHECK_MARK} .env gekopieerd van .env.example"
    elif [ -f ".env-old" ]; then
        cp .env-old .env
        echo -e "  ${CHECK_MARK} .env gekopieerd van .env-old"
    else
        # Maak een minimale .env met defaults
        cat > .env <<'ENVEOF'
MONGO_URL=mongodb://localhost:27017
DB_NAME=mac_studio_zoeker
CORS_ORIGINS=*
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:14b-instruct-q5_K_M
OLLAMA_API_KEY=ollama
USE_PLAYWRIGHT=true
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
ENVEOF
        echo -e "  ${CHECK_MARK} .env aangemaakt met standaardwaarden. Pas aan indien nodig."
    fi
fi

# Controleer .venv
if [ ! -d ".venv" ]; then
    echo "  📦 Virtuele omgeving aanmaken..."
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
    echo -e "  ${GREEN}✅ Virtuele omgeving aangemaakt.${NC}"
fi

echo -e "  ${GREEN}🚀 Backend starten op http://0.0.0.0:8001${NC}"
echo "     API: http://localhost:8001/api/"
echo ""

# Start backend met expliciet pad naar venv (geen 'source' nodig — robuuster)
.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload \
    > /tmp/maczoeker-backend.log 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# Wacht tot backend klaar is (max 15 seconden)
echo -n "  Wachten op backend"
for i in $(seq 1 15); do
    sleep 1
    echo -n "."
    if curl -s http://localhost:8001/api/health >/dev/null 2>&1; then
        echo ""
        echo -e "  ${GREEN}✅ Backend is ready (http://localhost:8001)${NC}"
        break
    fi
    if [ "$i" -eq 15 ]; then
        echo ""
        echo -e "  ${RED}❌ Backend start niet (timeout)${NC}"
        echo "  Bekijk log: cat /tmp/maczoeker-backend.log"
        kill_port 8001 "Backend"
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

# De browser draait op Windows en bereikt WSL2 via localhost-forwarding.
# 10.255.255.254 werkt alleen binnen WSL, niet vanuit de Windows-browser.
BACKEND_URL="http://localhost:8001"

if [ ! -f ".env" ]; then
    echo -e "  ⚠️  .env niet gevonden. .env.example kopiëren..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
    fi
fi

# Update REACT_APP_BACKEND_URL in frontend .env (altijd, voor het geval het IP veranderd is)
if grep -q "REACT_APP_BACKEND_URL=" ".env" 2>/dev/null; then
    CURRENT_URL=$(grep "REACT_APP_BACKEND_URL=" .env | cut -d'=' -f2)
    if [ "$CURRENT_URL" != "$BACKEND_URL" ]; then
        echo -e "  ${ARROW} Backend URL bijwerken: $CURRENT_URL → $BACKEND_URL"
        sed -i "s|REACT_APP_BACKEND_URL=.*|REACT_APP_BACKEND_URL=$BACKEND_URL|" .env
        echo -e "  ${CHECK_MARK} Backend URL bijgewerkt naar $BACKEND_URL"
    else
        echo -e "  ${CHECK_MARK} Backend URL correct: $BACKEND_URL"
    fi
else
    echo "REACT_APP_BACKEND_URL=$BACKEND_URL" >> .env
    echo -e "  ${CHECK_MARK} Backend URL toegevoegd: $BACKEND_URL"
fi

# Controleer node_modules
if [ ! -d "node_modules" ]; then
    echo "  📦 Dependencies installeren..."
    if command -v yarn &>/dev/null; then
        yarn install --silent
    else
        npm install --silent
    fi
    echo -e "  ${GREEN}✅ Dependencies geïnstalleerd.${NC}"
fi

# Bouw de productie-bundle (geoptimaliseerd, geen dev warnings)
echo "  📦 Productie-bundle bouwen..."
if command -v yarn &>/dev/null; then
    yarn build > /tmp/maczoeker-frontend-build.log 2>&1
else
    npm run build > /tmp/maczoeker-frontend-build.log 2>&1
fi

if [ ! -f "build/index.html" ]; then
    echo -e "  ${RED}❌ Build mislukt — bekijk /tmp/maczoeker-frontend-build.log${NC}"
    kill_port 8001 "Backend"
    exit 1
fi
echo -e "  ${CHECK_MARK} Productie-bundle gebouwd ($(du -sh build | cut -f1))"

echo -e "  ${GREEN}🚀 Frontend (productie) starten op http://localhost:3000${NC}"
echo ""

# Serve de productie-bundle met 'serve' (lichtgewicht, geen dev server overhead)
if ! command -v npx &>/dev/null; then
    echo -e "  ${RED}❌ npx niet gevonden — installeer Node.js${NC}"
    kill_port 8001 "Backend"
    exit 1
fi
npx serve -s build -l 3000 > /tmp/maczoeker-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

# Wacht tot frontend klaar is (max 10 seconden — serve start vrijwel direct)
echo -n "  Wachten op frontend"
for i in $(seq 1 10); do
    sleep 1
    echo -n "."
    if curl -s http://localhost:3000 >/dev/null 2>&1; then
        echo ""
        echo -e "  ${GREEN}✅ Frontend is ready (http://localhost:3000) [productie]${NC}"
        break
    fi
    if [ "$i" -eq 10 ]; then
        echo ""
        echo -e "  ${RED}❌ Frontend start niet (timeout)${NC}"
        echo "  Bekijk log: cat /tmp/maczoeker-frontend.log"
        kill_port 3000 "Frontend"
        kill_port 8001 "Backend"
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
echo "  Backend URL (voor frontend): $BACKEND_URL"
echo ""
echo "  Logs:"
echo "    - Backend:  cat /tmp/maczoeker-backend.log"
echo "    - Frontend: cat /tmp/maczoeker-frontend.log"
echo ""
echo "  Stop alle services:"
echo "    fuser -k 8001/tcp 3000/tcp"
echo ""
echo "  ${YELLOW}Druk Ctrl+C niet — services draaien op de achtergrond${NC}"
echo ""
