"""M4.22: retrospectively enumerate all public effective draw TYPES for true cuts."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mahtrain_core.ai_bounded_full_coverage_audit import (
    HISTORICAL_CHANGED, PROTOCOL, historical_changed_position, study,
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", choices=("development", "holdout", "both"),
                        default="both")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.cohort == "both":
        result = study()
    else:
        cohort, seed, rotation = next(
            block for block in HISTORICAL_CHANGED if block[0] == args.cohort
        )
        result = {
            "protocol": PROTOCOL,
            "historical_selected_after_m421": True,
            "retrospective_not_independent_validation": True,
            "online_ai_modified": False,
            "positions": [
                {"cohort": cohort, **historical_changed_position(seed, rotation)}
            ],
        }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    for row in result["positions"]:
        print("M4.22 FULL PUBLIC BRANCH COVERAGE", json.dumps({
            "cohort": row["cohort"],
            "seed": row["seed"], "rotation": row["rotation"],
            "actual_changes": row["actual_changes"],
            "coverage": row["coverage"],
            "official_component_deltas": row["official_component_deltas"],
            "historical_not_independent_validation": True,
        }, ensure_ascii=False))
