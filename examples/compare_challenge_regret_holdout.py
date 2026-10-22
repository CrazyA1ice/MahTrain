"""Run offline M3.94 genuine-regret-only independent-seed study.

Example: python examples/compare_challenge_regret_holdout.py --development 8420 --holdout 9400 --seeds 3 --rotations 4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_challenge_regret_holdout import study

def main() -> None:
    p=argparse.ArgumentParser(description="Offline true-regret four-seat paired study")
    p.add_argument("--development",type=int,default=8420)
    p.add_argument("--holdout",type=int,default=9400)
    p.add_argument("--seeds",type=int,default=3)
    p.add_argument("--rotations",type=int,default=4)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    result=study(development_start=a.development,holdout_start=a.holdout,
                 seeds_per_group=a.seeds,rotations=a.rotations)
    formatted=json.dumps(result,ensure_ascii=False,indent=2)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(formatted+"\n",encoding="utf8")
        print("Wrote offline public aggregate to",a.output)
    else:
        print(formatted)
    for group in ("development","holdout"):
        row=result[group]
        print("M3.94",group,"seeds",row["independent_seeds"],
              "paired",row["paired_games"],
              "changed",row["decision_counts"].get("changed_cuts",0),
              "net_delta_mean",row["mean_delta_net"],
              "exploratory_interval",row["cluster_interval_exploratory"]["lower"],
              row["cluster_interval_exploratory"]["upper"])

if __name__=="__main__":
    main()
