# Forensic Audit Report — Milestone 1 (Data Engineering & Security)

**Work Product**: `services/memory-service/` and `services/api-gateway/`
**Profile**: General Project / Forensic Auditor
**Verdict**: **CLEAN**

---

## 1. Observation

Direct empirical observations from source code analysis and test execution:

1. **RLS Tenant Isolation (`SET LOCAL app.current_tenant_id = $1`)**:
   - `services/memory-service/src/memory_service/store.py`:
     - Line 61: `await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tenant_id))` inside transaction in `PostgresMemoryStore.write`.
     - Line 108: `await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tenant_id))` inside transaction in `PostgresMemoryStore.query`.
     - Line 167: `await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tenant_id))` inside transaction in `PostgresMemoryStore.delete_for_learner`.
     - Line 199: `await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tid))` inside per-tenant transaction in `PostgresMemoryStore.prune_expired`.
   - `services/memory-service/src/memory_service/write_pipeline.py`:
     - Line 46: `await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tenant_id))` inside transaction in `PostgresConsentChecker.check_memory_write_consent`.
     - Line 126: `await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tenant_id))` inside transaction in `AsyncMemoryWriter.write_memory_chunked`.
     - Line 201: `await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tenant_id))` inside transaction in `AsyncMemoryWriter._write_to_dlq`.
   - `services/memory-service/src/memory_service/context.py`:
     - Line 70: `await conn.execute("SET LOCAL app.current_tenant_id = $1", str(query.tenant_id))` inside transaction in `ContextualRetrievalService.get_contextual_summary`.
   - `services/memory-service/src/memory_service/retrieval.py`:
     - Line 61: `await conn.execute("SET LOCAL app.current_tenant_id = $1", str(query.tenant_id))` inside transaction in `HybridRetrievalEngine.retrieve_hybrid`.
   - `services/api-gateway/src/api_gateway/identity_store.py`:
     - Line 53: `await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tenant_id))` inside transaction in `PostgresIdentityStore.create_guardian`.
     - Line 88: `await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tenant_id))` inside transaction in `PostgresIdentityStore.create_learner`.

2. **Auth & Cryptographic JWT Endpoints (`/api/v1/auth/demo`, `/login`, `/signup`, `/guest`)**:
   - `services/api-gateway/src/api_gateway/auth.py`:
     - Lines 37-64: `create_jwt_token` generates HMAC-SHA256 signed JWTs with role claims (`guardian`, `learner`, `admin`) using standard library `hmac` and `hashlib.sha256`.
     - Lines 66-134: `decode_jwt_token` verifies token structure, algorithm, signature (`hmac.compare_digest`), expiration (`exp > now`), and valid claims (`sub`, `tenant_id`, `role`).
     - Lines 149-165: `require_role` dependency strictly blocks unauthorized roles (e.g. learner token attempting guardian endpoints returns `403 Forbidden`).
     - Lines 168-182: `enforce_token_scope` ensures signed token scope matches request parameters.
   - `services/api-gateway/src/api_gateway/main.py`:
     - Lines 320-375: `POST /api/v1/auth/login` supports roles `learner`, `guardian`, `admin`, validating credentials and returning cryptographically signed tokens.
     - Lines 378-413: `POST /api/v1/auth/signup` registers accounts with role assignment and returns signed JWT tokens.
     - Lines 415-458: `POST /api/v1/auth/demo` provisions demo JWT tokens with fixed demo UUIDs.
     - Lines 461-477: `POST /api/v1/auth/guest` provisions guest learner tokens.

3. **Empirical Test Suite Execution**:
   - `py -m pytest services/api-gateway/tests`: 91 passed in 78.36s.
   - `py -m pytest services/memory-service/tests`: 23 passed in 0.43s.
   - Total test suite count: 114 passed, 0 failed.

4. **Forensic Check for Prohibited Patterns**:
   - Hardcoded test result strings: NONE found in source files.
   - Facade implementations (e.g. `return "ok"` or dummy hardcoded responses in production paths): NONE found. Production repository implementations (`PostgresMemoryStore`, `PostgresIdentityStore`, `PostgresConsentChecker`) use active database queries.
   - Pre-populated result artifacts: NONE found.
   - Security bypasses or disabled proxy checks: NONE found. Fail-closed behavior on HTTP timeouts/errors is enforced across gateway endpoints.

---

## 2. Logic Chain

1. **Step 1 (RLS Integrity)**: `AGENTS.md` Part 2 requires: *"Every database query against `learner_memories` or `learner_interest_profile` MUST issue `SET LOCAL app.current_tenant_id = $1` inside the transaction."*
   - Direct observation of `store.py`, `write_pipeline.py`, `context.py`, `retrieval.py`, and `identity_store.py` confirms every database operation executes `SET LOCAL app.current_tenant_id = $1` as the first statement inside transaction blocks.
   - Thus, RLS tenant isolation is genuinely implemented and compliant with architecture non-negotiables.

2. **Step 2 (Auth/JWT Verification)**: User request requires verification of authentic Auth/JWT handling on `/api/v1/auth/demo`, `/login`, `/signup`.
   - Direct observation of `auth.py` and `main.py` confirms HMAC-SHA256 signature generation and validation, token expiration checks, role-based authorization via `require_role`, and scope enforcement via `enforce_token_scope`.
   - Test suites in `test_auth_endpoints.py` and `test_role_auth.py` verify that invalid roles return HTTP 422, expired/tampered tokens return HTTP 401, and cross-role requests return HTTP 403.
   - Thus, auth handling is genuine and secure.

3. **Step 3 (Absence of Facades or Cheating)**:
   - All production paths connect to `asyncpg.Pool` with parameterized SQL queries.
   - 114 tests passed cleanly across memory service and api-gateway without relying on hardcoded test fixtures or bypasses.

---

## 3. Caveats

- Database tests run in isolated mock mode or in-memory double mode when postgres container connection is not active during test runner setup; production runtime requires PostgreSQL with `pgvector` extension and RLS policies active.

---

## 4. Conclusion

**Verdict: CLEAN**

Milestone 1 (Data Engineering & Security) work products in `services/memory-service/` and `services/api-gateway/` strictly comply with all architecture and child safety non-negotiables specified in `AGENTS.md`. Database operations maintain mandatory transactional RLS tenant scoping (`SET LOCAL app.current_tenant_id = $1`), authentication endpoints issue and verify cryptographically signed JWT tokens with strict role and tenant scope checks, and no facade implementations or integrity violations exist.

---

## 5. Verification Method

To independently verify this verdict, run the following commands in the workspace root (`d:\Vadi Bhen`):

```bash
# 1. Run full test suite for API Gateway and Memory Service
py -m pytest services/api-gateway/tests
py -m pytest services/memory-service/tests

# 2. Inspect RLS statements across memory-service source code
grep -rn "SET LOCAL app.current_tenant_id" services/memory-service/src/
grep -rn "SET LOCAL app.current_tenant_id" services/api-gateway/src/

# 3. Verify cryptographic JWT role check implementation
grep -rn "require_role" services/api-gateway/src/
```

*Invalidation Conditions*: Any failing unit or integration tests in `services/memory-service` or `services/api-gateway`, or any database query against `learner_memories`, `learner_interest_profile`, or `identity` tables executing outside an RLS-scoped transaction.
