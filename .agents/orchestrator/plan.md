# 10/10 Production MVP Refinement Plan

## Execution Milestones

### Milestone 1: Fix Orphaned Migration `007_dlq_and_agents.sql` (Data Integrity)
- Move `packages/db-schema/migrations/007_dlq_and_agents.sql` into `db/migrations/007_dlq_and_agents.sql`.
- Ensure migrations `001` through `008` execute cleanly in sequential order without FK/table errors.
- Verify DLQ and agent tracking tables/schemas are active and accessible.
- Verification Gate: Worker execution & test run -> Reviewer verification -> Forensic Auditor audit.

### Milestone 2: Canonicalize & Verify Deployment Story (Infra & DevOps)
- Establish `start_desktop.py` (`.\vadi.ps1 dev`) as canonical local single-process launcher.
- Establish `docker-compose.yml` (`.\vadi.ps1 docker-up` / `docker compose up`) as canonical production stack.
- Consolidate / remove / clearly mark redundant compose files (`infra/docker-compose.dev.yml`, `infra/docker-compose.mvp.yml`, unused k8s stubs).
- Verify `docker compose up` brings up all 9 services + webapp nginx cleanly with 100% passing health checks.
- Verification Gate: Worker implementation -> Reviewer verification -> Forensic Auditor audit.

### Milestone 3: Connect Child Companion UI to Real Voice Pipeline (Core Product UX)
- Upgrade `webapp/child/child.js` to communicate directly with `/api/v1/voice/turn` and `services/voice-gateway`.
- Connect low-latency streaming audio / voice responses to drive Vadi avatar animation states (`idle` -> `listening` -> `thinking` -> `speaking`).
- Implement barge-in handling and live canvas audio waveform visualization during TTS playback.
- Maintain strict fail-closed safety checking (`check_input_safety` and `check_output_safety`) on all voice turns.
- Verification Gate: Worker implementation -> Reviewer verification -> Challenger stress test -> Forensic Auditor audit.

### Milestone 4: Wire Real Database Data into Guardian Dashboard Charts (Governance UI)
- Remove all hardcoded fake data arrays in `webapp/guardian/guardian.js`.
- Wire `fetchGuardianOverview()` directly to `/api/v1/guardian/overview` so session trends, incident timelines, topic distributions render real database rows.
- Ensure charts reflect empty/seeded data states and update dynamically when a child completes new turns.
- Verification Gate: Worker implementation -> Reviewer verification -> Challenger stress test -> Forensic Auditor audit.

### Milestone 5: Verify Fine-Tuning Execution & CI Security Scanning (AI & Security)
- Verify `NanochatSFTTrainer` execution on scaled 624-example dataset (`scripts/corpus/data/train.jsonl` and `val.jsonl`), ensuring loss convergence and safety compliance.
- Replace stray `print()` statement in `services/orchestration/src/orchestration/graph.py:645` with structured JSON logging (`logger.info`).
- Add dependency vulnerability scanning (`pip-audit`) to `.github/workflows/ci.yml`.
- Verify full test suite passes (safety keywords `test_safety_keywords.py` and diversity `scratch/test_diversity.py`).
- Verification Gate: Worker implementation -> Reviewer verification -> Challenger stress test -> Forensic Auditor audit.
