r"""M4.39 NEW real matches, opt-in actor-only discard diagnostics.

Windows from MahTrain root:
  python examples\run_actor_discard_diagnostics.py --train-dir data/selfplay/m434-smoke --prior-evaluation-dir data/selfplay/m437-shadow-2 --seed-start 91300 --seeds 2 --out-dir data/selfplay/m439-actor-2

To resume after interruption rerun with identical options + --resume.
Runs FIVE real complete matches per never-seen original shuffle. No changes
to the live Challenge AI. Never upload PRIVATE_* files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_shadow_action_diagnostics import run_actor_diagnostics


def main() -> None:
    p=argparse.ArgumentParser(description="M4.39 new-seed frozen actor-choice diagnostics")
    p.add_argument("--train-dir",type=Path,required=True)
    p.add_argument("--prior-evaluation-dir",type=Path,required=True,
                   help="existing M4.37 reference: prior original seed exclusion only")
    p.add_argument("--seed-start",type=int,required=True)
    p.add_argument("--seeds",type=int,default=2)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--resume",action="store_true")
    a=p.parse_args()
    result=run_actor_diagnostics(
        training_dir=a.train_dir,
        prior_evaluation_dir=a.prior_evaluation_dir,
        seed_start=a.seed_start,seeds=a.seeds,
        out_dir=a.out_dir,resume=a.resume,
    )
    print(json.dumps({
        "original_shuffle_clusters":result["original_shuffle_seed_clusters"],
        "real_complete_games":result["actual_real_complete_games"],
        "actor_discard_opportunities":result["actor_discard_opportunities"],
        "actual_model_overrides":result["actual_model_override_count"],
        "overrides_with_lower_effective_tiles":
            result["actor_visible_effective_tile_count_lower_on_override"],
        "overrides_with_higher_effective_tiles":
            result["actor_visible_effective_tile_count_higher_on_override"],
        "mean_net_delta_points":result["paired_mean_official_net_delta_points"],
        "safe_report":str(a.out_dir/"safe_actor_decision_diagnostics.json"),
        "no_action_level_causal_claim":True,
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
