## 2026-07-22T10:38:00Z
You are teamwork_preview_worker_m1_1 operating as @backend-engineer to implement Milestone 1 (Requirement R1: Backend Route Mounting & Internal Service Connectivity in start_desktop.py).
Your working directory is `d:\Vadi Bhen\.agents\teamwork_preview_worker_m1_1`.

Mission (Milestone 1 — Requirement R1):
Fix the sub-application route mounting, lifespan initialization, dev mode fallbacks, and internal service connectivity in `start_desktop.py` and service main files so that all internal API calls (e.g. `POST /internal/v1/orchestration/turn`, `/internal/v1/voice/turn`, `/internal/v1/governance/consent/{learner_id}`, `/internal/v1/safety/check-input`, `/internal/v1/safety/check-output`, `/internal/v1/llm/chat/completions`, `/api/v1/guardian/overview`, `/api/v1/admin/overview`) reach their exact endpoints cleanly in single-process desktop development mode (`py -3 start_desktop.py`) without returning `404 Not Found` or `503 Service Unavailable`.

Specific fixes to execute:
1. In `start_desktop.py`:
   - Set environment defaults including `DASHBOARD_BFF_URL="http://127.0.0.1:8000"`, `ORCHESTRATION_URL`, `VOICE_GATEWAY_URL`, `GOVERNANCE_SERVICE_URL`, `PANEL_SERVICE_URL`, `SAFETY_PROXY_URL`, `INGESTION_SERVICE_URL`, `IS_DEV="true"`.
   - Avoid double-prefix routing mismatches by including sub-app routes/routers directly on `desktop_app` (or mounting at root `""`) so incoming request paths match registered route paths directly without path-stripping duplication. Ensure `/internal/v1/llm/chat/completions` route is mounted and accessible.
   - Wire a combined `desktop_lifespan` context manager on `desktop_app` that properly enters and manages child application lifespans (`orchestration_lifespan`, `governance_lifespan`, `dashboard_lifespan`, `api_gateway_lifespan`), initializing `graph`, `governance_pool`/`ledger`, `dashboard_repo`, and `identity_store`.
2. In `services/api-gateway/src/api_gateway/main.py`:
   - In `is_dev` mode when DB pool is absent, instantiate `InMemoryIdentityStore` so `/api/v1/guardian/enroll` and `/api/v1/guardian/learners` do not return 503.
3. In `services/governance-service/src/governance_service/main.py`:
   - Allow `ledger = ConsentLedger()` (in-memory) to serve requests when `governance_pool` is `None` in `is_dev` mode so 503 is not raised.
4. In `services/dashboard-bff/src/dashboard_bff/main.py`:
   - Instantiate `InMemoryDashboardRepository` when `settings.is_dev` is True so `/api/v1/guardian/overview` and `/api/v1/admin/overview` succeed without 503.

Run pytest on affected service test suites (`pytest services/api-gateway/tests/`, `pytest services/orchestration/tests/`, `pytest services/voice-gateway/tests/`, `pytest services/governance-service/tests/`, `pytest services/safety-proxy/tests/`, `pytest services/dashboard-bff/tests/`) and test `start_desktop.py` routes.

Write your handoff report to `d:\Vadi Bhen\.agents\teamwork_preview_worker_m1_1\handoff.md` with:
- Summary of code changes made (file paths & line numbers)
- Execution and test output results
- Layout compliance check against PROJECT.md
When done, notify parent via send_message.
