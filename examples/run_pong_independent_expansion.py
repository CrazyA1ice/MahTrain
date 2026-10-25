r"""M4.46: unchanged M4.45 peng threshold on 20 NEW original shuffles.

Windows PowerShell:
  python examples\run_pong_independent_expansion.py --train-dir data/selfplay/m434-smoke --prior-m445-dir data/selfplay/m445-pong-2 --seed-start 92500 --out-dir data/selfplay/m446-pong-20

If interrupted, run the EXACT same command adding --resume.
Only share safe_pong_independent_expansion.json. Keep PRIVATE* locally.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_pong_independent_expansion import (
    FROZEN_SEED_COUNT, run_independent_pong_expansion,
)


def main()->None:
    parser=argparse.ArgumentParser(
        description="M4.46 locked M4.45 policy on 20 genuinely fresh paid shuffle clusters"
    )
    parser.add_argument("--train-dir",type=Path,required=True)
    parser.add_argument("--prior-m445-dir",type=Path,required=True)
    parser.add_argument("--seed-start",type=int,default=92500)
    parser.add_argument("--out-dir",type=Path,required=True)
    parser.add_argument("--resume",action="store_true")
    args=parser.parse_args()
    safe=run_independent_pong_expansion(
        training_dir=args.train_dir,prior_m445_dir=args.prior_m445_dir,
        seed_start=args.seed_start,seeds=FROZEN_SEED_COUNT,
        out_dir=args.out_dir,resume=args.resume,
    )
    print(json.dumps({
        "independent_original_shuffles":safe["independent_original_shuffle_clusters"],
        "real_full_paid_games":safe["real_complete_paid_games"],
        "candidate_peng_overrides":safe["actual_peng_overrides"],
        "independent_shuffles_with_override":
            safe["original_shuffles_with_actual_peng_override"],
        "mean_official_net_delta_points":safe["mean_official_net_delta_points"],
        "safe_summary":str(args.out_dir/"safe_pong_independent_expansion.json"),
        "no_strength_claim":True,
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
