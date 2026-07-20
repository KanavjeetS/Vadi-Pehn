"""
Tests for Multi-Modal Document Ingestion & PII Redaction Service.
Verifies:
  1. Secondary spatial mask verification (PRD §9.2).
  2. Confidence gating (0.85 threshold) & discrepancy log routing (PRD §9).
  3. Governance consent check before ingestion.
"""
import sys
import os
import uuid
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from ingestion_service.main import app, service
from ingestion_service.service import DocumentIngestionService, DocumentUploadRequest, MockGovernanceConsentChecker

client = TestClient(app)


@pytest.mark.asyncio
async def test_process_document_upload_success():
    tenant_id = uuid.uuid4()
    learner_id = uuid.uuid4()

    req = DocumentUploadRequest(
        tenant_id=tenant_id,
        learner_id=learner_id,
        file_name="report_card_synthetic.png",
        file_bytes_base64="synthetic_report_card_image_data",
        in_app_expected_grade="A",
    )

    ingestion_svc = DocumentIngestionService()
    record = await ingestion_svc.process_document_upload(req)

    assert record.document_id is not None
    assert record.redaction_verified is True
    assert record.ocr_confidence >= 0.85
    assert record.requires_discrepancy_review is False


@pytest.mark.asyncio
async def test_process_document_upload_low_confidence_routes_to_discrepancy():
    tenant_id = uuid.uuid4()
    learner_id = uuid.uuid4()

    req = DocumentUploadRequest(
        tenant_id=tenant_id,
        learner_id=learner_id,
        file_name="low_conf_report_card.png",
        file_bytes_base64="low_conf_image_data",
    )

    ingestion_svc = DocumentIngestionService()
    record = await ingestion_svc.process_document_upload(req)

    assert record.ocr_confidence < 0.85
    assert record.requires_discrepancy_review is True
    assert any("below minimum threshold" in r for r in record.discrepancy_reasons)


@pytest.mark.asyncio
async def test_process_document_upload_consent_denied_raises():
    tenant_id = uuid.uuid4()
    learner_id = uuid.uuid4()

    denied_checker = MockGovernanceConsentChecker(allowed_learners=set())
    ingestion_svc = DocumentIngestionService(consent_checker=denied_checker)

    req = DocumentUploadRequest(
        tenant_id=tenant_id,
        learner_id=learner_id,
        file_name="report_card.png",
        file_bytes_base64="synthetic_data",
    )

    with pytest.raises(PermissionError, match="not granted"):
        await ingestion_svc.process_document_upload(req)


def test_fastapi_upload_endpoint():
    tenant_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    payload = {
        "tenant_id": tenant_id,
        "learner_id": learner_id,
        "file_name": "synthetic_card.png",
        "file_bytes_base64": "sample_data",
        "in_app_expected_grade": "A",
    }

    response = client.post("/internal/v1/documents/upload", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["redaction_verified"] is True
