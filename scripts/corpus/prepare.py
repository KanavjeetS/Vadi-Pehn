"""
Corpus preparation and PII scrubbing pipeline (`scripts/corpus/prepare.py`).
Implements: PRD §3.4, PRD §8, SD §10, and Child Safety Non-Negotiable #3 & #5.
Reads raw/synthetic seeds, scrubs PII, verifies child-safety compliance, and splits deterministically into train/val JSONL.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add services root to sys.path so we can import our PII scrubber
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "services" / "sibling-training" / "src"))

from sibling_training.pii_scrubber import RegexPIIScrubber


SYSTEM_PROMPT_TEMPLATE = (
    "You are Vadi-Pehn, a developmentally appropriate, supportive virtual sibling mentor "
    "for child age band {age_band}. Encourage independent thinking, maintain healthy boundaries, "
    "and never foster sycophancy or dependency."
)


def prepare_corpus(
    seeds_path: Path,
    output_dir: Path,
    train_ratio: float = 0.8,
    random_seed: int = 42,
) -> tuple[int, int]:
    """
    Execute PII scrubbing and deterministic train/val splitting over conversation seeds.
    Returns (num_train, num_val).
    """
    if not seeds_path.exists():
        raise FileNotFoundError(f"Seeds file not found at {seeds_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    scrubber = RegexPIIScrubber()

    with open(seeds_path, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    processed_items = []
    for item in raw_items:
        raw_prompt = item.get("prompt", "")
        raw_completion = item.get("completion", "")

        # Mandatory PII scrub
        scrubbed_prompt = scrubber.scrub_text(raw_prompt)
        scrubbed_completion = scrubber.scrub_text(raw_completion)

        # Mandatory compliance verification
        if not scrubber.verify_synthetic_compliance(scrubbed_prompt) or not scrubber.verify_synthetic_compliance(scrubbed_completion):
            raise ValueError(f"PII compliance violation in seed {item.get('id')}")

        age_band = item.get("age_band", 2)
        system_msg = SYSTEM_PROMPT_TEMPLATE.format(age_band=age_band)

        processed_items.append({
            "header": "SYNTHETIC_CORPUS_V1",
            "id": item.get("id"),
            "age_band": age_band,
            "category": item.get("category"),
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": scrubbed_prompt},
                {"role": "assistant", "content": scrubbed_completion},
            ],
        })

    # Deterministic split
    random.seed(random_seed)
    random.shuffle(processed_items)

    split_idx = max(1, int(len(processed_items) * train_ratio))
    train_items = processed_items[:split_idx]
    val_items = processed_items[split_idx:] if split_idx < len(processed_items) else processed_items[:1]

    train_path = output_dir / "train.jsonl"
    val_path = output_dir / "val.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for it in train_items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    with open(val_path, "w", encoding="utf-8") as f:
        for it in val_items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    print(f"[SUCCESS] Corpus prepared successfully at {output_dir}")
    print(f"   Train samples: {len(train_items)} ({train_path})")
    print(f"   Val samples:   {len(val_items)} ({val_path})")
    return len(train_items), len(val_items)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vadi-Pehn Corpus Preparation Script")
    parser.add_argument(
        "--seeds",
        type=Path,
        default=Path(__file__).resolve().parent / "seeds" / "synthetic_conversations.json",
        help="Path to input synthetic seeds JSON",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "data",
        help="Directory to write train.jsonl and val.jsonl",
    )
    args = parser.parse_args()

    try:
        prepare_corpus(args.seeds, args.output_dir)
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Corpus preparation failed: {e}", file=sys.stderr)
        sys.exit(1)
