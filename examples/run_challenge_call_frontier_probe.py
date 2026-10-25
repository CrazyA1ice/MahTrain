r"""M4.44: fresh-shuffle real Challenge legal response/kong opportunity census.

From repo root in Windows PowerShell (no extra Python packages):
  python examples\run_challenge_call_frontier_probe.py --train-dir data/selfplay/m434-smoke --prior-m442-dir data/selfplay/m442-safe-ties-2 --prior-m443-dir data/selfplay/m443-safe-tie-2 --seed-start 92100 --seeds 2 --out-dir data/selfplay/m444-call-frontier-2

Only one authentic complete 4-seat Challenge game per new shuffle.
Use same arguments plus --resume after interruption. Do not upload PRIVATE*
files. Only share safe_challenge_call_frontier.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mahtrain_core.ai_challenge_call_frontier import run_new_seed_claim_frontier


def main()->None:
    p=argparse.ArgumentParser(
        description="M4.44 new-shuffle unchanged Challenge call/kong/hu frontier"
    )
    p.add_argument("--train-dir",required=True,type=Path)
    p.add_argument("--prior-m442-dir",required=True,type=Path)
    p.add_argument("--prior-m443-dir",required=True,type=Path)
    p.add_argument("--seed-start",required=True,type=int)
    p.add_argument("--seeds",type=int,default=2)
    p.add_argument("--out-dir",required=True,type=Path)
    p.add_argument("--resume",action="store_true")
    args=p.parse_args()
    report=run_new_seed_claim_frontier(
        training_dir=args.train_dir,prior_m442_dir=args.prior_m442_dir,
        prior_m443_dir=args.prior_m443_dir,
        seed_start=args.seed_start,seeds=args.seeds,
        out_dir=args.out_dir,resume=args.resume,
    )
    c=report["counts"]
    print(json.dumps({
        "new_original_shuffle_clusters":report["independent_original_shuffle_clusters"],
        "real_finished_original_challenge_games":
            report["real_finished_four_player_challenge_games"],
        "claim_peng_or_ming_gang_windows":c["claim_action_choice_windows"],
        "own_kong_checks_with_options":c["own_kong_checks_with_options"],
        "legal_claim_hu_windows":c["claim_legal_hu_windows"],
        "safe_report":str(args.out_dir/"safe_challenge_call_frontier.json"),
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
