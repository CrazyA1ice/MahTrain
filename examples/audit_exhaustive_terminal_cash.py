"""M4.16: replay old M4.14 paired shuffles, audit real terminal da-jiao money."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_exhaustive_terminal_cash_audit import PROTOCOL,cohort,study

if __name__=="__main__":
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
            "retrospective_not_independent_holdout":True,
            "online_policy_modified":False,"results":cohort(start,4),
        }
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",
                            encoding="utf-8")
    for name in (("development","holdout") if a.cohort=="both" else
                 (a.cohort,)):
        group=output[name] if a.cohort=="both" else output["results"]
        print("M4.16 TRUE OFFICIAL TERMINAL STAGE AUDIT",json.dumps({
            "cohort":name,"shuffles":group["independent_shuffles"],
            "complete_games":group["complete_games"],
            "real_interventions":group["real_interventions"],
            "official_deltas":group["official_deltas"],
            "stage_deltas":group["stage_deltas"],
            "per_seed":group["per_seed"],
            "changed_position_terminal_audits":
                group["changed_position_terminal_audits"],
        },ensure_ascii=False))
