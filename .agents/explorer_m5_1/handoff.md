# Handoff Report — Milestone 5 Admin Observability Dashboard Integrity Remediation

**Agent**: `explorer_m5_1`  
**Date**: 2026-07-22  
**Target Milestone**: Milestone 5 (Admin Observability Dashboard)  
**Verdict Handled**: FORENSIC INTEGRITY AUDIT VIOLATION  

---

## 1. Observation

Direct observations and evidence collected from read-only inspection of the codebase:

### 1.1 Backend Hardcoded Facade Telemetry & Metrics (`models.py` & `admin_observability.py`)
- **File**: `services/dashboard-bff/src/dashboard_bff/models.py` (Lines 71–119)
  - `AdminOverview` Pydantic model defines static default values on almost every metric field:
    ```python
    active_traces: int = 142
    total_sessions: int = 850
    safety_pass_rate: float = 99.18
    service_latencies: dict[str, ServiceLatencyPercentiles] = {
        "API Gateway": ServiceLatencyPercentiles(p50=12.0, p95=45.0, p99=85.0),
        "Orchestration": ServiceLatencyPercentiles(p50=210.0, p95=850.0, p99=1400.0),
        "Safety Proxy": ServiceLatencyPercentiles(p50=42.0, p95=180.0, p99=280.0),
        "Voice Gateway": ServiceLatencyPercentiles(p50=340.0, p95=3200.0, p99=3650.0),
        "Memory": ServiceLatencyPercentiles(p50=15.0, p95=55.0, p99=110.0),
        "Governance": ServiceLatencyPercentiles(p50=18.0, p95=60.0, p99=120.0),
    }
    safety_triggers: dict[str, object] = {
        "unsafe_self_harm": 2,
        "unsafe_general": 5,
        "classifier_unavailable": 0,
        "safe_pass_rate": 99.18,
    }
    sla_metrics: dict[str, object] = {
        "self_harm_15min_sla_met": "100%",
        "average_reviewer_ack_minutes": 3.4,
    }
    trace_count_hourly: list[dict[str, object]] = [...] # Static 09:00 to 15:00 counts
    trace_summaries: list[TraceSummaryItem] = [...] # Static tr-9812 through tr-9815
    system_health_logs: list[SystemHealthLogItem] = [...] # Static hardcoded log lines
    ```
- **File**: `services/dashboard-bff/src/dashboard_bff/admin_observability.py` (Lines 40–90)
  - `get_admin_system_metrics()` endpoint returns a hardcoded static dictionary containing identical facade constants (`"active_traces": 142`, `"safety_pass_rate": 99.18`, etc.) without performing any database, governance, or telemetry aggregation.

### 1.2 Authentication / Security Role Bypass (`admin_observability.py`)
- **File**: `services/dashboard-bff/src/dashboard_bff/admin_observability.py` (Lines 17–37)
  - `verify_admin_role` function implementation:
    ```python
    def verify_admin_role(
        authorization: str | None = Header(None),
        x_user_role: str | None = Header(None),
    ) -> None:
        if authorization and authorization.startswith("Bearer "):
            try:
                from api_gateway.auth import decode_jwt_token
                payload = decode_jwt_token(authorization.split("Bearer ")[1].strip())
                if payload.get("role") == "admin":
                    return
            except Exception:
                pass

        if x_user_role == "admin":
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin-only authorization scope required.",
        )
    ```
  - Lines 31–32 immediately grant access if an unauthenticated client sends `X-User-Role: admin`, completely bypassing cryptographic JWT verification.
  - The function catches `Exception` silently without failing closed with `401 Unauthorized` on missing/invalid JWT tokens.

### 1.3 Hardcoded Fallback JWT Token in Webapp (`admin.js`)
- **File**: `webapp/admin/admin.js` (Lines 9–18)
  - Contains embedded hardcoded JWT fallback string and sends fake role header:
    ```javascript
    if (!token) {
        token = "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJzdWIiOiAiMDAwMDAwMDAtMDAwMC0wMDAwLTAwMDAtMDAwMDAwMDAwMDBhIiwgInRlbmFudF9pZCI6ICIwMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDEiLCAicm9sZSI6ICJhZG1pbiIsICJpYXQiOiAxNzg0NzE0NzczLCAiZXhwIjogMTc4NDcxODM3M30.7lM769I9MVCyBLOQTc8yv1P8Iga-IjxDU9UkBeC7-dw";
    }
    return {
        'Authorization': `Bearer ${token}`,
        'X-Tenant-ID': tenantId,
        'X-User-Role': 'admin',
        'Content-Type': 'application/json'
    };
    ```
  - Lines 111–120, 215–223, 269–274, 296–302 define static fallback datasets (`defaultHourly`, `defaultLatencies`, `defaultLogs`) inside UI rendering functions, displaying fake charts when API calls fail or return no data.

