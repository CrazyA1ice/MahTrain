r"""M4.47: eight fresh natural first-pass-with-peng paired real rollouts.

Run in MahTrain root:
 python examples\run_pong_pass_branch_rollouts.py --train-dir data/selfplay/m434-smoke --prior-m446-dir data/selfplay/m446-pong-20 --seed-start 92800 --out-dir data/selfplay/m447-pong-pass-8

No extra packages/CI payments. Add --resume to the exact same command
after interruption. Share safe_pong_pass_branch_rollouts.json only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mahtrain_core.ai_pong_pass_branch_rollouts import (
    SEED_COUNT, run_matched_pong_branch_trial,
)


def main()->None:
    p=argparse.ArgumentParser(description="M4.47 genuine matched-state first legal Challenge pass vs forced peng end-to-end branches")
    p.add_argument("--train-dir",required=True,type=Path)
    p.add_argument("--prior-m446-dir",required=True,type=Path)
    p.add_argument("--seed-start",required=True,type=int)
    p.add_argument("--out-dir",required=True,type=Path)
    p.add_argument("--resume",action="store_true")
    x=p.parse_args()
    safe=run_matched_pong_branch_trial(
        training_dir=x.train_dir,prior_m446_dir=x.prior_m446_dir,
        seed_start=x.seed_start,seeds=SEED_COUNT,
        out_dir=x.out_dir,resume=x.resume,
    )
    print(json.dumps({
        "independent_shuffles":safe["independent_original_shuffle_clusters"],
        "baseline_games":safe["actual_natural_original_challenge_games"],
        "first_eligible_pass_peng_shuffles":safe[
            "original_shuffles_with_legal_peng_after_challenge_pass"],
        "fully_paid_branch_games":safe["genuine_full_terminal_branch_games"],
        "mean_paired_net_all_shuffles":safe[
            "mean_forced_peng_minus_pass_all_seed_clusters"],
        "safe_report":str(x.out_dir/"safe_pong_pass_branch_rollouts.json"),
        "no_policy_promotion_or_generalization_claim":True,
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
