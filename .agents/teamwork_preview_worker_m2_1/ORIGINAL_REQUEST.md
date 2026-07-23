## 2026-07-22T11:02:10Z

You are teamwork_preview_worker_m2_1 operating as @backend-engineer / Full-Stack Engineer to implement Milestone 2 (Requirement R2: Multi-Role Authentication, Login & Signup System with Demo Toggles).
Your working directory is `d:\Vadi Bhen\.agents\teamwork_preview_worker_m2_1`.

Read the following before starting:
- `d:\Vadi Bhen\PROJECT.md`
- `d:\Vadi Bhen\.agents\AGENTS.md`
- `d:\Vadi Bhen\.agents\skills\vadi-pehn-development\SKILL.md`
- Explorer 2 handoff report: `d:\Vadi Bhen\.agents\teamwork_preview_explorer_m2_1\handoff.md`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Mission (Milestone 2 — Requirement R2):
1. **Backend Auth API Endpoints (`services/api-gateway/src/api_gateway/main.py`)**:
   - Implement `POST /api/v1/auth/login`:
     - Accepts JSON `{ "email": "...", "password": "...", "role": "learner"|"guardian"|"admin" }`.
     - Validates role and returns signed JWT `access_token`, `tenant_id`, `user_id` (learner_id or guardian_id or admin_id), and `role`.
   - Implement `POST /api/v1/auth/demo`:
     - Accepts JSON `{ "role": "learner"|"guardian"|"admin" }`.
     - Generates and returns a signed JWT for demo access with fixed demo UUIDs:
       - Default Demo `tenant_id`: `00000000-0000-0000-0000-000000000001`
       - Demo `guardian_id`: `00000000-0000-0000-0000-000000000002`
       - Demo `learner_id`: `00000000-0000-0000-0000-000000000003`
       - Demo `admin_id`: `00000000-0000-0000-0000-000000000004`
     - Uses `create_jwt_token` from `api_gateway.auth`.
   - Ensure CORS and OPTIONS preflight requests for `/api/v1/auth/*` are enabled.

2. **Web Frontend Pages & UI (`webapp/login.html` & `webapp/signup.html`)**:
   - Create `webapp/login.html`:
     - Modern, beautiful dark-themed glassmorphism styling consistent with Vadi-Pehn branding (`#0f172a`, purple gradients, clean cards).
     - Role selection tabs (`Learner / Child`, `Guardian / Parent`, `System Admin`).
     - Login form (`Email`, `Password`, `Login` button).
     - **Quick 'Demo Accounts' Section**: Three prominent one-click demo login buttons:
       - `🚀 One-Click Child Demo` -> logs in as demo learner and redirects to `/child/`
       - `🛡️ One-Click Guardian Demo` -> logs in as demo guardian and redirects to `/guardian/`
       - `⚙️ One-Click Admin Demo` -> logs in as demo admin and redirects to `/admin/`
     - On successful login, stores `access_token`, `tenant_id`, `role`, `user_id`, `learner_id`, `guardian_id` securely in `localStorage` (and fallback `sessionStorage`).
   - Create `webapp/signup.html`:
     - Matching UI styling with role selection cards (`Child Companion`, `Guardian Account`, `System Admin`).
     - Signup form inputs, validation, role routing upon account creation, and link to `/login.html`.
   - Update `webapp/index.html`:
     - Update navigation buttons (`btn-signin`, `btn-primary-kid`, `btn-secondary-guardian`) to route to `/login.html` or `/signup.html` instead of bypassing auth.

3. **Frontend Token Authorization**:
   - In `webapp/child/child.js`, `webapp/guardian/guardian.js`, and `webapp/admin/admin.js` (or common script):
     - Ensure API requests include `Authorization: Bearer <vadi_access_token>` and `X-Tenant-ID: <vadi_tenant_id>` from `localStorage`.

4. **Testing**:
   - Add unit/integration tests in `services/api-gateway/tests/test_auth_endpoints.py` testing `/api/v1/auth/login` and `/api/v1/auth/demo` for all 3 roles (`learner`, `guardian`, `admin`).
   - Run `pytest` and `ruff check`.

Write your handoff report to `d:\Vadi Bhen\.agents\teamwork_preview_worker_m2_1\handoff.md` with file paths, test results, and layout compliance check.
When complete, notify parent via send_message.
