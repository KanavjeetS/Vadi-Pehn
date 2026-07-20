# Vadi-Pehn Platform Monorepo

> **Virtual Sibling-Mentor Companion for Under-Resourced Youth** (PRD v2.0 Governance-Hardened Architecture)

---

## 🌟 Executive Overview

**Vadi-Pehn** ("elder sibling") is an agentic AI mentorship platform designed for youth aged 8–17 in under-resourced communities. It combines a warm, relational-safety-conscious elder sibling AI mentor with a multi-agent career exploration panel, an olmOCR document ingestion pipeline, an airtight fail-closed safety proxy, and a separate guardian governance console.

---

## 🚀 One-Click Quick Start (Desktop)

Launch the complete application server on your desktop with one command:

```powershell
py -3 start_desktop.py
```

This starts the unified FastAPI server on `http://127.0.0.1:8000` and automatically opens:
- **Platform Landing Portal**: `http://127.0.0.1:8000/`
- **Child Companion Application**: `http://127.0.0.1:8000/child/`
- **Guardian Governance Console**: `http://127.0.0.1:8000/guardian/`

---

## 🏗️ Architecture & Microservices

| Service | Path | Description | Key Specs |
|---|---|---|---|
| **API Gateway** | `services/api-gateway/` | Unified entry point with signed role-scoped JWT auth (`guardian` vs `learner`) | PRD §3.2, §13 |
| **Voice Gateway** | `services/voice-gateway/` | LiveKit + Silero VAD + Whisper STT + Kokoro TTS sentence-boundary streaming pipeline | PRD §6, SD §5.2 |
| **Safety Proxy** | `services/safety-proxy/` | NeMo Guardrails reverse proxy (3.0s fail-closed classifier timeout) | PRD §8, SD §4.3 |
| **Orchestration** | `services/orchestration/` | LangGraph session turn graph with session turn caps & AI disclosures | SD §5.1, PRD §5 |
| **Panel Service** | `services/panel-service/` | CrewAI multi-agent career panel + versioned Jinja2 speaking mentor personas | PRD §5.1, SD §4.4 |
| **Memory Service** | `services/memory-service/` | Postgres/pgvector/RLS hybrid RAG store (Dense + Sparse BM25 + RRF + Reranker) | SD §3.2, §7.1 |
| **Governance Service** | `services/governance-service/` | Consent Ledger, 15-min SLA Incident Queue, data retention bus | PRD §3, SD §3.4 |
| **Ingestion Service** | `services/ingestion-service/` | MinIO + spatial PII redaction + secondary mask verification + olmOCR | PRD §9 |
| **Dashboard BFF** | `services/dashboard-bff/` | Guardian dashboard backend-for-frontend with Relationship Health metrics | PRD §11 |

---

## 🛡️ Child Safety & Security Invariants

1. **Fail-Closed Safety Proxy**: Any classifier timeout (> 3.0s) or network error produces a `classifier_unavailable` verdict that **blocks generation** and routes to manual review queue.
2. **Cryptographic Role Separation**: Server-side signed JWT tokens enforce role permissions (`guardian` vs `learner`). Learner tokens attempting to reach guardian endpoints receive `403 Forbidden`.
3. **Zero Voice Audio Retention**: Raw audio byte buffers are transcribed and immediately zeroed/purged from memory (PRD §3.4).
4. **Mandatory Row Level Security (RLS)**: Database transactions set `SET LOCAL app.current_tenant_id = $1` inside transactions.
5. **Separated Governance DB**: Governance database instance is physically separate from Memory DB.

---

## 🧪 Testing & Verification

Run the complete workspace pytest test suite:

```bash
py -3 -m pytest
```

**Test Status**: **89 passed, 0 failed** across all 23 test suites (100% pass rate).
