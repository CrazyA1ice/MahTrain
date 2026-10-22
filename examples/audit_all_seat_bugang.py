"""M4.02: same actual natural match, ALL four seats, sealed labels vs Hu."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_all_seat_bugang_audit import study

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--development",type=int,default=28000)
    parser.add_argument("--holdout",type=int,default=29000)
    parser.add_argument("--seeds",type=int,default=8)
    parser.add_argument("--output",type=Path)
    p=parser.parse_args()
    r=study(development=p.development,holdout=p.holdout,seeds=p.seeds)
    if p.output:
        p.output.parent.mkdir(parents=True,exist_ok=True)
        p.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for name in ("development","holdout"):
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
