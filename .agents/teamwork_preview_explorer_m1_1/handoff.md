# Handoff Report — Milestone 1: Microservice Routing & Internal Connectivity Diagnosis

**Agent**: `teamwork_preview_explorer_m1_1` (Read-only Codebase Researcher — Backend & Routing)  
**Target File**: `d:\Vadi Bhen\.agents\teamwork_preview_explorer_m1_1\handoff.md`  
**Date**: 2026-07-22  

---

## Executive Summary
In single-process desktop development mode (`start_desktop.py`), internal API calls across all 9 microservices fail with `404 Not Found` or `503 Service Unavailable`. This report presents direct code observations, the step-by-step logic chain linking root causes to observed failures, caveats, conclusions, and an independent verification method for implementing Requirement R1 (Milestone 1).

---

## 1. Observation

### 1.1 `start_desktop.py` Mounting Configuration & Environment Setup
- **File**: `start_desktop.py`
- **Lines 19–25**:
  ```python
  os.environ.setdefault("ORCHESTRATION_URL", "http://127.0.0.1:8000")
  os.environ.setdefault("VOICE_GATEWAY_URL", "http://127.0.0.1:8000")
  os.environ.setdefault("GOVERNANCE_SERVICE_URL", "http://127.0.0.1:8000")
  os.environ.setdefault("PANEL_SERVICE_URL", "http://127.0.0.1:8000")
  os.environ.setdefault("SAFETY_PROXY_URL", "http://127.0.0.1:8000")
  os.environ.setdefault("INGESTION_SERVICE_URL", "http://127.0.0.1:8000")
  os.environ.setdefault("IS_DEV", "true")
  ```
  *Note*: `DASHBOARD_BFF_URL` is omitted from `start_desktop.py`.
- **Lines 55–68**:
  ```python
  # Mount internal service microservices for local single-process development
  desktop_app.mount("/internal/v1/documents", ingestion_app)
  desktop_app.mount("/internal/v1/orchestration", orchestration_app)
  desktop_app.mount("/internal/v1/voice", voice_gateway_app)
  desktop_app.mount("/internal/v1/governance", governance_app)
  desktop_app.mount("/internal/v1/panel", panel_app)
  desktop_app.mount("/internal/v1/safety", safety_proxy_app)
  desktop_app.mount("/api/v1/guardian/bff", dashboard_app)
  desktop_app.mount("/api/v1/voice/gateway", voice_gateway_app)

  # Include main Gateway and Dashboard BFF routes directly on desktop_app
  for route in api_gateway_app.routes:
      desktop_app.routes.append(route)
  for route in dashboard_app.routes:
      desktop_app.routes.append(route)
  ```

### 1.2 Microservice Route Definitions
- **`services/orchestration/src/orchestration/main.py`**:
  - Line 113: `@app.post("/internal/v1/orchestration/turn", response_model=TurnState)`
  - Line 133: `@app.post("/internal/v1/orchestration/stream")`
  - Line 120–122:
    ```python
    if graph is None:
        raise HTTPException(status_code=503, detail="orchestration runtime is not ready")
    ```
- **`services/voice-gateway/src/voice_gateway/main.py`**:
  - Line 91: `@app.post("/internal/v1/voice/token", response_model=ConnectTokenResponse)`
  - Line 107: `@app.post("/internal/v1/voice/turn", response_model=VoiceTurnResponse)`
  - Line 118: `@app.websocket("/v1/voice/connect")`
- **`services/governance-service/src/governance_service/main.py`**:
  - Line 75: `@app.get("/internal/v1/governance/consent/{learner_id}", response_model=ConsentRecord)`
  - Line 82–86:
    ```python
    if not isinstance(ledger, PostgresConsentLedger):
        raise HTTPException(status_code=503, detail="governance persistence is not ready")
    ```
  - Line 89: `@app.get("/internal/v1/governance/consent/summary/{tenant_id}")`
  - Line 101: `@app.post("/internal/v1/governance/consent/{learner_id}", response_model=ConsentRecord)`
  - Line 122: `@app.post("/internal/v1/governance/incident", response_model=SafetyIncident)`
  - Line 135: `@app.get("/internal/v1/governance/incidents/{tenant_id}")`
