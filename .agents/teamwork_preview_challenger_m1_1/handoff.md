# Handoff Report — Empirical Challenge of Milestone 1 Desktop Route Mounting

**Agent**: `teamwork_preview_challenger_m1_1` (Adversarial Challenger)  
**Target File**: `d:\Vadi Bhen\.agents\teamwork_preview_challenger_m1_1\handoff.md`  
**Date**: 2026-07-22  
**Verdict**: **FAIL**  

---

## 1. Observation

### 1.1 Test Execution & Commands

A dedicated empirical test harness `services/api-gateway/tests/test_challenger_m1_mounts.py` was constructed and executed using Pytest:

```powershell
py -3 -m pytest services/api-gateway/tests/test_challenger_m1_mounts.py -v
```

### 1.2 Summary of Empirical Results

- **Total Test Cases Executed**: 27
- **Passed**: 25
- **Failed**: 2 (`test_guardian_overview_normal`, `test_admin_overview_normal`)

#### Detailed Route Breakdown:

1. **Route Mounting Inventory**:
   - `test_all_required_routes_are_mounted`: **PASSED**.
   - Verified that all 13 expected internal and BFF routes (`/internal/v1/orchestration/turn`, `/internal/v1/voice/turn`, `/internal/v1/governance/consent/{learner_id}`, `/internal/v1/safety/check-input`, `/internal/v1/safety/check-output`, `/internal/v1/llm/chat/completions`, `/api/v1/guardian/overview`, `/api/v1/admin/overview`, `/internal/v1/governance/incident`, `/internal/v1/governance/incidents/{tenant_id}`, `/internal/v1/voice/token`, `/api/v1/guardian/enroll`, `/api/v1/guardian/learners`) are registered in `desktop_app.routes`.

2. **Internal Service Endpoints (`/internal/v1/*`)**:
   - `POST /internal/v1/orchestration/turn`: **PASSED** (200 OK under valid payload; 422 Unprocessable Entity under missing fields/invalid UUID/out-of-bound age_band/empty text).
   - `POST /internal/v1/voice/turn`: **PASSED** (200 OK under valid payload; 422 Unprocessable Entity under malformed payloads).
   - `GET /internal/v1/governance/consent/00000000-0000-0000-0000-000000000002`: **PASSED** (200 OK when providing `X-Tenant-ID` header; 422 Unprocessable Entity when missing header or invalid path UUID).
   - `POST /internal/v1/safety/check-input`: **PASSED** (200 OK returning valid `SafetyVerdictCode`; 422 Unprocessable Entity under malformed payloads).
   - `POST /internal/v1/safety/check-output`: **PASSED** (200 OK returning valid `SafetyVerdictCode`; 422 Unprocessable Entity under malformed payloads).
   - `POST /internal/v1/llm/chat/completions`: **PASSED** (200 OK returning mock dev chat completion; 422 Unprocessable Entity under invalid message structures).

3. **BFF Overview Endpoints (`/api/v1/*`)**:
   - `GET /api/v1/guardian/overview`: **FAILED** (Returned `503 Service Unavailable` with `{"detail": "dashboard service unavailable"}`).
   - `GET /api/v1/admin/overview`: **FAILED** (Returned `503 Service Unavailable` with `{"detail": "dashboard service unavailable"}`).
   - Unauthenticated & Role Boundary Rejections (`401 Unauthorized` for missing JWT; `403 Forbidden` for learner token on guardian route / guardian token on admin route): **PASSED** (Correctly returned 401/403 without returning 404 or 503).
   - Non-existent route `/internal/v1/nonexistent/endpoint`: **PASSED** (Correctly returned 404 Not Found).

### 1.3 Verbatim Error Trace

```
================================== FAILURES ===================================
________________________ test_guardian_overview_normal ________________________
    def test_guardian_overview_normal(desktop_client: TestClient):
        ...
        resp = desktop_client.get(
            "/api/v1/guardian/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
>       assert resp.status_code != 503, "Returned 503 Service Unavailable"
E       AssertionError: Returned 503 Service Unavailable
E       assert 503 != 503
E        +  where 503 = <Response [503 Service Unavailable]>.status_code

_________________________ test_admin_overview_normal __________________________
    def test_admin_overview_normal(desktop_client: TestClient):
        ...
        resp = desktop_client.get(
            "/api/v1/admin/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
>       assert resp.status_code != 503, "Returned 503 Service Unavailable"
E       AssertionError: Returned 503 Service Unavailable
E       assert 503 != 503
E        +  where 503 = <Response [503 Service Unavailable]>.status_code
```

