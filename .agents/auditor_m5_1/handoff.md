# Forensic Audit Report — Milestone 5 (Admin Observability & Tracing Center Native Dashboard)

**Work Product**: Milestone 5 (`webapp/admin/*`, `services/dashboard-bff/*`)  
**Profile**: General Project / Vadi-Pehn Platform  
**Verdict**: INTEGRITY VIOLATION  

---

## 1. Observation

Direct observations made during the forensic source code and test suite audit:

1. **Hardcoded Facade Telemetry & Metrics in Backend (`admin_observability.py` & `models.py`)**:
   - In `services/dashboard-bff/src/dashboard_bff/models.py`, `AdminOverview` Pydantic model defines static default values directly on model attributes (lines 78–120):
     ```python
     active_traces: int = 142
     total_sessions: int = 850
     safety_pass_rate: float = 99.18
     service_latencies: dict[str, ServiceLatencyPercentiles] = { ... }
     safety_triggers: dict[str, object] = { ... }
     sla_metrics: dict[str, object] = { ... }
     trace_count_hourly: list[dict[str, object]] = [ ... ]
     trace_summaries: list[TraceSummaryItem] = [ ... ]
     system_health_logs: list[SystemHealthLogItem] = [ ... ]
     ```
   - In `services/dashboard-bff/src/dashboard_bff/admin_observability.py`, the endpoint `get_admin_system_metrics()` (lines 40–90) returns a static dictionary of hardcoded metrics:
     ```python
     return {
         "langfuse_host": settings.langfuse.host,
         "active_traces": 142,
         "total_sessions": 850,
         "safety_triggers": { "unsafe_self_harm": 2, "unsafe_general": 5, "classifier_unavailable": 0, "safe_pass_rate": 99.18 },
         "sla_metrics": { "self_harm_15min_sla_met": "100%", "average_reviewer_ack_minutes": 3.4 },
         "voice_latency_p95_ms": 3200.0,
         ...
     }
     ```
     No query to Langfuse API, Prometheus, OpenTelemetry collector, or database persistence layer exists.

2. **Authentication / Security Role Bypass in `verify_admin_role` (`admin_observability.py`)**:
   - In `services/dashboard-bff/src/dashboard_bff/admin_observability.py` (lines 31–32):
     ```python
     if x_user_role == "admin":
         return
     ```
     Unauthenticated HTTP clients can bypass JWT authentication by supplying an unverified HTTP header `X-User-Role: admin`.

3. **Hardcoded Fallback JWT Token & Dummy Frontend Fallbacks (`admin.js`)**:
   - In `webapp/admin/admin.js` (lines 9–11):
     ```javascript
     if (!token) {
         token = "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJzdWIiOiAiMDAwMDAwMDAtMDAwMC0wMDAwLTAwMDAtMDAwMDAwMDAwMDBhIiwgInRlbmFudF9pZCI6ICIwMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDEiLCAicm9sZSI6ICJhZG1pbiIsICJpYXQiOiAxNzg0NzE0NzczLCAiZXhwIjogMTc4NDcxODM3M30.7lM769I9MVCyBLOQTc8yv1P8Iga-IjxDU9UkBeC7-dw";
     }
     ```
     Hardcoded JWT fallback token is present in client-side script.

4. **Self-Certifying Tests (`test_dashboard.py`)**:
   - In `services/dashboard-bff/tests/test_dashboard.py` (lines 62–63, 78–79):
     ```python
     assert data["active_traces"] == 142
     assert data["safety_pass_rate"] == 99.18
     ```
     Tests assert against hardcoded static facade outputs rather than dynamic telemetry calculations or database queries.

5. **Test Execution Command & Result**:
   - Command: `py -m pytest services/dashboard-bff/tests/`
   - Output: `6 passed, 2 warnings in 0.09s`

---

## 2. Logic Chain

1. **Step 1**: Prohibited Pattern #2 (Facade Implementations) strictly forbids correct-looking interfaces with no genuine backend logic. Observation #1 confirms that `/api/v1/admin/observability/metrics` and `AdminOverview` return fixed static data (`142` traces, `99.18%` pass rate, fixed latencies) without computing or fetching real telemetry.
2. **Step 2**: Prohibited Pattern #4 (Self-Certifying Tests) forbids tests checking against hardcoded values from facade code. Observation #4 shows `test_dashboard.py` asserting `data["active_traces"] == 142`, validating facade constants rather than testing functional metric aggregation.
3. **Step 3**: Safety & Auth Compliance (AGENTS.md Part 1 & Part 2) requires strict access control. Observation #2 demonstrates an authorization bypass via `X-User-Role: admin` header without JWT validation.
4. **Step 4**: Therefore, the Milestone 5 implementation contains multiple prohibited patterns (Facade implementation, hardcoded values, auth bypass), leading to a verdict of **INTEGRITY VIOLATION**.

---

## 3. Caveats

- No caveats. The source files and test suite were inspected directly and tested empirically.

---

## 4. Conclusion

Milestone 5 fails forensic integrity audit due to hardcoded facade endpoint implementations, self-certifying unit tests expecting static fake constants, and a header spoofing authorization bypass in `admin_observability.py`.

**Verdict**: **INTEGRITY VIOLATION**

---

## 5. Verification Method

To independently verify these findings:
1. View `services/dashboard-bff/src/dashboard_bff/admin_observability.py` lines 31-32 & 40-90 to observe the static return values and header auth bypass.
2. View `services/dashboard-bff/src/dashboard_bff/models.py` lines 78-120 to see static defaults on `AdminOverview`.
3. Run `py -m pytest services/dashboard-bff/tests/` to see that tests pass solely because they assert the hardcoded static values.
