"""M3.99 repeat-aware voluntary kong audits with untouched live policy."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_bugang_repeat_risk import study


def main() -> None:
    p=argparse.ArgumentParser(
        description="M3.99 repeated bu-gang and rob audit on unselected seeds")
    p.add_argument("--mode",choices=("natural","paired","all"),default="all")
    p.add_argument("--natural-development",type=int,default=20000)
    p.add_argument("--natural-holdout",type=int,default=21000)
    p.add_argument("--paired-development",type=int,default=22000)
    p.add_argument("--paired-holdout",type=int,default=23000)
    p.add_argument("--seeds",type=int,default=8)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    result=study(natural_development=args.natural_development,
                 natural_holdout=args.natural_holdout,
                 paired_development=args.paired_development,
                 paired_holdout=args.paired_holdout,
                 seeds_per_group=args.seeds,mode=args.mode)
    formatted=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(formatted+"\n",encoding="utf8")
        print("Saved offline M3.99 study:",args.output)
    else:
        print(formatted)
    if "natural" in result:
        for cohort,group in result["natural"].items():
            print("M3.99 NATURAL",json.dumps({
                "cohort":cohort,"independent_seeds":group["independent_seeds"],
                "four_seat_positions":group["four_seat_positions"],
                "counts":group["total_counts"],"per_seed":group["per_seed"],
            },ensure_ascii=False))
    if "paired" in result:
        for cohort,group in result["paired"].items():
            for arm,row in group["arms"].items():
                print("M3.99 PAIRED",json.dumps({
                    "cohort":cohort,"arm":arm,
                    "independent_seeds":group["independent_seeds"],
                    "offered":row["offered_positions"],
                    "changed":row["changed_positions"],
                    "mean_seed_cluster_net_delta":
                        row["mean_seed_cluster_net_delta"],
                    "positive_seeds":row["positive_seeds"],
                    "negative_seeds":row["negative_seeds"],
                    "tied_seeds":row["tied_seeds"],
                    "types":row["candidate_types"],
                    "official_component_delta":
                        row["cumulative_official_component_deltas"],
                    "per_seed":group["per_seed"],
                },ensure_ascii=False))


if __name__=="__main__":
    main()
