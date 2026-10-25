r"""M4.43: nine real finished Mahjong matches for each unseen original shuffle.

Run from MahTrain root in Windows PowerShell:
  python examples\run_safe_tie_risk_fan_trial.py --train-dir data/selfplay/m434-smoke --prior-m437-dir data/selfplay/m437-shadow-2 --prior-m439-dir data/selfplay/m439-actor-2 --prior-m441-dir data/selfplay/m441-guarded-2 --prior-m442-dir data/selfplay/m442-safe-ties-2 --seed-start 91900 --seeds 2 --out-dir data/selfplay/m443-safe-tie-2

Resume an interrupted run using exactly the same args plus --resume.
Only share safe_tie_risk_fan_trial.json, never PRIVATE* local checkpoints.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mahtrain_core.ai_safe_tie_policy_trial import run_safe_tie_trial


def main()->None:
    parser=argparse.ArgumentParser(
        description="M4.43 fresh-seed Challenge versus risk-first versus fan-first equal-ukeire controlled paid trial"
    )
    for name in ("train-dir","prior-m437-dir","prior-m439-dir",
                 "prior-m441-dir","prior-m442-dir","out-dir"):
        parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--seed-start",type=int,required=True)
    parser.add_argument("--seeds",type=int,default=2)
    parser.add_argument("--resume",action="store_true")
    a=parser.parse_args()
    result=run_safe_tie_trial(
        training_dir=a.train_dir,
        prior_m437_dir=a.prior_m437_dir,
        prior_m439_dir=a.prior_m439_dir,
        prior_m441_dir=a.prior_m441_dir,
        prior_m442_dir=a.prior_m442_dir,
        seed_start=a.seed_start,
        seeds=a.seeds,
        out_dir=a.out_dir,
        resume=a.resume,
    )
    print(json.dumps({
        "independent_original_shuffles":result["independent_original_shuffle_seed_clusters"],
        "finished_real_games":result["true_complete_official_games"],
        "risk_first_net_delta":result["risk_first"]["mean_paired_official_net_delta_points"],
        "risk_first_actual_overrides":result["risk_first"]["actual_safe_tie_overrides"],
        "fan_first_net_delta":result["fan_first"]["mean_paired_official_net_delta_points"],
        "fan_first_actual_overrides":result["fan_first"]["actual_safe_tie_overrides"],
        "safe_summary":str(a.out_dir/"safe_tie_risk_fan_trial.json"),
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
