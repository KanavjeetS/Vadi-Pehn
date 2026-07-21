"""
CrewAI Multi-Agent Panel Execution Engine with Voice TTS Integration.
Implements: PRD §5.1 (3-agent panel + fact validation agent turn),
           PRD §4 (Relational Safety: sibling-framed persona handoffs),
           PRD §6.5 (Voice TTS handoffs for panel personas).
"""

from __future__ import annotations

import base64
import os
import uuid
from typing import Any

import jinja2

from panel_service.abstractions import CrewAIRunner, FactValidationEngine
from panel_service.curator_agent import CuratorAgent
from panel_service.fact_validator import FactValidator
from panel_service.models import PanelRequest, PanelResponse, ProfessionalPersona
from panel_service.professional_agent import ProfessionalAgent
from services.abstractions import MockSafetyClient, SafetyClient


class CrewAIPanelRunner(CrewAIRunner):
    """
    CrewAI Multi-Agent Panel Engine.
    Executes turns with top-2 matched personas + 1 diversity persona + 1 fact validator agent.
    Supports voice TTS audio handoffs framed by the sibling persona.
    """

    def __init__(
        self,
        fact_validator: FactValidationEngine | None = None,
        tts_service: Any | None = None,
        safety_client: SafetyClient | None = None,
        professional_agent: ProfessionalAgent | None = None,
        curator_agent: CuratorAgent | None = None,
    ) -> None:
        self.fact_validator = fact_validator or FactValidator()
        self.tts_service = tts_service
        self.safety_client = safety_client or MockSafetyClient()
        self.professional_agent = professional_agent or ProfessionalAgent()
        self.curator_agent = curator_agent or CuratorAgent()
        self._init_jinja_env()

    def _init_jinja_env(self) -> None:
        personas_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "orchestration", "personas"
            )
        )
        if os.path.exists(personas_dir):
            self.jinja_env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(personas_dir)
            )
        else:
            self.jinja_env = None

    def _render_persona_prompt(self, template_name: str, age_band: int) -> str | None:
        if not self.jinja_env:
            return None
        try:
            template = self.jinja_env.get_template(f"{template_name}.jinja2")
            return template.render(age_band=age_band)
        except Exception:
            return None

    async def run_panel_turn(
        self,
        *,
        request: PanelRequest,
        personas: list[ProfessionalPersona],
    ) -> PanelResponse:
        """
        Executes panel turn across selected personas, runs fact validator agent,
        applies sibling handoff framing, and synthesizes mentor voice audio.
        """
        panel_id = f"panel_{uuid.uuid4().hex[:8]}"

        if not personas:
            return PanelResponse(
                panel_id=panel_id,
                session_id=request.session_id,
                status="no_match_fallback",
                selected_personas=[],
                sibling_framing_intro="Vadi: Main abhi tumhare liye perfect career expert dhoond raha hoon!",
                synthesized_guidance="No clean taxonomy match found for the requested topic.",
                fact_check_passed=True,
                queued_for_curation=True,
            )

        # 1. Generate Sibling Handoff Framing (PRD §4 Relational Safety)
        lead_persona = personas[0]
        sibling_intro = (
            f"Vadi: Main chahta hoon ki tum humari guest expert {lead_persona.title} se milo! "
            f"Woh tumhein {lead_persona.domain} ke baare mein real guidance dengi."
        )

        # 2. Synthesize guidance using versioned Jinja2 prompt if available
        custom_prompt = self._render_persona_prompt(
            lead_persona.code.lower(), request.age_band
        )

        professional_guidance = await self.professional_agent.generate_career_guidance(
            learner_id=request.learner_id,
            interests=request.top_interests,
            query=request.query_text,
        )
        guidance_claims = [
            str(professional_guidance["response"]),
            *[str(milestone) for milestone in professional_guidance["milestones"]],
        ]

        if custom_prompt:
            guidance_claims[0] = (
                f"{lead_persona.title}: {custom_prompt.splitlines()[0]}"
            )

        # 3. Fact Validation Agent runs after career suggestion agents
        validated_claims, fact_check_passed = (
            await self.fact_validator.validate_career_claims(
                claims=guidance_claims,
                approved_references=[p.approved_fact_source_ref for p in personas],
            )
        )

        learner_age = {1: 9, 2: 12, 3: 15}[request.age_band]
        curated = await self.curator_agent.curate_and_verify_context(
            tenant_id=request.tenant_id,
            learner_age=learner_age,
            raw_facts=validated_claims,
        )
        synthesized_text = " ".join(curated["verified_facts"])

        output_verdict = await self.safety_client.check_output(
            learner_id=request.learner_id,
            draft_reply_text=synthesized_text,
            tenant_id=request.tenant_id,
        )
        if output_verdict.blocks_generation:
            safe_fallback = "Vadi will find a safer way to explore this topic with you."
            fallback_verdict = await self.safety_client.check_output(
                learner_id=request.learner_id,
                draft_reply_text=safe_fallback,
                tenant_id=request.tenant_id,
            )
            synthesized_text = "" if fallback_verdict.blocks_generation else safe_fallback
            fact_check_passed = False

        # 4. Optional TTS Voice Synthesis for Panel Persona (PRD §6.5)
        audio_b64: str | None = None
        if self.tts_service and synthesized_text:
            try:
                audio_bytes = await self.tts_service.synthesize(
                    synthesized_text, language="hi"
                )
                if audio_bytes:
                    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            except Exception:
                audio_b64 = None

        return PanelResponse(
            panel_id=panel_id,
            session_id=request.session_id,
            status="success",
            selected_personas=personas,
            sibling_framing_intro=sibling_intro,
            synthesized_guidance=synthesized_text,
            persona_audio_base64=audio_b64,
            fact_check_passed=fact_check_passed,
            queued_for_curation=False,
        )
