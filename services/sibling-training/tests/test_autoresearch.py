"""
Unit tests for the Karpathy autoresearch loop verifying automated exploration of hyperparameter grids
and strict enforcement of our safety regression gate (`safety_score >= 1.0`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sibling_training.abstractions import OptimizerType
from sibling_training.autoresearch import AutoresearchExperiment, AutoresearchLoop


@pytest.mark.asyncio
async def test_autoresearch_overnight_grid(tmp_path: Path):
    loop = AutoresearchLoop(mode="sft", use_mock=True, output_dir=tmp_path / "ckpts")

    experiments = [
        AutoresearchExperiment(
            "exp1_muon", learning_rate=2e-5, optimizer=OptimizerType.MUON, batch_size=4
        ),
        AutoresearchExperiment(
            "exp2_adamw",
            learning_rate=1e-4,
            optimizer=OptimizerType.ADAMW,
            batch_size=8,
        ),
    ]

    train_batches = [
        [{"prompt": "Q1", "completion": "A1"}],
        [{"prompt": "Q2", "completion": "A2"}],
    ]
    val_data = [{"prompt": "Q_val", "completion": "A_val"}]

    summary = await loop.run_overnight_grid(experiments, train_batches, val_data)
    assert summary["total_experiments"] == 2
    assert summary["best_checkpoint"] is not None
    assert Path(summary["best_checkpoint"]).exists()
    assert len(summary["history"]) == 2
    assert all(item["safety_score"] >= 1.0 for item in summary["history"])
