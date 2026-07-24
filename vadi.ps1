<#
.SYNOPSIS
  Vadi-Pehn — PowerShell task runner (Windows equivalent of Makefile).
  Usage: .\vadi.ps1 <target>
  Run   .\vadi.ps1 help  to see all targets.
#>
param([string]$Target = "help")

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Write-Green  { param($msg) Write-Host $msg -ForegroundColor Green }
function Write-Yellow { param($msg) Write-Host $msg -ForegroundColor Yellow }
function Write-Cyan   { param($msg) Write-Host $msg -ForegroundColor Cyan }
function Write-Red    { param($msg) Write-Host $msg -ForegroundColor Red }

switch ($Target) {

  # ── Local single-process development ──────────────────────────────────────
  "dev" {
    Write-Green "Starting Vadi-Pehn Desktop Dev Server..."
    py "$Root\start_desktop.py"
  }

  # ── Docker: build all images ───────────────────────────────────────────────
  "docker-build" {
    Write-Green "Building all Docker images (parallel)..."
    docker compose -f "$Root\docker-compose.yml" build --parallel
  }

  # ── Docker: start full stack ───────────────────────────────────────────────
  "docker-up" {
    Write-Green "Starting Vadi-Pehn full stack in Docker..."
    docker compose -f "$Root\docker-compose.yml" up -d
    Write-Cyan ""
    Write-Cyan "Stack started:"
    Write-Cyan "  Webapp (nginx)    : http://localhost"
    Write-Cyan "  API Gateway       : http://localhost:8000"
    Write-Cyan "  Orchestration     : http://localhost:8001"
    Write-Cyan "  Safety Proxy      : http://localhost:8002"
    Write-Cyan "  Memory Service    : http://localhost:8003"
    Write-Cyan "  Governance        : http://localhost:8004"
    Write-Cyan "  Voice Gateway     : http://localhost:8008"
  }

  # ── Docker: stop stack ─────────────────────────────────────────────────────
  "docker-down" {
    Write-Yellow "Stopping Vadi-Pehn Docker stack..."
    docker compose -f "$Root\docker-compose.yml" down
  }

  # ── Docker: tail logs ─────────────────────────────────────────────────────
  "docker-logs" {
    docker compose -f "$Root\docker-compose.yml" logs -f --tail=100
  }

  # ── Docker: show container status ─────────────────────────────────────────
  "docker-ps" {
    docker compose -f "$Root\docker-compose.yml" ps
  }

  # ── Docker: clean everything ───────────────────────────────────────────────
  "docker-clean" {
    Write-Yellow "Removing containers, volumes, and local images..."
    docker compose -f "$Root\docker-compose.yml" down -v --rmi local
    docker system prune -f
  }

  # ── Docker: restart one service (usage: .\vadi.ps1 restart api-gateway) ───
  "restart" {
    $svc = $args[0]
    if (-not $svc) { Write-Red "Usage: .\vadi.ps1 restart <service-name>"; exit 1 }
    docker compose -f "$Root\docker-compose.yml" restart $svc
  }

  # ── Test suite ─────────────────────────────────────────────────────────────
  "check" {
    Write-Green "Running deployment canonicalization & stack validation checks..."
    py -m pytest "$Root\tests\test_deployment_canonicalization.py" -v
  }

  "test" {
    Write-Green "Running full test suite..."
    py -m pytest "$Root\services" "$Root\tests" -x -q --tb=short
  }

  "test-safety" {
    Write-Green "Running safety keyword regression tests..."
    py -m pytest "$Root\tests\test_safety_keywords.py" -v
  }

  "test-e2e" {
    Write-Green "Running E2E turn smoke test..."
    py -X utf8 "$Root\scratch\test_e2e_turn.py"
  }

  "test-diversity" {
    Write-Green "Running response diversity check..."
    py -X utf8 "$Root\scratch\test_diversity.py"
  }

  # ── Seed synthetic data ────────────────────────────────────────────────────
  "seed" {
    Write-Green "Seeding synthetic data..."
    py "$Root\db\seed_synthetic_data.py"
  }

  # ── Health checks ──────────────────────────────────────────────────────────
  "health" {
    Write-Cyan "Checking service health (local dev on :8080)..."
    $checks = @(
      @{name="api-gateway";    url="http://localhost:8080/healthz"},
      @{name="orchestration";  url="http://localhost:8080/health"},
      @{name="safety-proxy";   url="http://localhost:8080/health"}
    )
    foreach ($c in $checks) {
      try {
        $r = Invoke-WebRequest $c.url -UseBasicParsing -TimeoutSec 3
        Write-Green "  OK  $($c.name) ($($r.StatusCode))"
      } catch {
        Write-Red "  FAIL $($c.name)"
      }
    }
  }

  "health-docker" {
    Write-Cyan "Docker container status:"
    docker compose -f "$Root\docker-compose.yml" ps --format "table {{.Name}}\t{{.Status}}"
  }

  # ── Help ───────────────────────────────────────────────────────────────────
  default {
    Write-Cyan @"

Vadi-Pehn — PowerShell Task Runner
Usage: .\vadi.ps1 <target>

DEVELOPMENT (Canonical single-process launcher)
  dev              Start single-process dev server (http://localhost:8080 via start_desktop.py)

DOCKER (Canonical production stack)
  docker-build     Build all 9 Docker images (parallel)
  docker-up        Start full stack in Docker (http://localhost via root docker-compose.yml)
  docker-down      Stop all containers
  docker-logs      Tail all container logs
  docker-ps        Show container status
  docker-clean     Remove containers, volumes, and images
  restart <svc>    Restart one service (e.g. .\vadi.ps1 restart api-gateway)

TESTING & VALIDATION
  check            Deployment canonicalization & stack validation checks
  test             Full pytest suite
  test-safety      Safety keyword regression tests
  test-e2e         End-to-end conversation turn
  test-diversity   Response diversity check (5/5 unique)

DATABASE
  seed             Seed synthetic demo data

HEALTH
  health           Check /health endpoints (local dev)
  health-docker    Show Docker container status

"@
  }
}
