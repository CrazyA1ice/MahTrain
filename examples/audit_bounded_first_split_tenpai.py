"""Retrospective M4.21 first REAL M4.20 cut change / actual later ready-hand audit."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_bounded_first_split_tenpai_audit import (
    PROTOCOL,cohort,study,
)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","holdout","both"),
                   default="both")
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    if a.cohort=="both":
        x=study()
    else:
        start=60000 if a.cohort=="development" else 61000
        x={"protocol":PROTOCOL,"cohort":a.cohort,"seed_start":start,
           "retrospective_not_independent_validation":True,
           "online_ai_modified":False,"result":cohort(start,3)}
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",
                            encoding="utf-8")
    for block in (("development","holdout") if a.cohort=="both" else
                  (a.cohort,)):
        r=x[block] if a.cohort=="both" else x["result"]
        print("M4.21 TRUE FIRST CUT / OBSERVED TENPAI FORENSIC",json.dumps({
            "block":block,
            "independent_shuffles":r["independent_historical_shuffles"],
            "complete_games":r["complete_paired_games"],
            "true_cut_changes":r["total_actual_changes"],
            "changed_seat_positions":r["changed_seat_positions"],
            "official_deltas":r["official_component_deltas"],
            "settlement_stage_deltas":r["flower_pig_and_da_jiao_deltas"],
            "per_seed":r["per_seed"],
            "changed_position_forensics":r["changed_position_forensics"],
        },ensure_ascii=False))
