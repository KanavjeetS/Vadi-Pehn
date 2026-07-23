# Vadi-Pehn — Virtual Sibling-Mentor Platform

> An AI-powered companion for underserved children in India — voice-first, bilingual (Hindi/English), with parent-controlled consent and child-safety guardrails.

---

## 🗺️ Architecture Overview

```
Browser (webapp/nginx)
    │
    ▼
[Nginx :80]  ──→  /api/*  ──→  [API Gateway :8000]
    │                                  │
    ├── /child/      (Child companion)  ├── /internal/v1/orchestration/turn  →  [Orchestration]
    ├── /guardian/   (Parent portal)    ├── /internal/v1/voice/turn           →  [Voice Gateway]
    └── /admin/      (Admin dashboard)  └── /internal/v1/governance/consent   →  [Governance]

Services (all talk to each other via Docker network):
  orchestration  →  safety-proxy → [Llama Guard / dev-bypass]
               →  memory-service → [Supabase pgvector, RLS-scoped]
  voice-gateway  →  [ElevenLabs TTS / Groq Whisper STT]
  governance     →  [Separate Postgres / Supabase instance]
  dashboard-bff  →  [Memory + Governance DBs for overview APIs]
```

---

## 🚀 Quick Start — Local Development (Recommended)

**Single-process mode** — all 9 services run in one Python process. No Docker needed.

### Prerequisites
- Python 3.10+
- A `.env` file (see below)

### 1. Set up environment
```powershell
copy .env.example .env
# Edit .env and fill in your API keys (minimum: GROQ_API_KEY, ELEVENLABS_API_KEY)
```

### 2. Install dependencies
```powershell
pip install -r requirements.txt   # or: pip install fastapi uvicorn httpx asyncpg pydantic pydantic-settings jinja2 langgraph langchain-core langfuse groq httpx
```

### 3. Start the server
```powershell
py start_desktop.py
# or: make dev
```

### 4. Open in browser
| Portal | URL |
|---|---|
| 🏠 Landing page | http://localhost:8080 |
| 👧 Child companion | http://localhost:8080/child/ |
| 🛡️ Guardian dashboard | http://localhost:8080/guardian/ |
| ⚙️ Admin observability | http://localhost:8080/admin/ |
| 🔑 Login | http://localhost:8080/login.html |

### 5. One-click demo login
On the login page, click **Demo: Child**, **Demo: Guardian**, or **Demo: Admin** — no signup required.

---

## 🐳 Docker Deployment (Production MVP)

### Prerequisites
- Docker + Docker Compose v2
- A configured `.env` file with all required keys

### 1. Configure environment
```powershell
Copy-Item .env.example .env
# Edit .env — set ENVIRONMENT=production, fill DB credentials and API keys
```

### 2. Build and start
```powershell
# Windows (PowerShell):
.\vadi.ps1 docker-build    # Build all 9 Docker images (parallel)
.\vadi.ps1 docker-up       # Start the full stack detached

# Direct Docker commands (any OS):
docker compose build --parallel
docker compose up -d

# Linux/macOS (Make):
make docker-build
make docker-up
```

### 3. Access the app
| Portal | URL |
|---|---|
| 🌐 Full webapp (nginx) | http://localhost |
| 🔌 API Gateway | http://localhost:8000 |
| 📊 Orchestration | http://localhost:8001 |
| 🛡️ Safety Proxy | http://localhost:8002 |

### 4. Check health
```powershell
.\vadi.ps1 health-docker   # Show Docker container status
.\vadi.ps1 health          # Check all /health endpoints
```

### 5. View logs
```powershell
.\vadi.ps1 docker-logs     # All services
docker compose logs -f api-gateway   # Single service
```

---

## 🔑 Required API Keys

