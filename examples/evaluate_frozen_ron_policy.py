#!/usr/bin/env python3
"""M3.59 offline-only frozen risk model cross-strategy and paired whole-game trial."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.ai_ron_frozen_experiment import run_frozen_risk_research


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed-start",type=int,default=140)
    p.add_argument("--train-seeds",type=int,default=6)
    p.add_argument("--cross-seeds",type=int,default=2)
    p.add_argument("--paired-seeds",type=int,default=2)
    p.add_argument("--stride",type=int,default=3)
    p.add_argument("--risk-scale",type=float,default=1.8)
    p.add_argument("--json-out",type=Path)
    args=p.parse_args()
    if (args.seed_start<0 or args.train_seeds not in range(1,41)
        or args.cross_seeds not in range(1,11)
        or args.paired_seeds not in range(1,11)
        or args.seed_start+args.train_seeds+args.cross_seeds+
        args.paired_seeds>2**32):
        p.error("seed start must be uint32 with 1..40 train, 1..10 cross, 1..10 paired")
    start=args.seed_start
    train=list(range(start,start+args.train_seeds))
    start=train[-1]+1
    cross=list(range(start,start+args.cross_seeds))
    start=cross[-1]+1
    paired=list(range(start,start+args.paired_seeds))
    result=run_frozen_risk_research(
        train,cross,paired,stride=args.stride,
        risk_scale=args.risk_scale,bootstrap=512,
    )
    print("M3.59 OFFLINE frozen ron model, no live policy changes")
    print("training independent seeds",len(train),
          "candidate observations",result["training_samples"],
          "ron positives",result["training_ron_events"])
    print("model fingerprint",result["frozen_model_fingerprint"])
    for name,report in result["cross_policy"].items():
        print("cross-policy",name,"test samples",report["samples"],
              "ron positives",report["true_ron_events"],
              "Brier delta",report["brier_delta"],
              "payout MSE delta",report["payout_mse_delta"])
    pairs=result["paired"]
    print("paired full-ledger games",pairs["game_pairs"],
          "changed discards",pairs["total_changed_discards"])
    print("baseline total net",pairs["baseline_net_sum"],
          "frozen-risk total net",pairs["treatment_net_sum"],
          "paired delta",pairs["paired_net_delta"])
    print("seed-cluster paired net-delta interval",
          pairs["seed_bootstrap_net_delta"]["bootstrap_95pct_range"])
    print("WARNING: exploratory-only; small seed sample and strongly dependent plays.")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True,exist_ok=True)
        args.json_out.write_text(
            json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")


if __name__=="__main__":
    main()
