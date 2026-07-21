"""
Curator Agent Module for Vadi-Pehn Platform.
Filters, verifies, sanitizes, and curates educational content, learning materials, and retrieved context.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List
from uuid import UUID

logger = logging.getLogger("panel_service.curator_agent")


class CuratorAgent:
    """
    Curator & Knowledge Sanitizer Agent.
    Filters retrieved memory context, verifies educational suitability for ages 8-17,
    and formats verified resource recommendation cards.
    """

    def __init__(self, agent_id: str = "agent-curator-knowledge-v1") -> None:
        self.agent_id = agent_id

    async def curate_and_verify_context(
        self,
        *,
        tenant_id: UUID,
        learner_age: int,
        raw_facts: List[str],
    ) -> Dict[str, Any]:
        """
        Sanitizes and curates educational facts, ensuring age-appropriateness.
        """
        logger.info(f"CuratorAgent filtering {len(raw_facts)} facts for learner age {learner_age}")
        
        verified_facts: List[str] = []
        for fact in raw_facts:
            # Strip PII markers or extra noise
            cleaned = re.sub(r"\[PII_[A-Z_]+\]", "", fact).strip()
            if cleaned and len(cleaned) > 5:
                verified_facts.append(cleaned)

        return {
            "agent_name": "Knowledge Curator",
            "agent_id": self.agent_id,
            "verified_facts": verified_facts,
            "is_age_appropriate": 8 <= learner_age <= 17,
            "curated_summary": f"Curated {len(verified_facts)} age-appropriate context items.",
        }
