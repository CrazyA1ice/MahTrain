"""M4.03 independent natural-seed descriptive public-risk validation."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_all_seat_bugang_audit import aggregate
from mahtrain_core.ai_public_rob_seed_validation import (
    PROTOCOL,compare,summarize,study,
)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","holdout","both"),
                   default="both")
    p.add_argument("--development",type=int,default=30000)
    p.add_argument("--holdout",type=int,default=31000)
    p.add_argument("--seeds",type=int,default=12)
    p.add_argument("--development-file",type=Path)
    p.add_argument("--holdout-file",type=Path)
    p.add_argument("--output",type=Path)
    a=p.parse_args()

    # Predeclare all ranges even when one group is dispatched as an
    # independent CI matrix job. Do not filter based on a favorable label.
    if (type(a.seeds) is not int or not 1<=a.seeds<=12
        or not 0<=a.development<2**32 or
        not 0<=a.holdout<2**32 or
        max(a.development,a.holdout)+a.seeds>2**32 or
        a.development<a.holdout+a.seeds and
        a.holdout<a.development+a.seeds):
        raise ValueError("seed groups must be predeclared and disjoint")

    if a.development_file or a.holdout_file:
        if not(a.development_file and a.holdout_file):
            raise ValueError("both previously validated cohort files required")
        d=json.loads(a.development_file.read_text(encoding="utf-8"))
        h=json.loads(a.holdout_file.read_text(encoding="utf-8"))
        if (d.get("protocol")!=PROTOCOL or h.get("protocol")!=PROTOCOL
            or d.get("cohort")!="development" or h.get("cohort")!="holdout"
            or d.get("seed_start")!=a.development or
            h.get("seed_start")!=a.holdout or
            d.get("seed_count")!=a.seeds or h.get("seed_count")!=a.seeds):
            raise ValueError("wrong cohort files for declared independent seeds")
        result=compare(d["raw"],h["raw"])
        result["development_seed_range"]=[a.development,a.development+a.seeds]
        result["holdout_seed_range"]=[a.holdout,a.holdout+a.seeds]
    elif a.cohort=="both":
        result=study(development=a.development,holdout=a.holdout,seeds=a.seeds)
    else:
        start=a.development if a.cohort=="development" else a.holdout
        raw=aggregate(start,a.seeds)
        result={
            "protocol":PROTOCOL,"cohort":a.cohort,
            "seed_start":start,"seed_count":a.seeds,
            "live_policy_modified":False,
            "raw":raw,"seed_cluster_summary":summarize(raw),
        }

    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",
                            encoding="utf-8")
        print("M4.03 JSON saved:",a.output)
    if "cross_cohort_decision" in result:
        print("M4.03 HOLDOUT DECISION",json.dumps({
            "status":result["cross_cohort_decision"],
            "development":result["dev"],
            "holdout":result["holdout"],
            "calibrated_rob_probability":None,
        },ensure_ascii=False))
    else:
        print("M4.03 NATURAL VERIFIED",json.dumps({
            "cohort":result["cohort"],
            "summary":result["seed_cluster_summary"],
        },ensure_ascii=False))


if __name__=="__main__":
    main()
