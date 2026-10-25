"""M4.31 4-challenge real self-play, two legal same-stage cuts and paired
official terminal scores. Private action training labels remain LOCAL.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mahtrain_core.ai_selfplay_counterfactual import (
    PROTOCOL,run_experiment,
)
from mahtrain_core.ai_selfplay_learning import _assert_public


def _write_jsonl(path: Path,records: list[dict]) -> None:
    with gzip.open(path,"wt",encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(
                row,ensure_ascii=False,separators=(",",":"),allow_nan=False
            )+"\n")


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--seed-start",type=int,default=89500)
    parser.add_argument("--train-seeds",type=int,default=1)
    parser.add_argument("--holdout-seeds",type=int,default=1)
    parser.add_argument("--out-dir",type=Path,default=Path("data/selfplay/m431"))
    args=parser.parse_args()
    result=run_experiment(
        args.seed_start,args.train_seeds,args.holdout_seeds
    )
    output=args.out_dir
    output.mkdir(parents=True,exist_ok=True)
    for public in result["public_replays"]:
        _assert_public(public)
    _write_jsonl(output/"public_four_challenge_replays.jsonl.gz",
                 result["public_replays"])
    # Actor's OWN hand and private seeded experiment metadata: private.
    # The opponent hands and wall order never leave process memory.
    _write_jsonl(output/"PRIVATE_train_action_values.jsonl.gz",
                 result["private_training"])
    _write_jsonl(output/"PRIVATE_holdout_action_values.jsonl.gz",
                 result["private_holdout"])
    (output/"offline_preference_model.json").write_text(
        json.dumps(result["offline_model"],ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8",
    )
    (output/"PRIVATE_holdout_diagnostics.json").write_text(
        json.dumps(result["holdout"],ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8",
    )
    covered=sum(
        p["paired"]["status"]=="two_real_terminal_actions"
        for p in result["private_training"]+result["private_holdout"]
    )
    summary={
        "protocol":PROTOCOL,
        "all_four_ais_challenge":result["four_challenge_ais"],
        "natural_full_games":result["natural_games"],
        "natural_seed_clusters":args.train_seeds+args.holdout_seeds,
        "train_seed_clusters":args.train_seeds,
        "holdout_seed_clusters":args.holdout_seeds,
        "naturally_found_competing_discard_checkpoints":covered,
        "paired_full_terminal_rollout_games":
            result["full_counterfactual_terminal_games"],
        "total_complete_games":(
            result["natural_games"]+
            result["full_counterfactual_terminal_games"]),
        "training_action_value_examples":
            result["offline_model"]["trained_samples"],
        "holdout_natural_decisions":
            result["holdout"]["natural_covered_decisions"],
        "holdout_preferred_alternative":
            result["holdout"]["offline_prefers_alternative"],
        "holdout_direction_agreements":
            result["holdout"]["direction_agreement_count"],
        "online_policy_changed":False,
        "strength_improvement_proven":False,
        "return_type":"conditional_realized_net_not_population_EV",
    }
    (output/"summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(summary,ensure_ascii=False))


if __name__=="__main__":
    main()
