"""Run the OFFLINE fixed-policy call/kong three-arm paired experiment."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_challenge_call_kong_ablation import study


def main() -> None:
    parser=argparse.ArgumentParser(
        description="M3.95 offline challenge vs no-tie-peng/no-kong ablations")
    parser.add_argument("--development",type=int,default=12000)
    parser.add_argument("--holdout",type=int,default=13000)
    parser.add_argument("--seeds",type=int,default=2)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    data=study(development_start=args.development,
               holdout_start=args.holdout,seeds_per_group=args.seeds)
    rendered=json.dumps(data,ensure_ascii=False,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(rendered+"\n",encoding="utf-8")
        print("Saved offline aggregate:",args.output)
    else:
        print(rendered)
    for label in ("development","holdout"):
        group=data[label]
        for arm,metrics in group["comparisons"].items():
            print("M3.95 GROUP",label,arm,json.dumps({
                "independent_seeds":group["independent_seeds"],
                "complete_games":group["complete_games"],
                "mean_net_delta":metrics["mean_seed_cluster_net_delta"],
                "positive":metrics["positive_seeds"],
                "negative":metrics["negative_seeds"],
                "tied":metrics["tied_seeds"],
                "opportunities":metrics["opportunity_counts"],
                "per_seed":[{"seed":r["seed"],
                             "net_delta":r["four_seat_delta"][arm]["official_net"]}
                            for r in group["per_seed"]],
                "interval_95pct":metrics["interval_95pct"],
            },ensure_ascii=False))


if __name__=="__main__":
    main()
