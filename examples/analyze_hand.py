"""运行示例：python examples/analyze_hand.py

打印 14 张手牌的每个切牌选项、切后向听数、有效进张和局部最优切。
本示例仅演示训练算法，不是完整的四人川麻对局。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core import analyze_discards, format_hand, sort_hand  # noqa: E402

LABEL = {"m": "万", "s": "条", "p": "筒"}


def chinese(tile: str) -> str:
    return tile[1:] + LABEL[tile[0]]


def main() -> None:
    hand = (
        ["m1"] * 3
        + ["m4"] * 3
        + ["p1"] * 3
        + ["p4"] * 3
        + ["m9", "p9"]
    )
    missing_suit = "s"  # 当前玩家定缺条
    print("理牌:", format_hand(hand))
    print("定缺:", LABEL[missing_suit])
    result = analyze_discards(hand, missing_suit=missing_suit)
    if result["status"] == "already_winning":
        print("当前已合法胡牌，无需切牌。")
        return
    print("切牌 | 向听 | 有效进张 | 下摸概率 | 最优")
    for row in result["candidates"]:
        probability = f"{row['next_draw_probability']:.2%}"
        effective = ",".join(
            f"{chinese(item['tile'])}×{item['remaining']}"
            for item in sorted(row["effective_details"], key=lambda item: (("m", "s", "p").index(item["tile"][0]), -int(item["tile"][1:])))
        ) or "无"
        print(
            f"{chinese(row['discard']):4} | {row['shanten']:4} | "
            f"{row['effective_tile_count']:4}张 ({effective}) | "
            f"{probability:>8} | {'是' if row['local_optimal'] else '否'}"
        )
    print("局部最优切:", "、".join(chinese(t) for t in sort_hand(result["best_discards"])))


if __name__ == "__main__":
    main()