---

## 2. Logic Chain

1. **Route Ordering Mismatch**: In `start_desktop.py` (lines 70-85), `sub_apps` is populated as `[api_gateway_app, orchestration_app, voice_gateway_app, governance_app, panel_app, safety_proxy_app, ingestion_app, dashboard_app]`. When iterating and appending sub-app routes to `desktop_app.routes`, `api_gateway_app`'s routes are added first.
2. **Proxy Handler Capture**: `api_gateway_app` defines `@app.get("/api/v1/guardian/overview")` (`get_guardian_overview_proxy` in `services/api-gateway/src/api_gateway/main.py` lines 499-520) and `@app.get("/api/v1/admin/overview")` (`get_admin_overview_proxy` lines 523-540). Because `api_gateway_app` routes come first, incoming requests to `/api/v1/guardian/overview` and `/api/v1/admin/overview` on `desktop_app` hit `api_gateway_app`'s proxy handlers instead of `dashboard_app`'s direct handlers.
3. **Network Connection Refusal**: `get_guardian_overview_proxy` attempts an outbound HTTP request using `httpx.AsyncClient` to `f"{settings.dashboard.url.rstrip('/')}/api/v1/guardian/overview"` where `settings.dashboard.url` defaults to `http://127.0.0.1:8000`. In single-process desktop execution, no standalone loopback HTTP server is bound/listening on port 8000 (or `TestClient` executes in-process without port binding).
4. **Fail-Closed 503 Error**: `httpx.AsyncClient` raises `httpx.ConnectError` (Connection Refused). The exception handler in `api_gateway/main.py` (lines 516-520 & 539-543) catches `(httpx.HTTPError, ValueError)` and raises `HTTPException(status_code=503, detail="dashboard service unavailable")`.
5. **Secondary Network Dependency in `dashboard-bff`**: Furthermore, inside `services/dashboard-bff/src/dashboard_bff/main.py` (lines 95-105 & 144-151), `get_guardian_overview` and `get_admin_overview` ALSO issue outbound HTTP requests via `_get_json` to `settings.governance.url` (`http://127.0.0.1:8000/internal/v1/governance/consent/summary/{tenant_id}` and `/internal/v1/governance/incidents/{tenant_id}`). Even if `dashboard_app`'s handler were matched directly, it would fail with 503 for the same reason when running single-process without an active external network socket server.

---

## 3. Caveats

- **External Network Server Workaround**: If `uvicorn` is actively running as a separate background process listening on `http://127.0.0.1:8000`, the loopback HTTP calls will succeed, hiding this single-process architectural coupling issue. However, in single-process desktop mode (or any test runner / containerized single-process execution), `/api/v1/guardian/overview` and `/api/v1/admin/overview` fail with `503 Service Unavailable`.
- **Scope Limit**: The challenger did not modify implementation code per the review-only constraint.

---

## 4. Conclusion

Empirical verification disproves Worker 1's claim that all endpoints function without 503 Service Unavailable under normal operations in single-process desktop mode.

**Verdict**: **FAIL**

### Actionable Remediation Required:
1. In `start_desktop.py`, eliminate the double-proxy hop by either removing duplicate proxy endpoints in `api_gateway_app` or prioritizing `dashboard_app` routes.
2. In `dashboard_bff/main.py` and `api_gateway/main.py`, avoid loopback HTTP network calls (`httpx.AsyncClient` to `http://127.0.0.1:8000`) during single-process desktop development mode (`IS_DEV=true`). Use direct in-memory invocation or Starlette `ASGITransport` for in-process sub-application communication.

---

## 5. Verification Method

To independently reproduce and verify this failure:

1. Execute the empirical challenger test suite:
   ```powershell
   py -3 -m pytest services/api-gateway/tests/test_challenger_m1_mounts.py -v
   ```
2. Inspect the test output for `test_guardian_overview_normal` and `test_admin_overview_normal`.
3. Confirm both tests fail with status code `503 Service Unavailable`.
