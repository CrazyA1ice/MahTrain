r"""M4.50: confirm NEW-shuffle first-peng mid-vs-early paid branch contrast.

Run from MahTrain root, Windows PowerShell:
 python examples\run_pong_phase_confirmation.py --train-dir data/selfplay/m434-smoke --prior-m449-dir data/selfplay/m449-pong-strata-24 --seed-start 93600 --out-dir data/selfplay/m450-phase-48

Resume ONLY using identical args + --resume. Publish just the safe
safe_pong_phase_confirmation.json, NOT private sources/seed shards.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_pong_phase_confirmation import SEED_COUNT
from mahtrain_core.ai_pong_phase_confirmation_run import run_phase_confirmation


def main()->None:
    p=argparse.ArgumentParser(description="M4.50 original-shuffle validation of mid-vs-early pass/peng authentic official-game outcomes")
    p.add_argument("--train-dir",type=Path,required=True)
    p.add_argument("--prior-m449-dir",type=Path,required=True)
    p.add_argument("--seed-start",type=int,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--resume",action="store_true")
    a=p.parse_args()
    result=run_phase_confirmation(
        training_dir=a.train_dir,
        prior_m449_dir=a.prior_m449_dir,
        seed_start=a.seed_start,
        seeds=SEED_COUNT,
        out_dir=a.out_dir,
        resume=a.resume,
    )
    print(json.dumps({
        "new_independent_shuffle_clusters":SEED_COUNT,
        "real_true_full_games":result["actual_total_complete_paid_games"],
        "comparison_status":result["comparison_status"],
        "middle_minus_early":result["middle_minus_early_mean_net_points"],
        "safe_report":str(a.out_dir/"safe_pong_phase_confirmation.json"),
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
