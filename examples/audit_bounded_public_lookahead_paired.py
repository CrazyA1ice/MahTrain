"""Reproduce bounded M4.20 lookahead with official paired games and overhead."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_bounded_public_lookahead_paired import (
    PROTOCOL,cohort,study,
)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","holdout","both"),
                   default="both")
    p.add_argument("--seeds",type=int,default=3)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    if a.cohort=="both":
        if a.seeds!=3:
            raise ValueError("frozen two-cohort protocol uses three seeds each")
        data=study()
    else:
        start=60000 if a.cohort=="development" else 61000
        data={"protocol":PROTOCOL,"cohort":a.cohort,
              "seed_start":start,"online_ai_modified":False,
              "result":cohort(start,a.seeds)}
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",
                            encoding="utf8")
    keys=("development","holdout") if a.cohort=="both" else (a.cohort,)
    for k in keys:
        s=data[k] if a.cohort=="both" else data["result"]
        timings=[p["arms"]["bounded_two_transition"]["counts"][
            "lookahead_elapsed_ms_total"] for p in s["positions"]]
        peaks=[p["arms"]["bounded_two_transition"]["counts"][
            "lookahead_elapsed_ms_peak"] for p in s["positions"]]
        print("M4.20 FROZEN BOUNDED PUBLIC LOOKAHEAD PAIRED",json.dumps({
            "cohort":k,"independent_seeds":s["independent_shuffles"],
            "complete_games":s["complete_official_games"],
            "actual_changes":s["candidate_action_changes"],
            "affected_seeds":s["affected_seed_clusters"],
            "positive_seeds":s["positive_seed_clusters"],
            "negative_seeds":s["negative_seed_clusters"],
            "official_deltas":s["official_component_deltas"],
            "resource_counts":s["counts_by_arm"],
            "worst_candidate_ms_per_match":max(peaks,default=0),
            "mean_candidate_total_ms_per_match":(
                round(sum(timings)/len(timings),2) if timings else 0),
            "per_seed":s["per_seed"],
        },ensure_ascii=False))
