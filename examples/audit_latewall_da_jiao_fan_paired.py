"""M4.17: new preregistered four-seat full-score late-wall tenpai trial."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_latewall_da_jiao_fan_paired import (
    PROTOCOL,cohort,study,
)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","holdout","both"),
                   default="both")
    p.add_argument("--development",type=int,default=54000)
    p.add_argument("--holdout",type=int,default=55000)
    p.add_argument("--seeds",type=int,default=4)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    d,h,n=args.development,args.holdout,args.seeds
    if (type(d) is not int or type(h) is not int or type(n) is not int or
            not 1<=n<=8 or not 0<=d<2**32 or not 0<=h<2**32 or
            max(d,h)+n>2**32 or (d<h+n and h<d+n)):
        raise ValueError("requires two disjoint independent shuffle cohorts")
    if args.cohort=="both":
        output=study(development=d,holdout=h,seeds=n)
    else:
        start=d if args.cohort=="development" else h
        output={
            "protocol":PROTOCOL,"cohort":args.cohort,"seed_start":start,
            "online_policy_modified":False,"candidate_only_offline":True,
            "result":cohort(start,n),
        }
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(
            json.dumps(output,ensure_ascii=False,indent=2)+"\n",
            encoding="utf8")
    names=("development","holdout") if args.cohort=="both" else (args.cohort,)
    for name in names:
        result=output[name] if args.cohort=="both" else output["result"]
        print("M4.17 NEW LATE-WALL OFFICIAL TENPAI FAN PAIRED",json.dumps({
            "cohort":name,
            "independent_shuffles":result["independent_shuffles"],
            "complete_games":result["complete_official_games"],
            "baseline_cuts":result["baseline_cuts"],
            "baseline_late_cuts":result["baseline_late_cuts"],
            "baseline_tenpai_cuts":result["baseline_tenpai_cuts"],
            "actual_interventions":result["actual_interventions"],
            "baseline_no_change_reasons":{
                k:v for k,v in result["counts_by_arm"]["baseline"].items()
                if k.startswith("reason_")
            },
            "treated_seed_clusters":result["seed_clusters_with_interventions"],
            "positive_seeds":result["positive_seed_clusters"],
            "negative_seeds":result["negative_seed_clusters"],
            "mean_net_delta":result["mean_four_seat_net_delta"],
            "official_component_deltas":result["official_component_deltas"],
            "per_seed":result["per_seed"],
        },ensure_ascii=False))
