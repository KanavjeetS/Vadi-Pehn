"""
Adversarial Challenger Test Suite for Milestone 1 single-process desktop route mounting in start_desktop.py.
Empirically tests all /internal/v1/* routes and /api/v1/* BFF routes under:
1. Normal operations (valid payloads & headers) -> MUST NOT return 404 or 503.
2. Malformed payloads (missing fields, bad types, invalid UUIDs, out-of-bounds numbers) -> MUST return 422 Unprocessable Entity (not 404/503).
3. Auth failures (missing/invalid JWTs or role mismatches) -> MUST return 401 Unauthorized or 403 Forbidden (not 404/503).
4. Edge cases & boundaries.
"""

from __future__ import annotations

import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import start_desktop  # noqa: E402
from api_gateway.auth import create_jwt_token  # noqa: E402


@pytest.fixture(scope="module")
def desktop_client():
    with TestClient(start_desktop.desktop_app) as client:
        yield client


# --- 1. ROUTE MOUNTING INVENTORY ASSERTION ---

def _extract_route_paths(routes) -> list[str]:
    paths: list[str] = []
    for r in routes:
        path = getattr(r, "path", getattr(r, "path_format", None))
        if path is not None:
            paths.append(path)
        if hasattr(r, "routes") and r.routes:
            paths.extend(_extract_route_paths(r.routes))
        elif hasattr(r, "app") and hasattr(r.app, "routes") and r.app.routes:
            paths.extend(_extract_route_paths(r.app.routes))
    return paths


def test_all_required_routes_are_mounted(desktop_client: TestClient):
    """Verify that all required internal and BFF routes are present in desktop_app.routes."""
    mounted_paths = _extract_route_paths(start_desktop.desktop_app.routes)
    
    required_routes = [
        "/internal/v1/orchestration/turn",
        "/internal/v1/voice/turn",
        "/internal/v1/governance/consent/{learner_id}",
        "/internal/v1/safety/check-input",
        "/internal/v1/safety/check-output",
        "/internal/v1/llm/chat/completions",
        "/api/v1/guardian/overview",
        "/api/v1/admin/overview",
        "/internal/v1/governance/incident",
        "/internal/v1/governance/incidents/{tenant_id}",
        "/internal/v1/voice/token",
        "/api/v1/guardian/enroll",
        "/api/v1/guardian/learners",
    ]
    
    for route in required_routes:
        assert route in mounted_paths, f"CRITICAL BUG: Required route '{route}' is missing from desktop_app.routes!"


# --- 2. NORMAL OPERATIONS (No 404, No 503) ---

def test_orchestration_turn_normal(desktop_client: TestClient):
    """POST /internal/v1/orchestration/turn under normal conditions."""
    payload = {
        "session_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "learner_id": str(uuid.uuid4()),
        "age_band": 2,
        "message_text": "Hello Vadi! What is the moon made of?",
        "language": "en",
    }
    resp = desktop_client.post("/internal/v1/orchestration/turn", json=payload)
    assert resp.status_code != 404, "Returned 404 Not Found"
    assert resp.status_code != 503, "Returned 503 Service Unavailable"
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "final_reply" in data
    assert "session_id" in data


def test_voice_turn_normal(desktop_client: TestClient):
    """POST /internal/v1/voice/turn under normal conditions."""
    payload = {
        "session_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "learner_id": str(uuid.uuid4()),
        "age_band": 2,
        "text_fallback": "Hello Vadi via voice mode!",
        "language": "en",
    }
    resp = desktop_client.post("/internal/v1/voice/turn", json=payload)
    assert resp.status_code != 404, "Returned 404 Not Found"
    assert resp.status_code != 503, "Returned 503 Service Unavailable"
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "reply_text" in data
    assert "safety_verdict" in data
    assert "latency_report" in data


