"""M4.05 fixed-seed dual optional-call fastpath performance and payoff."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_dual_claim_fastpath_paired import (
    PROTOCOL,cohort,study,
)


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","holdout","both"),
                   default="both")
    p.add_argument("--development",type=int,default=34000)
    p.add_argument("--holdout",type=int,default=35000)
    p.add_argument("--seeds",type=int,default=8)
    p.add_argument("--output",type=Path)
    x=p.parse_args()
    if (not 1<=x.seeds<=8 or min(x.development,x.holdout)<0 or
        max(x.development,x.holdout)+x.seeds>2**32 or
        (x.development<x.holdout+x.seeds and
         x.holdout<x.development+x.seeds)):
        raise ValueError("cohorts must be predeclared and non-overlapping")
    if x.cohort=="both":
        result=study(development=x.development,
                     holdout=x.holdout,seeds=x.seeds)
    else:
        start=x.development if x.cohort=="development" else x.holdout
        result={
            "protocol":PROTOCOL,"online_challenge_modified":False,
            "cohort":x.cohort,"seed_start":start,
            "result":cohort(start,x.seeds),
        }
    if x.output:
        x.output.parent.mkdir(parents=True,exist_ok=True)
        x.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                            encoding="utf8")
        print("Saved M4.05",x.output)
    for name in ("development","holdout"):
        if name not in result and result.get("cohort")!=name:continue
        group=result[name] if name in result else result["result"]
        print("M4.05 PAIRED VERIFIED",json.dumps({
            "cohort":name,
            "independent_seeds":group["independent_shuffle_seeds"],
            "paired_positions":group["paired_four_seat_positions"],
            "complete_games":group["complete_official_games"],
            "seed_mean_net_delta":group["seed_average_official_net_delta"],
            "positive_seeds":group["positive_delta_seeds"],
            "negative_seeds":group["negative_delta_seeds"],
            "unchanged_seeds":group["unchanged_delta_seeds"],
            "components":group["official_component_deltas"],
            "counts":group["counts_by_arm"],
            "latency":group["latency_descriptive_only"],
            "per_seed":group["per_seed"],
        },ensure_ascii=False))


if __name__=="__main__":
    main()
