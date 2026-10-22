"""CLI to run the OFFLINE M3.93 paired official-net cut study.

Example: python examples/compare_challenge_reference_paired.py --start 8407 --seeds 2 --rotations 4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.ai_challenge_reference_paired import compare_reference_cuts

def main() -> None:
    parser=argparse.ArgumentParser(
        description="Offline challenge-vs-reference cut paired official-net study")
    parser.add_argument("--start",type=int,default=8407)
    parser.add_argument("--seeds",type=int,default=2)
    parser.add_argument("--rotations",type=int,default=4)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    data=compare_reference_cuts(
        seed_start=args.start,seeds=args.seeds,rotations=args.rotations)
    # No hands, wall, round tokens or future information in this summary.
    text=json.dumps(data,ensure_ascii=False,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text+"\n",encoding="utf-8")
        print("Saved research-only public aggregate:",args.output)
    else:
        print(text)

if __name__=="__main__":
    main()
