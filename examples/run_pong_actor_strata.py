r"""M4.49 first genuine Challenge pass/peng, only actor-visible strata.

Run from MahTrain root in Windows PowerShell:
 python examples\run_pong_actor_strata.py --train-dir data/selfplay/m434-smoke --prior-m448-dir data/selfplay/m448-pong-pass-24 --seed-start 93300 --out-dir data/selfplay/m449-pong-strata-24

Requires the PRIVATE files for M4.34..M4.48 still on this computer.
Only upload safe_pong_actor_strata.json. Add --resume on interruption.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_pong_actor_strata import SEED_COUNT
from mahtrain_core.ai_pong_actor_strata_run import run_actor_strata


def main()->None:
    p=argparse.ArgumentParser(
        description="M4.49 real first pass/peng paired payout by pre-action own-view category"
    )
    p.add_argument("--train-dir",type=Path,required=True)
    p.add_argument("--prior-m448-dir",type=Path,required=True)
    p.add_argument("--seed-start",type=int,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--resume",action="store_true")
    x=p.parse_args()
    safe=run_actor_strata(
        training_dir=x.train_dir,prior_m448_dir=x.prior_m448_dir,
        seed_start=x.seed_start,seeds=SEED_COUNT,
        out_dir=x.out_dir,resume=x.resume,
    )
    print(json.dumps({
        "new_original_shuffle_clusters":safe["independent_original_shuffle_clusters"],
        "legal_first_pass_peng_clusters":
            safe["eligible_first_peng_after_original_challenge_pass_clusters"],
        "real_completed_branch_games":safe["true_full_terminal_branch_games"],
        "safe_output":str(x.out_dir/"safe_pong_actor_strata.json"),
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
