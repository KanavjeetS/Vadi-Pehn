# Handoff Report — Codebase Research: Auth, Portals & Synthetic Data Seeding

## 1. Observation

Direct code observations with exact file paths, line numbers, and verbatim snippets:

### Auth & Navigation
- **Missing HTML Web Pages**:
  - `webapp/login.html`: Does **NOT** exist in `webapp/`.
  - `webapp/signup.html`: Does **NOT** exist in `webapp/`.
  - `webapp/index.html` (lines 437, 450, 451):
    ```html
    437: <a href="/guardian/" class="btn-signin">Guardian sign in</a>
    450: <a href="/child/" class="btn-primary-kid">Enter the kid space →</a>
    451: <a href="/guardian/" class="btn-secondary-guardian">Open guardian dashboard</a>
    ```
    Links directly to `/child/` and `/guardian/` without routing through authentication or role-selection UI.
- **API Gateway Auth Implementation**:
  - `services/api-gateway/src/api_gateway/main.py`:
    - Line 186: `POST /api/v1/guardian/enroll` (Guardian verification & JWT issuance with `role: "guardian"`).
    - Line 231: `POST /api/v1/guardian/learners` (Learner account provisioning with `role: "learner"`).
    - Line 271: `POST /api/v1/auth/guest` (Guest learner token issuance for `tenant_id: 00000000-0000-0000-0000-000000000001` and `learner_id: 00000000-0000-0000-0000-000000000002`).
  - `services/api-gateway/src/api_gateway/auth.py`:
    - Line 37: `create_jwt_token(*, user_id, tenant_id, role)` supports roles `("guardian", "learner", "admin")`.
    - Line 149: `require_role(required_role)` enforces exact role match (`token_payload.get("role") == required_role`).
  - **Missing API Endpoints**:
    - No `/api/v1/auth/login` endpoint for authenticating registered guardians/admins.
    - No `/api/v1/auth/demo` endpoint for One-Click Demo access (`learner`, `guardian`, `admin`).

### Guardian Dashboard (`webapp/guardian/index.html`)
- **Hardcoded Mock Stat Cards**:
  - `webapp/guardian/index.html` lines 444–465 contain static values:
    ```html
    445: <div class="stat-val">2h 52m</div>
    451: <div class="stat-val">5 days</div>
    457: <div class="stat-val">Curious</div>
    463: <div class="stat-val">World exposure</div>
    ```
- **Broken DOM Selector Bug**:
  - `webapp/guardian/index.html` lines 818–840:
    ```javascript
    828: const statCards = document.querySelectorAll('.stat-card h3');
    829: if (statCards.length >= 4) {
    830:     statCards[0].innerText = data.active_learners || '1';
    831:     ...
    ```
    Line 828 queries `.stat-card h3`, but stat card values are rendered inside `<div class="stat-val">` elements (lines 260–261 / 445–463). `statCards.length` is always `0`, causing overview API response updates to fail silently.
- **BFF Overview Data Model**:
  - `services/dashboard-bff/src/dashboard_bff/main.py` lines 70–119 (`get_guardian_overview`) returns `GuardianOverview` (`learners` list and `consent_status` dict). It does not compute aggregate values for total weekly engagement hours, streak, or mood trends.

### Admin Dashboard (`webapp/admin/index.html`)
- **Broken Iframe**:
  - `webapp/admin/index.html` lines 126–130:
    ```html
    <div class="card" style="margin-bottom: 24px;">
        <h3>Live Langfuse Tracing Dashboard</h3>
        <p style="color: var(--muted); font-size: 14px; margin-bottom: 16px;">Connected Host: <strong id="langfuse-host" style="color: #fff;">http://localhost:3000</strong></p>
        <iframe class="dashboard-frame" src="http://localhost:3000" title="Langfuse Dashboard"></iframe>
    </div>
    ```
    This iframe attempts to load `http://localhost:3000`, which displays a broken/blank connection failure frame when running standalone without an external Langfuse container on port 3000.

### Startup Seeding
- **Database Migrations & Seeding State**:
  - `db/migrations/` (001–006) defines DDL for `tenants`, `guardians`, `learners`, `learner_memories`, `consent_records`, and `safety_incidents`.
  - `scripts/migrate_cloud_db.py` applies DDL migrations but contains zero DML `INSERT` statements.
  - No `db/seed.sql` or startup seeding script exists in `db/` or `start_desktop.py`.

---

## 2. Logic Chain

