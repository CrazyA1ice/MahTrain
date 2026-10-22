"""M4.00 no-peek, retrospective public-feature/rob-Hu label audit."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_public_bugang_rob_pilot import study


def main() -> None:
    parser=argparse.ArgumentParser(
        description="M4.00: public-only pre-bu-gang features vs offline true legal rob eligibility")
    parser.add_argument("--development",type=int,default=24000)
    parser.add_argument("--holdout",type=int,default=25000)
    parser.add_argument("--seeds",type=int,default=8)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    result=study(development=args.development,holdout=args.holdout,
                 seeds=args.seeds)
    data=json.dumps(result,indent=2,ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(data+"\n",encoding="utf-8")
        print("Saved M4.00 result:",args.output)
    else:
        print(data)
    for cohort in ("development","holdout"):
        x=result[cohort]
        print("M4.00 PUBLIC RISK VERIFIED",json.dumps({
            "cohort":cohort,"seed_range":result[cohort+"_seed_range"],
            "total":x["counts"],"by_band":x["by_public_band"],
            "validation":x["predictive_validation_status"],
            "rob_probability":x["estimated_rob_probability"],
            "per_seed":x["per_seed"],
        },ensure_ascii=False))


if __name__=="__main__":
    main()
