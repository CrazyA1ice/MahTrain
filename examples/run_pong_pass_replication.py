r"""M4.48: 24 *new* original shuffles, unchanged M4.47 first pass/peng branches.

Windows PowerShell at MahTrain root:
 python examples\run_pong_pass_replication.py --train-dir data/selfplay/m434-smoke --prior-m447-dir data/selfplay/m447-pong-pass-8 --seed-start 93000 --out-dir data/selfplay/m448-pong-pass-24

Add --resume to the exact same command after interruption.
Only upload safe_pong_pass_replication.json; PRIVATE files stay local.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mahtrain_core.ai_pong_pass_replication import SEED_COUNT
from mahtrain_core.ai_pong_pass_replication_run import run_independent_branch_replication


def main()->None:
    parser=argparse.ArgumentParser(
        description="M4.48 24 fresh shuffle first Challenge pass/peng real paid branch replication"
    )
    parser.add_argument("--train-dir",type=Path,required=True)
    parser.add_argument("--prior-m447-dir",type=Path,required=True)
    parser.add_argument("--seed-start",type=int,required=True)
    parser.add_argument("--out-dir",type=Path,required=True)
    parser.add_argument("--resume",action="store_true")
    args=parser.parse_args()
    safe=run_independent_branch_replication(
        training_dir=args.train_dir,
        prior_m447_dir=args.prior_m447_dir,
        seed_start=args.seed_start,seeds=SEED_COUNT,
        out_dir=args.out_dir,resume=args.resume,
    )
    print(json.dumps({
        "independent_shuffles":safe["new_independent_original_shuffle_clusters"],
        "total_real_games":safe["total_true_complete_paid_games"],
        "matched_branch_pairs":safe["two_world_matched_branch_pairs"],
        "mean_forced_peng_minus_pass_points":
            safe["mean_forced_peng_minus_pass_official_net_points"],
        "sample_mean_cluster_bootstrap_interval_exploratory":
            safe["seed_cluster_bootstrap_mean_delta_percentile_95_exploratory"],
        "safe_report":str(args.out_dir/"safe_pong_pass_replication.json"),
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