def test_governance_consent_normal(desktop_client: TestClient):
    """GET /internal/v1/governance/consent/{learner_id} for target learner."""
    target_learner_id = "00000000-0000-0000-0000-000000000002"
    tenant_id = str(uuid.uuid4())
    resp = desktop_client.get(
        f"/internal/v1/governance/consent/{target_learner_id}",
        headers={"X-Tenant-ID": tenant_id, "X-Internal-Service-Token": ""},
    )
    assert resp.status_code != 404, "Returned 404 Not Found"
    assert resp.status_code != 503, "Returned 503 Service Unavailable"
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["learner_id"] == target_learner_id
    assert "conversation_storage" in data


def test_safety_check_input_normal(desktop_client: TestClient):
    """POST /internal/v1/safety/check-input under normal conditions."""
    payload = {
        "learner_id": str(uuid.uuid4()),
        "message_text": "Can you help me with my science project?",
        "age_band": 1,
    }
    resp = desktop_client.post("/internal/v1/safety/check-input", json=payload)
    assert resp.status_code != 404, "Returned 404 Not Found"
    assert resp.status_code != 503, "Returned 503 Service Unavailable"
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["code"] in ("safe", "classifier_unavailable", "unsafe_general", "unsafe_self_harm")


def test_safety_check_output_normal(desktop_client: TestClient):
    """POST /internal/v1/safety/check-output under normal conditions."""
    payload = {
        "learner_id": str(uuid.uuid4()),
        "draft_reply_text": "Sure! Science is super fun. What topic are you working on?",
    }
    resp = desktop_client.post("/internal/v1/safety/check-output", json=payload)
    assert resp.status_code != 404, "Returned 404 Not Found"
    assert resp.status_code != 503, "Returned 503 Service Unavailable"
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "code" in data


def test_llm_chat_completions_normal(desktop_client: TestClient):
    """POST /internal/v1/llm/chat/completions under normal conditions."""
    payload = {
        "messages": [{"role": "user", "content": "What color is the sky?"}],
        "max_tokens": 100,
        "temperature": 0.5,
    }
    resp = desktop_client.post("/internal/v1/llm/chat/completions", json=payload)
    assert resp.status_code != 404, "Returned 404 Not Found"
    assert resp.status_code != 503, "Returned 503 Service Unavailable"
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "choices" in data


