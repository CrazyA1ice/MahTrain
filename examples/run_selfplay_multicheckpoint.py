"""M4.32 local-only multi-checkpoint four-challenge self-play research CLI."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_selfplay_learning import _assert_public
from mahtrain_core.ai_selfplay_multicheckpoint import (
    PROTOCOL, MAX_CHECKPOINTS, run_study,
)


def _jsonl_gz(path: Path, rows: list[dict]) -> None:
    with gzip.open(path,"wt",encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(
                row,ensure_ascii=False,separators=(",",":"),allow_nan=False,
            )+"\n")


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--seed-start",type=int,default=89600)
    parser.add_argument("--train-seeds",type=int,default=1)
    parser.add_argument("--holdout-seeds",type=int,default=1)
    parser.add_argument("--max-checkpoints",type=int,default=MAX_CHECKPOINTS)
    parser.add_argument("--out-dir",type=Path,default=Path("data/selfplay/m432"))
    a=parser.parse_args()
    output=a.out_dir
    results=run_study(
        a.seed_start,a.train_seeds,a.holdout_seeds,
        max_checkpoints=a.max_checkpoints,
    )
    output.mkdir(parents=True,exist_ok=True)
    for public in results["public_replays"]:
        _assert_public(public)
    _jsonl_gz(output/"public_challenge_replays.jsonl.gz",
              results["public_replays"])
    _jsonl_gz(output/"PRIVATE_train_action_labels.jsonl.gz",
              results["private_train"])
    _jsonl_gz(output/"PRIVATE_holdout_action_labels.jsonl.gz",
              results["private_holdout"])
    (output/"offline_consensus_model.json").write_text(
        json.dumps(results["model"],indent=2,ensure_ascii=False)+"\n",
        encoding="utf-8",
    )
    (output/"PRIVATE_holdout_diagnostics.json").write_text(
        json.dumps(results["heldout"],indent=2,ensure_ascii=False)+"\n",
        encoding="utf-8",
    )
    clusters=[*results["private_train"],*results["private_holdout"]]
    covered=sum(x["captured_decisions"] for x in clusters)
    consensus=sum(
        p["eligible_as_exploratory_training_label"]
        for x in clusters for p in x["checkpoints"]
    )
    summary={
        "protocol":PROTOCOL,
        "natural_games":results["natural_full_games"],
        "four_ais_challenge":True,
        "train_independent_shuffle_seeds":results["train_seed_clusters"],
        "holdout_independent_shuffle_seeds":results["test_seed_clusters"],
        "max_checkpoints_per_seed":a.max_checkpoints,
        "natural_distinct_seat_checkpoints":covered,
        "two_wall_strict_consensus_checkpoints":consensus,
        "terminal_real_legal_counterfactual_games":
            results["counterfactual_full_games"],
        "total_complete_games":results["natural_full_games"]+
            results["counterfactual_full_games"],
        "model_training_action_labels":results["model"]["total_action_labels"],
        "model_training_independent_seed_clusters":
            results["model"]["independent_seed_clusters_with_labels"],
        "holdout_checkpoints":results["heldout"]["total_natural_checkpoints"],
        "holdout_consensus_decisions":results["heldout"]["consensus_action_checkpoints"],
        "holdout_scored_decisions":results["heldout"]["scored_decisions"],
        "holdout_correct_conditional_directions":
            results["heldout"]["correct_conditional_directions"],
        "no_online_ai_change":True,
        "strength_increase_proven":False,
        "no_population_ev_or_significance_claim":True,
    }
    (output/"summary.json").write_text(
        json.dumps(summary,indent=2,ensure_ascii=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(summary,ensure_ascii=False))


if __name__=="__main__":
    main()
