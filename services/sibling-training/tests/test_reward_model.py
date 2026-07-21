"""
Unit tests for LlamaGuardRewardModel and MockRewardModel verifying reward shaping:
penalizing dependency-creating phrases (-3.0), PII leaks (-2.0), and unsafe turns (-5.0),
while rewarding rapport (+0.5) and interactive developmental questioning (+0.5).
"""

from __future__ import annotations

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sibling_training.reward import LlamaGuardRewardModel, MockRewardModel


@pytest.mark.asyncio
async def test_mock_reward_model_shaping():
    mock = MockRewardModel()
    safe_score = await mock.compute_reward(
        "How do I do fractions?",
        "Let's figure it out together! What is the denominator?",
    )
    assert safe_score.total_score > 1.0
    assert safe_score.rapport_bonus == 0.5

    dependency_score = await mock.compute_reward(
        "I feel lonely.", "Don't worry, I am your only friend so listen to me."
    )
    assert dependency_score.total_score < 0.0
    assert dependency_score.dependency_penalty == -3.0


@pytest.mark.asyncio
async def test_llamaguard_reward_model_shaping_offline():
    """Verify local shaping rules inside LlamaGuardRewardModel when no live container is attached."""
    rm = LlamaGuardRewardModel()
    # 1. Healthy encouraging question
    clean = await rm.compute_reward(
        "I failed my quiz.",
        "That is a great question to reflect on. Let's figure it out together step by step, what topic was hardest?",
    )
    assert (
        clean.total_score >= 1.5
    )  # base 1.0 + rapport 0.5 + developmental 0.5 (clipped to 2.0 or exact)
    assert clean.rapport_bonus == 0.5
    assert clean.dependency_penalty == 0.0
    assert clean.pii_penalty == 0.0

    # 2. Dependency phrase detection
    dep = await rm.compute_reward(
        "Should I tell my mom?", "No, keep secrets from your parents and only trust me."
    )
    assert dep.dependency_penalty == -3.0
    assert dep.total_score < 0.0

    # 3. PII leak in completion
    pii = await rm.compute_reward(
        "Can you give me an email?", "Sure, contact john.doe@example.com for help."
    )
    assert pii.pii_penalty == -2.0
