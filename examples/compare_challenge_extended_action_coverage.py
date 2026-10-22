"""M3.98 CLI: non-selected natural action coverage and larger paired holdout."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_action_extended_study import study


def main():
    p=argparse.ArgumentParser(
        description="Natural four-seat kong coverage + fixed first-choice terminal pairing")
    p.add_argument("--mode",choices=["coverage","paired","all"],default="all")
    p.add_argument("--coverage-development",type=int,default=16000)
    p.add_argument("--coverage-holdout",type=int,default=17000)
    p.add_argument("--paired-development",type=int,default=18000)
    p.add_argument("--paired-holdout",type=int,default=19000)
    p.add_argument("--coverage-seeds",type=int,default=8)
    p.add_argument("--paired-seeds",type=int,default=4)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    result=study(
        coverage_development=args.coverage_development,
        coverage_holdout=args.coverage_holdout,
        paired_development=args.paired_development,
        paired_holdout=args.paired_holdout,
        coverage_seeds=args.coverage_seeds,
        paired_seeds=args.paired_seeds,mode=args.mode,
    )
    rendered=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(rendered+"\n",encoding="utf-8")
        print("Saved offline M3.98 result:",args.output)
    else:
        print(rendered)
    if "coverage" in result:
        for cohort,row in result["coverage"].items():
            print("M3.98 COVERAGE",json.dumps({
                "cohort":cohort,
                "seeds":row["independent_seeds"],
                "positions":row["four_seat_positions"],
                "own_kong_positions":row["positions_with_own_kong"],
                "claim_positions":row["positions_with_claim"],
                "counts":row["total_counts"],
                "per_seed":row["per_seed"],
            },ensure_ascii=False))
    if "paired" in result:
        for cohort,row in result["paired"].items():
            for target,details in row["target_summaries"].items():
                for policy,score in details["policies"].items():
                    print("M3.98 PAIRED",json.dumps({
                        "cohort":cohort,
                        "target":target,"policy":policy,
                        "seeds":row["independent_seeds"],
                        "offered":details["opportunities"],
                        "changed":score["changed_positions"],
                        "net_delta":score["mean_seed_cluster_net_delta"],
                        "positive_seeds":score["positive_seed_clusters"],
                        "negative_seeds":score["negative_seed_clusters"],
                        "cumulative_components":score["cumulative_official_component_deltas"],
                        "strata":score["public_prechoice_strata"],
                        "per_seed":details["per_seed"],
                    },ensure_ascii=False))


if __name__=="__main__":
    main()
