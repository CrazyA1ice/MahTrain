"""M4.12: replicate the frozen M4.11 candidate on NEW independent seeds."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_minggang_replication_gate import (
    PROTOCOL,DEVELOPMENT_START,HOLDOUT_START,SEEDS_PER_BLOCK,
    evaluate_block,original_paired_cohort,study,
)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","holdout","both"),
                   default="both")
    p.add_argument("--development",type=int,default=DEVELOPMENT_START)
    p.add_argument("--holdout",type=int,default=HOLDOUT_START)
    p.add_argument("--seeds",type=int,default=SEEDS_PER_BLOCK)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    d,h,n=args.development,args.holdout,args.seeds
    if (type(d) is not int or type(h) is not int or type(n) is not int or
            not 1<=n<=SEEDS_PER_BLOCK or not 0<=d<2**32 or
            not 0<=h<2**32 or max(d,h)+n>2**32 or
            (d<h+n and h<d+n)):
        raise ValueError("M4.12 requires precommitted independent disjoint ranges")
    if args.cohort=="both":
        result=study(development=d,holdout=h,seeds=n)
    else:
        seed_start=d if args.cohort=="development" else h
        block=evaluate_block(original_paired_cohort(seed_start,n),
                             start=seed_start,seeds=n)
        result={
            "protocol":PROTOCOL,"cohort":args.cohort,
            "seed_start":seed_start, "candidate_only_offline":True,
            "online_policy_modified":False,
            "result":block,
        }
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                               encoding="utf-8")
    for name in (("development","holdout") if args.cohort=="both"
                 else (args.cohort,)):
        block=result[name] if args.cohort=="both" else result["result"]
        print("M4.12 NEW INDEPENDENT FROZEN PAIRED REPLICATION",json.dumps({
            "cohort":name,"seeds":block["shuffle_seeds"],
            "games":block["complete_games"],
            "real_policy_changes":block["actual_interventions"],
            "treated_seed_clusters":block["independent_seeds_with_interventions"],
            "positive":block["positive_seed_clusters"],
            "negative":block["negative_seed_clusters"],
            "mean_official_net_delta":block["mean_four_seat_official_net_delta"],
            "official_components":block["official_component_deltas"],
            "gate":block["predeclared_more_research_gate_passed"],
            "blockers":block["blockers"],
            "per_seed":block["per_seed"],
        },ensure_ascii=False))