### 1.4 Self-Certifying Tests (`test_dashboard.py`)
- **File**: `services/dashboard-bff/tests/test_dashboard.py` (Lines 49–83)
  - `test_admin_overview_endpoint()` asserts: `assert data["active_traces"] == 142`, `assert data["safety_pass_rate"] == 99.18`.
  - `test_admin_observability_metrics_endpoint()` asserts: `assert data["active_traces"] == 142`, `assert data["safety_triggers"]["safe_pass_rate"] == 99.18`.
  - Lacks test cases for header spoofing rejection (`X-User-Role: admin`), missing authorization tokens (`401`), or invalid/non-admin roles (`403`).

---

## 2. Logic Chain

The step-by-step reasoning from observations to the proposed fix strategy:

### 2.1 Strategy for Dynamic Telemetry & Metrics Aggregation
1. **Model Clean-up**:
   - In `services/dashboard-bff/src/dashboard_bff/models.py`, remove all hardcoded static values (`142`, `99.18`, static latencies, static logs).
   - Use clean, dynamic defaults: `active_traces: int = 0`, `total_sessions: int = 0`, `safety_pass_rate: float = 100.0`, `service_latencies: dict[str, ServiceLatencyPercentiles] = Field(default_factory=dict)`, `safety_triggers: dict[str, Any] = Field(default_factory=dict)`, `sla_metrics: dict[str, Any] = Field(default_factory=dict)`, `trace_count_hourly: list[dict[str, Any]] = Field(default_factory=list)`, `trace_summaries: list[TraceSummaryItem] = Field(default_factory=list)`, `system_health_logs: list[SystemHealthLogItem] = Field(default_factory=list)`.
2. **Repository & BFF Aggregation Layer**:
   - Update `PostgresDashboardRepository` (and `InMemoryDashboardRepository` for dev mode) in `repository.py` to query real database metrics:
     - Active traces: count of trace/memory spans or active sessions in `learner_memories` / audit table for tenant.
     - Total sessions: count of distinct sessions.
     - Hourly trace distribution: `DATE_TRUNC('hour', created_at)` grouping for recent active hours.
     - Recent trace summaries and system health logs.
   - In `admin_observability.py` and `main.py`:
     - Query Governance Service (`/internal/v1/governance/incidents/{tenant_id}`) for live incident counts, SLA breach counts, and reviewer acknowledgment timing.
     - Compute `safety_triggers` and `sla_metrics` dynamically:
       - `unsafe_self_harm` count, `unsafe_general` count, `classifier_unavailable` count.
       - `safe_pass_rate`: derived dynamically from screened turns / incidents vs total turns (defaulting to 100.0 if zero incidents recorded).
       - SLA metrics: percentage of 15-minute SLA met vs breached, average reviewer acknowledgment time in minutes derived from `created_at` and `acknowledged_at`.
   - When the database or governance store is empty, return clean zero/empty data structures (`active_traces: 0`, `trace_count_hourly: []`, `recent_incidents: []`), eliminating fake static numbers.

### 2.2 Strategy for Auth & Security Role Bypass Fix
1. **Remove Header Spoofing Bypass**:
   - In `services/dashboard-bff/src/dashboard_bff/admin_observability.py`, delete lines 31–32 (`if x_user_role == "admin": return`).
2. **Integrate Centralized Auth Dependency**:
   - Replace custom header checking in `verify_admin_role` with `Depends(require_role("admin"))` imported from `api_gateway.auth`.
   - `require_role("admin")` enforces:
     - Extraction of `Authorization: Bearer <token>` (returns `401 Unauthorized` if header missing or malformed).
     - HMAC-SHA256 signature verification and expiration check via `decode_jwt_token` (returns `401 Unauthorized` if invalid/expired).
     - Scope check confirming `payload.get("role") == "admin"` (returns `403 Forbidden` if role is not `"admin"`).

