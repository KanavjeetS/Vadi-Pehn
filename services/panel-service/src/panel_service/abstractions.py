"""
Abstract base classes for the Multi-Agent Career Panel Service.
Implements: coding-standards §3 (abstract-first pattern).
PRD §5 (Career Exploration Panels), SD §4.4 (Panel Engine).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from panel_service.models import (
    OCRDocumentRequest,
    OCRDocumentResponse,
    PanelRequest,
    PanelResponse,
    ProfessionalPersona,
)


class PanelSelectionEngine(ABC):
    """
    Abstract interface for Panel Selection & Diversity Routing.
    Implements PRD §5.1: Top-2 interest matches + 1 diversity constraint persona.
    Enforces maximum 3 active relationships limit and 45-day auto-lapse.
    """

    @abstractmethod
    async def select_panel_personas(
        self,
        *,
        learner_id: UUID,
        top_interests: list[str],
        active_relationships: list[str],
    ) -> tuple[list[ProfessionalPersona], str]:
        """
        Selects 3 personas for the career panel.
        Returns (personas_list, status_code).
        Status code is 'success' or 'no_match_fallback'.
        """
        ...

    @abstractmethod
    async def check_relationship_bandwidth(
        self,
        *,
        learner_id: UUID,
        active_relationships_count: int,
    ) -> bool:
        """
        Returns True if the learner is allowed to form a new mentor relationship (count < 3).
        Returns False if the relationship bandwidth limit of 3 is reached.
        """
        ...


class FactValidationEngine(ABC):
    """
    Abstract interface for Fact Validation Agent.
    Cross-references suggestions and career statistics against approved fact source references.
    """

    @abstractmethod
    async def validate_career_claims(
        self,
        *,
        claims: list[str],
        approved_references: list[str],
    ) -> tuple[list[str], bool]:
        """
        Validates claims against references.
        Returns (validated_claims, all_facts_valid).
        """
        ...


class SLMOCRService(ABC):
    """
    Abstract interface for SLM (Qwen2-VL-7B) olmOCR document processing.
    Evaluates confidence score >= 0.85. Routes lower scores to discrepancy_log.
    """

    @abstractmethod
    async def process_document(
        self,
        *,
        request: OCRDocumentRequest,
    ) -> OCRDocumentResponse:
        """
        Extracts structured fields from uploaded academic documents (report cards/certificates).
        Applies PII scrubbing and confidence threshold gating.
        """
        ...


class CrewAIRunner(ABC):
    """
    Abstract interface for executing multi-agent CrewAI turns.
    """

    @abstractmethod
    async def run_panel_turn(
        self,
        *,
        request: PanelRequest,
        personas: list[ProfessionalPersona],
    ) -> PanelResponse:
        """
        Runs the 3 expert personas + fact validation agent turn.
        """
        ...
