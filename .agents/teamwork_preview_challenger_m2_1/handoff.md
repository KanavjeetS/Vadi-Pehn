# Handoff Report — Empirical Challenge of Milestone 2 Auth Endpoints & Token Validation

## 1. Observation

Direct empirical observations from executing adversarial tests against `api_gateway` (`services/api-gateway/src/api_gateway/main.py` and `services/api-gateway/src/api_gateway/auth.py`):

1. **Pytest Unit Test Suite Execution (`services/api-gateway/tests/test_auth_endpoints.py`)**:
   - Command: `py -m pytest services/api-gateway/tests/test_auth_endpoints.py -v`
   - Result: 10/10 tests PASSED in 0.20 seconds.
   - Tests verified: `test_auth_demo_learner`, `test_auth_demo_guardian`, `test_auth_demo_admin`, `test_auth_demo_invalid_role`, `test_auth_login_learner`, `test_auth_login_guardian`, `test_auth_login_admin`, `test_auth_login_invalid_role`, `test_auth_login_missing_credentials`, `test_auth_cors_options_preflight`.

2. **Empirical Adversarial Test Suite Execution (`.agents/teamwork_preview_challenger_m2_1/run_empirical_harness.py`)**:
   - Command: `py .agents/teamwork_preview_challenger_m2_1/run_empirical_harness.py`
   - Executed 19 distinct empirical attack & validation scenarios using FastAPI `TestClient`:
     - `/api/v1/auth/demo` with `role="learner"` -> `200 OK` (Valid JWT claims: `role: learner`, `sub: 00000000-0000-0000-0000-000000000003`).
     - `/api/v1/auth/demo` with `role="guardian"` -> `200 OK` (Valid JWT claims: `role: guardian`, `sub: 00000000-0000-0000-0000-000000000002`).
     - `/api/v1/auth/demo` with `role="admin"` -> `200 OK` (Valid JWT claims: `role: admin`, `sub: 00000000-0000-0000-0000-000000000004`).
     - `/api/v1/auth/demo` with invalid `role="hacker"` -> `422 Unprocessable Entity` ("Invalid role 'hacker'. Must be 'learner', 'guardian', or 'admin'.").
     - `/api/v1/auth/login` with `role="learner"`, `role="guardian"`, `role="admin"` -> `200 OK` (All return valid HMAC-SHA256 signed JWTs with corresponding role claims).
     - `/api/v1/auth/login` with invalid `role="hacker"` -> `422 Unprocessable Entity`.
     - `/api/v1/auth/login` with missing `email` or missing `password` -> `422 Unprocessable Entity`.
     - `/api/v1/auth/login` with empty payload `{}` -> `422 Unprocessable Entity`.
     - **JWT Cryptographic Verification**: Signed JWTs returned by endpoints decode cleanly via `api_gateway.auth.decode_jwt_token`.
     - **JWT Tamper Attack**: Modifying the payload role claim from `learner` to `admin` caused `decode_jwt_token` to raise `401 Unauthorized` ("Invalid token signature").
     - **JWT Forged Signature Attack**: Supplying an invalid signature string caused `decode_jwt_token` to raise `401 Unauthorized`.
     - **JWT Expiration Attack**: Crafting an expired token caused `decode_jwt_token` to raise `401 Unauthorized` ("Token has expired").
     - **RBAC Route Protection**:
       - Guardian JWT on `/api/v1/turn` (requires `learner`) -> `403 Forbidden` ("Access denied. Requires role 'learner', but token has role 'guardian'.").
       - Learner JWT on `/api/v1/guardian/overview` (requires `guardian`) -> `403 Forbidden`.
       - Guardian JWT on `/api/v1/admin/overview` (requires `admin`) -> `403 Forbidden`.

---

## 2. Logic Chain

1. **Authentication & Token Decoding Logic Verification**:
   - *Observation*: `api_gateway.auth.create_jwt_token` creates HMAC-SHA256 tokens encoded with base64url and includes claims `sub`, `tenant_id`, `role`, `iat`, `exp`.
   - *Reasoning*: `decode_jwt_token` computes `hmac.new(jwt_secret_key, signing_input, sha256)` and compares using `hmac.compare_digest`.
   - *Empirical Confirmation*: Any modification to header/payload or signature invalidates the signature match, correctly returning HTTP 401 Unauthorized.

2. **Role & Payload Validation**:
   - *Observation*: Both `auth_login` and `auth_demo` in `main.py` explicitly check `payload.role not in ("learner", "guardian", "admin")` and raise HTTP 422 Unprocessable Entity.
   - *Reasoning*: Invalid roles (e.g. `role="hacker"`) are strictly blocked before token creation.
   - *Empirical Confirmation*: Requests with `role="hacker"` consistently return 422 with informative error messages.

3. **RBAC Isolation**:
   - *Observation*: Route handlers use `Depends(require_role("..."))` which extracts and validates token claims via `verify_auth_token`.
   - *Empirical Confirmation*: Cross-role authorization attempts (e.g. Guardian accessing Learner turn endpoint, or Learner accessing Guardian overview endpoint) are strictly denied with 403 Forbidden.

---

## 3. Caveats

- **Default Role in Demo Request**: `AuthDemoRequest` defines `role: str = "learner"`. Therefore, sending an empty JSON payload `{}` to `/api/v1/auth/demo` defaults to `role="learner"` and returns HTTP 200 OK rather than 422. This is intentional for demo convenience (allowing default parameter fallback for demo child login), but should be kept in mind if strict mandatory role payload requirement is desired.
- **No severe caveats**: All security-critical requirements (signature verification, expiry checking, role validation, 400/422 status codes, 403 RBAC enforcement) pass empirically.

---

## 4. Conclusion

**Final Verdict**: `PASS`

The multi-role authentication system (`/api/v1/auth/login`, `/api/v1/auth/demo`) and token validation logic in `api_gateway`:
- Correctly issues signed JWT tokens for `learner`, `guardian`, and `admin` roles with fixed demo UUIDs and correct claims.
- Correctly validates roles and credentials, returning `422 Unprocessable Entity` for invalid roles (`role="hacker"`), missing emails, missing passwords, or malformed payloads.
- Successfully decodes and cryptographically verifies JWT tokens using `api_gateway.auth.decode_jwt_token`.
- Demonstrates fail-closed security against token tampering, signature forging, expired tokens, and cross-role privilege escalation attempts (401/403).

---

## 5. Verification Method

To independently verify these empirical results:

1. **Run the Auth Unit Test Suite**:
   ```powershell
   py -m pytest services/api-gateway/tests/test_auth_endpoints.py -v
   ```

2. **Run the Adversarial Empirical Test Harness**:
   ```powershell
   py .agents/teamwork_preview_challenger_m2_1/run_empirical_harness.py
   ```

3. **Inspect Output JSON**:
   Review `.agents/teamwork_preview_challenger_m2_1/test_results.json` for detailed per-test assertions and execution logs.
