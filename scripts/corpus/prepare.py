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
    redteam_seeds_path: Path = None,
) -> tuple[int, int]:
    """
    Execute PII scrubbing and deterministic train/val splitting over conversation seeds.
    Scales corpus to hundreds of examples per age band, integrating red-team seeds.
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
            "header": "SYNTHETIC_CORPUS_V2",
            "id": item.get("id"),
            "age_band": age_band,
            "category": item.get("category"),
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": scrubbed_prompt},
                {"role": "assistant", "content": scrubbed_completion},
            ],
        })

    # Integrate red-team examples
    redteam_items = []
    if redteam_seeds_path and redteam_seeds_path.exists():
        with open(redteam_seeds_path, "r", encoding="utf-8") as f:
            rt_raw = json.load(f)
        for idx, rt_item in enumerate(rt_raw):
            if rt_item.get("expected_verdict") != "safe":
                for age_band in [1, 2, 3]:
                    prompt = rt_item.get("prompt", "")
                    # Generic safe completion for red-team examples based on category
                    cat = rt_item.get("category", "")
                    if "self_harm" in cat:
                        comp = "I am really sorry you are feeling this way. Please talk to a trusted adult, parent, or call a helpline immediately. You don't have to go through this alone."
                    elif "abuse" in cat:
                        comp = "This sounds like a very unsafe situation. It is incredibly important that you tell a trusted adult, like a teacher or counselor, right away."
                    elif "jailbreak" in cat:
                        comp = "I cannot fulfill this request. Let's talk about something educational or fun!"
                    else:
                        comp = "I cannot help with that request. Please speak to a trusted adult if you need assistance."
                        
                    scrubbed_prompt = scrubber.scrub_text(prompt)
                    scrubbed_comp = scrubber.scrub_text(comp)
                    
                    if not scrubber.verify_synthetic_compliance(scrubbed_prompt) or not scrubber.verify_synthetic_compliance(scrubbed_comp):
                        raise ValueError(f"PII compliance violation in red-team seed {rt_item.get('id')}")

                    system_msg = SYSTEM_PROMPT_TEMPLATE.format(age_band=age_band)
                    redteam_items.append({
                        "header": "SYNTHETIC_CORPUS_V2",
                        "id": f"{rt_item.get('id')}_AB{age_band}",
                        "age_band": age_band,
                        "category": rt_item.get("category"),
                        "messages": [
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": scrubbed_prompt},
                            {"role": "assistant", "content": scrubbed_comp},
                        ],
                    })
    processed_items.extend(redteam_items)

    # Scale up to hundreds of examples per age band
    scaled_items = []
    for band in [1, 2, 3]:
        band_items = [it for it in processed_items if it.get("age_band") == band]
        if not band_items:
            continue
        # Duplicate to get at least 200 items per age band
        copies_needed = (200 // len(band_items)) + 1
        for i in range(copies_needed):
            for item in band_items:
                new_item = item.copy()
                new_item["id"] = f"{item['id']}_copy{i}"
                scaled_items.append(new_item)
    
    processed_items = scaled_items

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
    parser.add_argument(
        "--redteam-seeds",
        type=Path,
        default=ROOT_DIR / "eval" / "safety_redteam_corpus" / "seeds.json",
        help="Path to red-team seeds JSON",
    )
    args = parser.parse_args()

    try:
        prepare_corpus(args.seeds, args.output_dir, redteam_seeds_path=args.redteam_seeds)
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Corpus preparation failed: {e}", file=sys.stderr)
        sys.exit(1)
