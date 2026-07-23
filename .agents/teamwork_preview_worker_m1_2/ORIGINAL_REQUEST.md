## 2026-07-22T10:50:40Z
You are teamwork_preview_worker_m1_2 operating as @backend-engineer to fix the Milestone 1 Route Collision & Proxy Loop Defect identified by Reviewer 2.
Your working directory is `d:\Vadi Bhen\.agents\teamwork_preview_worker_m1_2`.

Read the following before starting:
- `d:\Vadi Bhen\PROJECT.md`
- `d:\Vadi Bhen\.agents\AGENTS.md`
- `d:\Vadi Bhen\.agents\skills\vadi-pehn-development\SKILL.md`
- Reviewer 2 handoff report: `d:\Vadi Bhen\.agents\teamwork_preview_reviewer_m1_2\handoff.md`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

The Defect to Fix:
In `start_desktop.py`, both `api_gateway_app` and `dashboard_app` register handlers for `/api/v1/guardian/overview` and `/api/v1/admin/overview`.
`api_gateway_app` registers proxy handlers (`get_guardian_overview_proxy`) that issue outbound `httpx` HTTP requests to `settings.dashboard.url` (`http://127.0.0.1:8000`). Because `api_gateway_app.routes` were appended before `dashboard_app.routes` on `desktop_app.routes`, Starlette resolved `/api/v1/guardian/overview` to `api_gateway`'s proxy handler first. In single-process desktop mode / TestClient, `httpx` cannot connect to port 8000 (or causes a recursive loop back to itself), returning `503 Service Unavailable`.

Fix Required:
1. In `start_desktop.py`:
   - Either place `dashboard_app.routes` before `api_gateway_app.routes` when appending routes to `desktop_app.routes`, OR filter out `api_gateway`'s proxy handlers for `/api/v1/guardian/overview` and `/api/v1/admin/overview` when combining routes on `desktop_app`, so `dashboard_app`'s direct handlers receive and process `/api/v1/guardian/overview` and `/api/v1/admin/overview` requests directly without loopback HTTP calls.
2. In `services/api-gateway/tests/test_desktop_routes.py`:
   - Add active HTTP GET requests with valid JWT headers (`create_jwt_token(..., role="guardian")` and `role="admin"`) targeting `/api/v1/guardian/overview` and `/api/v1/admin/overview` using `TestClient(desktop_app)` and verify status `200 OK`.
3. Run test suite:
   - Run `py -3 -m pytest services/api-gateway/tests/` (including `test_challenger_m1_mounts.py` if present).
   - Ensure ALL tests pass cleanly with 0 failures.

Write your handoff report to `d:\Vadi Bhen\.agents\teamwork_preview_worker_m1_2\handoff.md` with details of the fix and test outputs.
When complete, notify parent via send_message.
