"""M4.04 joint pass/peng/ming-gang legal slate vs current challenge paired run."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_joint_optional_action_slate import cohort,study,PROTOCOL


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--development",type=int,default=32000)
    p.add_argument("--holdout",type=int,default=33000)
    p.add_argument("--seeds",type=int,default=4)
    p.add_argument("--cohort",choices=("development","holdout","both"),
                   default="both")
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    if (type(args.seeds) is not int or not 1<=args.seeds<=8 or
        not 0<=args.development<2**32 or
        not 0<=args.holdout<2**32 or
        max(args.development,args.holdout)+args.seeds>2**32 or
        (args.development<args.holdout+args.seeds and
         args.holdout<args.development+args.seeds)):
        raise ValueError("invalid or overlapping predeclared seed ranges")
    if args.cohort=="both":
        report=study(development=args.development,
                     holdout=args.holdout,seeds=args.seeds)
    else:
        start=(args.development if args.cohort=="development"
               else args.holdout)
        report={
            "protocol":PROTOCOL,"live_policy_modified":False,
            "cohort":args.cohort,"seed_start":start,
            "results":cohort(start,args.seeds),
        }
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",
                               encoding="utf8")
        print("Saved M4.04 paired evaluation:",args.output)
    for group in ("development","holdout"):
        if group not in report:continue
        x=report[group]
        print("M4.04 FINAL PAIRED",json.dumps({
            "cohort":group,
            "seeds":x["independent_shuffle_seeds"],
            "seed_mean_delta":x["counterfactual_mean_seed_delta"],
            "delta_components":x["sum_official_component_deltas"],
            "positive_seeds":x["positive_delta_seeds"],
            "negative_seeds":x["negative_delta_seeds"],
            "counts":x["aggregate_counts"],
            "per_seed":x["per_seed"],
        },ensure_ascii=False))
    if "results" in report:
        x=report["results"]
        print("M4.04 FINAL PAIRED",json.dumps({
            "cohort":report["cohort"],
            "seeds":x["independent_shuffle_seeds"],
            "seed_mean_delta":x["counterfactual_mean_seed_delta"],
            "delta_components":x["sum_official_component_deltas"],
            "positive_seeds":x["positive_delta_seeds"],
            "negative_seeds":x["negative_delta_seeds"],
            "counts":x["aggregate_counts"],
            "per_seed":x["per_seed"],
        },ensure_ascii=False))


if __name__=="__main__":
    main()
