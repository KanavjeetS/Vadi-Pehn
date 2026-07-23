## 2026-07-22T05:41:30Z
You are worker_m4_1, a specialist worker (@backend-engineer & @data-engineer) for Milestone 4 (Guardian Governance Portal & Startup Synthetic Data Seeding — Requirement R4).
Your working directory is `d:\Vadi Bhen\.agents\worker_m4_1`.

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Task Scope & Requirements:
1. Startup Synthetic Data Seeding:
   - Create `db/seed_synthetic_data.py` (or integrated startup seeder) that seeds synthetic PRD-compliant test data.
   - Seed default tenant (`00000000-0000-0000-0000-000000000001`), default guardian (`00000000-0000-0000-0000-000000000002`), default learner (`00000000-0000-0000-0000-000000000003` - 'Aria'), synthetic 1536-dim vector memories, active consent records (`conversation_storage`, `document_ingestion`, `voice_recording`), and safety incidents with 15-minute SLA tracking (`sla_deadline`).
   - Call this seeder cleanly on startup in `start_desktop.py` (or during database initialization) so that when `py -3 start_desktop.py` runs, the database is pre-populated with rich data for default tenant/guardian.
2. Guardian Governance Portal (`webapp/guardian/index.html` & `webapp/guardian/guardian.js`):
   - Remove static mock values / hardcoded strings.
   - Fix DOM selector bug in `webapp/guardian/index.html` line 828 (change `document.querySelectorAll('.stat-card h3')` to `document.querySelectorAll('.stat-card .stat-val')` or bind elements cleanly by ID).
   - Enrich `services/dashboard-bff/src/dashboard_bff/main.py` endpoint `GET /api/v1/guardian/overview` if necessary to return accurate streak, engagement hours, consent status, and safety incidents.
   - Ensure consent toggles (`conversation_storage`, `document_ingestion`, `voice_recording`) and incident resolution APIs call governance endpoints properly.
3. Build & Test:
   - Run `pytest services/dashboard-bff/tests/` using run_command.
   - Verify seeding script runs without errors.
   - Document all changes and test outputs in `d:\Vadi Bhen\.agents\worker_m4_1\handoff.md`.
