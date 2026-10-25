"""Run M4.29 conditional full terminal-score intervention contrasts (offline)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_delayed_bugang_terminal_paired import (
    PROTOCOL,SHARDS,run_shard,combine_shards,
)


def main() -> None:
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--shard",choices=tuple(SHARDS))
    group.add_argument("--combine",action="store_true")
    parser.add_argument("--input-dir",type=Path)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.shard is not None:
        if args.input_dir is not None:
            parser.error("--input-dir only valid with --combine")
        result=run_shard(args.shard)
    else:
        if args.input_dir is None:
            parser.error("--combine requires --input-dir")
        listed=list(args.input_dir.glob("m429-*.json"))
        expected={f"m429-{name}.json" for name in SHARDS}
        if len(listed)!=len(expected) or {x.name for x in listed}!=expected:
            raise ValueError("exactly 5 registered M4.29 shard artifacts required")
        result=combine_shards({
            name:json.loads(
                (args.input_dir/f"m429-{name}.json").read_text(encoding="utf-8")
            ) for name in SHARDS
        })
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(
        json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2)+"\n",
        encoding="utf-8")
    if args.shard:
        rows=result["rows"]
        print(json.dumps({
            "protocol":PROTOCOL,"shard":args.shard,
            "real_terminal_games":len(rows)*2,
            "case_id":result["case_id"],
            "conditional_official_net_differences":[
                r["forced_minus_hold"]["official_net"] for r in rows
            ],
            "not_natural_winrate_or_EV":True,
        },ensure_ascii=False))
    else:
        print(json.dumps({
            "protocol":PROTOCOL,
            "real_terminal_games":result["complete_terminal_games"],
            "paired_constructed_worlds":result["paired_conditional_worlds"],
            "conditional_official_score_deltas":
                result["weighted_difference_means_for_constructed_cases"],
            "positive_pairs":result["positive_conditional_world_deltas"],
            "negative_pairs":result["negative_conditional_world_deltas"],
            "tied_pairs":result["tied_conditional_world_deltas"],
            "per_case":result["per_case"],
            "population_EV":None,
            "online_policy_changed":False,
        },ensure_ascii=False))


if __name__=="__main__":
    main()
