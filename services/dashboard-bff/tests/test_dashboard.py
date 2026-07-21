"""
Unit and Integration Tests for Guardian Dashboard BFF (Phase 8).
Verifies:
  1. Guardian surface overview & RLS scoping headers
  2. Admin incident triage overview
"""

from __future__ import annotations

import sys
import os
from uuid import uuid4

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from dashboard_bff.main import app
from api_gateway.auth import create_jwt_token

client = TestClient(app)


def test_health_check() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_guardian_overview_endpoint() -> None:
    tenant_id = str(uuid4())
    guardian_id = str(uuid4())

    token = create_jwt_token(user_id=guardian_id, tenant_id=tenant_id, role="guardian")
    res = client.get(
        "/api/v1/guardian/overview", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    data = res.json()
    assert data["guardian_id"] == guardian_id
    assert data["tenant_id"] == tenant_id
    assert len(data["learners"]) == 1
    assert data["learners"][0]["relationship_health_trend"] == "healthy"
    assert data["consent_status"]["conversation_storage"]


def test_admin_overview_endpoint() -> None:
    tenant_id = str(uuid4())

    token = create_jwt_token(user_id=str(uuid4()), tenant_id=tenant_id, role="admin")
    res = client.get(
        "/api/v1/admin/overview", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == tenant_id
    assert data["total_learners"] == 150
    assert len(data["recent_incidents"]) == 1


def test_learner_token_cannot_access_guardian_bff():
    token = create_jwt_token(
        user_id=str(uuid4()), tenant_id=str(uuid4()), role="learner"
    )
    res = client.get(
        "/api/v1/guardian/overview", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 403


def test_header_only_bff_request_is_unauthorized():
    res = client.get(
        "/api/v1/guardian/overview",
        headers={"X-Tenant-ID": str(uuid4()), "X-Guardian-ID": str(uuid4())},
    )
    assert res.status_code == 401
