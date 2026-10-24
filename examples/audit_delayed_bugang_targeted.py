"""M4.26 reproducible constructed decisions (not natural game frequency)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mahtrain_core.ai_delayed_bugang_targeted import (
    PROTOCOL, SHARDS, evaluate_shard, audit_and_combine,
)


def main() -> None:
    parser=argparse.ArgumentParser()
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--shard",choices=tuple(SHARDS))
    action.add_argument("--combine",action="store_true")
    parser.add_argument("--input-dir",type=Path)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.shard:
        if args.input_dir is not None:
            parser.error("--input-dir is only for --combine")
        result=evaluate_shard(args.shard)
    else:
        if args.input_dir is None:
            parser.error("--combine requires --input-dir")
        observed=list(args.input_dir.glob("m426-*.json"))
        names={f"m426-{name}.json" for name in SHARDS}
        if len(observed)!=len(SHARDS) or {x.name for x in observed} != names:
            raise ValueError("missing or unknown audit shard artifact")
        payloads={
            name:json.loads(
                (args.input_dir/f"m426-{name}.json").read_text(encoding="utf-8")
            ) for name in SHARDS
        }
        result=audit_and_combine(payloads)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(
        result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
        encoding="utf-8")
    if args.shard:
        rows=result["cases"]
        print(json.dumps({
            "protocol":PROTOCOL,"shard":args.shard,"cases":len(rows),
            "guard_disagreements":sum(x["guard_disagreement"] for x in rows),
            "paid_choices":sum(x["paid_action"]=="bu_gang" for x in rows),
            "delayed_guarded_choices":sum(
                x["delayed_guarded_action"]=="bu_gang" for x in rows),
            "synthetic_not_population_frequency":True,
        },ensure_ascii=False))
    else:
        print(json.dumps(result["measured_counts"],ensure_ascii=False))
        print("Constructed coverage only: not natural frequency or EV.")


if __name__=="__main__":
    main()
