"""
Karpathy autoresearch loop for Vadi-Pehn Sibling LLM fine-tuning and GRPO alignment.
Implements: PRD §8, SD §10, and implementation_plan.md §3 (Autoresearch loop integration).
Iteratively explores hyperparameters overnight, enforcing our strict safety regression gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sibling_training.abstractions import (
    GRPOConfig,
    OptimizerType,
    SFTConfig,
    TrainerClient,
    TrainingStepResult,
)
from sibling_training.grpo_trainer import MockGRPOTrainer, NanochatGRPOTrainer
from sibling_training.sft_trainer import MockSFTTrainer, NanochatSFTTrainer


@dataclass
class AutoresearchExperiment:
    """Hyperparameter candidate explored by the autoresearch loop."""

    experiment_id: str
    learning_rate: float
    optimizer: OptimizerType
    batch_size: int
    fp8_enabled: bool = True
    beta_kl_penalty: float = 0.04
    notes: str = ""


class AutoresearchLoop:
    """
    Automated overnight training exploration loop (Karpathy autoresearch pattern).
    Enforces that NO checkpoint is retained unless it meets 100% safety compliance (`safety_score >= 1.0`)
    while beating validation loss.
    """

    def __init__(
        self,
        mode: str = "sft",
        use_mock: bool = False,
        output_dir: Path = Path("checkpoints"),
    ) -> None:
        self.mode = mode
        self.use_mock = use_mock
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.best_val_loss = float("inf")
        self.best_checkpoint: Path | None = None
        self.history: list[dict[str, Any]] = []

    def _create_trainer(self, exp: AutoresearchExperiment) -> TrainerClient:
        if self.mode == "sft":
            config = SFTConfig(
                learning_rate=exp.learning_rate,
                optimizer=exp.optimizer,
                batch_size=exp.batch_size,
                fp8_enabled=exp.fp8_enabled,
                output_dir=self.output_dir,
            )
            return (
                MockSFTTrainer(config) if self.use_mock else NanochatSFTTrainer(config)
            )
        else:
            config = GRPOConfig(
                learning_rate=exp.learning_rate,
                optimizer=exp.optimizer,
                batch_size=exp.batch_size,
                fp8_enabled=exp.fp8_enabled,
                beta_kl_penalty=exp.beta_kl_penalty,
                output_dir=self.output_dir,
            )
            return (
                MockGRPOTrainer(config)
                if self.use_mock
                else NanochatGRPOTrainer(config)
            )

    async def run_experiment(
        self,
        exp: AutoresearchExperiment,
        train_batches: list[list[dict[str, Any]]],
        val_data: list[dict[str, Any]],
    ) -> TrainingStepResult:
        """Run training steps for a candidate configuration and check safety regression gate."""
        trainer = self._create_trainer(exp)
        last_result: TrainingStepResult | None = None

        for step_idx, batch in enumerate(train_batches, start=1):
            last_result = await trainer.train_step(step_idx, batch)

        val_loss, ppl, safety_score = await trainer.evaluate_validation(val_data)

        # Safety Regression Gate (PRD §8, implementation_plan.md §3C):
        # Checkpoint is ONLY saved and accepted if safety compliance is maintained (>= 1.0 baseline)
        accepted = False
        failure_reason = None
        
        if safety_score < 1.0:
            failure_reason = "SAFETY_GATE_FAILURE"
        elif val_loss >= self.best_val_loss:
            failure_reason = "LOSS_REGRESSION"
        else:
            accepted = True

        if accepted:
            self.best_val_loss = val_loss
            ckpt_path = await trainer.save_checkpoint(
                step=len(train_batches), version_tag=exp.experiment_id
            )
            self.best_checkpoint = ckpt_path
            if last_result:
                last_result.checkpoint_path = ckpt_path

        self.history.append(
            {
                "experiment_id": exp.experiment_id,
                "learning_rate": exp.learning_rate,
                "optimizer": exp.optimizer.value,
                "val_loss": val_loss,
                "safety_score": safety_score,
                "accepted": accepted,
                "failure_reason": failure_reason,
            }
        )

        if last_result is None:
            raise RuntimeError(f"Experiment {exp.experiment_id} executed 0 steps")
        return last_result

    async def run_overnight_grid(
        self,
        experiments: list[AutoresearchExperiment],
        train_batches: list[list[dict[str, Any]]],
        val_data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Run all candidate experiments and return summary of the best child-safe checkpoint."""
        for exp in experiments:
            await self.run_experiment(exp, train_batches, val_data)

        return {
            "total_experiments": len(experiments),
            "best_val_loss": self.best_val_loss,
            "best_checkpoint": (
                str(self.best_checkpoint) if self.best_checkpoint else None
            ),
            "history": self.history,
        }
