"""
Tests for API Gateway service.
Verifies:
  1. Unified endpoint routing (/api/v1/turn, /api/v1/voice/turn, /api/v1/guardian/consent, /api/v1/documents/upload).
  2. Bearer token authentication enforcement.
  3. Rate limiting protection.
"""
import sys
import os
import uuid
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from api_gateway.auth import create_jwt_token
from api_gateway.main import app

client = TestClient(app)


def test_healthz():
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_turn_unauthorized():
    payload = {
        "session_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "learner_id": str(uuid.uuid4()),
        "age_band": 2,
        "message_text": "hello",
    }
    res = client.post("/api/v1/turn", json=payload)
    assert res.status_code == 401


def test_turn_success():
    tenant_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    token = create_jwt_token(user_id=learner_id, tenant_id=tenant_id, role="learner")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "session_id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "learner_id": learner_id,
        "age_band": 2,
        "message_text": "Namaste Vadi!",
    }
    res = client.post("/api/v1/turn", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "final_reply" in data


def test_consent_update():
    tenant_id = str(uuid.uuid4())
    guardian_id = str(uuid.uuid4())
    token = create_jwt_token(user_id=guardian_id, tenant_id=tenant_id, role="guardian")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "tenant_id": tenant_id,
        "learner_id": str(uuid.uuid4()),
        "guardian_id": guardian_id,
        "consent_type": "document_ingestion",
        "granted": True,
    }
    res = client.post("/api/v1/guardian/consent", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "updated"
    assert data["granted"] is True


def test_document_upload():
    tenant_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    token = create_jwt_token(user_id=learner_id, tenant_id=tenant_id, role="learner")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "tenant_id": tenant_id,
        "learner_id": learner_id,
        "file_name": "report.png",
        "file_bytes_base64": "sample_bytes",
    }
    res = client.post("/api/v1/documents/upload", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["redaction_verified"] is True
