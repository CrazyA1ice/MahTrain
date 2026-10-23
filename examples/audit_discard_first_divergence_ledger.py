"""Reproduce M4.14 frozen-shuffle first-divergence official cash forensics."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_discard_first_divergence_ledger import (
    PROTOCOL,cohort,study,
)

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","holdout","both"),
                   default="both")
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    if a.cohort=="both":
        output=study()
    else:
        start=52000 if a.cohort=="development" else 53000
        output={
            "protocol":PROTOCOL,"cohort":a.cohort,"seed_start":start,
            "retrospective_not_independent_validation":True,
            "online_policy_modified":False,"result":cohort(start,4),
        }
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(
            json.dumps(output,ensure_ascii=False,indent=2)+"\n",
            encoding="utf8")
    names=("development","holdout") if a.cohort=="both" else (a.cohort,)
    for name in names:
        x=output[name] if a.cohort=="both" else output["result"]
        print("M4.15 REAL FIRST CUT DIVERGENCE AND OFFICIAL COMPONENTS",
              json.dumps({
                  "cohort":name,
                  "independent_shuffles":x["independent_shuffle_seeds"],
                  "complete_games":x["complete_games"],
                  "real_cut_changes":x["actual_policy_changes"],
                  "positions_with_changes":x["changed_positions"],
                  "total_official_deltas":x["official_deltas"],
                  "per_seed":x["per_seed"],
                  "changed_position_diagnostics":
                      x["changed_position_diagnostics"],
              },ensure_ascii=False))

if __name__=="__main__":
    main()
