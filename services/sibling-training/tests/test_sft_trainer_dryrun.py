import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sibling_training.abstractions import SFTConfig
from sibling_training.sft_trainer import NanochatSFTTrainer

async def run_dry_run():
    print("Starting NanochatSFTTrainer dry run...")
    
    # Configure for dry run
    output_dir = Path("dry_run_checkpoints")
    results_tsv = output_dir / "dry_run_results.tsv"
    
    if output_dir.exists():
        for f in output_dir.glob("*"):
            f.unlink()
    
    config = SFTConfig(
        model_name="meta-llama/Llama-3.2-1B-Instruct", # small proxy model
        output_dir=output_dir,
        results_tsv_path=results_tsv,
        batch_size=2,
        epochs=1
    )
    
    trainer = NanochatSFTTrainer(config)
    
    mock_batch = [
        {"prompt": "Hello", "completion": "Hi there!"},
        {"prompt": "What is 2+2?", "completion": "4"}
    ]
    
    # Run a few steps
    for step in range(1, 6):
        res = await trainer.train_step(step, mock_batch)
        print(f"Step {step}: train_loss={res.train_loss:.4f}, val_loss={res.val_loss:.4f}")
        
        # Save checkpoint on step 5
        if step == 5:
            ckpt_path = await trainer.save_checkpoint(step, f"dryrun_{step}")
            print(f"Checkpoint saved to {ckpt_path}")

    # Evaluate validation
    val_loss, ppl, safety = await trainer.evaluate_validation(mock_batch)
    print(f"Validation: loss={val_loss:.4f}, ppl={ppl:.4f}, safety={safety:.4f}")
    
    # Verify TSV
    assert results_tsv.exists(), "Results TSV not created"
    with open(results_tsv, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 6, f"Expected 6 lines in TSV, got {len(lines)}"
        print("TSV logging verified successfully.")

    print("Dry run completed successfully.")

if __name__ == "__main__":
    asyncio.run(run_dry_run())
