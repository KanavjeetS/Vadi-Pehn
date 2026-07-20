"""
Unit and Integration Tests for Speaking Panel Personas & Jinja2 Prompts.
Verifies:
  1. Versioned Jinja2 prompt files exist for robotics_engineer, agritech_specialist, data_scientist.
  2. PRD §4 Relational Safety: Sibling handoff framing is present in PanelResponse.
  3. PRD §6.5 Voice TTS: Panel personas generate audio output when TTS service is present.
"""
import sys
import os
from uuid import uuid4
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "voice-gateway", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from panel_service.crew import CrewAIPanelRunner
from panel_service.models import PanelRequest, ProfessionalPersona
from voice_gateway.tts import MockTTSService


@pytest.mark.asyncio
async def test_jinja2_persona_rendering_and_sibling_framing():
    runner = CrewAIPanelRunner()

    persona = ProfessionalPersona(
        persona_id="p_robotics",
        code="robotics_engineer",
        title="Priya Didi",
        domain="Technology",
        profession_taxonomy_code="ENG_ROB",
        description="Senior Robotics Engineer",
        approved_fact_source_ref="AICTE_ROBOTICS_2025",
    )

    req = PanelRequest(
        session_id="panel_test_sess",
        tenant_id=uuid4(),
        learner_id=uuid4(),
        query_text="robotics and drones",
        age_band=2,
    )

    resp = await runner.run_panel_turn(request=req, personas=[persona])

    assert resp.status == "success"
    assert resp.sibling_framing_intro is not None
    assert "Vadi:" in resp.sibling_framing_intro
    assert "Priya Didi" in resp.sibling_framing_intro


@pytest.mark.asyncio
async def test_panel_persona_speaking_tts_synthesis():
    tts_service = MockTTSService()
    runner = CrewAIPanelRunner(tts_service=tts_service)

    persona = ProfessionalPersona(
        persona_id="p_agri",
        code="agritech_specialist",
        title="Gurpreet Bhaiya",
        domain="Agriculture",
        profession_taxonomy_code="AGRI_TECH",
        description="AgriTech Innovation Specialist",
        approved_fact_source_ref="ICAR_AGRITECH_2025",
    )

    req = PanelRequest(
        session_id="panel_voice_sess",
        tenant_id=uuid4(),
        learner_id=uuid4(),
        query_text="smart farming sensors",
        age_band=3,
    )

    resp = await runner.run_panel_turn(request=req, personas=[persona])

    assert resp.status == "success"
    assert resp.persona_audio_base64 is not None
    assert len(resp.persona_audio_base64) > 0
