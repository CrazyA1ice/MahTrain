"""Run M4.28 physically valid root/fan-cap and hidden-rob stress studies."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mahtrain_core.ai_delayed_bugang_risk_envelope import (
    PROTOCOL,SHARDS,evaluate_shard,combine
)


def main():
    p=argparse.ArgumentParser()
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--shard",choices=tuple(SHARDS))
    group.add_argument("--combine",action="store_true")
    p.add_argument("--input-dir",type=Path)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if args.shard:
        if args.input_dir is not None:
            p.error("--input-dir only valid with --combine")
        data=evaluate_shard(args.shard)
    else:
        if args.input_dir is None:
            p.error("--combine requires --input-dir")
        files=list(args.input_dir.glob("m428-*.json"))
        names={f"m428-{s}.json" for s in SHARDS}
        if len(files)!=len(names) or {f.name for f in files}!=names:
            raise ValueError("M4.28 rejects missing, extra or duplicate shards")
        data=combine({
            n:json.loads(
                (args.input_dir/f"m428-{n}.json").read_text(encoding="utf8")
            ) for n in SHARDS
        })
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(
        json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
        encoding="utf8")
    if args.shard:
        print(json.dumps({
            "protocol":PROTOCOL,"shard":args.shard,
            "constructed_cases":len(data["cases"]),
            "constructed_legal_rob_witness_count":sum(
                r["constructed_same_view_rob_witness_found"] for r in data["cases"]),
            "official_EV_study":False,
        },ensure_ascii=False))
    else:
        print(json.dumps({
            "protocol":PROTOCOL,
            "cases":data["constructed_checkpoints"],
            "root_conditional_multiplier_gains":data[
                "conditional_root_multiplier_gain_counts"],
            "rob_legal_hidden_world_cases":data[
                "legally_robbed_hidden_world_count"],
            "measured_rob_probability":data["rob_probability"],
            "measured_official_EV":data["official_EV_estimate"],
            "live_policy_changed":data["online_policy_changed"],
        },ensure_ascii=False))


if __name__=="__main__":
    main()
