"""M4.34 local Windows CPU self-play batch: parallel, resume, independent seeds.

PowerShell example (from repo root):
  .\.venv\Scripts\python.exe examples\run_local_selfplay_batch.py --seed-start 89800 --train-seeds 4 --holdout-seeds 4 --workers 4

Repeat with --resume after interruption. Private raw data remains ONLY in
gitignored data/selfplay/m434-local (or an OUTSIDE-repository directory).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_selfplay_local_batch import (
    BatchPlan, DEFAULT_OUTPUT, run_local_batch,
)


def main() -> None:
    parser=argparse.ArgumentParser(
        description="CPU-only, resumable, independently shuffled four-challenge AI batch"
    )
    parser.add_argument("--seed-start",type=int,default=89800)
    parser.add_argument("--train-seeds",type=int,default=4)
    parser.add_argument("--holdout-seeds",type=int,default=4)
    parser.add_argument("--max-checkpoints",type=int,default=2)
    parser.add_argument("--workers",type=int,default=2,
                        help="Windows-safe process count, 1..16")
    parser.add_argument("--resume",action="store_true",
                        help="ONLY resume identical seed plan and private shard dir")
    parser.add_argument("--out-dir",type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    plan=BatchPlan(args.seed_start,args.train_seeds,args.holdout_seeds,
                   args.max_checkpoints)
    def progress(done: int,total: int) -> None:
        print(f"newly completed {done} / planned {total} independent natural seeds",
              flush=True)
    summary=run_local_batch(
        plan,args.out_dir,workers=args.workers,
        resume=args.resume,progress=progress
    )
    print(json.dumps({
        "natural_games":summary["natural_full_games"],
        "actual_legal_terminal_branch_games":
            summary["terminal_paired_branch_games"],
        "training_consensus_labels":summary["training_consensus_labels"],
        "untouched_holdout_consensus_labels":
            summary["holdout_consensus_labels"],
        "conditional_two_wall_mixed_or_tied_decisions":
            summary["two_wall_mixed_or_tied_points"],
        "holdout_accuracy_if_at_least_five":
            summary["holdout_accuracy_if_at_least_five"],
        "not_validated_as_stronger_ai":True,
        "safe_aggregate_report":str(
            Path(args.out_dir)/"safe_aggregate_summary.json"
        ),
    },ensure_ascii=False),flush=True)


if __name__=="__main__":
    # Required on Windows with spawn: children import the module only and
    # never recursively start other worker processes.
    main()
