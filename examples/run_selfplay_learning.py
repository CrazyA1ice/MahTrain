"""Local-only M4.30 4-AI self-play -> safe public replay + private learner
data -> frozen offline model -> untouched seed-cluster benchmark.

No network/download needed. Never commit the private actor-view archive.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_selfplay_learning import (
    PROTOCOL,run_pilot,_assert_public
)


def _write_jsonl_gzip(path: Path, rows: list[dict]) -> None:
    with gzip.open(path,"wt",encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row,ensure_ascii=False,allow_nan=False,
                               separators=(",",":"))+"\n")


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--seed-start",type=int,default=88000)
    parser.add_argument("--train-seeds",type=int,default=2)
    parser.add_argument("--holdout-seeds",type=int,default=2)
    parser.add_argument(
        "--out-dir",type=Path,default=Path("data/selfplay/m430"),
        help="LOCAL RESEARCH folder. Private actor-hand training rows must stay private.",
    )
    args=parser.parse_args()
    result=run_pilot(
        args.seed_start,args.train_seeds,args.holdout_seeds,
    )
    output=args.out_dir
    output.mkdir(parents=True,exist_ok=True)
    for row in result["public_replays"]:
        _assert_public(row)
    _write_jsonl_gzip(
        output/"public_replays.jsonl.gz",result["public_replays"]
    )
    _write_jsonl_gzip(
        output/"PRIVATE_actor_training.jsonl.gz",
        result["private_actor_examples"],
    )
    for name,obj in (
        ("pilot_model.json",result["offline_model"]),
        ("holdout_report.json",result["heldout"]),
    ):
        (output/name).write_text(
            json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+"\n",
            encoding="utf-8",
        )
    evaluation=result["heldout"]
    report={
        "protocol":PROTOCOL,
        "training_complete_games":len(result["private_actor_examples"]),
        "public_replay_archives":len(result["public_replays"]),
        "training_independent_seeds":result["training_seed_clusters"],
        "heldout_independent_seeds":result["holdout_seed_clusters"],
        "heldout_real_complete_games":evaluation["heldout_complete_games"],
        "heldout_mean_official_score_difference":
            evaluation["mean_conditional_holdout_delta"],
        "changed_discard_choices":evaluation["changed_discard_choices"],
        "learning_source":"actor_only_trajectory_outcomes",
        "policy_automatically_promoted":False,
        "skill_gain_not_yet_proven":True,
        "public_replay_path":str(output/"public_replays.jsonl.gz"),
        "private_research_path":str(output/"PRIVATE_actor_training.jsonl.gz"),
    }
    (output/"summary.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",
        encoding="utf-8"
    )
    print(json.dumps(report,ensure_ascii=False))


if __name__=="__main__":
    main()
