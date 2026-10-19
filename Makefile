# Mac Studio Beschikbaarheid Zoeker — Makefile
# Installatie en start scripts voor lokale ontwikkeling.

.PHONY: all install-backend install-frontend install-all \
        start-backend start-frontend start-all \
        stop \
        test test-backend test-frontend \
        clean \
        setup-mongo setup-playwright \
        seed reset-demo \
        check-status

# Standaard doel
all: install-all

# ---------------------------------------------------------------------------
# Installatie
# ---------------------------------------------------------------------------

install-all: install-backend install-frontend
	@echo "✅ Installatie voltooid."

install-backend:
	@echo "📦 Backend installeren..."
	cd backend && python3 -m venv .venv
	cd backend && .venv/bin/pip install -r requirements.txt
	cd backend && [ -f .env ] || cp .env.example .env
	@echo "✅ Backend geïnstalleerd. Pas backend/.env aan (LMSTUDIO_MODEL)."

install-frontend:
	@echo "📦 Frontend installeren..."
	cd frontend && [ -f .env ] || cp .env.example .env
	@if ! command -v node &>/dev/null; then \
		echo "⚠️  Node.js niet gevonden, installeren via Homebrew..."; \
		brew install node; \
	fi
	@if ! command -v yarn &>/dev/null; then \
		echo "⚠️  yarn niet gevonden, installeren..."; \
		npm install -g yarn; \
	fi
	cd frontend && yarn install
	@echo "✅ Frontend geïnstalleerd."

setup-mongo:
	@echo "🍄 MongoDB controleren..."
	@if brew list mongodb-community &>/dev/null; then \
		echo "MongoDB geïnstalleerd, service starten..."; \
		brew services start mongodb-community; \
	else \
		echo "⚠️  MongoDB niet geïnstalleerd. Voer:"; \
		echo "    brew tap mongodb/brew && brew install mongodb-community"; \
		echo "    brew services start mongodb-community"; \
	fi

setup-playwright:
	@echo "🌐 Playwright browsers installeren..."
	cd backend && .venv/bin/pip install playwright
	cd backend && .venv/bin/python -m playwright install chromium
	@echo "✅ Playwright klaar."

# ---------------------------------------------------------------------------
# Starten
# ---------------------------------------------------------------------------

start-backend:
	@echo "🚀 Backend starten op poort 8001..."
	cd backend && .venv/bin/python -m uvicorn server:app --host "$${BACKEND_HOST:-127.0.0.1}" --port 8001 --reload

start-frontend:
	@echo "🚀 Frontend starten op poort 3000..."
	cd frontend && yarn start

start-all:
	@echo "🚀 Backend en frontend starten..."
	@echo "Terminal 1: Backend (Ctrl+C om te stoppen)"
	@echo "Terminal 2: Frontend (Ctrl+C om te stoppen)"
	@echo "Open een tweede terminal en voer 'make start-frontend' uit."
	make start-backend

# ---------------------------------------------------------------------------
# Testen
# ---------------------------------------------------------------------------

test-backend:
	@echo "🧪 Backend tests uitvoeren..."
	cd backend && .venv/bin/pytest -v

test-frontend:
	@echo "🧪 Frontend tests uitvoeren..."
	cd frontend && yarn test --watchAll=false

test: test-backend

# ---------------------------------------------------------------------------
# Status & Hulpprogramma's
# ---------------------------------------------------------------------------

check-status:
	@echo "=== Status controle ==="
	@echo ""
	@echo "MongoDB:"; \
	if brew services list | grep -q mongodb-community; then \
		echo "  ✅ MongoDB draait"; \
	else \
		echo "  ❌ MongoDB draait niet"; \
	fi
	@echo ""
	@echo "Backend (poort 8001):"
	@curl -s http://localhost:8001/api/ >/dev/null 2>&1 && echo "  ✅ Backend bereikbaar" || echo "  ❌ Backend niet bereikbaar"
	@echo ""
	@echo "Frontend (poort 3000):"
	@curl -s http://localhost:3000 >/dev/null 2>&1 && echo "  ✅ Frontend bereikbaar" || echo "  ❌ Frontend niet bereikbaar"
	@echo ""
	@echo "LM Studio (poort 1234):"
	@curl -s http://localhost:1234/v1/models >/dev/null 2>&1 && echo "  ✅ LM Studio bereikbaar" || echo "  ⚠️  LM Studio niet bereikbaar (optioneel)"

reset-demo:
	@echo "🗑️  Demo-data verwijderen en opnieuw seeden..."
	@echo "MongoDB leegmaken en backend herstarten voor opnieuw seeden."
	@echo "Voer uit:"
	@echo "  mongosh mac_studio_zoeker --eval \"db.dropDatabase()\""
	@echo "  # Herstart dan de backend"

clean:
	@echo "🧹 Opruimen..."
	rm -rf backend/.venv
	find frontend -name "node_modules" -type d -prune -exec rm -rf {} + 2>/dev/null || true
	find frontend -name "build" -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Opgeschoond. Voer 'make install-all' opnieuw uit."
