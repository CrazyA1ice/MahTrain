"""Run M4.10 authorized actual post-supplement cut audit on fixed seeds."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_minggang_actual_exit_risk import (
    PROTOCOL,cohort,study,
)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--cohort",choices=("development","holdout","both"),
                        default="both")
    parser.add_argument("--development",type=int,default=44000)
    parser.add_argument("--holdout",type=int,default=45000)
    parser.add_argument("--seeds",type=int,default=8)
    parser.add_argument("--output",type=Path)
    a=parser.parse_args()
    if (not 1<=a.seeds<=12 or
            not 0<=a.development<2**32 or not 0<=a.holdout<2**32 or
            max(a.development,a.holdout)+a.seeds>2**32 or
            (a.development<a.holdout+a.seeds and
             a.holdout<a.development+a.seeds)):
        raise ValueError("development and holdout seeds must be disjoint")
    if a.cohort=="both":
        output=study(development=a.development,holdout=a.holdout,seeds=a.seeds)
    else:
        start=a.development if a.cohort=="development" else a.holdout
        output={"protocol":PROTOCOL,"cohort":a.cohort,
                "seed_start":start,"online_policy_modified":False,
                "results":cohort(start,a.seeds)}
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",
                            encoding="utf-8")
    for name in (("development","holdout") if a.cohort=="both" else
                 (a.cohort,)):
        x=output[name] if a.cohort=="both" else output["results"]
        print("M4.10 ACTUAL POST-TAIL CUT NATURAL VERIFIED",json.dumps({
            "cohort":name,
            "independent_seeds":x["independent_shuffle_seeds"],
            "complete_games":x["complete_games"],
            "pre_tail":x["pre_tail_counts"],"post_tail":x["post_tail_counts"],
            "per_seed":x["per_seed"],
            "seeds_with_actual_exit":x["seeds_with_actual_exit"],
            "seeds_with_actual_ron":x["seeds_with_actual_ron"],
        },ensure_ascii=False))
