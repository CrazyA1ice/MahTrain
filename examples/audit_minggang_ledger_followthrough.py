"""M4.08: inspect actual verified Kong postings/refunds and post-Kong Ron."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_minggang_ledger_followthrough import (
    PROTOCOL,natural_cohort,study,
)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","holdout","both"),default="both")
    p.add_argument("--development",type=int,default=40000)
    p.add_argument("--holdout",type=int,default=41000)
    p.add_argument("--seeds",type=int,default=4)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    if (not 1<=a.seeds<=8 or not 0<=a.development<2**32 or
            not 0<=a.holdout<2**32 or
            max(a.development,a.holdout)+a.seeds>2**32 or
            (a.development<a.holdout+a.seeds and a.holdout<a.development+a.seeds)):
        raise ValueError("invalid independent preregistered cohorts")
    if a.cohort=="both":
        result=study(development=a.development,holdout=a.holdout,seeds=a.seeds)
    else:
        start=a.development if a.cohort=="development" else a.holdout
        result={"protocol":PROTOCOL,"online_policy_modified":False,
                "cohort":a.cohort,"seed_start":start,
                "results":natural_cohort(start,a.seeds)}
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                            encoding="utf-8")
    names=("development","holdout") if a.cohort=="both" else (a.cohort,)
    for name in names:
        report=result[name] if a.cohort=="both" else result["results"]
        print("M4.08 VERIFIED OFFICIAL KONG LIFECYCLE",json.dumps({
            "cohort":name,
            "independent_seeds":report["independent_initial_shuffle_seeds"],
            "complete_games":report["complete_games"],
            "dual_windows":report["total_dual_windows"],
            "actual_all_seat_minggang":report["actual_all_seat_minggang"],
            "actual_challenge_minggang":report["actual_challenge_seat_minggang"],
            "counters":report["counts"],"per_seed":report["per_seed"],
        },ensure_ascii=False))
