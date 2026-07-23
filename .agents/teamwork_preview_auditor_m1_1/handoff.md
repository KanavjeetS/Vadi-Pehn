# Forensic Integrity Audit Report — Milestone 1 Desktop Route Mounting & Connectivity

**Auditor**: `teamwork_preview_auditor_m1_1` (Forensic Integrity Auditor)  
**Target Work Product**: Worker 1 (`teamwork_preview_worker_m1_1`) changes:
- `start_desktop.py`
- `services/api-gateway/src/api_gateway/main.py`
- `services/governance-service/src/governance_service/consent_ledger.py` & `main.py`
- `services/dashboard-bff/src/dashboard_bff/repository.py` & `main.py`
- `services/orchestration/src/orchestration/main.py`
- `services/safety-proxy/src/safety_proxy/main.py`
- `services/api-gateway/tests/test_desktop_routes.py`

**Date**: 2026-07-22  
**Verdict**: **CLEAN**

---

## 1. Forensic Audit Report Summary

**Work Product**: Worker 1 Desktop Preview & Backend Connectivity Implementation  
**Profile**: General Project / Forensic Integrity Audit  
**Verdict**: **CLEAN**

### Phase Results
- **Hardcoded Test Results Check**: PASS — No embedded static outputs or fake assertions.
- **Facade Implementation Check**: PASS — In-memory dev stores (`InMemoryIdentityStore`, `ConsentLedger`, `InMemoryDashboardRepository`, `InMemoryVectorStore`) implement full stateful CRUD interfaces matching production abstract base classes.
- **Bypassed Safety Checks Check**: PASS — NeMo Guardrails safety proxy endpoints (`/check-input`, `/check-output`) and 3.0s timeout fail-closed logic (`CLASSIFIER_UNAVAILABLE`) are fully intact.
- **Fabricated Verification Outputs Check**: PASS — No pre-populated logs or fabricated artifacts.
- **Child Safety Non-Negotiables Check**: PASS — No safety bypass, fail-closed enforcement maintained, RLS tenant isolation queries present (`SET LOCAL app.current_tenant_id = $1`), synthetic test data used exclusively.
- **Behavioral & Runtime Verification Check**: PASS — All 60 pytest integration & unit tests passed (60 passed in 8.47s).

---

## 2. Observation

### 2.1 Direct Code Inspection Findings

1. **`start_desktop.py` (Lines 15–96)**:
   - Environment variables configured for single-process desktop dev mode (`IS_DEV=true`, `DASHBOARD_BFF_URL=http://127.0.0.1:8000`, etc.).
   - `desktop_lifespan` uses `contextlib.AsyncExitStack` to manage `orchestration_lifespan`, `governance_lifespan`, `dashboard_lifespan`, and `api_gateway_lifespan`.
   - Iterates over `sub_apps` and appends missing routes directly to `desktop_app.routes`, fixing sub-app path prefix routing without breaking internal service endpoint matching.
   - Static mounts for `/child`, `/guardian`, `/admin`, and `/` correctly linked.

2. **`services/api-gateway/src/api_gateway/main.py` (Lines 67–85, 200–350)**:
   - `lifespan` initializes `InMemoryIdentityStore()` when `settings.is_dev` is True, and `PostgresIdentityStore(pool)` when `settings.is_dev` is False.
   - Enforces role-based JWT authentication (`require_role("guardian")`, `require_role("learner")`), token scope validation (`enforce_token_scope`), rate-limiting (`check_rate_limit`), and fail-closed error handling (returning HTTP 503 on upstream failures).

3. **`services/governance-service/src/governance_service/main.py` & `consent_ledger.py`**:
   - `ConsentLedger.summary()` method provides aggregate consent status across learners in-memory.
   - `PostgresConsentLedger` retains transaction-scoped RLS (`SET LOCAL app.current_tenant_id = $1`).
   - Lifespan initializes `PostgresConsentLedger` when connected to DB, or `ConsentLedger` in dev mode. Internal token verification (`require_internal_service_token`) is enforced across all internal governance routes.

4. **`services/dashboard-bff/src/dashboard_bff/main.py` & `repository.py`**:
   - `InMemoryDashboardRepository` implements `learners()` and `learner_count()` filtering by `tenant_id` and `guardian_id`.
   - `PostgresDashboardRepository` strictly issues `SET LOCAL app.current_tenant_id = $1` in postgres transactions.

