"""M4.13: complete official paired Peng vs Pass public risk trial."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_peng_forced_cut_risk_paired import PROTOCOL,GATE,cohort,study

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","holdout","both"),default="both")
    p.add_argument("--development",type=int,default=50000)
    p.add_argument("--holdout",type=int,default=51000)
    p.add_argument("--seeds",type=int,default=4)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    d,h,n=args.development,args.holdout,args.seeds
    if not (0<=d<2**32 and 0<=h<2**32 and 1<=n<=8 and
            max(d,h)+n<=2**32 and not (d<h+n and h<d+n)):
        raise ValueError("new independent development and holdout required")
    if args.cohort=="both":
        result=study(development=d,holdout=h,seeds=n)
    else:
        start=d if args.cohort=="development" else h
        result={"protocol":PROTOCOL,"cohort":args.cohort,
                "seed_start":start,"online_policy_modified":False,
                "result":cohort(start,n)}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                               encoding="utf-8")
    names=("development","holdout") if args.cohort=="both" else (args.cohort,)
    for name in names:
        x=result[name] if args.cohort=="both" else result["result"]
        print("M4.13 FROZEN PENG GUARD FULL MATCH",json.dumps({
            "cohort":name,"independent_seeds":x["independent_shuffles"],
            "complete_official_games":x["complete_official_games"],
            "selected_peng_windows":x["selected_peng_windows"],
            "actual_changes":x["candidate_policy_interventions"],
            "gate":GATE,
            "mean_seed_net_delta":x["mean_four_seat_net_delta"],
            "positive_seeds":x["positive_seeds"],
            "negative_seeds":x["negative_seeds"],
            "official_components":x["component_deltas"],
            "per_seed":x["per_seed"],
        },ensure_ascii=False))
