r"""M4.40: read existing M4.39 actor-only traces; no new Mahjong games.

From MahTrain root (Windows PowerShell):
  python examples\audit_frozen_score_geometry.py --train-dir data/selfplay/m434-smoke --actor-evaluation-dir data/selfplay/m439-actor-2 --report-dir data/selfplay/m440-geometry-2

Only upload safe_frozen_score_geometry.json; private training and candidate
records are never written to the public summary. No new games or model edits.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mahtrain_core.ai_shadow_score_geometry import audit_frozen_score_geometry


def main()->None:
    p=argparse.ArgumentParser(description="M4.40 read-only frozen model score contribution audit")
    p.add_argument("--train-dir",type=Path,required=True)
    p.add_argument("--actor-evaluation-dir",type=Path,required=True)
    p.add_argument("--report-dir",type=Path,required=True,
                   help="new empty private output folder under data/selfplay")
    args=p.parse_args()
    result=audit_frozen_score_geometry(
        training_dir=args.train_dir,
        actor_evaluation_dir=args.actor_evaluation_dir,
        report_dir=args.report_dir,
    )
    print(json.dumps({
        "verified_overrides":result["overrides_verified_against_exact_frozen_weights"],
        "cut_with_reduced_visible_ukeire":result["cut_effective_tile_count_decreased"],
        "feature_weight_signs":result["frozen_weight_signs_only"],
        "mean_frozen_margin":result["mean_verified_model_margin"],
        "descriptive_not_causal":True,
        "safe_summary":str(args.report_dir/"safe_frozen_score_geometry.json"),
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
