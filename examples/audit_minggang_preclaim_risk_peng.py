"""M4.11: fixed paired full-game Ming-Gang -> Peng risk policy research."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_minggang_preclaim_paired import (
    PROTOCOL,PUBLIC_THREAT_GATE,study,cohort,
)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","holdout","both"),
                   default="both")
    p.add_argument("--development",type=int,default=46000)
    p.add_argument("--holdout",type=int,default=47000)
    p.add_argument("--seeds",type=int,default=4)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    if (type(a.development) is not int or type(a.holdout) is not int or
            type(a.seeds) is not int or not 1 <= a.seeds <= 8 or
            not 0 <= a.development < 2**32 or
            not 0 <= a.holdout < 2**32 or
            max(a.development,a.holdout)+a.seeds > 2**32 or
            (a.development < a.holdout+a.seeds and
             a.holdout < a.development+a.seeds)):
        raise ValueError("independent fixed development and holdout seed blocks required")
    if a.cohort=="both":
        report=study(development=a.development,holdout=a.holdout,
                     seeds=a.seeds)
    else:
        start=a.development if a.cohort=="development" else a.holdout
        report={
            "protocol":PROTOCOL,"cohort":a.cohort,"seed_start":start,
            "online_policy_modified":False,"candidate_only_offline":True,
            "results":cohort(start,a.seeds),
        }
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",
                            encoding="utf-8")
    names=("development","holdout") if a.cohort=="both" else (a.cohort,)
    for name in names:
        r=report[name] if a.cohort=="both" else report["results"]
        print("M4.11 REAL PAIRED OFFICIAL CASH",json.dumps({
            "cohort":name,"seeds":r["independent_shuffle_seeds"],
            "complete_games":r["complete_games"],
            "public_threat_gate":PUBLIC_THREAT_GATE,
            "candidate_real_policy_changes":r["candidate_real_policy_changes"],
            "average_official_net_delta":r["seed_mean_official_net_delta"],
            "positive_seeds":r["positive_delta_seeds"],
            "negative_seeds":r["negative_delta_seeds"],
            "unchanged_seeds":r["unchanged_delta_seeds"],
            "components":r["official_component_deltas"],
            "per_seed":r["per_seed"],
        },ensure_ascii=False))
