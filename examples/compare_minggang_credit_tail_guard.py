"""Reproduce M4.06 real-authority Ming-Gang credit/tail guard pairing."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_minggang_credit_tail_guard import (
    PROTOCOL,cohort,study,
)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","holdout","both"),default="both")
    p.add_argument("--development",type=int,default=36000)
    p.add_argument("--holdout",type=int,default=37000)
    p.add_argument("--seeds",type=int,default=8)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    if (not 1<=a.seeds<=8 or
        not 0<=a.development<2**32 or not 0<=a.holdout<2**32 or
        max(a.development,a.holdout)+a.seeds>2**32 or
        (a.development<a.holdout+a.seeds and a.holdout<a.development+a.seeds)):
        raise ValueError("invalid disjoint predeclared cohort")
    report=(study(development=a.development,holdout=a.holdout,seeds=a.seeds)
            if a.cohort=="both" else {
                "protocol":PROTOCOL,"online_policy_modified":False,
                "cohort":a.cohort,
                "seed_start":(a.development if a.cohort=="development" else a.holdout),
                "results":cohort(a.development if a.cohort=="development"
                                 else a.holdout,a.seeds)})
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",
                            encoding="utf-8")
    for name in ("development","holdout"):
        if name not in report and report.get("cohort")!=name:continue
        x=report[name] if name in report else report["results"]
        print("M4.06 VERIFIED RESEARCH",json.dumps({
            "cohort":name,"seeds":x["independent_initial_shuffle_seeds"],
            "games":x["complete_games"],"paired_positions":x["paired_seat_positions"],
            "mean_official_net_delta":x["average_official_net_delta"],
            "positive_seeds":x["positive_seed_clusters"],
            "negative_seeds":x["negative_seed_clusters"],
            "components":x["components"],"counts":x["counts_by_arm"],
            "latency":x["latency_by_arm"],"per_seed":x["per_seed"],
        },ensure_ascii=False))
