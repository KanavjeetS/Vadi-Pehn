# Original User Request

## 2026-07-24T04:34:46Z

# Teamwork Project Prompt — Vadi-Pehn 10/10 Production MVP Refinement

Vadi-Pehn is a virtual sibling-mentor platform (ages 8-17) built with fail-closed safety (`NeMo Guardrails`), multi-role JWT authentication, Supabase pgvector RAG, and ElevenLabs/Groq voice synthesis. Based on the independent audit report (Score 6/10 Production Readiness, 8/10 Engineering Quality), this task bridges the gap between strong backend architecture and a 10/10 production-ready, deployable MVP.

Working directory: `d:\Vadi Bhen`  
Integrity mode: **development**

---

## 🎯 Priority Execution Roadmap

The team must execute work in the strict priority order established by the audit:

1. **Fix Orphaned Migration `007_dlq_and_agents.sql`** (Data Integrity)
2. **Canonicalize & Verify Deployment Story** (Infra & DevOps)
3. **Connect Child Companion UI to Real Voice Pipeline** (Core Product UX)
4. **Wire Real Database Data into Guardian Dashboard Charts** (Governance UI)
5. **Verify Fine-Tuning Execution & CI Security Scanning** (AI & Security)

---

## Requirements

### R1. Fix Database Migration Continuity (Priority 1)
- Move `packages/db-schema/migrations/007_dlq_and_agents.sql` into `db/migrations/007_dlq_and_agents.sql`.
- Verify that `db/migrations/` executes cleanly in order (`001` through `008`) without missing tables or foreign key errors.
- Ensure all dead letter queue (DLQ) and agent tracking schemas from migration 007 are active and accessible to services.

### R2. Canonicalize & Document Deployment Paths (Priority 2)
- Establish **`start_desktop.py`** (`.\vadi.ps1 dev`) as the official canonical local single-process development launcher.
- Establish **`docker-compose.yml`** (`.\vadi.ps1 docker-up` / `docker compose up`) as the official canonical production stack.
- Consolidate, remove, or clearly mark redundant compose files (`infra/docker-compose.dev.yml`, `infra/docker-compose.mvp.yml`, unused k8s stubs) to eliminate deployment ambiguity.
- Verify `docker compose up` brings up all 9 services + webapp nginx cleanly with 100% passing health checks.

### R3. Real-Time Voice Pipeline Integration in Child UI (Priority 3)
- Upgrade `webapp/child/child.js` to communicate directly with `/api/v1/voice/turn` and `services/voice-gateway`.
- Connect low-latency streaming audio / voice responses to drive Vadi avatar animation states seamlessly (`idle` → `listening` → `thinking` → `speaking`).
- Implement barge-in handling and live canvas audio waveform visualization during TTS playback.
- Maintain strict fail-closed safety checking (`check_input_safety` and `check_output_safety`) on all voice turns.

### R4. Real Guardian Dashboard Metrics & Charts (Priority 4)
- Remove all hardcoded fake data arrays (`[18, 24, 12...]`, static doughnut percentages) in `webapp/guardian/guardian.js`.
- Wire `fetchGuardianOverview()` directly to `/api/v1/guardian/overview` so session trends, incident timelines, and topic distributions render real database rows.
- Ensure charts gracefully reflect empty/seeded data states and update dynamically when a child completes new conversation turns.

### R5. Fine-Tuning Verification & CI Hardening (Priority 5)
- Verify `NanochatSFTTrainer` execution on the scaled 624-example dataset (`scripts/corpus/data/train.jsonl` and `val.jsonl`), ensuring loss convergence and 100% safety compliance on evaluation replays.
- Replace the single stray `print()` statement in `services/orchestration/src/orchestration/graph.py:645` with structured JSON logging (`logger.info`).
- Add dependency vulnerability scanning (`pip-audit`) to `.github/workflows/ci.yml`.

---

## Acceptance Criteria

### Data & Migration Continuity
- [ ] `db/migrations/` contains unbroken sequence 001 to 008, including `007_dlq_and_agents.sql`.
- [ ] Running all migrations against a fresh PostgreSQL instance succeeds without errors.

### Deployment & Infra
- [ ] `.\vadi.ps1 dev` launches local single-process desktop server cleanly on `http://127.0.0.1:8080`.
- [ ] `docker compose up` / `.\vadi.ps1 docker-up` starts full stack on `http://localhost:80` with all 9 microservices reporting healthy status.
- [ ] Redundant compose files in `infra/` are archived or aligned with root `docker-compose.yml`.

### Voice & Child Experience
- [ ] Child UI (`/child/`) connects to `services/voice-gateway` and plays streaming voice output.
- [ ] Vadi avatar state transitions dynamically through `idle`, `listening`, `thinking`, and `speaking` during voice interactions.
- [ ] Live canvas waveform visualizer animates in sync with audio output.

### Guardian Dashboard
- [ ] `guardian.js` has zero hardcoded metric/chart arrays; all charts render data returned by `/api/v1/guardian/overview`.
- [ ] Completing new turns in `/child/` updates session counts and engagement metrics on `/guardian/`.

### AI & Code Quality
- [ ] No stray `print()` calls in production Python code under `services/`.
- [ ] CI workflow runs `ruff`, `black`, `mypy`, `pytest`, and `pip-audit`.
- [ ] All safety keyword tests (`pytest tests/test_safety_keywords.py`) and diversity tests (`scratch/test_diversity.py`) pass 100%.
