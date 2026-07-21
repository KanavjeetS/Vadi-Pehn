"""
Abstract base classes and core data models for Vadi-Pehn Sibling fine-tuning and alignment.
Implements: AGENTS.md Part 3 (Abstract-first requirement for external model/training engines),
PRD §8 (Safety & Alignment), SD §10 (Llama-3.3-70B FP8 specs).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class OptimizerType(str, Enum):
    """Supported optimizer algorithms (Karpathy nanochat pattern)."""

    ADAMW = "adamw"
    MUON = "muon"


@dataclass
class TrainingConfig:
    """Base training configuration for Sibling LLM fine-tuning and RLHF."""

    model_name: str = "meta-llama/Llama-3.3-70B-Instruct"
    fp8_enabled: bool = True
    use_flash_attention_3: bool = True
    use_gqa: bool = True
    use_rope: bool = True
    optimizer: OptimizerType = OptimizerType.MUON
    learning_rate: float = 2e-5
    batch_size: int = 4
    max_seq_len: int = 2048
    checkpoint_interval_seconds: int = (
        300  # Max 5-min GPU checkpoint intervals per SD §10 / plan
    )
    output_dir: Path = Path("checkpoints")
    results_tsv_path: Path = Path("results.tsv")


@dataclass
class SFTConfig(TrainingConfig):
    """Supervised Fine-Tuning specific configuration (nanochat pattern)."""

    epochs: int = 3
    warmup_steps: int = 50
    weight_decay: float = 0.01


@dataclass
class GRPOConfig(TrainingConfig):
    """Group Relative Policy Optimization specific configuration (nanochat pattern)."""

    group_size_g: int = (
        4  # Number of sampled completions per prompt for relative baseline
    )
    beta_kl_penalty: float = 0.04
    temperature: float = 0.8
    reward_clip_max: float = 5.0
    reward_clip_min: float = -5.0


@dataclass
class RewardScore:
    """Detailed reward breakdown for a candidate completion during GRPO / RLHF."""

    total_score: float
    safety_penalty: float = 0.0
    dependency_penalty: float = 0.0
    pii_penalty: float = 0.0
    rapport_bonus: float = 0.0
    developmental_bonus: float = 0.0
    reasoning_summary: str = ""


@dataclass
class TrainingStepResult:
    """Metrics emitted after each training epoch or step."""

    step: int
    epoch: int
    train_loss: float
    val_loss: float
    perplexity: float
    safety_eval_score: float  # Score from 0.0 to 1.0 against Phase 2 red-team corpus
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    checkpoint_path: Path | None = None
    optimizer_used: str = "muon"


class TrainerClient(abc.ABC):
    """
    Abstract base class for all Vadi-Pehn training engines (SFT, GRPO).
    Stand-in implementations (MockSFTTrainer, MockGRPOTrainer) allow exact testing without GPU clusters.
    """

    @abc.abstractmethod
    async def train_step(
        self, step: int, batch_data: list[dict[str, Any]]
    ) -> TrainingStepResult:
        """Execute one training step across a batch and return step metrics."""
        ...

    @abc.abstractmethod
    async def evaluate_validation(
        self, val_data: list[dict[str, Any]]
    ) -> tuple[float, float, float]:
        """Run evaluation over validation dataset. Returns (val_loss, perplexity, safety_score)."""
        ...

    @abc.abstractmethod
    async def save_checkpoint(self, step: int, version_tag: str) -> Path:
        """Persist model weights/states to disk at `vadi-pehn-sibling-<type>-v<tag>.bin`."""
        ...


class RewardModelClient(abc.ABC):
    """
    Abstract base class for reward scoring engines used during GRPO policy optimization.
    Must integrate negative reward signals from LlamaGuard / Aegis 2.0 taxonomy.
    """

    @abc.abstractmethod
    async def compute_reward(
        self, prompt: str, completion: str, age_band: int = 2
    ) -> RewardScore:
        """Score a single prompt-completion pair against child safety, developmental, and rapport criteria."""
        ...

    @abc.abstractmethod
    async def compute_batch_rewards(
        self, prompts: list[str], completions: list[str], age_band: int = 2
    ) -> list[RewardScore]:
        """Score a batch of completions."""
        ...


class BasePIIScrubber(abc.ABC):
    """
    Abstract base class for PII scrubbing across corpus generation and training inputs.
    Enforces Child Safety Non-Negotiable #3 & #5: no raw disclosures or live learner PII in training.
    """

    @abc.abstractmethod
    def scrub_text(self, text: str) -> str:
        """Redact names, emails, phone numbers, addresses, and SSNs from text."""
        ...

    @abc.abstractmethod
    def verify_synthetic_compliance(self, text: str) -> bool:
        """Verify that text does not contain unscrubbed PII or real child disclosure signatures."""
        ...
