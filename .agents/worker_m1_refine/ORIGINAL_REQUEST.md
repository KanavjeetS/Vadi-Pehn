## 2026-07-23T13:49:55Z

You are the Data Engineering & Security Worker (@data-engineer & @security-engineer) for Milestone 1 of Vadi-Pehn Full MVP Refinement.
Working directory: d:\Vadi Bhen
Metadata directory: d:\Vadi Bhen\.agents\worker_m1_refine

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Tasks for Milestone 1 (Divisions 1 & 5):
1. Data Engineering (DB schemas & RLS):
   - Review DB schemas in `services/memory-service/` and `db/`.
   - Ensure `learner_memories` and `learner_interest_profile` database transactions consistently execute `SET LOCAL app.current_tenant_id = $1` before queries.
   - Ensure Governance DB (consent, incidents, logs) configuration remains physically separate from Memory DB (pgvector).
2. Security (Auth Hardening & Demo Auth):
   - Ensure `POST /api/v1/auth/demo` and `POST /api/v1/auth/login` / `signup` in `services/api-gateway/src/api_gateway/` or auth routes work cleanly.
   - Specifically verify that calling `POST /api/v1/auth/demo` with payload `{"role": "learner"}` (or guardian/admin) returns `200 OK` with JSON containing valid `access_token`, `tenant_id`, `learner_id` (or guardian_id), and `role`.
   - Verify JWT issuance and authorization header validation (`Bearer <token>` and `X-Tenant-ID`).

Run unit/integration tests for API gateway auth and memory service (e.g. `py -3 -m pytest services/api-gateway/` and `py -3 -m pytest services/memory-service/`).
Create a handoff report at `d:\Vadi Bhen\.agents\worker_m1_refine\handoff.md` detailing changes made and exact test results.
