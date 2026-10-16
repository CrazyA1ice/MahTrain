"""Reproducible paired AI-discard benchmark, stdlib only.

Run: python examples/benchmark_ai.py --seeds 12
     python examples/benchmark_ai.py --seeds 12 --json-out results/ai_baseline.json
The JSON includes paired per-position records and hardware-specific latency.
No simulated full-match win rates or unverified skill-ranking claims.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_benchmark import benchmark  # noqa: E402


def main() -> None:
    parser=argparse.ArgumentParser(
        description="M3.5：AI相同牌面决策质量对照，非完整对局胜率")
    parser.add_argument("--seed-start",type=int,default=0)
    parser.add_argument("--seeds",type=int,default=12)
    parser.add_argument("--json-out",type=Path)
    args=parser.parse_args()
    try:
        report=benchmark(seed_start=args.seed_start,seeds=args.seeds)
    except (ValueError,RuntimeError) as exc:
        parser.error(str(exc))
    print("MahTrain M3.5 · 三档AI同局面牌效基准（非胜率）")
    print("种子：",args.seed_start,"起，共",args.seeds,"局；",
          "可比较手牌：",report["usable_positions"],
          "；已胡跳过：",report["skipped_already_winning"])
    print("档位       最低向听率   最优有效进张率  平均向听劣势  平均决策耗时(ms)")
    for level,title in (("basic","入门"),("advanced","进阶"),
                        ("challenge","挑战")):
        value=report["levels"][level]
        print(f"{title:<10} {value['best_shanten_rate']*100:>6.1f}%"
              f"        {value['best_ukeire_rate']*100:>6.1f}%"
              f"         {value['average_shanten_regret']:>6.3f}"
              f"            {value['average_decision_ms']:>8.4f}")
    print("说明：每档在完全相同手牌上独立作一次切牌决策；"
          "部分牌例是有实体牌守恒的无缺门对照场景。"
          "耗时随机器变化；这些数字不是实战胡牌率或胜率。")
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True,exist_ok=True)
        args.json_out.write_text(
            json.dumps(report,ensure_ascii=False,indent=2)+"\n",
            encoding="utf-8",
        )
        print("JSON 报告：",args.json_out)


if __name__=="__main__":
    main()
