# Vadi-Pehn Infrastructure & Deployment Directory

> **CANONICAL LAUNCHERS SUMMARY**:
> - **Local Development (Single-Process Desktop Server)**: Run `.\vadi.ps1 dev` or `python start_desktop.py`
> - **Production Multi-Container Stack (Docker Compose)**: Run `.\vadi.ps1 docker-up` or `docker compose -f docker-compose.yml up -d`

---

## Deployment Architecture Overview

Vadi-Pehn supports two official deployment modes:

### 1. Single-Process Desktop Mode (Local Dev / Desktop App)
- **Launcher**: `start_desktop.py` (Invoked via `.\vadi.ps1 dev`)
- **Port**: `http://localhost:8080`
- **Behavior**: Single Python process using FastAPI mounts for all 9 microservices plus static file mounts for Child (`/child`), Guardian (`/guardian`), and Admin (`/admin`) web applications.
- **Data Stores**: In-memory vector store & synthetic mock databases by default.

### 2. Multi-Container Stack (Production / Pilot Deployment)
- **Launcher**: `docker-compose.yml` at project root (Invoked via `.\vadi.ps1 docker-up`)
- **Port**: `http://localhost` (served via Nginx reverse proxy)
- **Behavior**: 9 containerized FastAPI microservices + Nginx webapp frontend + 2 physically isolated PostgreSQL database instances (`postgres-memory` with pgvector and `postgres-governance`).

---

## Directory Contents & Status

| Path | Status | Purpose / Action |
|---|---|---|
| `../docker-compose.yml` | **CANONICAL** | Primary multi-container production stack definition. |
| `../start_desktop.py` | **CANONICAL** | Primary single-process local development server. |
| `infra/docker-compose.yml` | DEPRECATED | Legacy infra stub. Use root `docker-compose.yml`. |
| `infra/docker-compose.dev.yml` | DEPRECATED | Legacy dev stub. Use `.\vadi.ps1 dev` or root `docker-compose.yml`. |
| `infra/docker-compose.mvp.yml` | DEPRECATED | Legacy pilot stub. Use root `docker-compose.yml`. |
| `infra/k8s/` | EXPERIMENTAL | Enterprise Kubernetes deployment stubs for future cloud hosting. |

---

## Troubleshooting & Utilities

- Check stack health: `.\vadi.ps1 health` (desktop) or `.\vadi.ps1 health-docker` (docker)
- Run deployment validation suite: `.\vadi.ps1 check`
- Full test suite: `.\vadi.ps1 test`
