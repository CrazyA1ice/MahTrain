r"""M4.42: fresh independent Challenge-only safe-cut opportunity probe.

Windows PowerShell from MahTrain root:
  python examples\run_challenge_tie_opportunity_probe.py --train-dir data/selfplay/m434-smoke --prior-m437-dir data/selfplay/m437-shadow-2 --prior-m439-dir data/selfplay/m439-actor-2 --prior-m441-dir data/selfplay/m441-guarded-2 --seed-start 91700 --seeds 2 --out-dir data/selfplay/m442-safe-ties-2

Each original shuffle requires only ONE genuine full Challenge four-seat game
(no shadow candidates yet). If interrupted, same arguments plus --resume.
Share ONLY safe_challenge_tie_opportunities.json, not PRIVATE* files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mahtrain_core.ai_challenge_tie_opportunities import run_new_seed_tie_audit


def main()->None:
    parser=argparse.ArgumentParser(description="M4.42 live Challenge safe alternative space on independent new shuffles")
    parser.add_argument("--train-dir",type=Path,required=True)
    parser.add_argument("--prior-m437-dir",type=Path,required=True)
    parser.add_argument("--prior-m439-dir",type=Path,required=True)
    parser.add_argument("--prior-m441-dir",type=Path,required=True)
    parser.add_argument("--seed-start",type=int,required=True)
    parser.add_argument("--seeds",type=int,default=2)
    parser.add_argument("--out-dir",type=Path,required=True)
    parser.add_argument("--resume",action="store_true")
    args=parser.parse_args()
    safe=run_new_seed_tie_audit(
        training_dir=args.train_dir,
        prior_m437_dir=args.prior_m437_dir,
        prior_m439_dir=args.prior_m439_dir,
        prior_m441_dir=args.prior_m441_dir,
        seed_start=args.seed_start,
        seeds=args.seeds,
        out_dir=args.out_dir,
        resume=args.resume,
    )
    totals=safe["counts"]
    print(json.dumps({
        "independent_shuffles":safe["independent_original_shuffle_clusters"],
        "real_complete_baseline_games":safe["actual_complete_four_challenge_games"],
        "challenge_discard_decisions":totals["discard_decisions"],
        "decisions_with_safe_same_ukeire_alternative":
            totals["decisions_with_equal_ukeire_alternative"],
        "decisions_with_higher_ukeire_alternative":
            totals["decisions_with_higher_ukeire_alternative"],
        "safe_summary":str(args.out_dir/"safe_challenge_tie_opportunities.json"),
        "no_new_policy_claim":True,
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