def test_guardian_overview_normal(desktop_client: TestClient):
    """GET /api/v1/guardian/overview with valid guardian JWT."""
    guardian_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    token = create_jwt_token(user_id=guardian_id, tenant_id=tenant_id, role="guardian")
    resp = desktop_client.get(
        "/api/v1/guardian/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code != 404, "Returned 404 Not Found"
    assert resp.status_code != 503, "Returned 503 Service Unavailable"
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["guardian_id"] == guardian_id
    assert data["tenant_id"] == tenant_id
    assert "learners" in data


def test_admin_overview_normal(desktop_client: TestClient):
    """GET /api/v1/admin/overview with valid admin JWT."""
    admin_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    token = create_jwt_token(user_id=admin_id, tenant_id=tenant_id, role="admin")
    resp = desktop_client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code != 404, "Returned 404 Not Found"
    assert resp.status_code != 503, "Returned 503 Service Unavailable"
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["tenant_id"] == tenant_id
    assert "total_learners" in data
    assert "open_incidents_count" in data


# --- 3. MALFORMED PAYLOADS & MISSING FIELDS (Expect 422, NOT 404 or 503) ---

@pytest.mark.parametrize(
    "path,payload",
    [
        ("/internal/v1/orchestration/turn", {}),
        ("/internal/v1/orchestration/turn", {"session_id": "123"}),
        ("/internal/v1/orchestration/turn", {"session_id": "123", "tenant_id": "invalid-uuid", "learner_id": str(uuid.uuid4()), "message_text": "hi"}),
        ("/internal/v1/orchestration/turn", {"session_id": "123", "tenant_id": str(uuid.uuid4()), "learner_id": str(uuid.uuid4()), "age_band": 99, "message_text": "hi"}),
        ("/internal/v1/orchestration/turn", {"session_id": "123", "tenant_id": str(uuid.uuid4()), "learner_id": str(uuid.uuid4()), "message_text": ""}),
        ("/internal/v1/voice/turn", {}),
        ("/internal/v1/voice/turn", {"session_id": "123", "tenant_id": "bad-uuid"}),
        ("/internal/v1/safety/check-input", {}),
        ("/internal/v1/safety/check-input", {"learner_id": "bad-uuid"}),
        ("/internal/v1/safety/check-output", {}),
        ("/internal/v1/safety/check-output", {"learner_id": str(uuid.uuid4())}),
        ("/internal/v1/llm/chat/completions", {}),
        ("/internal/v1/llm/chat/completions", {"messages": "not-a-list"}),
        ("/internal/v1/llm/chat/completions", {"messages": [], "temperature": 10.0}),
    ],
)
def test_malformed_payloads_return_422(desktop_client: TestClient, path: str, payload: dict):
    resp = desktop_client.post(path, json=payload)
    assert resp.status_code == 422, f"Path {path} with payload {payload} expected 422, got {resp.status_code}: {resp.text}"


def test_governance_consent_malformed(desktop_client: TestClient):
    """GET /internal/v1/governance/consent/{learner_id} missing X-Tenant-ID header -> 422."""
    learner_id = str(uuid.uuid4())
    resp = desktop_client.get(f"/internal/v1/governance/consent/{learner_id}")
    assert resp.status_code == 422, f"Expected 422 Unprocessable Entity, got {resp.status_code}"

    resp_bad_uuid = desktop_client.get(
        "/internal/v1/governance/consent/invalid-uuid",
        headers={"X-Tenant-ID": str(uuid.uuid4())},
    )
    assert resp_bad_uuid.status_code == 422, f"Expected 422 Unprocessable Entity, got {resp_bad_uuid.status_code}"


# --- 4. AUTHENTICATION & AUTHORIZATION BOUNDARY TESTS ---

def test_guardian_overview_auth_failures(desktop_client: TestClient):
    """GET /api/v1/guardian/overview auth edge cases."""
    # 1. Missing Authorization header -> 401
    resp_no_auth = desktop_client.get("/api/v1/guardian/overview")
    assert resp_no_auth.status_code == 401, f"Expected 401, got {resp_no_auth.status_code}"

    # 2. Malformed token -> 401
    resp_bad_token = desktop_client.get(
        "/api/v1/guardian/overview", headers={"Authorization": "Bearer invalid.jwt.token"}
    )
    assert resp_bad_token.status_code == 401, f"Expected 401, got {resp_bad_token.status_code}"

    # 3. Wrong role (learner token attempting guardian endpoint) -> 403
    learner_token = create_jwt_token(user_id=str(uuid.uuid4()), tenant_id=str(uuid.uuid4()), role="learner")
    resp_wrong_role = desktop_client.get(
        "/api/v1/guardian/overview", headers={"Authorization": f"Bearer {learner_token}"}
    )
    assert resp_wrong_role.status_code == 403, f"Expected 403, got {resp_wrong_role.status_code}"


def test_admin_overview_auth_failures(desktop_client: TestClient):
    """GET /api/v1/admin/overview auth edge cases."""
    # 1. Missing Authorization header -> 401
    resp_no_auth = desktop_client.get("/api/v1/admin/overview")
    assert resp_no_auth.status_code == 401, f"Expected 401, got {resp_no_auth.status_code}"

    # 2. Guardian token attempting admin endpoint -> 403
    guardian_token = create_jwt_token(user_id=str(uuid.uuid4()), tenant_id=str(uuid.uuid4()), role="guardian")
    resp_wrong_role = desktop_client.get(
        "/api/v1/admin/overview", headers={"Authorization": f"Bearer {guardian_token}"}
    )
    assert resp_wrong_role.status_code == 403, f"Expected 403, got {resp_wrong_role.status_code}"


# --- 5. NON-EXISTENT ROUTE IS 404 ---

def test_nonexistent_route_returns_404(desktop_client: TestClient):
    """Verify that an unmounted route correctly returns 404."""
    resp = desktop_client.get("/internal/v1/nonexistent/endpoint")
    assert resp.status_code == 404