1. **Auth & Routing Deficit**:
   - *Observation*: `webapp/login.html` and `webapp/signup.html` are missing; `webapp/index.html` bypasses auth and links directly to `/child/` and `/guardian/`.
   - *Reasoning*: To enforce multi-role auth (Milestone 2) and enable one-click demo login, we need `login.html` and `signup.html` containing role selector cards/buttons that store signed JWT tokens in `sessionStorage` (`vadi_access_token`, `vadi_tenant_id`, `vadi_role`, `vadi_learner_id`/`vadi_guardian_id`) and route `learner` -> `/child/`, `guardian` -> `/guardian/`, `admin` -> `/admin/`.
   - *API Requirement*: `api_gateway/main.py` requires `POST /api/v1/auth/login` and `POST /api/v1/auth/demo` to issue signed JWTs using `create_jwt_token` for any of the 3 roles.

2. **Guardian Overview Data Flow Disconnect**:
   - *Observation*: `webapp/guardian/index.html` line 828 queries `document.querySelectorAll('.stat-card h3')` (returns 0 elements), and `dashboard_bff/main.py:70-119` returns `GuardianOverview` without weekly engagement hours, streak, common mood, or growing skill fields.
   - *Reasoning*: Fixing line 828 to query `document.querySelectorAll('.stat-card .stat-val')` and enriching `GuardianOverview` (or adding helper fields in `dashboard_bff/models.py`) will connect the frontend directly to `/api/v1/guardian/overview`.

3. **Admin Dashboard Observability Fix**:
   - *Observation*: `webapp/admin/index.html` lines 126–130 renders a broken `http://localhost:3000` iframe.
   - *Reasoning*: Standalone desktop mode operates locally without an external Langfuse container on port 3000. Removing the iframe and implementing native Chart.js charts (Trace Volume, Safety Pass vs Block Rate, SLA Compliance, Voice Latency Distribution) backed by `/api/v1/admin/observability/metrics` and `/api/v1/admin/overview` provides standalone, native admin observability.

4. **Synthetic Data Seeding Requirement**:
   - *Observation*: `db/migrations/` creates schema tables but no test data. Fresh databases return empty lists for learners, memories, consent, and incidents.
   - *Reasoning*: Creating `db/seed_synthetic_data.py` (or `db/seed.sql`) with fixed synthetic UUIDs (`tenant_id: 00000000-0000-0000-0000-000000000001`, `guardian_id: 00000000-0000-0000-0000-000000000002`, `learner_id: 00000000-0000-0000-0000-000000000003` for 'Aria'), synthetic 1536-dim vector memories, active consent settings, and safety incidents with `sla_deadline = NOW() + INTERVAL '15 minutes'`, and invoking it on startup in `start_desktop.py` will guarantee a seeded environment out-of-the-box.

---

## 3. Caveats

- **Read-Only Scope**: This report contains investigation and fix strategies only. Application code modifications must be executed by subsequent implementer tasks.
- **Desktop Single-Process Mounting**: In `start_desktop.py`, route ordering between `api_gateway_app.routes` and `dashboard_app.routes` must be reconciled so `/api/v1/guardian/overview` and `/api/v1/admin/overview` invoke `dashboard_bff` logic directly without unnecessary loopback HTTP requests.

---

## 4. Conclusion

The Vadi-Pehn platform has strong core auth logic (`api_gateway/auth.py` JWT creation and role checking) and microservice routing, but requires:
1. **Web UI Creation**: `webapp/login.html` and `webapp/signup.html` with One-Click Demo buttons.
2. **Backend Auth Endpoints**: `POST /api/v1/auth/login` and `POST /api/v1/auth/demo` in `api_gateway/main.py`.
3. **Guardian Portal Fix**: Correct DOM selector in `webapp/guardian/index.html:828` and enrich `GuardianOverview` response model in `dashboard_bff`.
4. **Admin Observability Fix**: Remove broken port 3000 iframe in `webapp/admin/index.html` and replace with native Chart.js charts connected to `/api/v1/admin/overview` and `/api/v1/admin/observability/metrics`.
5. **Synthetic Startup Seeding**: Implement startup data seeding (`db/seed_synthetic_data.py`) for default tenant, guardian, learner, memories, consent, and 15-min SLA safety incidents.

---

## 5. Verification Method

To independently verify existing functionality and future implementations:

1. **Run Existing Auth & BFF Unit Tests**:
   ```powershell
   py -m pytest services/api-gateway/tests services/dashboard-bff/tests
   ```
   *Expected Output*: 15 passed tests.

2. **Verify Auth API Endpoints (Post-Implementation)**:
   ```powershell
   # Test Demo Auth Endpoint
   curl -X POST http://127.0.0.1:8000/api/v1/auth/demo -H "Content-Type: application/json" -d "{\"role\": \"guardian\"}"
   # Expected: 200 OK with access_token and role="guardian"
   ```

3. **Verify Portal Rendering**:
   - `http://127.0.0.1:8000/login.html` -> Verify Demo Account buttons work and store JWT in `sessionStorage`.
   - `http://127.0.0.1:8000/guardian/` -> Verify stat cards display values populated from `/api/v1/guardian/overview`.
   - `http://127.0.0.1:8000/admin/` -> Verify iframe is replaced with native Chart.js charts.
