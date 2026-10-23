"""Reproduce M4.07 independent paired public-only Ming-Gang risk observation."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_minggang_public_risk_audit import PROTOCOL,cohort,study

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","holdout","both"),default="both")
    p.add_argument("--development",type=int,default=38000)
    p.add_argument("--holdout",type=int,default=39000)
    p.add_argument("--seeds",type=int,default=4)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    if (not 1<=a.seeds<=8 or not 0<=a.development<2**32 or
            not 0<=a.holdout<2**32 or
            max(a.development,a.holdout)+a.seeds>2**32 or
            (a.development<a.holdout+a.seeds and a.holdout<a.development+a.seeds)):
        raise ValueError("invalid disjoint natural cohorts")
    report=(study(development=a.development,holdout=a.holdout,seeds=a.seeds)
            if a.cohort=="both" else {
                "protocol":PROTOCOL,"online_policy_modified":False,
                "cohort":a.cohort,
                "seed_start":a.development if a.cohort=="development" else a.holdout,
                "results":cohort(a.development if a.cohort=="development"
                                 else a.holdout,a.seeds)})
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",
                            encoding="utf-8")
    names=("development","holdout") if a.cohort=="both" else (a.cohort,)
    for name in names:
        data=report[name] if a.cohort=="both" else report["results"]
        print("M4.07 NATURAL RISK AUDIT",json.dumps({
            "cohort":name,
            "seeds":data["independent_initial_shuffle_seeds"],
            "games":data["complete_games"],
            "paired_positions":data["paired_seat_positions"],
            "dual_windows":data["natural_dual_windows"],
            "risk_counters":data["risk_counters"],
            "per_seed":data["per_seed"],
        },ensure_ascii=False))
