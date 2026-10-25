"""Run frozen same-view M4.27 constructed decision cause audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mahtrain_core.ai_delayed_bugang_attribution import (
    PROTOCOL, SHARDS, diagnose_shard, combine,
)


def main() -> None:
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--shard",choices=tuple(SHARDS))
    group.add_argument("--combine",action="store_true")
    parser.add_argument("--input-dir",type=Path)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.shard:
        if args.input_dir is not None:
            parser.error("--input-dir only valid with --combine")
        result=diagnose_shard(args.shard)
    else:
        if args.input_dir is None:
            parser.error("--combine requires --input-dir")
        found=list(args.input_dir.glob("m427-*.json"))
        expected={f"m427-{name}.json" for name in SHARDS}
        if len(found)!=len(SHARDS) or {f.name for f in found} != expected:
            raise ValueError("missing or unexpected M4.27 shard files")
        result=combine({
            name:json.loads(
                (args.input_dir/f"m427-{name}.json").read_text(encoding="utf-8")
            ) for name in SHARDS
        })
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(
        json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
        encoding="utf-8")
    if args.shard:
        print(json.dumps({
            "protocol":PROTOCOL, "shard":args.shard,
            "cases":len(result["cases"]),
            "same_view_disagreements":sum(
                x["same_view_action_changed"] for x in result["cases"]),
        },ensure_ascii=False))
    else:
        print(json.dumps({
            "protocol":PROTOCOL,
            "cases":result["total_constructed_checkpoints"],
            "same_view_disagreements":result["same_view_policy_disagreement_count"],
            "strict_target_rejections":result["strict_guard_rejected_target_count"],
            "cause_breakdown":result["guard_reason_counts"],
            "five_detail_candidates":result["disagreement_cases"],
            "is_natural_game_experiment":False,
            "claim_of_EV_improvement":False,
        },ensure_ascii=False))


if __name__=="__main__":
    main()
