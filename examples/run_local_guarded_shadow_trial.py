r"""M4.41 preregistered fresh-shuffle experiment; all nine games truly paid.

From repository root in Windows PowerShell:
  python examples\run_local_guarded_shadow_trial.py --train-dir data/selfplay/m434-smoke --prior-m437-dir data/selfplay/m437-shadow-2 --prior-m439-dir data/selfplay/m439-actor-2 --seed-start 91500 --seeds 2 --out-dir data/selfplay/m441-guarded-2

A crash after a FULL nine-game independent-seed cluster can be resumed by
appending --resume to the identical command. Does not modify live Challenge.
Only share safe_guarded_frozen_shadow_trial.json, never PRIVATE* shards.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_shadow_guarded_trial import run_guarded_trial


def main()->None:
    parser=argparse.ArgumentParser(
        description="M4.41 original Challenge vs frozen and conservative-guard shadow"
    )
    parser.add_argument("--train-dir",type=Path,required=True)
    parser.add_argument("--prior-m437-dir",type=Path,required=True)
    parser.add_argument("--prior-m439-dir",type=Path,required=True)
    parser.add_argument("--seed-start",type=int,required=True)
    parser.add_argument("--seeds",type=int,default=2)
    parser.add_argument("--out-dir",type=Path,required=True)
    parser.add_argument("--resume",action="store_true")
    args=parser.parse_args()
    result=run_guarded_trial(
        training_dir=args.train_dir,
        prior_m437_dir=args.prior_m437_dir,
        prior_m439_dir=args.prior_m439_dir,
        seed_start=args.seed_start,
        seeds=args.seeds,
        out_dir=args.out_dir,
        resume=args.resume,
    )
    print(json.dumps({
        "independent_shuffles":result["completed_original_shuffle_clusters"],
        "real_nine_game_total":result["actual_complete_paid_games"],
        "unguarded_delta":result["unguarded"][
            "mean_paired_official_net_delta_points"],
        "guarded_delta":result["guarded"][
            "mean_paired_official_net_delta_points"],
        "unguarded_overrides":result["unguarded"]["actual_model_overrides"],
        "guarded_overrides":result["guarded"]["actual_model_overrides"],
        "guarded_rejected_regressions":
            result["guarded"]["guard_blocked_lower_ukeire_overrides"],
        "safe_summary":str(args.out_dir/
                            "safe_guarded_frozen_shadow_trial.json"),
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
