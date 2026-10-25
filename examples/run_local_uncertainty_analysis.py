r"""Read an EXISTING M4.34 local batch and evaluate ALL legal paired outcomes.

From MahTrain root (no new games, no third-party dependencies):
  python examples/run_local_uncertainty_analysis.py --out-dir data/selfplay/m434-smoke

Writes PRIVATE offline diagnostic weights and holdout results, and safe
aggregate report in the SAME local private folder. Does not edit online AI.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_selfplay_uncertainty import analyze_saved_local_batch


def main() -> None:
    parser=argparse.ArgumentParser(
        description="M4.35 analyze genuine saved two-wall action deltas "
                    "without re-simulating or relabeling any natural game"
    )
    parser.add_argument("--out-dir",type=Path,required=True)
    args=parser.parse_args()
    report=analyze_saved_local_batch(args.out_dir)
    print(json.dumps({
        "independent_original_shuffle_seeds":
            report["original_natural_seed_clusters"],
        "train_legal_decisions":report["train"]["all_natural_legal_actions"],
        "train_strict_sign_mixed_or_tied_but_retained":
            report["train"]["world_signs_conflict_or_tie"],
        "all_legal_train_actions_used":
            report["new_offline_train_points"],
        "holdout_legal_decisions":
            report["holdout"]["all_natural_legal_actions"],
        "holdout_direction_accuracy_only_if_five_or_more":
            report["heldout_direction_accuracy_if_at_least_five"],
        "no_change_to_live_ai":True,
        "safe_summary_path":
            str(args.out_dir/"safe_uncertainty_summary.json"),
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
