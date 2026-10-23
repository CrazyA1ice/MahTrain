"""M4.14 frozen public near-value discard research, complete official games."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_discard_nearvalue_risk_paired import (
    PROTOCOL,MIN_PUBLIC_THREAT_REDUCTION,MIN_VALUE_RETENTION,
    MIN_UKEIRE_RETENTION,cohort,study,
)
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--cohort",choices=("development","holdout","both"),
                        default="both")
    parser.add_argument("--development",type=int,default=52000)
    parser.add_argument("--holdout",type=int,default=53000)
    parser.add_argument("--seeds",type=int,default=4)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    d,h,n=args.development,args.holdout,args.seeds
    if (type(d) is not int or type(h) is not int or type(n) is not int or
            not 0<=d<2**32 or not 0<=h<2**32 or not 1<=n<=8 or
            max(d,h)+n>2**32 or (d<h+n and h<d+n)):
        raise ValueError("new disjoint precommitted shuffle blocks required")
    if args.cohort=="both":
        report=study(development=d,holdout=h,seeds=n)
    else:
        start=d if args.cohort=="development" else h
        report={"protocol":PROTOCOL,"cohort":args.cohort,
                "seed_start":start,"online_policy_modified":False,
                "result":cohort(start,n)}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",
                               encoding="utf-8")
    for name in (("development","holdout") if args.cohort=="both" else
                 (args.cohort,)):
        x=report[name] if args.cohort=="both" else report["result"]
        print("M4.14 FROZEN NEARVALUE DISCARDS PAIRED OFFICIAL",json.dumps({
            "cohort":name,
            "independent_shuffle_seeds":x["independent_shuffle_seeds"],
            "complete_games":x["complete_games"],
            "baseline_discard_decisions":x["total_baseline_discards"],
            "multiple_minimum_shanten_cuts":x[
                "multiple_minimum_shanten_cuts"],
            "real_discard_interventions":x["actual_discard_interventions"],
            "changed_seed_clusters":x["seeds_with_interventions"],
            "positive_seeds":x["positive_seed_clusters"],
            "negative_seeds":x["negative_seed_clusters"],
            "official_net_delta":x["official_component_deltas"].get("official_net",0),
            "mean_seed_net_delta":x["mean_four_seat_official_net_delta"],
            "frozen_public_reduction":MIN_PUBLIC_THREAT_REDUCTION,
            "value_retention":MIN_VALUE_RETENTION,
            "ukeire_retention":MIN_UKEIRE_RETENTION,
            "per_seed":x["per_seed"],
        },ensure_ascii=False))
