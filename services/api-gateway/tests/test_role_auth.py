"""
Unit and Role-Isolation Tests for Cryptographic JWT Auth.
Verifies:
  1. PRD §3.2 Guardian Verification & Enrollment Flow.
  2. PRD §3.2 Linked Minor Learner Provisioning Flow.
  3. Server-side Role Enforcement: Learner token receives 403 Forbidden on Guardian endpoints.
  4. Server-side Role Enforcement: Guardian token receives 403 Forbidden on Learner conversation endpoints.
"""

import sys
import os
import uuid
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from api_gateway.auth import create_jwt_token
from api_gateway.main import app

client = TestClient(app)


def test_guardian_enrollment_and_learner_provisioning():
    tenant_id = str(uuid.uuid4())

    # 1. Enroll Guardian via NGO verification
    enroll_payload = {
        "tenant_id": tenant_id,
        "guardian_name": "Ramesh Kumar",
        "phone_number": "+919876543210",
        "verification_method": "ngo_cosign",
        "caseworker_id": "caseworker-01",
    }
    res_enroll = client.post("/api/v1/guardian/enroll", json=enroll_payload)
    assert res_enroll.status_code == 201
    guardian_data = res_enroll.json()
    guardian_token = guardian_data["access_token"]
    assert guardian_data["verification_status"] == "verified"
    assert guardian_token is not None

    # 2. Guardian provisions minor learner account
    prov_payload = {
        "display_name": "Alex",
        "age_band": 2,
        "preferred_language": "hi",
    }
    headers = {"Authorization": f"Bearer {guardian_token}"}
    res_prov = client.post(
        "/api/v1/guardian/learners", json=prov_payload, headers=headers
    )
    assert res_prov.status_code == 201
    learner_data = res_prov.json()
    learner_token = learner_data["access_token"]
    assert learner_data["display_name"] == "Alex"
    assert learner_token is not None


def test_learner_token_forbidden_on_guardian_endpoints():
    """CRITICAL SECURITY ASSERTION: Learner token must be rejected with 403 on Guardian routes."""
    tenant_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    learner_token = create_jwt_token(
        user_id=learner_id, tenant_id=tenant_id, role="learner"
    )

    headers = {"Authorization": f"Bearer {learner_token}"}
    consent_payload = {
        "tenant_id": tenant_id,
        "learner_id": learner_id,
        "guardian_id": str(uuid.uuid4()),
        "consent_type": "document_ingestion",
        "granted": True,
    }

    res = client.post("/api/v1/guardian/consent", json=consent_payload, headers=headers)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_guardian_token_forbidden_on_learner_chat_endpoints():
    """CRITICAL ROLE ISOLATION: Guardian token cannot speak as the child on turn endpoints."""
    tenant_id = str(uuid.uuid4())
    guardian_id = str(uuid.uuid4())
    guardian_token = create_jwt_token(
        user_id=guardian_id, tenant_id=tenant_id, role="guardian"
    )

    headers = {"Authorization": f"Bearer {guardian_token}"}
    turn_payload = {
        "session_id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "learner_id": str(uuid.uuid4()),
        "age_band": 2,
        "message_text": "Hello",
    }

    res = client.post("/api/v1/turn", json=turn_payload, headers=headers)
    assert res.status_code == 403


def test_learner_token_success_on_turn_endpoint():
    """Happy path: Learner token accesses /api/v1/turn successfully."""
    tenant_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    learner_token = create_jwt_token(
        user_id=learner_id, tenant_id=tenant_id, role="learner"
    )

    headers = {"Authorization": f"Bearer {learner_token}"}
    turn_payload = {
        "session_id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "learner_id": learner_id,
        "age_band": 2,
        "message_text": "Namaste Vadi!",
    }

    res = client.post("/api/v1/turn", json=turn_payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
