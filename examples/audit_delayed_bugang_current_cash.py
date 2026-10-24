"""Offline current-rule vs old-guard paired game audit; no hidden game data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_delayed_bugang_paired import (
    DEFAULT_GROUPS, DEFAULT_SEEDS, PROTOCOL, cohort,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group",choices=sorted(DEFAULT_GROUPS),required=True)
    ap.add_argument("--seeds",type=int,default=DEFAULT_SEEDS)
    ap.add_argument("--output",type=Path,required=True)
    args = ap.parse_args()
    result = {
        "protocol":PROTOCOL,
        "group":args.group,
        "start_seed":DEFAULT_GROUPS[args.group],
        "new_cash_rule":"current_m423",
        "result":cohort(DEFAULT_GROUPS[args.group],args.seeds),
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8")
    short=result["result"]
    print(json.dumps({
        "protocol":PROTOCOL,
        "group":args.group,
        "independent_seeds":short["independent_shuffle_seeds"],
        "complete_games":short["complete_games"],
        "net_delta":short["mean_current_minus_unguarded"]["official_net"],
        "opportunity_counts":short["opportunity_counts"],
        "saved":str(args.output),
    },ensure_ascii=False))


if __name__=="__main__":
    main()
