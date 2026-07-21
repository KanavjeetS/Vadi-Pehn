"""
Unit and Integration Tests for Panel Service (Phase 7).
Verifies:
  1. Top-2 interest matches + 1 diversity constraint persona selection (PRD §5.1)
  2. No-match fallback handling without fabricating personas (PRD §5.1)
  3. Relationship bandwidth limit (max 3 active relationships)
  4. 45-day inactive auto-lapse logic (SD §3.3)
  5. Fact Validation Agent claim filtering against approved references (PRD §5.1)
  6. SLM OCR confidence threshold gating (< 0.85 -> discrepancy queue, SD §3.5)
  7. Mandatory PII scrubbing on OCR text ingestion
  8. End-to-end panel execution workflow
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import sys
import os
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from panel_service.crew import CrewAIPanelRunner
from panel_service.diversity import PanelSelector
from panel_service.fact_validator import FactValidator
from panel_service.models import OCRDocumentRequest, PanelRequest, RelationshipRecord
from panel_service.slm_ocr import QwenSLMOCRService


@pytest.fixture
def panel_selector() -> PanelSelector:
    return PanelSelector()


@pytest.fixture
def fact_validator() -> FactValidator:
    return FactValidator()


@pytest.fixture
def ocr_service() -> QwenSLMOCRService:
    return QwenSLMOCRService(confidence_threshold=0.85)


@pytest.mark.asyncio
async def test_top_2_plus_diversity_selection(panel_selector: PanelSelector) -> None:
    """Verifies selection of top-2 interest matches + 1 diversity persona."""
    learner_id = uuid4()
    top_interests = ["Technology", "Robotics"]

    personas, status = await panel_selector.select_panel_personas(
        learner_id=learner_id,
        top_interests=top_interests,
        active_relationships=[],
    )

    assert status == "success"
    assert len(personas) == 3
    # First 2 are tech matches, 3rd is from another domain (diversity constraint)
    assert personas[0].domain == "Technology"
    assert personas[2].domain != "Technology"  # Diversity persona!


@pytest.mark.asyncio
async def test_no_match_fallback(panel_selector: PanelSelector) -> None:
    """PRD §5.1 ASSERTION: Returns no_match_fallback when no taxonomy match exists; NEVER fabricates a match."""
    learner_id = uuid4()
    top_interests = ["UNMATCHABLE_UNKNOWN_TOPIC_12345"]

    personas, status = await panel_selector.select_panel_personas(
        learner_id=learner_id,
        top_interests=top_interests,
        active_relationships=[],
    )

    assert status == "no_match_fallback"
    assert len(personas) == 0
    assert len(panel_selector.curation_queue) == 1
    assert panel_selector.curation_queue[0]["reason"] == "no_taxonomy_match"


@pytest.mark.asyncio
async def test_relationship_bandwidth_limit(panel_selector: PanelSelector) -> None:
    """PRD §5.1 ASSERTION: Max 3 active relationships allowed per learner."""
    learner_id = uuid4()

    allowed_under_limit = await panel_selector.check_relationship_bandwidth(
        learner_id=learner_id, active_relationships_count=2
    )
    assert allowed_under_limit  # 2 < 3, allowed

    allowed_at_limit = await panel_selector.check_relationship_bandwidth(
        learner_id=learner_id, active_relationships_count=3
    )
    assert not allowed_at_limit  # 3 is limit, blocked!


@pytest.mark.asyncio
async def test_45_day_inactive_auto_lapse(panel_selector: PanelSelector) -> None:
    """SD §3.3 ASSERTION: 45+ days inactive relationships automatically lapse."""
    now = datetime.now(timezone.utc)
    active_rel = RelationshipRecord(
        relationship_id="rel_01",
        learner_id=uuid4(),
        persona_id="p_tech_01",
        introduced_at=now - timedelta(days=20),
        last_interaction_at=now - timedelta(days=10),
    )
    lapsed_rel = RelationshipRecord(
        relationship_id="rel_02",
        learner_id=uuid4(),
        persona_id="p_agri_01",
        introduced_at=now - timedelta(days=60),
        last_interaction_at=now - timedelta(days=50),  # > 45 days ago!
    )

    updated = panel_selector.evaluate_relationship_lapses(
        [active_rel, lapsed_rel], lapse_days=45
    )

    assert updated[0].is_active
    assert not updated[1].is_active
    assert updated[1].lapsed_at is not None


@pytest.mark.asyncio
async def test_fact_validator_filters_hallucinations(
    fact_validator: FactValidator,
) -> None:
    """PRD §5.1 ASSERTION: Fact Validation Agent filters invalid/hallucinated career claims."""
    claims = [
        "Software engineering requires logical thinking and practice.",
        "You can earn $1,000,000 in your first week with zero training.",
        "Building solar grids requires electrical safety knowledge.",
    ]
    approved_refs = ["gov_labor_tech_2025.json"]

    validated, all_valid = await fact_validator.validate_career_claims(
        claims=claims, approved_references=approved_refs
    )

    assert not all_valid
    assert len(validated) == 2
    assert "earn $1,000,000" not in validated[0]
    assert "earn $1,000,000" not in validated[1]


@pytest.mark.asyncio
async def test_slm_ocr_confidence_gating(ocr_service: QwenSLMOCRService) -> None:
    """SD §3.5 ASSERTION: Confidence < 0.85 routes to discrepancy_queue and skips learner profile write."""
    # 1. High Confidence Document
    req_good = OCRDocumentRequest(
        document_id="doc_good",
        tenant_id=uuid4(),
        learner_id=uuid4(),
        document_type="report_card",
        mock_extracted_text="Student Name: Alex. Math A, Science B.",
    )
    res_good = await ocr_service.process_document(request=req_good)
    assert res_good.confidence_score >= 0.85
    assert res_good.passed_confidence_gate
    assert not res_good.routed_to_discrepancy_queue

    # 2. Low Confidence Blurry Document
    req_bad = OCRDocumentRequest(
        document_id="doc_bad",
        tenant_id=uuid4(),
        learner_id=uuid4(),
        document_type="report_card",
        mock_extracted_text="BLURRY LOW_CONFIDENCE text...",
    )
    res_bad = await ocr_service.process_document(request=req_bad)
    assert res_bad.confidence_score < 0.85
    assert not res_bad.passed_confidence_gate
    assert res_bad.routed_to_discrepancy_queue


@pytest.mark.asyncio
async def test_slm_ocr_pii_redaction(ocr_service: QwenSLMOCRService) -> None:
    """Verifies that PII (emails, phones) is redacted during OCR ingestion."""
    req_pii = OCRDocumentRequest(
        document_id="doc_pii",
        tenant_id=uuid4(),
        learner_id=uuid4(),
        document_type="report_card",
        mock_extracted_text="Contact email: teacher@school.edu phone: 555-123-4567. Grade A.",
    )
    res = await ocr_service.process_document(request=req_pii)
    raw_text = res.extracted_fields["raw_text"]
    assert "[REDACTED_EMAIL]" in raw_text
    assert "[REDACTED_PHONE]" in raw_text


@pytest.mark.asyncio
async def test_e2e_crewai_panel_execution() -> None:
    """Verifies end-to-end multi-agent panel execution workflow."""
    selector = PanelSelector()
    runner = CrewAIPanelRunner()

    personas, status = await selector.select_panel_personas(
        learner_id=uuid4(),
        top_interests=["Technology"],
        active_relationships=[],
    )

    req = PanelRequest(
        session_id="sess_panel_01",
        tenant_id=uuid4(),
        learner_id=uuid4(),
        query_text="How do I get started with artificial intelligence?",
        top_interests=["Technology"],
        age_band=2,
    )

    res = await runner.run_panel_turn(request=req, personas=personas)
    assert res.status == "success"
    assert len(res.selected_personas) == 3
    assert res.fact_check_passed
    assert not res.queued_for_curation


@pytest.mark.asyncio
async def test_panel_output_is_blocked_when_safety_blocks_generation() -> None:
    from services.abstractions import MockSafetyClient, SafetyVerdictCode

    runner = CrewAIPanelRunner(
        safety_client=MockSafetyClient(
            default_verdict=SafetyVerdictCode.UNSAFE_GENERAL
        )
    )
    persona = ProfessionalPersona(
        persona_id="p_safe_test",
        code="TECH_DEV",
        title="Synthetic Technology Mentor",
        domain="Technology",
        profession_taxonomy_code="TECH",
        description="[SYNTHETIC_TEST_CASE]",
        approved_fact_source_ref="synthetic_reference.json",
    )
    request = PanelRequest(
        session_id="panel_safety_test",
        tenant_id=uuid4(),
        learner_id=uuid4(),
        query_text="[SYNTHETIC_TEST_CASE] technology",
        top_interests=["Technology"],
        age_band=2,
    )

    response = await runner.run_panel_turn(request=request, personas=[persona])

    assert response.synthesized_guidance == ""
    assert not response.fact_check_passed
    assert len(runner.safety_client.output_calls) == 2
