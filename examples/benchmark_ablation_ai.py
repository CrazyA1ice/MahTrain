"""CLI for M3.10 five-policy controlled discard ablation."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_ablation_benchmark import ablation_benchmark  # noqa: E402
from mahtrain_core.ai_ablation_report import render_ablation_html  # noqa: E402
from mahtrain_core.ai_ablation_benchmark import PRESSURE_FIELDS  # noqa: E402

NAMES = {
    "baseline": "独立牌形基线",
    "advanced": "进阶",
    "challenge_no_ukeire": "无进张排序",
    "challenge_no_pressure": "无风险平局",
    "challenge": "完整挑战",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="M3.11：五策略、多种子敏感性分析与离线报告（非正式胜率）")
    parser.add_argument("--seed-start", type=int, default=11)
    parser.add_argument("--seeds", type=int, default=1)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--csv-out", type=Path)
    parser.add_argument("--contrast-csv-out", type=Path,
                        help="按独立种子输出每个策略差值（单位：百分点）")
    parser.add_argument("--pressure-csv-out", type=Path,
                        help="按种子汇总启停弱风险规则实际是否改变切牌，不输出暗手")
    parser.add_argument("--official-csv-out", type=Path,
                        help="M3.33 只导出方案A已核验整种子五策略正式积分，无暗牌")
    parser.add_argument("--html-out", type=Path,
                        help="单文件离线图表，无脚本、无暗手或未来牌墙")
    args = parser.parse_args()
    try:
        report = ablation_benchmark(args.seed_start, args.seeds)
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print("MahTrain M3.11：多种子受控消融与稳健性")
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
    if "pressure_diagnostics" in report:
        print("M3.12 弱风险规则触发诊断（同局面影子比较）：")
        for policy, row in report["pressure_diagnostics"].items():
            print(policy, "切牌",row["decisions"],
                  "进张并列",row["effective_ties"],
                  "压力区分",row["pressure_discriminates"],
                  "切牌可能不同",row["would_change"],
                  "当前策略实际不同",row["actual_changed"])
        print("说明：同局面比较不会改变真实牌墙或给出替代切牌带来的胜负。")
    official=report["official_score_analysis"]
    print("M3.33 五策略规则A正式积分：",official["valid_seeds"],
          "/",official["requested_seeds"],"个完整洗牌种子核验；",
          "排除",official["excluded_seed_count"],"个整种子。")
    print("正式积分口径：胡牌 + 已核验流局赔付，不含模拟杠钱；"
          "未核验整种子不进入积分/切牌联动统计。")
    for level in report["opponents"]:
        item=official["levels"][level]
        print(NAMES[level],"出场",item["seat_exposures"],
              "净积分/出场",item["official_mean_per_exposure"],
              "最低向听率",item["min_shanten_fraction"],
              "有效张均值",item["mean_effective_copies"],
              "实际放铳/百次切牌",item["deal_in_events_per_100_discards"])
    analysis = report["seed_analysis"]
    print("独立种子：", analysis["distinct_seed_count"],
          "；统计单位：", analysis["unit"])
    for key, counts in analysis["direction_counts"].items():
        c = counts["win_event_fraction"]
        print("跨种子胡牌事件差值方向：", key,
              f"正{c['positive']} / 负{c['negative']} / "
              f"相同{c['tied']} / 未定义{c['undefined']}")
    print("留一种子敏感性：",
          "已计算（仅描述性）" if analysis["leave_one_seed_out"] is not None
          else "不足5独立种子，不计算")
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
    if args.contrast_csv_out:
        args.contrast_csv_out.parent.mkdir(parents=True, exist_ok=True)
        metrics = ("win_event_fraction", "min_shanten_fraction",
                   "local_optimal_fraction")
        columns = ["seed", "contrast", *(m+"_delta_pp" for m in metrics)]
        with args.contrast_csv_out.open(
                "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns)
            writer.writeheader()
            for group in analysis["per_seed_differences"]:
                for contrast, values in group["differences"].items():
                    writer.writerow({
                        "seed": group["seed"], "contrast": contrast,
                        **{metric+"_delta_pp": (
                            round(100*values[metric], 2)
                            if values[metric] is not None else "")
                            for metric in metrics},
                    })
        print("逐种子策略差值 CSV：", args.contrast_csv_out)
    if args.pressure_csv_out:
        args.pressure_csv_out.parent.mkdir(parents=True,exist_ok=True)
        columns = ["seed","policy",*PRESSURE_FIELDS]
        with args.pressure_csv_out.open(
                "w",newline="",encoding="utf-8-sig") as fh:
            writer=csv.DictWriter(fh,fieldnames=columns)
            writer.writeheader()
            for group in report["per_seed"]:
                for policy,row in group["pressure_diagnostics"].items():
                    writer.writerow({
                        "seed":group["seed"],"policy":policy,**row,
                    })
        print("弱风险规则触发 CSV：",args.pressure_csv_out)
    if args.official_csv_out:
        args.official_csv_out.parent.mkdir(parents=True, exist_ok=True)
        columns=["seed","policy","seat_exposures","official_total",
                 "official_mean_per_exposure","discards","min_shanten_cuts",
                 "local_optimal_cuts","effective_copies_total","deal_in_events"]
        with args.official_csv_out.open(
                "w",newline="",encoding="utf-8-sig") as fh:
            writer=csv.DictWriter(fh,fieldnames=columns)
            writer.writeheader()
            for cluster in official["per_seed"]:
                for level in report["opponents"]:
                    writer.writerow({"seed":cluster["seed"],"policy":level,
                                     **cluster["levels"][level]})
        print("方案A正式积分逐种子CSV：",args.official_csv_out)
    if args.html_out:
        args.html_out.parent.mkdir(parents=True, exist_ok=True)
        args.html_out.write_text(render_ablation_html(report), encoding="utf-8")
        print("离线可视化 HTML：", args.html_out)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2)+"\n",
            encoding="utf-8",
        )
        print("结果 JSON：", args.json_out)


if __name__ == "__main__":
    main()
