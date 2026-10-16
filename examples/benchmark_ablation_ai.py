"""CLI for M3.10 five-policy controlled discard ablation."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_ablation_benchmark import ablation_benchmark  # noqa: E402

NAMES = {
    "baseline": "独立牌形基线",
    "advanced": "进阶",
    "challenge_no_ukeire": "无进张排序",
    "challenge_no_pressure": "无风险平局",
    "challenge": "完整挑战",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="M3.10：五策略、每洗牌种子五局四座次消融实验（非正式胜率）")
    parser.add_argument("--seed-start", type=int, default=11)
    parser.add_argument("--seeds", type=int, default=1)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--csv-out", type=Path)
    args = parser.parse_args()
    try:
        report = ablation_benchmark(args.seed_start, args.seeds)
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print("MahTrain M3.10：有效进张、弱风险规则受控消融")
    print("独立种子：", report["independent_shuffle_seeds"],
          "；轮换完整牌局：", report["games"])
    print("策略             参与    胡牌事件    放铳    最低向听率    局部最优率")
    for level in report["opponents"]:
        row = report["levels"][level]
        print(f"{NAMES[level]:<14} {row['exposures']:>4} "
              f"{row['wins']:>10} {row['deal_ins']:>6} "
              f"{100*(row['min_shanten_fraction'] or 0):>10.1f}% "
              f"{100*(row['local_optimal_fraction'] or 0):>10.1f}%")
    print("配对差值（概率相减，非百分比；非官方胜率）：")
    for key, value in report["paired_differences"].items():
        print(key, value)
    print("区间状态：", report["interval_status"])
    if args.csv_out:
        args.csv_out.parent.mkdir(parents=True, exist_ok=True)
        columns = ["seed", "policy", "exposures", "wins", "deal_ins",
                   "discards", "minimum_shanten", "local_optimal"]
        with args.csv_out.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns)
            writer.writeheader()
            for seed in report["per_seed"]:
                for level in report["opponents"]:
                    writer.writerow({
                        "seed": seed["seed"], "policy": level,
                        **seed["levels"][level],
                    })
        print("逐种子 CSV：", args.csv_out)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2)+"\n",
            encoding="utf-8",
        )
        print("结果 JSON：", args.json_out)


if __name__ == "__main__":
    main()
