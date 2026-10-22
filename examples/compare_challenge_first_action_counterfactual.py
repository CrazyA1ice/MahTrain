"""M3.97 reproducible official 108-tile single-action terminal counterfactuals."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_challenge_action_counterfactual import study


def main():
    p=argparse.ArgumentParser(
        description="M3.97: offline first call/kong terminal outcomes, no live oracle")
    p.add_argument("--development",type=int,default=14000)
    p.add_argument("--holdout",type=int,default=15000)
    p.add_argument("--seeds",type=int,default=2)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    data=study(development_start=args.development,
               holdout_start=args.holdout,seeds_per_group=args.seeds)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(
            json.dumps(data,ensure_ascii=False,indent=2)+"\n",
            encoding="utf-8")
        print("Saved offline counterfactual:",args.output)
    else:
        print(json.dumps(data,ensure_ascii=False,indent=2))
    for cohort in ("development","holdout"):
        for target,summary in data[cohort]["targets"].items():
            for policy,item in summary["policy_comparisons"].items():
                print("M3.97 RESULT",json.dumps({
                    "cohort":cohort,"target":target,"policy":policy,
                    "offered_positions":summary["offered_positions"],
                    "changed_positions":item["changed_positions"],
                    "mean_seed_cluster_net_delta":
                        item["mean_seed_cluster_net_delta"],
                    "positive_seeds":item["positive_seeds"],
                    "negative_seeds":item["negative_seeds"],
                    "tied_seeds":item["tied_seeds"],
                    "cumulative_official_component_deltas":
                        item["cumulative_official_component_deltas"],
                    "per_seed":summary["per_seed"],
                    "interval_95pct":item["interval_95pct"],
                },ensure_ascii=False))


if __name__=="__main__":
    main()
