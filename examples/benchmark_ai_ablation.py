"""M3.10: real-game challenge ablations with two distinct opponent cohorts."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mahtrain_core.ai_ablation import ablation_benchmark  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="M3.10 挑战AI公开进张/弱风险两项独立消融：每种子8局"
    )
    parser.add_argument("--seed-start", type=int, default=11)
    parser.add_argument("--seeds", type=int, default=1)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--csv-out", type=Path)
    args = parser.parse_args()
    try:
        report = ablation_benchmark(args.seed_start, args.seeds)
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print("MahTrain M3.10 · 挑战档策略消融（非正式比赛胜率）")
    print("独立种子：", report["independent_shuffle_seeds"],
          "；对照场次：", report["games"],
          "；区间：", report["interval_status"])
    for cohort, data in report["cohorts"].items():
        print("\n对手分组：",cohort)
        print("策略                     参与  胡牌事件  放铳  最低向听率  局部最优率")
        for level, s in data["levels"].items():
            low = s["min_shanten_fraction"]
            optimal = s["local_optimal_fraction"]
            print(f"{level:<23} {s['exposures']:>4} "
                  f"{s['wins']:>8} {s['deal_ins']:>5} "
                  f"{100*low:>10.1f}% " if low is not None
                  else f"{level:<23} {s['exposures']:>4} "
                       f"{s['wins']:>8} {s['deal_ins']:>5}        —",
                  f" {100*optimal:.1f}%" if optimal is not None else " —")
        print("完整挑战档－其他策略（正数仅表示本批样本完整档更高）：")
        for level, differences in data["challenge_minus_other"].items():
            print(" ", level, differences)
    if args.csv_out:
        args.csv_out.parent.mkdir(parents=True, exist_ok=True)
        fields = ["cohort", "seed", "level", "exposures", "wins",
                  "deal_ins", "discards", "minimum_shanten", "local_optimal"]
        with args.csv_out.open("w",newline="",encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for cohort, data in report["cohorts"].items():
                for seed in data["per_seed"]:
                    for level, row in seed["levels"].items():
                        writer.writerow({
                            "cohort": cohort, "seed": seed["seed"],
                            "level": level, **row
                        })
        print("逐种子 CSV：", args.csv_out)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2)+"\n",
            encoding="utf-8",
        )
        print("聚合 JSON：", args.json_out)


if __name__=="__main__":
    main()
