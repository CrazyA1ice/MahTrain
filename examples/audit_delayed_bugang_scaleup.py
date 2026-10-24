"""Run one predeclared M4.25 shard or strictly merge all four; offline only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mahtrain_core.ai_delayed_bugang_scaleup import (
    PROTOCOL, SHARDS, run_shard, combine_shards,
)


def _save(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False,
                               indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--shard", choices=tuple(SHARDS))
    mode.add_argument("--combine", action="store_true")
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.shard:
        if args.input_dir is not None:
            parser.error("--input-dir is only used with --combine")
        result = run_shard(args.shard)
        _save(args.out, result)
        print(json.dumps({
            "protocol": PROTOCOL, "shard": args.shard,
            "seed_start": result["seed_start"],
            "complete_games": result["result"]["complete_games"],
            "mean_net": result["result"]["mean_current_minus_unguarded"][
                "official_net"],
            "opportunity_counts": result["result"]["opportunity_counts"],
        }, ensure_ascii=False))
        return
    if args.input_dir is None:
        parser.error("--combine requires --input-dir")
    found = list(args.input_dir.glob("m425-*.json"))
    expected = {f"m425-{name}.json" for name in SHARDS}
    if {p.name for p in found} != expected or len(found) != len(SHARDS):
        raise ValueError("missing, duplicate or unregistered shard artifacts")
    inputs = {
        name: json.loads(
            (args.input_dir / f"m425-{name}.json").read_text(encoding="utf-8")
        ) for name in SHARDS
    }
    result = combine_shards(inputs)
    _save(args.out, result)
    for cohort_name in ("development", "holdout"):
        group = result[cohort_name]
        print(json.dumps({
            "protocol": PROTOCOL,
            "cohort": cohort_name,
            "independent_seeds": group["independent_shuffle_seeds"],
            "complete_games": group["complete_games"],
            "guarded_minus_unguarded_net": group[
                "current_guard_minus_old_guard"]["official_net"],
            "guarded_minus_unguarded_components": group[
                "current_guard_minus_old_guard"],
            "positive_seed_clusters": group["positive_clusters"],
            "negative_seed_clusters": group["negative_clusters"],
            "zero_seed_clusters": group["zero_clusters"],
            "actual_interventions": group["observed_old_guard_interventions"],
            "opportunity_counts": group["opportunity_counts"],
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