### 2.3 Strategy for Frontend JWT & Fallback Cleanup
1. **Clean Token Retrieval & Auth Headers**:
   - In `webapp/admin/admin.js`, refactor `getAuthHeaders()` to retrieve tokens exclusively from `localStorage` or `sessionStorage`.
   - Remove the embedded fallback JWT string and the `X-User-Role: admin` header.
   - If no valid token exists in storage, immediately redirect to `/login.html`.
2. **Response Error Handling & Auth Redirects**:
   - Update `fetchAdminObservabilityData()` to check response status codes.
   - If a `401 Unauthorized` or `403 Forbidden` response is returned, clear stored credentials and redirect to `/login.html`.
3. **Eliminate Fake UI Fallback Datasets**:
   - Remove static mock arrays (`defaultHourly`, `defaultLatencies`, `defaultLogs`) from chart and table rendering functions (`renderTraceVolumeChart`, `renderSafetyPassRateChart`, `renderMicroserviceLatencyChart`, `renderTraceSummariesTable`, `renderSystemHealthLogsTable`).
   - Display clear "No telemetry data available" or empty chart states when the backend returns empty metrics.

### 2.4 Strategy for Dynamic Test Assertions & Security Test Coverage
1. **Dynamic Schema Assertions**:
   - In `services/dashboard-bff/tests/test_dashboard.py`, replace fixed-constant assertions (`assert data["active_traces"] == 142`) with dynamic schema assertions:
     - `assert isinstance(data["active_traces"], int)`
     - `assert 0.0 <= data["safety_triggers"]["safe_pass_rate"] <= 100.0`
     - `assert isinstance(data["service_latencies"], dict)`
     - `assert isinstance(data["trace_count_hourly"], list)`
2. **Auth & Security Test Cases**:
   - Add `test_admin_observability_unauthenticated_returns_401()`: verify request without `Authorization` header returns `401 Unauthorized`.
   - Add `test_admin_observability_header_spoofing_rejected()`: verify request with `X-User-Role: admin` but missing/invalid JWT returns `401 Unauthorized`.
   - Add `test_admin_observability_non_admin_role_rejected()`: verify request with guardian or learner JWT returns `403 Forbidden`.
   - Add `test_admin_observability_valid_admin_jwt_accepted()`: verify request with valid admin JWT returns `200 OK`.

---

## 3. Caveats

- **Scope & Read-Only Constraint**: Investigation was strictly read-only. No source files, web application files, or test suites outside `.agents/explorer_m5_1/` were modified during this analysis turn.
- **Dev Mode Environment Alignment**: In development mode (`settings.is_dev == True`), `InMemoryDashboardRepository` and governance mocks must be updated alongside Postgres repositories to return dynamic empty/populated schemas rather than hardcoded facade numbers.

---

## 4. Conclusion

The forensic integrity audit failure for Milestone 5 is caused by static facade constants in backend models and router endpoints, an unauthenticated role spoofing bypass in `verify_admin_role`, an embedded fallback JWT string in `admin.js`, and self-certifying test assertions in `test_dashboard.py`.

Formulated remediation plan directly resolves all four audit findings:
1. Dynamic metrics aggregation with zero-data empty structures.
2. Cryptographic JWT authentication with `require_role("admin")` and removal of header spoofing.
3. Secure frontend token extraction from `localStorage` with explicit unauthenticated/401/403 redirects to `/login.html`.
4. Comprehensive test coverage asserting dynamic schemas and fail-closed auth security controls.

---

## 5. Verification Method

To verify the implementation once applied by `@backend-engineer`:

1. **Automated Unit & Integration Tests**:
   Run the pytest test suite for `dashboard-bff`:
   ```bash
   pytest services/dashboard-bff/tests/test_dashboard.py -v
   ```
   *Expected Result*: All tests pass, validating dynamic metrics schemas, `200 OK` for valid admin JWT, `401 Unauthorized` for missing token / spoofed header, and `403 Forbidden` for non-admin role tokens.

2. **Security & Header Spoofing Rejection Verification**:
   Execute HTTP client queries against running service:
   - `curl -i http://localhost:8000/api/v1/admin/observability/metrics -H "X-User-Role: admin"`
     *Expected Result*: `HTTP/1.1 401 Unauthorized`
   - `curl -i http://localhost:8000/api/v1/admin/observability/metrics`
     *Expected Result*: `HTTP/1.1 401 Unauthorized`

3. **Static Analysis & Facade Audit**:
   Verify via `grep_search` that no static facade constants (`142`, `99.18`, embedded fallback JWT strings) exist in `admin_observability.py`, `models.py`, `admin.js`, or `test_dashboard.py`.
