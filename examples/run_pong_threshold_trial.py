r"""M4.45 fresh independent shuffle 5 real full-game Challenge vs +1/+2 peng.

From the MahTrain root in Windows PowerShell:
  python examples\run_pong_threshold_trial.py --train-dir data/selfplay/m434-smoke --prior-m444-dir data/selfplay/m444-call-frontier-2 --seed-start 92300 --seeds 2 --out-dir data/selfplay/m445-pong-2

Add --resume after interruption (same arguments), do NOT overwrite old
PRIVATE* checkpoints. Only upload safe_pong_threshold_trial.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_pong_threshold_trial import run_pong_threshold_trial


def main()->None:
    ap=argparse.ArgumentParser(
        description="M4.45 preregistered new-seed +1/+2 effective copy peng after Challenge pass"
    )
    ap.add_argument("--train-dir",type=Path,required=True)
    ap.add_argument("--prior-m444-dir",type=Path,required=True)
    ap.add_argument("--seed-start",type=int,required=True)
    ap.add_argument("--seeds",type=int,default=2)
    ap.add_argument("--out-dir",type=Path,required=True)
    ap.add_argument("--resume",action="store_true")
    args=ap.parse_args()
    report=run_pong_threshold_trial(
        training_dir=args.train_dir,prior_m444_dir=args.prior_m444_dir,
        seed_start=args.seed_start,seeds=args.seeds,
        out_dir=args.out_dir,resume=args.resume,
    )
    print(json.dumps({
        "original_independent_shuffle_clusters":report["independent_original_shuffle_clusters"],
        "fully_settled_five_game_comparisons":report["complete_authoritative_games"],
        "candidate_peng_overrides":report["actor_only_response_counts"]["actual_peng_overrides"],
        "experimental_mean_official_net_delta_points":report["mean_official_net_delta_points"],
        "safe_summary":str(args.out_dir/"safe_pong_threshold_trial.json"),
        "not_proven_better_than_challenge":True,
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
