r"""M4.38: diagnose SAVED M4.37 official result without any new games.

Example from repo root on Windows (Python 3.11+):
  python examples\audit_saved_shadow_loss.py --evaluation-dir data/selfplay/m437-shadow-2 --report-dir data/selfplay/m438-audit-2

The old evaluation directory is read-only and never modified. Only the
aggregate summary is safe to share. Detailed seat/seed CSV is private.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_shadow_loss_audit import audit_saved_shadow_results


def main() -> None:
    parser=argparse.ArgumentParser(
        description="M4.38 read-only genuine four-seat frozen shadow loss audit"
    )
    parser.add_argument("--evaluation-dir",type=Path,required=True,
                        help="completed, unchanged M4.37 private output folder")
    parser.add_argument("--report-dir",type=Path,required=True,
                        help="new empty gitignored private audit output folder")
    args=parser.parse_args()
    result=audit_saved_shadow_results(
        evaluation_dir=args.evaluation_dir,
        report_dir=args.report_dir,
    )
    print(json.dumps({
        "original_shuffle_seed_clusters":
            result["original_shuffle_seed_clusters"],
        "real_complete_games":result["total_complete_authoritative_games"],
        "mean_net_delta_points":
            result["paired_mean_official_net_delta_points"],
        "paid_components":
            result["paid_net_delta_accounting_by_component_points"],
        "actual_changed_discards":
            result["observed_actual_overrides"],
        "cannot_infer_causal_loss_from_individual_cuts":True,
        "safe_report":str(args.report_dir/
                         "safe_shadow_loss_attribution_summary.json"),
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
