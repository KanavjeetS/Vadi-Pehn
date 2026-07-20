"""
Panel Selection, Diversity Routing, and Relationship Bandwidth Enforcement.
Implements: PRD §5.1 (3-agent panel composition, top-2 + 1 diversity, relationship bandwidth limit).
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import UUID

from panel_service.abstractions import PanelSelectionEngine
from panel_service.models import ProfessionalPersona, RelationshipRecord


# Pre-defined catalog of 8 domain expert personas (PRD §5.1, SD §4.4 MoE taxonomy)
DEFAULT_PERSONA_CATALOG: list[ProfessionalPersona] = [
    ProfessionalPersona(
        persona_id="p_tech_01",
        code="TECH_DEV",
        title="Software & Robotics Engineer",
        domain="Technology",
        profession_taxonomy_code="TECH",
        description="Builds software systems, AI algorithms, and autonomous drones.",
        approved_fact_source_ref="gov_labor_tech_2025.json",
    ),
    ProfessionalPersona(
        persona_id="p_agri_01",
        code="AGRI_BOT",
        title="Agricultural Technologist",
        domain="Agriculture",
        profession_taxonomy_code="AGRI",
        description="Uses smart sensors, hydroponics, and crop data for sustainable farming.",
        approved_fact_source_ref="gov_agri_cert_2025.json",
    ),
    ProfessionalPersona(
        persona_id="p_health_01",
        code="HEALTH_NURSE",
        title="Healthcare Specialist",
        domain="Healthcare",
        profession_taxonomy_code="HEALTH",
        description="Provides medical care, diagnostic analysis, and public health support.",
        approved_fact_source_ref="gov_health_board_2025.json",
    ),
    ProfessionalPersona(
        persona_id="p_edu_01",
        code="EDU_TEACH",
        title="STEM Educator",
        domain="Education",
        profession_taxonomy_code="EDU",
        description="Designs interactive science curricula and mentors young students.",
        approved_fact_source_ref="gov_edu_standards_2025.json",
    ),
    ProfessionalPersona(
        persona_id="p_trades_01",
        code="TRADES_ELEC",
        title="Renewable Energy Electrician",
        domain="Trades",
        profession_taxonomy_code="TRADES",
        description="Installs and maintains solar power grids and clean electrical systems.",
        approved_fact_source_ref="gov_trades_assoc_2025.json",
    ),
    ProfessionalPersona(
        persona_id="p_arts_01",
        code="ARTS_DESIGN",
        title="Digital Media Designer",
        domain="Arts",
        profession_taxonomy_code="ARTS",
        description="Creates visual graphics, user interface designs, and digital animations.",
        approved_fact_source_ref="gov_arts_guild_2025.json",
    ),
    ProfessionalPersona(
        persona_id="p_biz_01",
        code="BIZ_ENTR",
        title="Social Enterprise Manager",
        domain="Business",
        profession_taxonomy_code="BIZ",
        description="Launches community businesses and manages sustainable budgets.",
        approved_fact_source_ref="gov_biz_bureau_2025.json",
    ),
    ProfessionalPersona(
        persona_id="p_gov_01",
        code="GOV_OFFICER",
        title="Civil Services Officer",
        domain="Government",
        profession_taxonomy_code="GOV",
        description="Administers public policies, urban planning, and community development.",
        approved_fact_source_ref="gov_civil_service_2025.json",
    ),
]


class PanelSelector(PanelSelectionEngine):
    """
    Implements panel selection, diversity constraints, relationship bandwidth enforcement, and lapse rules.
    """

    def __init__(self, catalog: list[ProfessionalPersona] | None = None) -> None:
        self.catalog = catalog or DEFAULT_PERSONA_CATALOG
        self.curation_queue: list[dict[str, Any]] = []

    async def check_relationship_bandwidth(
        self,
        *,
        learner_id: UUID,
        active_relationships_count: int,
    ) -> bool:
        """
        PRD §5.1 RELATIONSHIP BANDWIDTH RULE:
        Max active relationships per learner: 3.
        Returns False if active_relationships_count >= 3.
        """
        return active_relationships_count < 3

    def evaluate_relationship_lapses(
        self,
        relationships: list[RelationshipRecord],
        lapse_days: int = 45,
    ) -> list[RelationshipRecord]:
        """
        SD §3.3 LAPSE RULE:
        If last interaction was > 45 days ago, set lapsed_at = NOW().
        """
        now = datetime.now(timezone.utc)
        updated = []
        for rel in relationships:
            if rel.is_active:
                days_since_interaction = (now - rel.last_interaction_at).days
                if days_since_interaction >= lapse_days:
                    rel_dict = rel.model_dump()
                    rel_dict["lapsed_at"] = now
                    rel = RelationshipRecord(**rel_dict)
            updated.append(rel)
        return updated

    async def select_panel_personas(
        self,
        *,
        learner_id: UUID,
        top_interests: list[str],
        active_relationships: list[str],
    ) -> tuple[list[ProfessionalPersona], str]:
        """
        Selects 3 personas: Top-2 interest matches + 1 diversity constraint persona.
        Returns (personas, status).
        If no clean taxonomy match exists, returns ([], "no_match_fallback") and queues for curation.
        """
        if not top_interests:
            self.curation_queue.append({"learner_id": str(learner_id), "reason": "empty_interests"})
            return [], "no_match_fallback"

        # 1. Match interests against catalog taxonomy codes (word boundary / exact match)
        matched_personas: list[ProfessionalPersona] = []
        for interest in top_interests:
            interest_upper = interest.upper().strip()
            for p in self.catalog:
                if (p.profession_taxonomy_code == interest_upper or
                    p.domain.upper() == interest_upper or
                    interest_upper in p.title.upper() or
                    p.profession_taxonomy_code in interest_upper):
                    if p not in matched_personas:
                        matched_personas.append(p)

        if not matched_personas:
            # NO CLEAN TAXONOMY MATCH: Queue for curation review, DO NOT fabricate match (PRD §5.1)
            self.curation_queue.append({
                "learner_id": str(learner_id),
                "interests": top_interests,
                "reason": "no_taxonomy_match"
            })
            return [], "no_match_fallback"

        # 2. Select top matched personas (up to 2) and fill up to 3 with distinct diversity personas
        selected: list[ProfessionalPersona] = []
        used_domains: set[str] = set()

        # Add up to 2 interest matches
        for p in matched_personas:
            if len(selected) < 2 and p.domain not in used_domains:
                selected.append(p)
                used_domains.add(p.domain)

        # Fill remaining slots up to 3 with diversity constraint personas from unused domains
        for p in self.catalog:
            if len(selected) >= 3:
                break
            if p.domain not in used_domains and p not in selected:
                selected.append(p)
                used_domains.add(p.domain)

        # Fallback if catalog is small
        for p in self.catalog:
            if len(selected) >= 3:
                break
            if p not in selected:
                selected.append(p)

        return selected, "success"
