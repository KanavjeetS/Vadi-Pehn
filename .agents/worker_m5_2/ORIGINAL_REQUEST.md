## 2026-07-22T15:47:30Z

<USER_REQUEST>
You are worker_m5_2 operating as @backend-engineer & @frontend-engineer in d:\Vadi Bhen\.agents\worker_m5_2.
Read d:\Vadi Bhen\.agents\skills\vadi-pehn-development\SKILL.md before coding.

Your task is to execute the Milestone 5 (Admin Observability Dashboard) Forensic Audit Remediation Plan per d:\Vadi Bhen\.agents\explorer_m5_1\handoff.md and auditor report d:\Vadi Bhen\.agents\auditor_m5_1\handoff.md:

1. **`services/dashboard-bff/src/dashboard_bff/models.py`**:
   - Remove hardcoded static defaults (`active_traces = 142`, `safety_pass_rate = 99.18`, static service latencies dicts, static hourly trace arrays, static health logs).
   - Define clean, dynamic defaults (`active_traces: int = 0`, `total_sessions: int = 0`, `safety_pass_rate: float = 100.0`, `service_latencies: dict[str, ServiceLatencyPercentiles] = Field(default_factory=dict)`, `trace_count_hourly: list[dict[str, Any]] = Field(default_factory=list)`, etc.).

2. **`services/dashboard-bff/src/dashboard_bff/admin_observability.py`**:
   - Fix `verify_admin_role`: REMOVE `if x_user_role == "admin": return`. Require proper JWT decoding (using `api_gateway.auth` or `decode_jwt_token`) verifying `payload.get("role") == "admin"`. Fail closed with `401 Unauthorized` if token is missing or invalid, and `403 Forbidden` if role is not `"admin"`.
   - Compute/aggregate telemetry metrics dynamically from database / governance service / memory sessions or return clean dynamic empty/default models when data is empty. Do NOT return static hardcoded facade dicts.

3. **`webapp/admin/admin.js`**:
   - Remove the embedded hardcoded JWT fallback token string and fake `X-User-Role: admin` header.
   - Retrieve tokens strictly from `localStorage`/`sessionStorage`. If no token exists, redirect to `/login.html?role=admin`.
   - Remove hardcoded static fallback arrays (`defaultHourly`, `defaultLatencies`, `defaultLogs`) from UI rendering functions; render clean empty states if telemetry data is empty.

4. **`services/dashboard-bff/tests/test_dashboard.py`**:
   - Update test assertions to check dynamic schema (field types, key existence) rather than hardcoded static numbers (`142`, `99.18`).
   - Add security tests:
     - `test_admin_observability_unauthenticated_returns_401()`: missing token returns 401.
     - `test_admin_observability_header_spoofing_rejected()`: `X-User-Role: admin` header without valid JWT returns 401.
     - `test_admin_observability_non_admin_role_rejected()`: learner/guardian JWT returns 403.
     - `test_admin_observability_valid_admin_jwt_accepted()`: valid admin JWT returns 200.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Run tests:
`py -m pytest services/dashboard-bff/tests/`

Write handoff report to `d:\Vadi Bhen\.agents\worker_m5_2\handoff.md` and notify orchestrator with `send_message`.
</USER_REQUEST>