- **`services/safety-proxy/src/safety_proxy/main.py`**:
  - Line 59: `@app.post("/internal/v1/safety/check-input", response_model=SafetyResponseDto)`
  - Line 85: `@app.post("/internal/v1/safety/check-output", response_model=SafetyResponseDto)`
  - Line 107: `@app.post("/internal/v1/llm/chat/completions")`
- **`services/ingestion-service/src/ingestion_service/main.py`**:
  - Line 43: `@app.post("/internal/v1/documents/upload", response_model=ExtractedAcademicRecord)`
  - Line 76: `@app.get("/internal/v1/discrepancies")`
- **`services/panel-service/src/panel_service/main.py`**:
  - Line 47: `@app.post("/internal/v1/panel/trigger", response_model=PanelResponse)`
  - Line 67: `@app.post("/internal/v1/panel/ingest-document", response_model=OCRDocumentResponse)`
- **`services/dashboard-bff/src/dashboard_bff/main.py`**:
  - Lines 38–40:
    ```python
    if settings.is_dev:
        yield
        return
    ```
  - Lines 81–84:
    ```python
    if dashboard_repo is None:
        raise HTTPException(status_code=503, detail="dashboard persistence is not ready")
    ```
- **`services/api-gateway/src/api_gateway/main.py`**:
  - Lines 66–68:
    ```python
    if settings.is_dev:
        yield
        return
    ```
  - Lines 198–200 & 244–246:
    ```python
    if identity_store is None:
        raise HTTPException(status_code=503, detail="identity persistence is not ready")
    ```
  - Lines 327–332 (`handle_text_turn`):
    ```python
    except (httpx.HTTPError, ValueError) as exc:
        logger.error(f"Orchestration turn failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestration service or safety check unavailable (fail-closed)",
        ) from exc
    ```
  - Lines 498–511 (`get_guardian_overview_proxy`):
    ```python
    resp = await client.get(f"{settings.dashboard.url.rstrip('/')}/api/v1/guardian/overview", ...)
    ```

### 1.3 Internal Client Request Call Paths
- **`services/safety-proxy/src/safety_proxy/client.py`**:
  - Lines 65 & 105: Calls `f"{self.base_url}/internal/v1/safety/check-input"` and `f"{self.base_url}/internal/v1/safety/check-output"`. Catches `httpx.HTTPStatusError` (from 404 response) and returns `SafetyVerdict.unavailable()`.
- **`services/orchestration/src/orchestration/llm_client.py`**:
  - Lines 55 & 94: Calls `f"{self.base_url}/internal/v1/llm/chat/completions"`.

---

## 2. Logic Chain

1. **Step 1 — Double-Prefix Routing Mismatch (404 Not Found)**:
   - *Observation*: `start_desktop.py` mounts `orchestration_app` at `/internal/v1/orchestration`. Inside `orchestration_app`, the route is defined as `@app.post("/internal/v1/orchestration/turn")`.
   - *Reasoning*: In Starlette / FastAPI, when a request hits `desktop_app` for `/internal/v1/orchestration/turn`, Starlette matches the mount `/internal/v1/orchestration` and strips that prefix from the request path before passing it to `orchestration_app`. `orchestration_app` receives the path as `/turn`. Because `orchestration_app` registered `/internal/v1/orchestration/turn` rather than `/turn` (or `/`), it cannot match `/turn` and returns `404 Not Found`.
   - *Impact*: The same double-prefix routing mismatch occurs across `safety_proxy_app`, `governance_app`, `voice_gateway_app`, `ingestion_app`, and `panel_app`.

2. **Step 2 — Unmounted Path for LLM Proxy (404 Not Found)**:
   - *Observation*: `SafetyProxyLLMClient` sends requests to `http://127.0.0.1:8000/internal/v1/llm/chat/completions`. `start_desktop.py` mounts `safety_proxy_app` at `/internal/v1/safety`.
   - *Reasoning*: `start_desktop.py` does not mount any app at `/internal/v1/llm`. Request `/internal/v1/llm/chat/completions` fails to match any mount or route on `desktop_app`, resulting in a `404 Not Found` generated directly by `desktop_app`.

