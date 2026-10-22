"""M4.02: same actual natural match, ALL four seats, sealed labels vs Hu."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_all_seat_bugang_audit import study,aggregate,PROTOCOL

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--development",type=int,default=28000)
    parser.add_argument("--holdout",type=int,default=29000)
    parser.add_argument("--seeds",type=int,default=8)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--cohort",choices=("development","holdout","both"),default="both")
    p=parser.parse_args()
    if p.cohort=="both":
        r=study(development=p.development,holdout=p.holdout,seeds=p.seeds)
    else:
        # Cohorts are separate Actions jobs for faster independent audits.
        if p.seeds<1 or p.seeds>12 or min(p.development,p.holdout)<0 or max(p.development,p.holdout)+p.seeds>2**32 or (p.development<p.holdout+p.seeds and p.holdout<p.development+p.seeds):
            raise ValueError("cohort controls must remain disjoint")
        r={"protocol":PROTOCOL,"live_policy_modified":False,
           p.cohort:aggregate(p.development if p.cohort=="development" else p.holdout,p.seeds)}
    if p.output:
        p.output.parent.mkdir(parents=True,exist_ok=True)
        p.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for name in ("development","holdout"):
        if name not in r: continue
        v=r[name]
        print("M4.02 ALL-SEAT VERIFIED",json.dumps({
            "cohort":name,
            "independent_seeds":v["independent_initial_shuffle_seeds"],
            "games":v["completed_games"],
            "seat_observations":v["observed_seat_positions"],
            "counts":v["counts"],"by_band":v["by_public_band"],
            "by_level":v["by_agent_level"],"per_seed":v["per_seed"],
            "status":v["status"],
        },ensure_ascii=False))
