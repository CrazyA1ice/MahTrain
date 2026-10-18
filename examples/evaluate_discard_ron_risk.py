#!/usr/bin/env python3
"""M3.57 offline candidate-discard deal-in risk + payout pilot (stdlib).

It writes aggregate held-out metrics only, never concealed tile identities,
per-target waits, individual observations, or trained live weights.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.ai_ron_calibration import run_candidate_ron_pilot


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start",type=int,default=100)
    parser.add_argument("--train-seeds",type=int,default=4)
    parser.add_argument("--test-seeds",type=int,default=3)
    parser.add_argument("--stride",type=int,default=6)
    parser.add_argument("--json-out",type=Path)
    args=parser.parse_args()
    if (args.seed_start<0 or args.train_seeds<1 or args.test_seeds<1
        or args.train_seeds>50 or args.test_seeds>50
        or args.seed_start+args.train_seeds+args.test_seeds>2**32):
        parser.error("invalid independent train/test shuffle seed configuration")
    train=list(range(args.seed_start,args.seed_start+args.train_seeds))
    test=list(range(train[-1]+1,train[-1]+1+args.test_seeds))
    report=run_candidate_ron_pilot(train,test,stride=args.stride)
    print("M3.57 offline candidate-specific true ron (not live AI)")
    print("Independent seed clusters",len(train),"train /",len(test),"held out")
    print("Train candidate rows",report["train_n"],
          "true ron events",report["train_ron_events"])
    print("Held-out candidate rows",report["test_n"],
          "true ron events",report["test_ron_events"])
    for name in ("baseline","candidate"):
        scores=report[name]
        print(name,"Brier",scores["brier"],
              "LogLoss",scores["log_loss"],
              "ECE",scores["ece"],
              "Payout MSE",scores["payout_multiplier_mse"])
    print("Brier delta",report["brier_delta_vs_legal_suit_prior"])
    print("Payout MSE delta",report["payout_mse_delta"])
    print("Warning: exploratory only; not a validated posterior or online AI.")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True,exist_ok=True)
        args.json_out.write_text(
            json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
