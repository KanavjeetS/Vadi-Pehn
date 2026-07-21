"""
Unit tests for SFT trainer (NanochatSFTTrainer & MockSFTTrainer) verifying step execution,
TSV metric logging (`results.tsv`), and checkpoint serialization (`vadi-pehn-sibling-sft-v<version>.bin`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sibling_training.abstractions import OptimizerType, SFTConfig
from sibling_training.sft_trainer import MockSFTTrainer, NanochatSFTTrainer


@pytest.mark.asyncio
async def test_mock_sft_trainer_step_and_checkpoint(tmp_path: Path):
    config = SFTConfig(output_dir=tmp_path / "ckpts")
    trainer = MockSFTTrainer(config)

    res = await trainer.train_step(1, [{"prompt": "hi", "completion": "hello"}])
    assert res.step == 1
    assert res.optimizer_used == "muon"

    ckpt_path = await trainer.save_checkpoint(1, "test_tag")
    assert ckpt_path.exists()
    assert ckpt_path.name == "vadi-pehn-sibling-sft-vtest_tag.bin"
    assert "MOCK_SFT_CHECKPOINT" in ckpt_path.read_text("utf-8")


@pytest.mark.asyncio
async def test_nanochat_sft_trainer_tsv_logging_and_loss_decay(tmp_path: Path):
    tsv_path = tmp_path / "results.tsv"
    config = SFTConfig(
        output_dir=tmp_path / "ckpts",
        results_tsv_path=tsv_path,
        optimizer=OptimizerType.MUON,
    )
    trainer = NanochatSFTTrainer(config)
    assert tsv_path.exists()

    res1 = await trainer.train_step(1, [{"prompt": "Q1", "completion": "A1"}])
    res2 = await trainer.train_step(50, [{"prompt": "Q2", "completion": "A2"}])

    assert res2.train_loss < res1.train_loss, "Loss must decrease as steps advance"
    tsv_content = tsv_path.read_text("utf-8")
    assert "muon" in tsv_content
    assert str(res1.step) in tsv_content
    assert str(res2.step) in tsv_content
