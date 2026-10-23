"""M4.09: independent natural-shuffle prospective-bin audit; no AI changes."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_minggang_prospective_strata import (
    PROTOCOL, cohort, study,
)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","holdout","both"),
                   default="both")
    p.add_argument("--development",type=int,default=42000)
    p.add_argument("--holdout",type=int,default=43000)
    p.add_argument("--seeds",type=int,default=8)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    if (type(args.development) is not int or type(args.holdout) is not int or
            type(args.seeds) is not int or not 1 <= args.seeds <= 12 or
            not 0 <= args.development < 2**32 or
            not 0 <= args.holdout < 2**32 or
            max(args.development,args.holdout)+args.seeds>2**32 or
            (args.development<args.holdout+args.seeds and
             args.holdout<args.development+args.seeds)):
        raise ValueError("cohort seed blocks must be disjoint and predeclared")
    if args.cohort=="both":
        result=study(development=args.development,holdout=args.holdout,
                     seeds=args.seeds)
    else:
        start=(args.development if args.cohort=="development"
               else args.holdout)
        result={
            "protocol":PROTOCOL,
            "online_policy_modified":False,
            "cohort":args.cohort,"seed_start":start,
            "results":cohort(start,args.seeds),
        }
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(
            json.dumps(result,ensure_ascii=False,indent=2)+"\n",
            encoding="utf-8",
        )
    for name in (("development","holdout") if args.cohort=="both" else
                 (args.cohort,)):
        report=result[name] if args.cohort=="both" else result["results"]
        print("M4.09 NATURAL MINGGANG RISK STRATA",json.dumps({
            "cohort":name,
            "independent_seeds":report["independent_shuffle_seeds"],
            "games":report["complete_games"],
            "counts":report["counts"],
            "distinct_seeds_with_award":report[
                "distinct_seeds_with_awarded_minggang"],
            "distinct_seeds_with_actual_ron":report[
                "distinct_seeds_with_actual_ron"],
            "per_seed":report["per_seed"],
            "calibrated_probability":report["calibrated_ron_probability"],
        },ensure_ascii=False))
