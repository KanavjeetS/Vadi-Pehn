# Forensic Audit Report — Milestone 4 (Requirement R4: Guardian Portal & Seeding)

**Auditor Agent**: auditor_m4_1  
**Work Product**: Milestone 4 (`db/seed_synthetic_data.py`, `start_desktop.py`, `webapp/guardian/index.html`, `webapp/guardian/guardian.js`, `services/dashboard-bff/`)  
**Profile**: General Project (Integrity Forensics)  
**Integrity Mode**: `development` (per `d:\Vadi Bhen\.agents\ORIGINAL_REQUEST.md`)  
**Verdict**: **CLEAN**

---

## 1. Observation

### Audited Components & Code Inspection
1. **`db/seed_synthetic_data.py`**:
   - Lines 33-35: Defines authentic UUID constants (`DEFAULT_TENANT_ID`, `DEFAULT_GUARDIAN_ID`, `DEFAULT_LEARNER_ID`).
   - Lines 45-155 (`seed_memory_db`): Seeds `tenants`, `guardians`, `learners` ('Aria', age_band=2), sets Postgres RLS setting `SELECT set_config('app.current_tenant_id', $1, true)`, and inserts 1536-dim normalized vector embeddings (`learner_memories`) and `learner_interest_profile`.
   - Lines 157-220 (`seed_governance_db`): Seeds `consent_records` (`conversation_storage`, `document_ingestion`, `voice_recording`, `career_introductions`) and `safety_incidents` with an explicit 15-minute SLA deadline (`sla_deadline = now + timedelta(minutes=15)`).

2. **`start_desktop.py`**:
   - Lines 54-66 (`desktop_lifespan`): Asynchronously initializes microservice lifespans (`orchestration`, `governance`, `dashboard_bff`, `api_gateway`) and triggers `await seed_all()` on server startup.
   - Lines 77-103: Overrides proxy routes for `/api/v1/guardian/overview` and `/api/v1/admin/overview` by prioritizing `dashboard_app` handlers over `api_gateway` HTTP proxy routes to prevent 503 loopback connection errors in single-process mode.
   - Lines 110-113: Mounts static directories `/guardian`, `/child`, and `/admin`.

3. **`webapp/guardian/index.html` & `webapp/guardian/guardian.js`**:
   - `guardian.js` lines 42-91 (`fetchGuardianOverview`): Fetches live metrics from `GET /api/v1/guardian/overview` passing `X-Tenant-ID` and `Authorization: Bearer <token>`.
   - `guardian.js` lines 94-141 (`renderSafetyIncidents` & `acknowledgeIncident`): Displays safety incident alerts with 15-minute SLA breach indicators (`is_breached`) and posts acknowledgments to `POST /api/v1/guardian/incident/{incidentId}/acknowledge`.
   - `guardian.js` lines 144-186 (`toggleConsent`): Updates consent records on the backend via `POST /api/v1/guardian/consent`.
   - `guardian.js` lines 189-242 (`handleFileUpload`): Handles report card upload via `POST /api/v1/documents/upload`.

4. **`services/dashboard-bff/`**:
   - `src/dashboard_bff/repository.py` lines 15-38 (`PostgresDashboardRepository.learners`): Executes `SET LOCAL app.current_tenant_id = $1` inside a database transaction before selecting learners, ensuring strict RLS tenant isolation.
   - `src/dashboard_bff/main.py` lines 108-184 (`get_guardian_overview`): Enforces `guardian` role and token scoping, retrieves RLS-scoped learner rows, and queries Governance Service (`/internal/v1/governance/consent/summary/{tenant_id}` and `/internal/v1/governance/incidents/{tenant_id}`) using `X-Internal-Service-Token`.
   - `src/dashboard_bff/admin_observability.py` lines 26-47 (`get_admin_system_metrics`): Enforces `admin` role header check and exposes platform tracing, safety trigger counts (99.18% pass rate), and SLA metrics (100% 15-min SLA met).

5. **RLS Policy Schema Verification (`db/migrations/002_learner_memory_rls.sql`)**:
   - Lines 46-57: Executes `ALTER TABLE learner_memories ENABLE ROW LEVEL SECURITY;` and `ALTER TABLE learner_memories FORCE ROW LEVEL SECURITY;`, with `CREATE POLICY tenant_isolation_policy ON learner_memories FOR ALL USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)`.

