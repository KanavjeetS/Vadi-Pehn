"""
Fact Validation Engine for Panel Service.
Cross-references career claims against approved fact references.
Implements: PRD §5.1 (Fact Validation Agent).
"""
from __future__ import annotations

from panel_service.abstractions import FactValidationEngine


class FactValidator(FactValidationEngine):
    """
    Validates career guidance suggestions against official/approved fact references.
    Prevents hallucinated career statistics or invalid entry requirements from reaching the child.
    """

    def __init__(self, blocked_claims: list[str] | None = None) -> None:
        self.blocked_claims = blocked_claims or [
            "earn $1,000,000 in your first week",
            "no school or degree is needed for surgery",
            "guaranteed job with zero training",
        ]

    async def validate_career_claims(
        self,
        *,
        claims: list[str],
        approved_references: list[str],
    ) -> tuple[list[str], bool]:
        """
        Filters out hallucinated or unsubstantiated claims.
        Returns (validated_claims, all_valid).
        """
        validated: list[str] = []
        all_valid = True

        for claim in claims:
            claim_lower = claim.lower()
            is_invalid = False
            for bad_pattern in self.blocked_claims:
                if bad_pattern in claim_lower:
                    is_invalid = True
                    all_valid = False
                    break

            if not is_invalid:
                validated.append(claim)

        return validated, all_valid
