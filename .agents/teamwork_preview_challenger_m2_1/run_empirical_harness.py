"""
Empirical Test Harness for Auth Endpoints & JWT Security Validation.
Executed by Adversarial Challenger teamwork_preview_challenger_m2_1.
"""

import os
import sys
import json
import time
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "services", "api-gateway", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from api_gateway.main import app
from api_gateway.auth import create_jwt_token, decode_jwt_token, _b64_encode, _b64_decode

client = TestClient(app)

results = []

def record(test_name, passed, detail=""):
    results.append({"test": test_name, "passed": passed, "detail": detail})
    status_str = "PASS" if passed else "FAIL"
    print(f"[{status_str}] {test_name}: {detail}")

print("=== STARTING EMPIRICAL AUTH SUITE ===")

# --- 1. DEMO ENDPOINT TESTS ---
try:
    # Learner role
    res = client.post("/api/v1/auth/demo", json={"role": "learner"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    body = res.json()
    assert body["role"] == "learner"
    token = body["access_token"]
    claims = decode_jwt_token(token)
    assert claims["role"] == "learner"
    assert claims["sub"] == "00000000-0000-0000-0000-000000000003"
    record("Demo Endpoint - role='learner'", True, "Returned valid signed learner JWT")
except Exception as e:
    record("Demo Endpoint - role='learner'", False, str(e))

try:
    # Guardian role
    res = client.post("/api/v1/auth/demo", json={"role": "guardian"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    body = res.json()
    assert body["role"] == "guardian"
    token = body["access_token"]
    claims = decode_jwt_token(token)
    assert claims["role"] == "guardian"
    assert claims["sub"] == "00000000-0000-0000-0000-000000000002"
    record("Demo Endpoint - role='guardian'", True, "Returned valid signed guardian JWT")
except Exception as e:
    record("Demo Endpoint - role='guardian'", False, str(e))

try:
    # Admin role
    res = client.post("/api/v1/auth/demo", json={"role": "admin"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    body = res.json()
    assert body["role"] == "admin"
    token = body["access_token"]
    claims = decode_jwt_token(token)
    assert claims["role"] == "admin"
    assert claims["sub"] == "00000000-0000-0000-0000-000000000004"
    record("Demo Endpoint - role='admin'", True, "Returned valid signed admin JWT")
except Exception as e:
    record("Demo Endpoint - role='admin'", False, str(e))

try:
    # Invalid role 'hacker'
    res = client.post("/api/v1/auth/demo", json={"role": "hacker"})
    assert res.status_code in (400, 422), f"Expected 400/422, got {res.status_code}"
    record("Demo Endpoint - role='hacker' (invalid)", True, f"Status code {res.status_code} returned: {res.json().get('detail')}")
except Exception as e:
    record("Demo Endpoint - role='hacker' (invalid)", False, str(e))

try:
    # Missing role field
    res = client.post("/api/v1/auth/demo", json={})
    assert res.status_code == 422, f"Expected 422, got {res.status_code}"
    record("Demo Endpoint - missing role field", True, "Pydantic validation caught missing role (422)")
except Exception as e:
    record("Demo Endpoint - missing role field", False, str(e))


# --- 2. LOGIN ENDPOINT TESTS ---
try:
    # Valid learner login
    payload = {"email": "child@vadi.demo", "password": "password123", "role": "learner"}
    res = client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    body = res.json()
    claims = decode_jwt_token(body["access_token"])
    assert claims["role"] == "learner"
    record("Login Endpoint - Learner login", True, "Successfully issued token for learner")
except Exception as e:
    record("Login Endpoint - Learner login", False, str(e))

try:
    # Valid guardian login
    payload = {"email": "parent@vadi.demo", "password": "password123", "role": "guardian"}
    res = client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    body = res.json()
    claims = decode_jwt_token(body["access_token"])
    assert claims["role"] == "guardian"
    record("Login Endpoint - Guardian login", True, "Successfully issued token for guardian")
except Exception as e:
    record("Login Endpoint - Guardian login", False, str(e))

try:
    # Valid admin login
    payload = {"email": "admin@vadi.demo", "password": "password123", "role": "admin"}
    res = client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    body = res.json()
    claims = decode_jwt_token(body["access_token"])
    assert claims["role"] == "admin"
    record("Login Endpoint - Admin login", True, "Successfully issued token for admin")
except Exception as e:
    record("Login Endpoint - Admin login", False, str(e))

try:
    # Invalid role 'hacker'
    payload = {"email": "test@vadi.demo", "password": "password123", "role": "hacker"}
    res = client.post("/api/v1/auth/login", json=payload)
    assert res.status_code in (400, 422), f"Expected 400/422, got {res.status_code}"
    record("Login Endpoint - role='hacker'", True, f"Status code {res.status_code} returned")
except Exception as e:
    record("Login Endpoint - role='hacker'", False, str(e))

try:
    # Missing email
    payload = {"email": "", "password": "password123", "role": "learner"}
    res = client.post("/api/v1/auth/login", json=payload)
    assert res.status_code in (400, 422), f"Expected 400/422, got {res.status_code}"
    record("Login Endpoint - missing email", True, f"Status code {res.status_code} returned")
except Exception as e:
    record("Login Endpoint - missing email", False, str(e))

try:
    # Missing password
    payload = {"email": "child@vadi.demo", "password": "", "role": "learner"}
    res = client.post("/api/v1/auth/login", json=payload)
    assert res.status_code in (400, 422), f"Expected 400/422, got {res.status_code}"
    record("Login Endpoint - missing password", True, f"Status code {res.status_code} returned")
except Exception as e:
    record("Login Endpoint - missing password", False, str(e))

try:
    # Missing fields completely
    res = client.post("/api/v1/auth/login", json={})
    assert res.status_code == 422, f"Expected 422, got {res.status_code}"
    record("Login Endpoint - empty payload", True, "Pydantic validation rejected empty payload (422)")
except Exception as e:
    record("Login Endpoint - empty payload", False, str(e))


# --- 3. JWT TOKEN VERIFICATION & ATTACK TESTING ---
try:
    # Valid token verification
    valid_token = create_jwt_token(user_id="user_123", tenant_id="tenant_456", role="guardian")
    claims = decode_jwt_token(valid_token)
    assert claims["sub"] == "user_123"
    assert claims["tenant_id"] == "tenant_456"
    assert claims["role"] == "guardian"
    record("JWT Validation - Valid token", True, "Successfully decoded and verified valid token")
except Exception as e:
    record("JWT Validation - Valid token", False, str(e))

try:
    # Tampered payload (Privilege escalation attempt: learner -> admin)
    valid_token = create_jwt_token(user_id="user_123", tenant_id="tenant_456", role="learner")
    parts = valid_token.split(".")
    payload_dict = json.loads(_b64_decode(parts[1]).decode("utf-8"))
    payload_dict["role"] = "admin"  # Modify claim!
    tampered_payload_b64 = _b64_encode(json.dumps(payload_dict).encode("utf-8"))
    tampered_token = f"{parts[0]}.{tampered_payload_b64}.{parts[2]}"
    
    raised_unauthorized = False
    try:
        decode_jwt_token(tampered_token)
    except Exception as exc:
        if getattr(exc, "status_code", None) == 401:
            raised_unauthorized = True
    assert raised_unauthorized, "Tampered payload token did NOT raise 401 Unauthorized!"
    record("JWT Security - Payload tamper attempt", True, "Signature verification correctly rejected tampered token with 401")
except Exception as e:
    record("JWT Security - Payload tamper attempt", False, str(e))

try:
    # Tampered signature
    valid_token = create_jwt_token(user_id="user_123", tenant_id="tenant_456", role="guardian")
    parts = valid_token.split(".")
    tampered_token = f"{parts[0]}.{parts[1]}.invalidsignature123"
    raised_unauthorized = False
    try:
        decode_jwt_token(tampered_token)
    except Exception as exc:
        if getattr(exc, "status_code", None) == 401:
            raised_unauthorized = True
    assert raised_unauthorized, "Tampered signature did NOT raise 401 Unauthorized!"
    record("JWT Security - Signature tamper attempt", True, "Signature check rejected invalid signature with 401")
except Exception as e:
    record("JWT Security - Signature tamper attempt", False, str(e))

try:
    # Expired token test
    from services.config import settings
    import hmac, hashlib
    now = int(time.time()) - 3600 # 1 hour ago
    hdr = _b64_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8"))
    pld = _b64_encode(json.dumps({"sub": "u1", "tenant_id": "t1", "role": "learner", "iat": now-3600, "exp": now}).encode("utf-8"))
    sig_inp = f"{hdr}.{pld}".encode("utf-8")
    sig = _b64_encode(hmac.new(settings.auth.jwt_secret_key.encode("utf-8"), sig_inp, hashlib.sha256).digest())
    expired_token = f"{hdr}.{pld}.{sig}"
    
    raised_unauthorized = False
    try:
        decode_jwt_token(expired_token)
    except Exception as exc:
        if getattr(exc, "status_code", None) == 401 and "expired" in str(getattr(exc, "detail", "")).lower():
            raised_unauthorized = True
    assert raised_unauthorized, "Expired token did NOT raise 401 Token has expired!"
    record("JWT Security - Expired token rejection", True, "Expired token rejected with 401 detail='Token has expired'")
except Exception as e:
    record("JWT Security - Expired token rejection", False, str(e))


# --- 4. ROLE ENFORCEMENT ON PROTECTED ROUTE TESTS ---
try:
    # Guardian trying to access /api/v1/turn (requires learner)
    guardian_token = create_jwt_token(user_id="g1", tenant_id="t1", role="guardian")
    res = client.post(
        "/api/v1/turn",
        json={
            "session_id": "00000000-0000-0000-0000-000000000010",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "learner_id": "00000000-0000-0000-0000-000000000003",
            "age_band": "8-10",
            "message_text": "Hello",
            "language": "hi",
        },
        headers={"Authorization": f"Bearer {guardian_token}"}
    )
    assert res.status_code == 403, f"Expected 403 Forbidden for Guardian on Learner route, got {res.status_code}"
    record("RBAC Security - Guardian token on /api/v1/turn", True, "403 Forbidden correctly returned")
except Exception as e:
    record("RBAC Security - Guardian token on /api/v1/turn", False, str(e))

try:
    # Learner trying to access /api/v1/guardian/overview (requires guardian)
    learner_token = create_jwt_token(user_id="00000000-0000-0000-0000-000000000003", tenant_id="00000000-0000-0000-0000-000000000001", role="learner")
    res = client.get(
        "/api/v1/guardian/overview",
        headers={"Authorization": f"Bearer {learner_token}"}
    )
    assert res.status_code == 403, f"Expected 403 Forbidden for Learner on Guardian overview, got {res.status_code}"
    record("RBAC Security - Learner token on /api/v1/guardian/overview", True, "403 Forbidden correctly returned")
except Exception as e:
    record("RBAC Security - Learner token on /api/v1/guardian/overview", False, str(e))

try:
    # Guardian trying to access /api/v1/admin/overview (requires admin)
    res = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": f"Bearer {guardian_token}"}
    )
    assert res.status_code == 403, f"Expected 403 Forbidden for Guardian on Admin overview, got {res.status_code}"
    record("RBAC Security - Guardian token on /api/v1/admin/overview", True, "403 Forbidden correctly returned")
except Exception as e:
    record("RBAC Security - Guardian token on /api/v1/admin/overview", False, str(e))

print("\n=== SUMMARY OF EMPIRICAL TEST RESULTS ===")
total = len(results)
passed_cnt = sum(1 for r in results if r["passed"])
failed_cnt = total - passed_cnt
print(f"Total Tests Run: {total}")
print(f"Passed: {passed_cnt}")
print(f"Failed: {failed_cnt}")
print(f"Final Verdict: {'PASS' if failed_cnt == 0 else 'FAIL'}")

output_path = os.path.join(os.path.dirname(__file__), "test_results.json")
with open(output_path, "w") as f:
    json.dump({"total": total, "passed": passed_cnt, "failed": failed_cnt, "verdict": "PASS" if failed_cnt == 0 else "FAIL", "details": results}, f, indent=2)
