.PHONY: dev docker-up docker-down docker-build docker-logs docker-clean \
        test lint seed health help

# ── Local single-process development ──────────────────────────────────────────
dev:
	@echo "🚀 Starting Vadi-Pehn Desktop Dev Server..."
	py start_desktop.py

dev-linux:
	python3 start_desktop.py

# ── Docker deployment ──────────────────────────────────────────────────────────
docker-build:
	@echo "🏗️  Building all Docker images..."
	docker compose build --parallel

docker-up:
	@echo "🚀 Starting Vadi-Pehn in Docker..."
	docker compose up -d
	@echo ""
	@echo "✅ Stack started:"
	@echo "   🌐 Webapp (nginx)   : http://localhost"
	@echo "   🔌 API Gateway      : http://localhost:8000"
	@echo "   🤖 Orchestration    : http://localhost:8001"
	@echo "   🛡️  Safety Proxy     : http://localhost:8002"
	@echo "   🧠 Memory Service   : http://localhost:8003"
	@echo "   ⚖️  Governance       : http://localhost:8004"
	@echo "   🎙️  Voice Gateway    : http://localhost:8008"

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f --tail=100

docker-clean:
	docker compose down -v --rmi local
	docker system prune -f

docker-ps:
	docker compose ps

# ── Testing ────────────────────────────────────────────────────────────────────
test:
	@echo "🧪 Running full test suite..."
	py -m pytest services/ tests/ -x -q --tb=short 2>&1 | tail -20

test-safety:
	py -m pytest tests/test_safety_keywords.py -v

test-e2e:
	py -X utf8 scratch/test_e2e_turn.py

test-diversity:
	py -X utf8 scratch/test_diversity.py

# ── Code quality ───────────────────────────────────────────────────────────────
lint:
	ruff check services/ --fix
	black services/ --check

format:
	black services/
	ruff check services/ --fix

# ── Database ───────────────────────────────────────────────────────────────────
migrate:
	@echo "📦 Running DB migrations..."
	@for f in db/migrations/*.sql; do \
		echo "  → $$f"; \
	done
	@echo "Apply migrations manually via psql or Supabase SQL editor."

seed:
	py db/seed_synthetic_data.py

# ── Health checks ──────────────────────────────────────────────────────────────
health:
	@echo "🏥 Checking service health..."
	@curl -sf http://localhost:8000/healthz  && echo "✅ api-gateway" || echo "❌ api-gateway"
	@curl -sf http://localhost:8001/health   && echo "✅ orchestration" || echo "❌ orchestration"
	@curl -sf http://localhost:8002/health   && echo "✅ safety-proxy"  || echo "❌ safety-proxy"
	@curl -sf http://localhost:8003/health   && echo "✅ memory-service" || echo "❌ memory-service"
	@curl -sf http://localhost:8004/health   && echo "✅ governance-service" || echo "❌ governance-service"
	@curl -sf http://localhost:8008/health   && echo "✅ voice-gateway" || echo "❌ voice-gateway"

health-docker:
	docker compose ps --format "table {{.Name}}\t{{.Status}}"

# ── Help ───────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "Vadi-Pehn — Available Makefile targets:"
	@echo ""
	@echo "  DEVELOPMENT"
	@echo "    make dev              Start single-process dev server (Windows)"
	@echo "    make dev-linux        Start single-process dev server (Linux/macOS)"
	@echo ""
	@echo "  DOCKER"
	@echo "    make docker-build     Build all Docker images"
	@echo "    make docker-up        Start full stack in Docker (detached)"
	@echo "    make docker-down      Stop all containers"
	@echo "    make docker-logs      Tail all container logs"
	@echo "    make docker-clean     Remove containers, volumes, and images"
	@echo "    make docker-ps        Show container status"
	@echo ""
	@echo "  TESTING"
	@echo "    make test             Full pytest suite"
	@echo "    make test-safety      Safety keyword regression tests"
	@echo "    make test-e2e         End-to-end conversation turn smoke test"
	@echo "    make test-diversity   Response diversity check (5/5 unique)"
	@echo ""
	@echo "  DATABASE"
	@echo "    make migrate          List pending migrations"
	@echo "    make seed             Seed synthetic data"
	@echo ""
	@echo "  HEALTH"
	@echo "    make health           Check all service health endpoints (local)"
	@echo "    make health-docker    Show Docker container status"
	@echo ""
