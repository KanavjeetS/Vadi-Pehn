"""
Tests for start_desktop.py route mounting and internal service connectivity in desktop dev mode.
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


@pytest.fixture
def desktop_client():
    with TestClient(start_desktop.desktop_app) as client:
        yield client


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


def test_start_desktop_route_mounts(desktop_client: TestClient):
    routes = _extract_route_paths(start_desktop.desktop_app.routes)
    
    expected_routes = [
        "/internal/v1/orchestration/turn",
        "/internal/v1/voice/turn",
        "/internal/v1/governance/consent/{learner_id}",
        "/internal/v1/safety/check-input",
        "/internal/v1/safety/check-output",
        "/internal/v1/llm/chat/completions",
        "/api/v1/guardian/overview",
        "/api/v1/admin/overview",
        "/api/v1/guardian/enroll",
        "/api/v1/guardian/learners",
    ]
    
    for route in expected_routes:
        assert route in routes, f"Route {route} missing from desktop_app.routes"


def test_safety_check_input_endpoint(desktop_client: TestClient):
    resp = desktop_client.post(
        "/internal/v1/safety/check-input",
        json={
            "learner_id": str(uuid.uuid4()),
            "message_text": "Hello Vadi, how are you?",
            "age_band": 1,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["code"] in ("safe", "classifier_unavailable")


def test_llm_chat_completions_endpoint(desktop_client: TestClient):
    resp = desktop_client.post(
        "/internal/v1/llm/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Tell me a joke"}]
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "choices" in data or "id" in data


def test_governance_consent_endpoint(desktop_client: TestClient):
    learner_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    resp = desktop_client.get(
        f"/internal/v1/governance/consent/{learner_id}",
        headers={
            "X-Tenant-ID": tenant_id,
            "X-Internal-Service-Token": "",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["learner_id"] == learner_id


def test_guardian_enroll_and_learners(desktop_client: TestClient):
    tenant_id = str(uuid.uuid4())
    resp = desktop_client.post(
        "/api/v1/guardian/enroll",
        json={
            "tenant_id": tenant_id,
            "guardian_name": "Test Guardian",
            "phone_number": "+919876543210",
            "verification_method": "guardian_otp",
        },
    )
    assert resp.status_code in (200, 201)
    guardian_id = resp.json()["guardian_id"]
    token = create_jwt_token(user_id=guardian_id, tenant_id=tenant_id, role="guardian")

    prov_resp = desktop_client.post(
        "/api/v1/guardian/learners",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "display_name": "Test Minor",
            "age_band": 1,
            "preferred_language": "hi",
        },
    )
    assert prov_resp.status_code == 201
    assert prov_resp.json()["display_name"] == "Test Minor"


def test_guardian_overview_active_request(desktop_client: TestClient):
    guardian_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    token = create_jwt_token(user_id=guardian_id, tenant_id=tenant_id, role="guardian")
    resp = desktop_client.get(
        "/api/v1/guardian/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["guardian_id"] == guardian_id
    assert data["tenant_id"] == tenant_id
    assert "learners" in data


def test_admin_overview_active_request(desktop_client: TestClient):
    admin_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    token = create_jwt_token(user_id=admin_id, tenant_id=tenant_id, role="admin")
    resp = desktop_client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == tenant_id
    assert "total_learners" in data
    assert "open_incidents_count" in data