5. **`services/orchestration/src/orchestration/main.py`**:
   - `lifespan` instantiates `OrchestrationGraph` with `InMemoryVectorStore` in dev mode, and `PostgresMemoryStore` + `NomicEmbeddingClient` + `HybridRetrievalEngine` in production mode.
   - Turn execution follows `check_input_safety` -> `retrieve_memory` -> `generate_reply` -> `check_output_safety` -> `write_memory`.

6. **`services/safety-proxy/src/safety_proxy/main.py` & `actions.py`**:
   - `check_input_endpoint` and `check_output_endpoint` execute classification with a `3.0s` `asyncio.wait_for` timeout. On timeout or error, return `SafetyVerdictCode.CLASSIFIER_UNAVAILABLE` (fail-closed).
   - `/internal/v1/llm/chat/completions` returns mock assistant message ONLY in dev mode when vLLM container is unreachable, preserving dev workflow without disabling safety pre/post filters.

7. **`services/api-gateway/tests/test_desktop_routes.py`**:
   - Contains 5 automated tests validating route mounting on `desktop_app`, safety input classification, LLM chat completions proxy, governance consent retrieval, and guardian enrollment / minor provisioning.

### 2.2 Empirical Runtime Test Output

Executed `pytest` across all microservices:
```powershell
py -3 -m pytest services/api-gateway/tests/ services/orchestration/tests/ services/voice-gateway/tests/ services/governance-service/tests/ services/safety-proxy/tests/ services/dashboard-bff/tests/
```
**Output**:
```
======================= 60 passed, 20 warnings in 8.47s =======================
```

---

## 3. Logic Chain

1. **No Facade or Hardcoded Violations**: The implementation of in-memory fallback repositories (`InMemoryIdentityStore`, `ConsentLedger`, `InMemoryDashboardRepository`, `InMemoryVectorStore`) is designed to support single-process desktop dev mode when external Postgres databases are not running. These classes store state and perform filtering dynamically on input data rather than returning static fake strings or hardcoded assertions.
2. **Safety Fail-Closed Integrity**: Inspection of `safety_proxy/main.py` and `actions.py` confirms that input and output safety pre-filters run on every turn. In the event of classification failure, exception, or network timeout (>3.0s), the system returns `SafetyVerdictCode.CLASSIFIER_UNAVAILABLE`, which blocks LLM generation in accordance with Child Safety Non-Negotiable #2.
3. **Tenant Isolation Compliance**: Code inspection of all database repositories (`PostgresIdentityStore`, `PostgresConsentLedger`, `PostgresDashboardRepository`, `PostgresMemoryStore`) confirms that every transaction executes `SET LOCAL app.current_tenant_id = $1` before querying tables, satisfying Part 2 Architecture Non-Negotiable #1.
4. **Empirical Verification**: Execution of the pytest suite confirms 60/60 tests pass cleanly, demonstrating functional correctness across route resolution, authentication, governance, safety, and desktop app lifespans.

---

## 4. Caveats

- **Production Environment Pre-requisite**: When `IS_DEV=false`, the platform requires active PostgreSQL database instances with pgvector extension enabled and vLLM inference server running.

---

## 5. Conclusion

The work product created by Worker 1 (`teamwork_preview_worker_m1_1`) is authentic, robust, compliant with all child safety and architectural non-negotiables, and free of any integrity violations.

**Verdict**: **CLEAN**

---

## 6. Verification Method

### 6.1 Automated Verification Commands

1. **Run Full Test Suite**:
   ```powershell
   py -3 -m pytest services/api-gateway/tests/ services/orchestration/tests/ services/voice-gateway/tests/ services/governance-service/tests/ services/safety-proxy/tests/ services/dashboard-bff/tests/
   ```
   *Expected Result*: 60 passed.

2. **Verify Desktop App Route Mounts**:
   ```powershell
   py -3 -c "import start_desktop; print(len(start_desktop.desktop_app.routes))"
   ```
   *Expected Result*: Prints number of mounted routes (includes all sub-app routes and static mounts).

### 6.2 Manual Inspection Target Files
- `start_desktop.py`
- `services/api-gateway/src/api_gateway/main.py`
- `services/governance-service/src/governance_service/consent_ledger.py`
- `services/dashboard-bff/src/dashboard_bff/repository.py`
- `services/orchestration/src/orchestration/main.py`
- `services/safety-proxy/src/safety_proxy/main.py`
