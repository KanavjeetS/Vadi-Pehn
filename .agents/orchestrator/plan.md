# Vadi-Pehn Full MVP Refinement — 11-Division Execution Plan

## Overview
This plan decomposes the 11-Division Engineering Execution into 5 sequential, verifiable milestones designed to refine Vadi-Pehn into a production-grade virtual sibling-mentor platform.

## Milestones & Division Mapping

### Milestone 1: Data Engineering & Security (Divisions 1 & 5)
- **Division 1 (Data Engineering)**:
  - Verify DB schemas & Supabase pgvector setup (`learner_memories`, `learner_interest_profile`).
  - Ensure RLS policies with `SET LOCAL app.current_tenant_id = $1` in transactions.
  - Verify separation of Governance DB and Memory DB.
- **Division 5 (Security)**:
  - Auth hardening & Demo account authentication (`POST /api/v1/auth/demo` with role=learner/guardian/admin returning valid JWTs).
  - Secure JWT validation & tenant/role scoping.

### Milestone 2: Backend Engineering & Infrastructure/DevOps (Divisions 2 & 7)
- **Division 2 (Backend Engineering)**:
  - Hardening API Gateway, Governance Service, and Dashboard BFF.
  - Wire `GET /api/v1/guardian/overview` and `GET /api/v1/admin/overview` to query real Supabase/DB tables (no static zero stubs).
  - Add `X-Request-ID` header to all API responses for OpenTelemetry tracing.
  - Rate limiting verification.
- **Division 7 (Infrastructure / DevOps)**:
  - `docker-compose.yml` at repo root referencing all 9 microservices with healthchecks and `.env`.
  - `.env.example` at repo root with placeholder values and inline documentation.
  - `Makefile` with targets: `make dev`, `make docker-up`, `make docker-down`, `make test`, `make lint`.
  - `services/logging_config.py` module with structured JSON logging, initialized in `start_desktop.py` and all service `main.py` entry points.

### Milestone 3: AI Safety & AI Platform (Divisions 3 & 4)
- **Division 4 (AI Safety)**:
  - Add Hinglish self-harm keywords (`"marna chahta"`, `"marna chahti"`, `"jeena nahi chahta"`, `"khatam karna chahta"`, `"khud ko hurt"`) to `SELF_HARM_KEYWORDS` in `actions.py`.
  - Preserve `classify_input` and `classify_output` dev bypass logic (`SAFETY_PROXY_ALLOW_DEV_BYPASS=true`).
  - Verify safety deflection for prompt injections (`"ignore previous instructions"`) and fixed escalation for self-harm (`"kill myself"`).
- **Division 3 (AI Platform)**:
  - Memory Writes: Ensure `AsyncMemoryWriter.write_memory_async()` saves turns to `learner_memories` (with consent check defaulting to True in dev).
  - Memory Reads: Implement `LIMIT 5` recency-based fallback in `retrieve_memory` when vector embedding client is unavailable.
  - Persona Template Rendering: Verify `sibling.jinja2` system prompt rendering.
  - Career Panel Integration: Dynamically load matching persona `.jinja2` template when `panel_triggered=True`.

### Milestone 4: Frontend Engineering, Product & UX, Design & Brand (Divisions 6, 9, 11)
- **Division 6, 9, 11 (Frontend & Design)**:
  - `webapp/login.html`: Glassmorphism card, animated gradient background, smooth sliding role tabs, one-click demo login buttons, form validation.
  - `webapp/signup.html`: Matching design, multi-step wizard, password strength meter, guardian linking code.
  - `webapp/child/index.html` + `child.js`:
    - Vadi avatar character with idle, listening, speaking states (CSS/Lottie animations).
    - Staggered slide-in chat bubbles.
    - Live audio waveform visualizer (Web Audio API / Canvas) during TTS playback.
    - XP progress bar, streak counter, level badge.
    - Mood emoji chips & topic chips.
    - Floating background particles & dark mode toggle.
    - Voice recording pulsing visualizer.
  - `webapp/guardian/index.html` + `guardian.js`:
    - Real session & incident metrics from `/api/v1/guardian/overview`.
    - Interactive Chart.js line chart & topic donut chart.
    - Safety incident timeline with 15-min SLA tracking.
    - Consent toggle switches.
  - `webapp/admin/index.html` + `admin.js`:
    - Real metrics from `/api/v1/admin/overview`.
    - KPI metric cards with counter animations.
    - Groq LLM status badge & recent incidents table.

### Milestone 5: QA & Testing (Division 8 & Final Validation)
- **Division 8 (QA & Testing)**:
  - Safety Keyword Test Suite (`tests/test_safety_keywords.py` with 20 fixed pairs).
  - Fix any failing existing tests (`pytest services/`). Target: 100% pass rate.
  - Verify E2E turn test (`scratch/test_e2e_turn.py`).
  - Verify Diversity test (`scratch/test_diversity.py` 5/5 unique responses).
  - Final full-suite verification & Forensic Audit.

## Verification Gate per Milestone
Each milestone must pass:
1. Worker implementation report with build & test verification logs.
2. Reviewer / Challenger pass verdict.
3. Forensic Auditor CLEAN verdict (Zero-Tolerance Binary Veto).
