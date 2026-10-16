"""Run M3.6 four-AI full-turn self-play, stdlib only.

Examples:
  python examples/tournament_ai.py --seeds 2
  python examples/tournament_ai.py --seed-start 100 --seeds 20 \
    --json-out results/ai_tournament.json \
    --csv-out results/ai_tournament.csv
These are experimental win events, NOT settled official match win rates.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_tournament import tournament  # noqa: E402


def main() -> None:
    parser=argparse.ArgumentParser(
        description="M3.6：四位启发式AI完整摸切的座位轮换实验")
    parser.add_argument("--seed-start",type=int,default=0)
    parser.add_argument("--seeds",type=int,default=2)
    parser.add_argument("--json-out",type=Path)
    parser.add_argument("--csv-out",type=Path)
    parser.add_argument("--seed-csv-out",type=Path,help="按独立种子合并三次轮换后的统计表")
    args=parser.parse_args()
    try:
        result=tournament(args.seed_start,args.seeds)
    except (ValueError,RuntimeError) as e:
        parser.error(str(e))
    print("MahTrain M3.6 · 4座位 x 3档AI平衡轮换实验（非正式胜率）")
    print("种子：",args.seed_start,"～",args.seed_start+args.seeds-1,
          "；试验局数：",result["games"])
    print("终局：",result["terminal_phase_counts"])
    print("档位     座位暴露  胡牌事件  放铳责任次数  最低向听切牌率  局部最优切率")
    for level,title in (("basic","入门"),("advanced","进阶"),
                        ("challenge","挑战")):
        s=result["levels"][level]
        print(f"{title:<8} {s['seat_exposures']:>6}"
              f"     {s['win_events']:>6}"
              f"        {s['deal_in_events']:>6}"
              f"       {100*(s['discard_min_shanten_fraction'] or 0):>6.1f}%"
              f"        {100*(s['discard_local_optimal_fraction'] or 0):>6.1f}%")
    cluster=result["seed_analysis"]
    print("M3.8 按种子配对：独立洗牌",cluster["distinct_seed_count"],
          "个；每种子三次座位轮换是关联实验。")
    for metric,title in (
        ("win_event_fraction","胡牌事件/参局"),
        ("local_optimal_fraction","局部最优切牌率"),
    ):
        rows=cluster["paired_challenge_differences"][metric]
        print(title,"挑战－入门",rows["challenge_minus_basic"],
              "挑战－进阶",rows["challenge_minus_advanced"])
    print("区间：",cluster["interval_status"],
          "（只供探索，不是正式比赛胜率区间）")
    print("声明：这是规则草案下的AI自博弈事件统计；流局和杠钱正式结算"
          "未接通。胡牌事件与分数不能当作官方血战胜率和最终收益。")
    if args.seed_csv_out:
        args.seed_csv_out.parent.mkdir(parents=True,exist_ok=True)
        fields=["seed","level","seat_exposures","win_events",
                "deal_in_events","discards","min_shanten_discards",
                "locally_optimal_discards","win_event_fraction",
                "local_optimal_fraction","min_shanten_fraction"]
        with args.seed_csv_out.open("w",newline="",encoding="utf-8-sig") as f:
            writer=csv.DictWriter(f,fieldnames=fields)
            writer.writeheader()
            for group in cluster["per_seed"]:
                for level in ("basic","advanced","challenge"):
                    writer.writerow({
                        "seed":group["seed"],"level":level,
                        **group["levels"][level],
                    })
        print("按种子统计 CSV：",args.seed_csv_out)
    if args.csv_out:
        fields=[
            "seed","rotation","dealer","seat","level","terminal_phase",
            "seat_won","win_kind","deal_ins","partial_hu_points",
            "actions","wall_remaining",
        ]
        args.csv_out.parent.mkdir(parents=True,exist_ok=True)
        with args.csv_out.open("w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=fields)
            w.writeheader()
            for match in result["matches"]:
                for seat,level in enumerate(match["assignment"]):
                    wins=[win for win in match["winners"] if win["seat"]==seat]
                    w.writerow({
                        "seed":match["seed"],"rotation":match["rotation"],
                        "dealer":match["dealer"],"seat":seat,"level":level,
                        "terminal_phase":match["terminal_phase"],
                        "seat_won":bool(wins),
                        "win_kind":wins[0]["kind"] if wins else "",
                        "deal_ins":sum(
                            win["source"]==seat and win["seat"]!=seat
                            for win in match["winners"]
                        ),
                        "partial_hu_points":match["partial_win_balances"][seat],
                        "actions":match["actions"],
                        "wall_remaining":match["wall_remaining"],
                    })
        print("CSV 座位结果：",args.csv_out)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True,exist_ok=True)
        args.json_out.write_text(
            json.dumps(result,ensure_ascii=False,indent=2)+"\n",
            encoding="utf-8",
        )
        print("JSON 全程事件记录：",args.json_out)


if __name__=="__main__":
    main()
