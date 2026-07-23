# Project: Vadi-Pehn Platform Execution

## Architecture
Vadi-Pehn is a 9-microservice virtual sibling-mentor platform:
- `api_gateway`: Entry router for web & mobile clients.
- `dashboard_bff`: Backend-for-Frontend serving Guardian and Admin web clients.
- `orchestration`: LangGraph engine executing turn pipeline (`check_input_safety` -> `retrieve_memory` -> `generate_reply` -> `check_output_safety` -> `write_memory`).
- `voice_gateway`: Audio streaming, VAD (Silero), STT (Whisper), TTS (Kokoro/ElevenLabs Indian female voice profile).
- `governance`: Consent Ledger, Safety Incident Queue (15-min SLA), Governance Postgres DB.
- `panel`: CrewAI multi-agent career panel & diversity matching.
- `safety_proxy`: NeMo Guardrails fail-closed safety proxy.
- `ingestion`: Document OCR (olmOCR) and PII redaction pipeline.
- `memory_service`: Supabase pgvector Postgres memory store with RLS tenant isolation.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Backend Route Mounting & Internal Connectivity | Fix sub-app route mounting in `start_desktop.py`, ensure internal connectivity across 9 services | None | DONE |
| 2 | Multi-Role Authentication System | Implement `/login.html`, `/signup.html`, learner/guardian/admin roles, one-click Demo buttons, localStorage JWTs | M1 | DONE |
| 3 | Child Companion Portal & Voice Synthesis | `/child/` UI, ElevenLabs/Kokoro Indian female voice, particle/typing animations, audio visualizer, AI identity disclosure | M1, M2 | DONE |
| 4 | Guardian Governance Portal & Synthetic Data Seeding | `/guardian/` UI, `/api/v1/guardian/overview`, startup synthetic data seeding, streak/engagement/consent/incidents | M1, M2 | DONE |
| 5 | Admin Observability & Native Tracing Dashboard | `/admin/` UI, `/api/v1/admin/overview`, remove port 3000 iframe, native interactive charts | M1, M2 | DONE |
| 6 | PRD Compliance & Memory RAG Verification | E2E verification of turn execution, embedding creation in `learner_memories`, memory retrieval in follow-up turns | M1-M5 | DONE |

## Interface Contracts
### Internal Service Routes (`start_desktop.py`)
- `POST /internal/v1/orchestration/turn` -> Orchestration service turn endpoint
- `POST /internal/v1/voice/turn` -> Voice gateway audio/turn endpoint
- `POST /internal/v1/governance/consent/{learner_id}` -> Governance consent management
- `POST /internal/v1/safety/check-input` -> Safety proxy input check (verdict: safe|unsafe_self_harm|unsafe_general|classifier_unavailable)
- `POST /internal/v1/safety/check-output` -> Safety proxy output check
- `GET /api/v1/guardian/overview` -> Guardian BFF overview metrics
- `GET /api/v1/admin/overview` -> Admin BFF metrics & telemetry

## Code Layout
```
d:\Vadi Bhen\
├── start_desktop.py          ← Single-process desktop entry point
├── services/
│   ├── api-gateway/
│   ├── orchestration/
│   ├── voice-gateway/
│   ├── safety-proxy/
│   ├── panel-service/
│   ├── memory-service/
│   ├── governance-service/
│   ├── ingestion-service/
│   └── dashboard-bff/
├── webapp/                   ← Static web UI & web apps
│   ├── child/
│   ├── guardian/
│   ├── admin/
│   ├── login.html
│   └── signup.html
└── db/
```
