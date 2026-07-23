## 2026-07-22T15:26:27Z
You are worker_m4_3, a specialist worker (@data-engineer & @backend-engineer) fixing RLS tenant isolation issues identified by Challenger M4 in `db/seed_synthetic_data.py`.
Your working directory is `d:\Vadi Bhen\.agents\worker_m4_3`.

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Specific Issues to Fix in `db/seed_synthetic_data.py`:
1. Move `await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_id))` to the VERY START of the transaction in `seed_memory_db()`, BEFORE inserting into `tenants`, `guardians`, `learners`, `learner_memories`, and `learner_interest_profile`.
2. Add `await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_id))` at the VERY START of the transaction in `seed_governance_db()`, BEFORE inserting into `consent_records` and `safety_incidents`.

Build & Verify:
- Run `py -3 db/seed_synthetic_data.py` to confirm seeding succeeds.
- Run `pytest services/dashboard-bff/tests/` and `pytest services/governance-service/tests/`.
- Document all changes and verification in `d:\Vadi Bhen\.agents\worker_m4_3\handoff.md`.
