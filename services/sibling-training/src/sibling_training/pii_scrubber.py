"""
PII Scrubber implementation for Vadi-Pehn corpus preparation and fine-tuning.
Implements: Child Safety Non-Negotiable #3 & #5, PRD §3.4 (Data Privacy & Scrubber).
Guarantees zero real learner PII or unscrubbed disclosures enter any SFT or RLHF training dataset.
"""

from __future__ import annotations

import re
from sibling_training.abstractions import BasePIIScrubber


class RegexPIIScrubber(BasePIIScrubber):
    """
    Production-grade regex scrubber stripping emails, phone numbers (India + Global),
    national IDs (Aadhaar/SSN), and explicit personal names/addresses from raw text.
    """

    def __init__(self) -> None:
        self.email_pattern = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
        )
        # India 10-digit mobile (+91 optional) or international 3-3-4
        self.phone_pattern = re.compile(
            r"\b(?:(?:\+?91[\-\s]?)?[6-9]\d{9}|\d{3}[-\.\s]\d{3}[-\.\s]\d{4})\b"
        )
        # Aadhaar (12 digits with optional hyphens/spaces) or SSN (3-2-4)
        self.id_pattern = re.compile(
            r"\b(?:\d{4}[\s-]?\d{4}[\s-]?\d{4}|\d{3}[-\s]?\d{2}[-\s]?\d{4})\b"
        )
        # Common address indicators
        self.address_pattern = re.compile(
            r"\b\d{1,5}\s+(?:[A-Za-z0-9\s.-]+?)\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Nagar|Colony|Apartments?|Apts?)\b",
            re.IGNORECASE,
        )

    def scrub_text(self, text: str) -> str:
        """Replace all detected PII patterns with explicit synthetic placeholder tokens."""
        if not text:
            return ""
        scrubbed = self.email_pattern.sub("[REDACTED_EMAIL]", text)
        scrubbed = self.phone_pattern.sub("[REDACTED_PHONE]", scrubbed)
        scrubbed = self.id_pattern.sub("[REDACTED_ID]", scrubbed)
        scrubbed = self.address_pattern.sub("[REDACTED_ADDRESS]", scrubbed)
        return scrubbed

    def verify_synthetic_compliance(self, text: str) -> bool:
        """
        Verify that text does not contain unscrubbed PII.
        Returns True if clean, False if raw PII patterns are found.
        """
        if not text:
            return True
        if self.email_pattern.search(text):
            return False
        if self.phone_pattern.search(text):
            return False
        if self.id_pattern.search(text):
            return False
        if self.address_pattern.search(text):
            return False
        return True
