"""M4.33 multi-shuffle self-play audited cohort, local private/public exports.

Runs real official matches; user-selected seed range is kept LOCAL. This
script never uploads private snapshots, hidden seed identities or full wall.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mahtrain_core.ai_selfplay_cohort_audit import (
    PROTOCOL, run_audited_cohort,
)
from mahtrain_core.ai_selfplay_learning import _assert_public


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_jsonl_gz(path: Path, values: list[dict]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for value in values:
            handle.write(
                json.dumps(
                    value, ensure_ascii=False,
                    allow_nan=False, separators=(",", ":"),
                ) + "\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Four-Challenge natural self-play independent cohort audit"
    )
    parser.add_argument("--seed-start", type=int, default=89700)
    parser.add_argument("--train-seeds", type=int, default=2)
    parser.add_argument("--holdout-seeds", type=int, default=2)
    parser.add_argument("--max-checkpoints", type=int, default=2)
    parser.add_argument(
        "--out-dir", type=Path, default=Path("data/selfplay/m433"),
        help="Keep ALL private actor-hand data local and ignored by git",
    )
    args = parser.parse_args()
    study, safe = run_audited_cohort(
        args.seed_start, args.train_seeds, args.holdout_seeds,
        max_checkpoints=args.max_checkpoints,
    )
    output = args.out_dir
    output.mkdir(parents=True, exist_ok=True)

    for tape in study["public_replays"]:
        _assert_public(tape)
    write_jsonl_gz(
        output / "public_four_challenge_replays.jsonl.gz",
        study["public_replays"],
    )
    write_jsonl_gz(
        output / "PRIVATE_actor_train.jsonl.gz", study["private_train"],
    )
    write_jsonl_gz(
        output / "PRIVATE_actor_holdout.jsonl.gz", study["private_holdout"],
    )
    write_json(output / "PRIVATE_offline_model.json", study["model"])
    write_json(output / "PRIVATE_holdout_diagnostics.json", study["heldout"])
    write_json(output / "safe_aggregate_audit.json", safe)

    # The CLI itself prints only vetted coverage, no wall, private hand,
    # seed IDs, raw model features, per-seat sequence or secret labels.
    public_notice = {
        "protocol": PROTOCOL,
        "natural_full_games": safe["original_natural_full_games"],
        "paired_terminal_games":
            safe["conditioned_full_terminal_action_branch_games"],
        "train_seed_clusters":
            safe["splits"]["train"]["independent_initial_shuffle_clusters"],
        "holdout_seed_clusters":
            safe["splits"]["holdout"]["independent_initial_shuffle_clusters"],
        "train_consensus_labels":
            safe["splits"]["train"]["strict_two_world_consensus_labels"],
        "holdout_consensus_labels":
            safe["splits"]["holdout"]["strict_two_world_consensus_labels"],
        "holdout_scored": safe["holdout_scored_consensus_decisions"],
        "heldout_accuracy": (
            safe["holdout_exploratory_direction_accuracy_if_at_least_five"]
        ),
        "no_policy_promotion": True,
    }
    print(json.dumps(public_notice, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
