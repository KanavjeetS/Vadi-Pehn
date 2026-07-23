# Handoff Report — Challenger M4-1

**Verdict**: **FAIL**

---

## Challenge Summary

**Overall risk assessment**: HIGH (RLS Policy Violation in Data Seeding Pipeline)

Adversarial verification was conducted on Milestone 4 (Requirement R4 — Guardian Portal & Seeding). While unit test suites and web app DOM/API payload integrations passed, critical RLS compliance flaws were uncovered in `db/seed_synthetic_data.py` that break RLS isolation during DB seeding.

---

## 1. Observation

### Observation 1.1: Data Seeding Offline/Online Resilience (`db/seed_synthetic_data.py`)
- **Code Inspected**: `db/seed_synthetic_data.py` lines 49-53 & 161-165, and `start_desktop.py` lines 61-64.
- **Empirical Execution**: Executed `py -3 db/seed_synthetic_data.py` via `run_command`. When Postgres DB is online, seeding completed with `Memory DB: True, Governance DB: True`.
- **Offline Fallback**: `asyncpg.connect` uses a 5.0s timeout and wraps connection attempts in `try...except Exception`. On connection failure, it logs `Memory DB connection failed (...)` / `Governance DB connection failed (...)` and returns `False`. `start_desktop.py` wraps `await seed_all()` in `try...except` so application startup does not crash when DB is offline.

### Observation 1.2: RLS Context Initialization Flaws in `seed_synthetic_data.py`
- **Memory DB Seeding**: Lines 58-97 issue `INSERT INTO tenants`, `INSERT INTO guardians`, and `INSERT INTO learners`. `SELECT set_config('app.current_tenant_id', $1, true)` is only called at line 100 — **AFTER** inserting into `tenants`, `guardians`, and `learners`.
- **Identity RLS Policy**: `db/migrations/006_identity_rls.sql` lines 4-9 & 11-24 enable and force RLS on `tenants`, `guardians`, and `learners` with `USING (tenant_id::text = current_setting('app.current_tenant_id', true))`.
- **Governance DB Seeding**: `seed_governance_db()` lines 157-220 insert into `consent_records` and `safety_incidents`. **`SELECT set_config('app.current_tenant_id', ...)` IS NEVER CALLED** anywhere in `seed_governance_db()`.
- **Governance RLS Policy**: `db/migrations/governance/001_governance_schema.sql` lines 30-41 enable and force RLS on `consent_records` and `safety_incidents` checking `current_setting('app.current_tenant_id', true)`.

### Observation 1.3: DOM Selectors & Consent API Payloads (`webapp/guardian`)
- **DOM Selectors**: `guardian.js` binds to `.stat-card .stat-val`, `#consent-memory`, `#consent-ocr`, `#consent-voice`, `#consent-panel`, `#incidents-list`, and `#upload-list`. All corresponding ID and class attributes exist in `webapp/guardian/index.html`.
- **API Payloads**: `guardian.js` `toggleConsent()` posts `{ tenant_id, guardian_id, learner_id, consent_type, granted }` to `/api/v1/guardian/consent`. `api-gateway/main.py` validates `ConsentPayload` and forwards `{ [consent_field]: granted }` to Governance Service `POST /internal/v1/governance/consent/{learner_id}` using headers `X-Tenant-ID` and `X-Guardian-ID`. Models match specifications.

### Observation 1.4: Test Suite Verification
- **Dashboard BFF**: `py -3 -m pytest services/dashboard-bff/tests/` -> **5 passed** in 0.09s.
- **Governance Service**: `py -3 -m pytest services/governance-service/tests/` -> **5 passed** in 0.37s.

---

## 2. Logic Chain

1. System Architecture Non-Negotiable (AGENTS.md Part 2) states: *"Every database query against learner_memories or learner_interest_profile MUST issue SET LOCAL app.current_tenant_id = $1 inside the transaction."*
2. Migration `006_identity_rls.sql` forces RLS on `tenants`, `guardians`, and `learners`, requiring `app.current_tenant_id` to equal `tenant_id` for any write/read. Migration `001_governance_schema.sql` forces RLS on `consent_records` and `safety_incidents`, requiring `app.current_tenant_id` to be set.
3. In `db/seed_synthetic_data.py`:
   - In `seed_memory_db()`, `set_config('app.current_tenant_id', ...)` is deferred until line 100, AFTER `tenants`, `guardians`, and `learners` inserts. If RLS is enforced by Postgres on identity tables, these initial inserts fail RLS checks.
   - In `seed_governance_db()`, `set_config('app.current_tenant_id', ...)` is entirely absent. When RLS is enforced on Governance DB, all seeding inserts fail RLS policy checks.
4. Therefore, `db/seed_synthetic_data.py` violates Part 2 Architecture Non-Negotiables and fails under strict RLS enforcement.

---

## 3. Challenges & Attack Scenarios

### [HIGH] Challenge 1: Governance DB Seeding Fails Under RLS Enforcement
- **Assumption challenged**: `seed_governance_db()` can seed consent records and incidents without setting tenant context.
- **Attack scenario**: On a database with RLS enabled (`001_governance_schema.sql`), running `seed_synthetic_data.py` causes `seed_governance_db()` to fail due to `app.current_tenant_id` being unset (`current_setting` returns empty string, violating RLS policy).
- **Blast radius**: Governance DB seeding fails completely on production/staging Postgres instances enforcing RLS.
- **Mitigation**: Add `await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(DEFAULT_TENANT_ID))` at the beginning of `async with conn.transaction():` inside `seed_governance_db()`.

### [HIGH] Challenge 2: Memory DB Identity Table Inserts Bypass Tenant RLS Setting
- **Assumption challenged**: Identity tables can be seeded before setting transaction tenant RLS context.
- **Attack scenario**: On a database with `006_identity_rls.sql` applied, `INSERT INTO guardians` and `INSERT INTO learners` are executed at lines 70 and 84 before `set_config` at line 100. Postgres rejects the inserts with RLS policy violation.
- **Blast radius**: Memory DB seeding fails on setup when RLS policies are enforced on identity tables.
- **Mitigation**: Move `await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(DEFAULT_TENANT_ID))` to line 57 (immediately after `async with conn.transaction():`).

---

## 4. Caveats

- In local development mode (`IS_DEV=true`), when Postgres is offline, microservices fallback to in-memory repositories (`InMemoryDashboardRepository`, `ConsentLedger`), so the RLS seeding failure in `seed_synthetic_data.py` is masked unless tested against live Postgres with RLS migrations applied.
- All mock-based pytest suites pass cleanly because they mock or substitute the database connection.

---

## 5. Conclusion

**Verdict**: **FAIL**

Milestone 4 implementation fulfills DOM selector alignment, Consent API payload specifications, offline/online fallback handling in `start_desktop.py`, and passes all test suites (`dashboard-bff` and `governance-service`). However, it **FAILS RLS Compliance** due to missing and misplaced `app.current_tenant_id` context initialization in `db/seed_synthetic_data.py`.

---

## 6. Verification Method

To verify these findings:
1. Inspect `db/seed_synthetic_data.py` lines 56-101 (`seed_memory_db`) and lines 168-212 (`seed_governance_db`).
2. Observe that line 100 calls `set_config` after lines 58, 70, and 84.
3. Observe that `seed_governance_db` lacks `set_config('app.current_tenant_id', ...)` entirely.
4. Run `py -3 -m pytest services/dashboard-bff/tests/` and `py -3 -m pytest services/governance-service/tests/` to confirm test execution.
