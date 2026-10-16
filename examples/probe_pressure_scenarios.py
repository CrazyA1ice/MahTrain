"""Run physically feasible constructed open-pung fixture checks (M3.13).

These are same-state diagnostics, NOT simulated completed matches and do not
measure actual wins or defensive success.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mahtrain_core.ai_pressure_scenarios import pressure_scenario_matrix  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="M3.13：五个构造的实体牌可行副露局面，用真实牌效算法验证压力规则")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--csv-out", type=Path)
    args = parser.parse_args()
    report = pressure_scenario_matrix()
    print("MahTrain M3.13：合法实体牌数量校验 + 构造局面的真实向听/进张算法")
    print("说明：构造的单决策快照，不是从真实对局中筛到的比赛结果。")
    print("场景                                  进张并列 压力区分 规则改切")
    for row in report["scenarios"]:
        print(f"{row['scenario']:<37} "
              f"{str(row['effective_tie']):<8} "
              f"{str(row['public_pressure_discriminates']):<9} "
              f"{row['choice_would_change']}")
    print("汇总：",report["summary"])
    if args.json_out:
        args.json_out.parent.mkdir(parents=True,exist_ok=True)
        args.json_out.write_text(
            json.dumps(report,ensure_ascii=False,indent=2)+"\n",
            encoding="utf-8",
        )
        print("JSON:",args.json_out)
    if args.csv_out:
        args.csv_out.parent.mkdir(parents=True,exist_ok=True)
        columns=list(report["scenarios"][0])
        with args.csv_out.open("w",newline="",encoding="utf-8-sig") as fh:
            writer=csv.DictWriter(fh,fieldnames=columns)
            writer.writeheader()
            writer.writerows(report["scenarios"])
        print("CSV:",args.csv_out)


if __name__=="__main__":
    main()
