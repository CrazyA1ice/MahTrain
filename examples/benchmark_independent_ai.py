"""M3.9 independent shape-only baseline versus three existing heuristic tiers.

Four games per shuffle seed, one seat for each of the four policies on every
rotation. CLI results are experimental win events, NOT official win rates.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_independent_benchmark import independent_benchmark  # noqa: E402

NAMES={"baseline":"独立牌形","basic":"入门","advanced":"进阶","challenge":"挑战"}


def main() -> None:
    parser=argparse.ArgumentParser(
        description="M3.9：独立规则基线与三档AI四座位配对对局")
    parser.add_argument("--seed-start",type=int,default=11)
    parser.add_argument("--seeds",type=int,default=1)
    parser.add_argument("--json-out",type=Path)
    parser.add_argument("--csv-out",type=Path)
    args=parser.parse_args()
    try:
        report=independent_benchmark(args.seed_start,args.seeds)
    except (ValueError,RuntimeError) as exc:
        parser.error(str(exc))
    print("MahTrain M3.9 · 独立牌形基线与三档AI（每种子4局）")
    print("独立洗牌种子：",report["independent_shuffle_seeds"],
          "；完整对局：",report["games"],
          "；终局状态：",report["terminal_phase_counts"])
    print("策略         参与次数   胡牌事件   放铳事件   最低向听率   局部最优率")
    for level in report["opponents"]:
        s=report["levels"][level]
        print(f"{NAMES[level]:<10} {s['exposures']:>5} "
              f"{s['wins']:>10} {s['deal_ins']:>8} "
              f"{100*(s['min_shanten_fraction'] or 0):>10.1f}% "
              f"{100*(s['local_optimal_fraction'] or 0):>10.1f}%")
    print("与独立规则基线的配对差值（按相同种子，不是正式胜率）：")
    for level,metrics in report["paired_differences_vs_baseline"].items():
        print(NAMES[level],metrics)
    print("统计区间：",report["interval_status"],
          "；只有不少于5个不同洗牌种子才显示探索性成组重抽样。")
    if args.csv_out:
        args.csv_out.parent.mkdir(parents=True,exist_ok=True)
        columns=["seed","level","exposures","wins","deal_ins","discards",
                 "minimum_shanten","local_optimal"]
        with args.csv_out.open("w",newline="",encoding="utf-8-sig") as fh:
            writer=csv.DictWriter(fh,fieldnames=columns)
            writer.writeheader()
            for seed in report["per_seed"]:
                for level in report["opponents"]:
                    writer.writerow({
                        "seed":seed["seed"],"level":level,
                        **seed["levels"][level],
                    })
        print("逐种子 CSV：",args.csv_out)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True,exist_ok=True)
        args.json_out.write_text(
            json.dumps(report,ensure_ascii=False,indent=2)+"\n",
            encoding="utf-8",
        )
        print("结果 JSON：",args.json_out)


if __name__=="__main__":
    main()
