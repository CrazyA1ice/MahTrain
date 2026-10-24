"""M4.18 reproducible original challenge vs one-shanten-ukeire paired games."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_one_shanten_ukeire_paired import PROTOCOL,cohort,study

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","holdout","both"),
                   default="both")
    p.add_argument("--development",type=int,default=56000)
    p.add_argument("--holdout",type=int,default=57000)
    p.add_argument("--seeds",type=int,default=4)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    d,h,n=a.development,a.holdout,a.seeds
    if (type(d) is not int or type(h) is not int or type(n) is not int
            or not 1<=n<=8 or not 0<=d<2**32 or not 0<=h<2**32 or
            max(d,h)+n>2**32 or (d<h+n and h<d+n)):
        raise ValueError("disjoint preregistered independent shuffle blocks required")
    if a.cohort=="both":
        result=study(development=d,holdout=h,seeds=n)
    else:
        start=d if a.cohort=="development" else h
        result={"protocol":PROTOCOL,"cohort":a.cohort,"seed_start":start,
                "online_ai_modified":False,"candidate_only_offline":True,
                "result":cohort(start,n)}
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(
            json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    names=("development","holdout") if a.cohort=="both" else (a.cohort,)
    for name in names:
        group=result[name] if a.cohort=="both" else result["result"]
        print("M4.18 NEW ONE-SHANTEN PAIRED OFFICIAL",json.dumps({
            "cohort":name,"independent_seeds":group["independent_shuffle_seeds"],
            "complete_games":group["complete_official_games"],
            "total_baseline_cuts":group["baseline_total_cuts"],
            "one_shanten_cuts":group["baseline_one_shanten_ranked"],
            "multiple_minimum_one_shanten_cuts":group["baseline_one_shanten_multi"],
            "real_changes":group["actual_discard_interventions"],
            "changed_seeds":group["independent_seeds_with_interventions"],
            "positive_seeds":group["positive_seed_clusters"],
            "negative_seeds":group["negative_seed_clusters"],
            "mean_net_delta":group["mean_four_seat_net_delta"],
            "official_components":group["official_component_deltas"],
            "no_change_reasons":{
                k:v for k,v in group["counts_by_arm"]["baseline"].items()
                if k.startswith("reason_")
            },"per_seed":group["per_seed"],
        },ensure_ascii=False))