| Key | Where to get | Used for |
|---|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | LLM (Llama 3.3-70B) + Whisper STT |
| `ELEVENLABS_API_KEY` | [elevenlabs.io](https://elevenlabs.io) | Indian female TTS voice |
| `MEMORY_DB_DSN` | [supabase.com](https://supabase.com) | pgvector memory store |
| `GOVERNANCE_DB_DSN` | Second Supabase project | Consent ledger (separate DB per PRD) |

All other keys (LiveKit, NVIDIA, Langfuse) are optional for the MVP.

---

## 🧪 Testing

```bash
make test            # Full pytest suite (target: 184+ tests)
make test-safety     # Safety keyword regression (Hinglish + English)
make test-e2e        # Live end-to-end conversation turn
make test-diversity  # Response uniqueness check (5/5)
```

---

## 🗂️ Project Structure

```
Vadi Bhen/
├── webapp/                     # Static frontend
│   ├── index.html              # Landing page
│   ├── login.html              # Multi-role auth (demo buttons)
│   ├── signup.html             # Registration flow
│   ├── child/                  # Child companion SPA
│   ├── guardian/               # Guardian dashboard SPA
│   └── admin/                  # Admin observability SPA
│
├── services/
│   ├── api-gateway/            # Auth, rate limiting, routing
│   ├── orchestration/          # LangGraph AI pipeline
│   ├── safety-proxy/           # NeMo Guardrails (fail-closed)
│   ├── memory-service/         # pgvector RAG + RLS
│   ├── governance-service/     # Consent Ledger
│   ├── panel-service/          # Career mentor personas
│   ├── dashboard-bff/          # Guardian + Admin BFF
│   ├── voice-gateway/          # ElevenLabs TTS / Whisper STT
│   └── ingestion-service/      # Document OCR pipeline
│
├── db/
│   ├── migrations/             # PostgreSQL migration files
│   └── seed_synthetic_data.py  # Demo data seeder
│
├── docker-compose.yml          # Production stack
├── nginx.conf                  # Static webapp + API proxy
├── start_desktop.py            # Single-process dev server
├── Makefile                    # All dev/deploy commands
├── .env.example                # Environment variable template
└── PRD.md / SystemDesign.md    # Product & architecture spec
```

---

## 🛡️ Safety Architecture

Vadi-Pehn is built **fail-closed** for child safety:

- **Safety Proxy**: Every LLM input and output passes through a Llama Guard 3 classifier
- **Pre-filter**: Keyword blocklist for self-harm (English + Hinglish) fires before the LLM
- **3-second timeout**: If the classifier is unavailable, the turn is blocked (not allowed through)
- **Dev bypass**: `SAFETY_PROXY_ALLOW_DEV_BYPASS=true` is only applied at the HTTP layer in `main.py` — `actions.py` remains strictly fail-closed
- **RLS**: Every database query is scoped by `tenant_id` via `SET LOCAL app.current_tenant_id`

> ⚠️ **Production rule**: Set `SAFETY_PROXY_ALLOW_DEV_BYPASS=false` and `ENVIRONMENT=production` before any real-world deployment.

---

## 🌐 Deployment Checklist

Before going live:

- [ ] `ENVIRONMENT=production` in `.env`
- [ ] `SAFETY_PROXY_ALLOW_DEV_BYPASS=false`
- [ ] Strong random `JWT_SECRET_KEY` (32+ chars)
- [ ] Strong random `INTERNAL_SERVICE_TOKEN`
- [ ] `CORS_ALLOWED_ORIGINS` set to your real domain(s)
- [ ] Supabase pgvector extensions enabled (`CREATE EXTENSION vector; CREATE EXTENSION pg_trgm;`)
- [ ] DB migrations applied (`db/migrations/*.sql`)
- [ ] `GROQ_API_KEY` and `ELEVENLABS_API_KEY` set
- [ ] Docker images built and health-checked: `make docker-up && make health-docker`

---

## 👥 Team & Personas

Built by an 11-division engineering team following the `AGENTS.md` constitution:
`@architect` · `@backend-engineer` · `@voice-engineer` · `@safety-engineer` · `@data-engineer` · `@qa-auditor` · `@devops` · `@researcher` · `@doc-keeper`
