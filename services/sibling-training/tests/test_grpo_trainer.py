"""
Unit tests for GRPO policy alignment trainer verifying group advantage normalization,
reward shaping integration, and checkpoint persistence.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sibling_training.abstractions import GRPOConfig
from sibling_training.grpo_trainer import MockGRPOTrainer, NanochatGRPOTrainer
from sibling_training.reward import MockRewardModel


@pytest.mark.asyncio
async def test_grpo_group_advantages_computation():
    trainer = NanochatGRPOTrainer(GRPOConfig())
    # Given 4 rewards where one is high and others low
    rewards = [1.0, 1.0, 1.0, 5.0]
    advantages = await trainer._compute_group_advantages(rewards)
    assert len(advantages) == 4
    # The last candidate should have positive advantage (> 0) while the first three negative (< 0)
    assert advantages[-1] > 0
    assert all(a < 0 for a in advantages[:3])


@pytest.mark.asyncio
async def test_nanochat_grpo_step_and_checkpoint(tmp_path: Path):
    tsv_path = tmp_path / "grpo_results.tsv"
    config = GRPOConfig(output_dir=tmp_path / "ckpts", results_tsv_path=tsv_path)
    trainer = NanochatGRPOTrainer(config, reward_model=MockRewardModel())

    res = await trainer.train_step(1, [{"prompt": "Help me with algebra"}])
    assert res.train_loss > 0
    assert tsv_path.exists()
    assert "grpo" in tsv_path.name or "results.tsv" in tsv_path.name

    ckpt_path = await trainer.save_checkpoint(1, "tag_grpo")
    assert ckpt_path.exists()
    assert "VADI_PEHN_GRPO_CHECKPOINT_V1" in ckpt_path.read_text("utf-8")