3. **Step 3 — 404 Errors Converted to 503 Service Unavailable**:
   - *Observation*: When `api_gateway` calls `ORCHESTRATION_URL/internal/v1/orchestration/turn` or `VOICE_GATEWAY_URL/internal/v1/voice/turn`, `_post_json` executes `response.raise_for_status()`.
   - *Reasoning*: The 404 response from the mounted sub-app triggers `httpx.HTTPStatusError` (which is a subclass of `httpx.HTTPError`). The exception handler in `api_gateway/main.py` catches `httpx.HTTPError` and raises `HTTPException(status_code=503, detail="Orchestration service or safety check unavailable (fail-closed)")`.
   - *Impact*: Internal 404 routing mismatches manifest externally to web and mobile clients as `503 Service Unavailable`.

4. **Step 4 — Unexecuted Sub-Application Lifespans in Single-Process Mode (503 Service Unavailable)**:
   - *Observation*: `orchestration_app` has `@asynccontextmanager async def lifespan(_: FastAPI)` which creates the DB pool and initializes `graph`. `governance_app` initializes `governance_pool` and `ledger`.
   - *Reasoning*: Starlette/FastAPI does NOT automatically run the `@asynccontextmanager lifespan` of sub-applications mounted via `desktop_app.mount(...)`. Consequently, `graph` in `orchestration_app` remains `None`, and `governance_pool` in `governance_app` remains `None`.
   - *Impact*: Any request that reaches `orchestration_app` triggers `if graph is None: raise HTTPException(status_code=503, detail="orchestration runtime is not ready")`. Requests reaching `governance_app` trigger `if not isinstance(ledger, PostgresConsentLedger): raise HTTPException(status_code=503, detail="governance persistence is not ready")`.

5. **Step 5 — Development Bypass Leaving Null Persistence Handlers (503 Service Unavailable)**:
   - *Observation*: In `api_gateway/main.py` and `dashboard_bff/main.py`, the `lifespan` handler executes `if settings.is_dev: yield; return`, skipping initialization of `identity_store` and `dashboard_repo`.
   - *Reasoning*: Even if lifespan handlers were executed, setting `IS_DEV=true` causes `identity_store` and `dashboard_repo` to remain `None`.
   - *Impact*: Endpoints `/api/v1/guardian/enroll`, `/api/v1/guardian/learners`, `/api/v1/guardian/overview`, and `/api/v1/admin/overview` explicitly check for `None` and raise `503 Service Unavailable`.

6. **Step 6 — Unconfigured `DASHBOARD_BFF_URL` (503 Service Unavailable)**:
   - *Observation*: `start_desktop.py` omits `DASHBOARD_BFF_URL` from `os.environ.setdefault(...)`. `settings.dashboard.url` defaults to `http://dashboard-bff:8000`.
   - *Reasoning*: `api_gateway` proxies `/api/v1/guardian/overview` by sending an HTTP request to `http://dashboard-bff:8000/api/v1/guardian/overview`. Outside Docker container networking, `dashboard-bff` hostname is unresolvable.
   - *Impact*: `httpx.get` fails with a DNS/Connect error, caught by `api_gateway` and converted into `503 Service Unavailable ("dashboard service unavailable")`.

---

## 3. Caveats
- **Read-Only Scope**: No application code or configuration files were modified during this investigation.
- **Database Presence Assumption**: Single-process desktop mode assumes either local PostgreSQL DB instances (`vadi_memory` on port 5432, `vadi_governance` on port 5433) are active, or lightweight in-memory fallback stores (`InMemoryIdentityStore`, `InMemoryVectorStore`, `ConsentLedger`) are enabled for developer testing.
- **Network Scope**: Tested in CODE_ONLY environment with local loopback (`http://127.0.0.1:8000`).

---

## 4. Conclusion & Fix Strategy for Requirement R1

