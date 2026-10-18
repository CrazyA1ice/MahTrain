#!/usr/bin/env python3
"""M3.56 offline self-play tenpai calibration pilot; stdlib only.

Only AGGREGATE seed-split results are written to JSON. True private hands are
used transiently by the trusted test harness solely to compute labels.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core.ai_tenpai_calibration import run_seed_split_pilot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=70)
    parser.add_argument("--train-seeds", type=int, default=2)
    parser.add_argument("--test-seeds", type=int, default=1)
    parser.add_argument("--stride", type=int, default=5)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    if (type(args.train_seeds) is not int or not 1 <= args.train_seeds <= 40
        or not 1 <= args.test_seeds <= 40
        or args.seed_start < 0
        or args.seed_start + args.train_seeds + args.test_seeds > 2**32):
        parser.error("must have 1..40 training and test shuffle seeds within uint32")
    train = list(range(args.seed_start, args.seed_start + args.train_seeds))
    test = list(range(train[-1] + 1, train[-1] + args.test_seeds + 1))
    report = run_seed_split_pilot(train, test, stride=args.stride)
    print("MahTrain M3.56 / offline only, disjoint shuffle seeds")
    print("Train:", train, "observations:", report["train_n"],
          "true tenpai:", report["train_positives"])
    print("Held-out seeds:", test, "observations:", report["test_n"],
          "true tenpai:", report["candidate"]["positives"])
    for label, item in (("Prior baseline", report["baseline"]),
                        ("Public-feature logistic", report["candidate"])):
        print(label + ": Brier=" + str(item["brier"])
              + " LogLoss=" + str(item["log_loss"])
              + " ECE=" + str(item["ece"]))
    print("Held-out Brier delta (candidate minus prior):",
          report["brier_delta_vs_prior"])
    print("WARNING: exploratory, not an online policy or proven improvement.")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
