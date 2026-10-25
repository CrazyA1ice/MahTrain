r"""Evaluate frozen M4.35 OFFLINE weights in real independent full Mahjong games.

From MahTrain root:
  python examples/run_local_shadow_headtohead.py --train-dir data/selfplay/m434-smoke --seed-start 90100 --seeds 2 --out-dir data/selfplay/m437-shadow
  # if interrupted, rerun THE SAME command with --resume appended

Five actual official complete games per NEW original shuffle: one unchanged
four-challenge baseline and four one-shadow-rotated comparisons. Keeps
private per-game records locally, uploads no hands or shuffles. Does NOT
modify online AI or promise any strength improvement.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_shadow_headtohead import evaluate_frozen_shadow


def main() -> None:
    p=argparse.ArgumentParser(
        description="M4.37 resumable frozen four-seat candidate vs unchanged Challenge"
    )
    p.add_argument("--train-dir",type=Path,required=True,
                   help="EXISTING completed M4.34 batch with M4.35 model")
    p.add_argument("--seed-start",type=int,default=90100)
    p.add_argument("--seeds",type=int,default=2)
    p.add_argument("--resume",action="store_true",
                   help="reuse validated saved five-game seed clusters after an interruption")
    p.add_argument("--out-dir",type=Path,required=True,
                   help="NEW empty private gitignored data/selfplay directory")
    a=p.parse_args()
    result=evaluate_frozen_shadow(
        training_dir=a.train_dir,seed_start=a.seed_start,
        seeds=a.seeds,out_dir=a.out_dir,resume=a.resume
    )
    print(json.dumps({
        "independent_evaluation_shuffles":
            result["independent_initial_shuffle_seed_clusters"],
        "real_full_game_count":result["actual_real_complete_games"],
        "legal_candidate_discard_overrides":
            result["candidate_legal_minimum_shanten_overrides"],
        "seat_rotated_mean_actual_net_score_delta":
            result["seat_rotated_seed_cluster_mean_delta_points"],
        "sufficient_independent_seeds_for_exploratory_comparison":
            result["enough_independent_seeds_for_exploratory_comparison"],
        "reused_prior_completed_seed_shards":
            result["reused_prior_completed_seed_shards"],
        "fully_written_private_seed_shards":
            result["interruption_safe_completed_seed_shards"],
        "no_strength_improvement_claim":True,
        "safe_report":
            str(a.out_dir/"safe_four_seat_shadow_summary.json"),
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