### Conclusion
The 404 Not Found and 503 Service Unavailable errors in single-process desktop development mode are caused by:
1. **Route Prefix Duplication**: Mounting microservices with sub-path prefixes (e.g. `/internal/v1/orchestration`) when internal app routes already include the full prefix (`/internal/v1/orchestration/turn`).
2. **Missing Mount**: `SafetyProxyLLMClient` calling `/internal/v1/llm/chat/completions` which has no root mount on `desktop_app`.
3. **Unexecuted Lifespans**: Mounted sub-apps do not run their `lifespan` context managers, leaving `graph`, `governance_pool`, and `dashboard_repo` uninitialized (`None`).
4. **Dev Lifespan Bypass**: `is_dev` checks in `api_gateway` and `dashboard_bff` preventing setup of fallback stores.
5. **Missing Base URL**: Omission of `DASHBOARD_BFF_URL=http://127.0.0.1:8000` in `start_desktop.py`.

### Fix Strategy for Requirement R1

#### Action 1: Fix Sub-App Mounting in `start_desktop.py`
Replace prefix-specific sub-app mounts with direct route inclusion or root-level sub-app mounts:
```python
# In start_desktop.py:
# Include sub-app routers directly onto desktop_app so route paths match incoming requests exact-path:
for app_instance in (
    api_gateway_app,
    orchestration_app,
    voice_gateway_app,
    governance_app,
    panel_app,
    safety_proxy_app,
    ingestion_app,
    dashboard_app,
):
    for route in app_instance.routes:
        desktop_app.routes.append(route)
```
Or mount `orchestration_app`, `safety_proxy_app`, `governance_app`, `voice_gateway_app`, `ingestion_app`, `panel_app` at root `desktop_app.mount("", subapp)` / include routers without path-stripping.

#### Action 2: Trigger Lifespan Initialization for Single-Process Mode
Update `desktop_app` lifespan in `start_desktop.py` to manage and invoke child lifespans / initialize global runtimes:
```python
@asynccontextmanager
async def desktop_lifespan(app: FastAPI):
    async with (
        orchestration_lifespan(orchestration_app),
        governance_lifespan(governance_app),
        dashboard_lifespan(dashboard_app),
        api_gateway_lifespan(api_gateway_app),
    ):
        yield
```

#### Action 3: Enable In-Memory Fallback Stores in `is_dev` Mode
- In `api_gateway/main.py`: When `settings.is_dev` is True and DB pool is unavailable, instantiate `identity_store = InMemoryIdentityStore()` so `/api/v1/guardian/enroll` and `/api/v1/guardian/learners` succeed.
- In `governance_service/main.py`: Allow `ledger = ConsentLedger()` (in-memory) to serve requests when `governance_pool` is `None` in development mode.
- In `dashboard_bff/main.py`: Instantiate `InMemoryDashboardRepository` when `settings.is_dev` is True.

#### Action 4: Centralize Desktop Environment Defaults in `start_desktop.py`
Add `DASHBOARD_BFF_URL` to `start_desktop.py`:
```python
os.environ.setdefault("DASHBOARD_BFF_URL", "http://127.0.0.1:8000")
```

---

## 5. Verification Method

To independently verify the diagnosis and fix:

1. **Verify Route Matching**:
   - Run: `py -3 -c "import start_desktop; print([r.path for r in start_desktop.desktop_app.routes])"`
   - Confirm endpoints `/internal/v1/orchestration/turn`, `/internal/v1/voice/turn`, `/internal/v1/governance/consent/{learner_id}`, `/internal/v1/safety/check-input`, `/internal/v1/safety/check-output`, and `/internal/v1/llm/chat/completions` are mapped directly without prefix duplication.

2. **Verify Lifespan Runtimes**:
   - Check that `orchestration.main.graph` and `governance_service.main.ledger` are initialized on `desktop_app` startup.

3. **Execute Test Suite**:
   - Run: `pytest -v` across all service test suites:
     - `services/api-gateway/tests/`
     - `services/orchestration/tests/`
     - `services/voice-gateway/tests/`
     - `services/governance-service/tests/`
     - `services/safety-proxy/tests/`
     - `services/dashboard-bff/tests/`
     - `services/ingestion-service/tests/`
     - `services/panel-service/tests/`
   - Invalidation Condition: Any 404 or 503 response on internal `/internal/v1/*` endpoints during local single-process execution indicates incomplete route mounting or lifespan setup.