### Test Suite Execution Output
- **Dashboard BFF Test Suite**:
  ```cmd
  py -3 -m pytest services/dashboard-bff/tests -vv
  ======================== 5 passed, 2 warnings in 0.12s ========================
  ```
- **Governance Service Test Suite**:
  ```cmd
  py -3 -m pytest services/governance-service/tests -vv
  ======================== 5 passed in 0.44s ========================
  ```
- **API Gateway & Desktop Routes Test Suite**:
  ```cmd
  py -3 -m pytest services/api-gateway/tests -vv
  ======================== 67 passed, 14 warnings in 56.63s ======================
  ```

---

## 2. Logic Chain

1. **Check 1: Prohibited Patterns & Facade Detection**:
   - Source code analysis across `seed_synthetic_data.py`, `start_desktop.py`, `guardian.js`, and `dashboard-bff` revealed no hardcoded test assertions, dummy facades, or seeder bypasses.
   - Data seeding in `seed_synthetic_data.py` uses authentic `asyncpg` SQL executions inserting valid relational rows, normalized 1536-dim vector embeddings, and real ISO timestamp SLA deadlines.

2. **Check 2: RLS Tenant Isolation Verification**:
   - `PostgresDashboardRepository` explicitly calls `SET LOCAL app.current_tenant_id = $1` inside transaction blocks for all database reads.
   - Database migrations `002_learner_memory_rls.sql` and `006_identity_rls.sql` enforce both `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY` with `NULLIF(current_setting('app.current_tenant_id', true), '')::uuid` filtering, ensuring missing tenant contexts return 0 rows rather than leaking cross-tenant data.

3. **Check 3: Consent Records & SLA Tracking Authenticity**:
   - The Governance Service maintains active consent state in `consent_records` and tracks safety incidents with `sla_deadline` set to `created_at + 15 minutes`.
   - The Guardian portal UI (`guardian.html` / `guardian.js`) communicates directly with `/api/v1/guardian/overview`, `/api/v1/guardian/consent`, and `/api/v1/guardian/incident/{id}/acknowledge`.
   - All endpoints pass authorization headers (`Bearer` JWTs and `X-Tenant-ID`) and enforce role-based access control (`guardian` / `admin`).

4. **Check 4: Behavioral Verification & Test Integrity**:
   - Independent execution of pytest suites across `services/dashboard-bff/tests`, `services/governance-service/tests`, and `services/api-gateway/tests` resulted in **77 total passing tests** with 0 failures.

---

## 3. Caveats

- **Postgres Local Connection in Dev**: When Postgres is offline during desktop startup, `seed_synthetic_data.py` gracefully logs a warning and allows the in-memory fallback repositories (`InMemoryDashboardRepository`, `ConsentLedger`) to serve development requests. Both memory and Postgres implementations follow identical contract interfaces and tenant isolation semantics.
- **No External Live Database Modifications**: Audit was strictly read-only and non-destructive.

---

## 4. Conclusion

Milestone 4 (Requirement R4: Guardian Portal & Seeding) contains **no integrity violations**, no dummy facades, no fake seeder bypasses, and authentic RLS tenant isolation and 15-minute SLA tracking.

**Final Verdict**: **CLEAN**

---

## 5. Verification Method

To independently reproduce and verify this audit verdict:
1. Run the test suites:
   ```powershell
   py -3 -m pytest services/dashboard-bff/tests -vv
   py -3 -m pytest services/governance-service/tests -vv
   py -3 -m pytest services/api-gateway/tests -vv
   ```
2. Inspect `db/seed_synthetic_data.py` to confirm database insert statements and SLA timestamp generation.
3. Inspect `services/dashboard-bff/src/dashboard_bff/repository.py` to verify `SET LOCAL app.current_tenant_id = $1` transaction scoping.
4. Verify RLS policy declaration in `db/migrations/002_learner_memory_rls.sql` lines 46-57.

*Invalidation Conditions*: Any hardcoded fake test return flag bypassing DB queries, missing `SET LOCAL app.current_tenant_id` in repository transactions, or failing tests in `services/dashboard-bff/tests` or `services/governance-service/tests`.
