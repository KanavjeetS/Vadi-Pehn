"""
Unit tests for the PII scrubber verifying complete redaction of raw disclosures,
emails, phone numbers, and IDs before entering SFT/RLHF training datasets.
Implements: Child Safety Non-Negotiable #3 & #5.
"""
from __future__ import annotations

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sibling_training.pii_scrubber import RegexPIIScrubber


def test_scrubber_redacts_email_and_phone():
    scrubber = RegexPIIScrubber()
    raw = "My name is Rahul and my email is rahul.sharma@example.co.in and phone is +91 9876543210."
    scrubbed = scrubber.scrub_text(raw)
    assert "[REDACTED_EMAIL]" in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed
    assert "rahul.sharma@example.co.in" not in scrubbed
    assert "9876543210" not in scrubbed
    assert scrubber.verify_synthetic_compliance(scrubbed) is True


def test_scrubber_redacts_aadhaar_ssn():
    scrubber = RegexPIIScrubber()
    raw = "My ID number is 1234 5678 9012 for verification."
    scrubbed = scrubber.scrub_text(raw)
    assert "[REDACTED_ID]" in scrubbed
    assert "1234 5678 9012" not in scrubbed
    assert scrubber.verify_synthetic_compliance(scrubbed) is True


def test_verify_synthetic_compliance_detects_raw_pii():
    scrubber = RegexPIIScrubber()
    assert scrubber.verify_synthetic_compliance("Hello, let's learn algebra today.") is True
    assert scrubber.verify_synthetic_compliance("Contact me at secret@gmail.com immediately.") is False
    assert scrubber.verify_synthetic_compliance("Call +91-9123456789 now.") is False
