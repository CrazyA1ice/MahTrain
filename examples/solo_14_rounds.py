"""Playable console solo trainer with auto win/kong yes/no prompts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core import SoloTrainingSession, analyze_discards, format_hand

SUITS = {"m": "万", "s": "条", "p": "筒"}


def label(tile: str) -> str:
    return tile[1:] + SUITS[tile[0]]


def ask_yes_no(prompt: str) -> bool:
    while True:
        answer = input(prompt).strip().lower()
        if answer in ("y", "yes", "是", "好", "1"):
            return True
        if answer in ("n", "no", "否", "不", "0"):
            return False
        print("请输入 y/n。")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MahTrain 单人14轮摸切训练")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--rounds", type=int, default=14)
    parser.add_argument("--missing-suit", choices=("m", "s", "p"))
    parser.add_argument("--auto", action="store_true",
                        help="自动同意胡牌，自动选择最优切牌；默认不主动开杠")
    parser.add_argument("--auto-kong", action="store_true",
                        help="自动答应可开的暗杠，体验杠区和牌墙尾部补牌")
    args = parser.parse_args(argv)
    game = SoloTrainingSession(args.seed, args.missing_suit, args.rounds)
    initial = game.public_state()
    print(f"MahTrain · 最多{args.rounds}轮，固定花色顺序 万→条→筒，组内1→9升序")
    print("定缺：", SUITS[initial["missing_suit"]])
    print("初始手牌：", format_hand(initial["hand"]))
    print("说明：胡牌/杠牌由系统发现后主动询问；已杠四张移至独立区域。")
    try:
        while not game.finished:
            state = game.draw_next()
            print(f"\n第{state['current_round']}轮 · 摸牌 {label(state['drawn_tile'])}")
            while state["phase"] != "await_discard" and not game.finished:
                print("手牌：", format_hand(state["hand"]))
                if state["exposed_kongs"]:
                    print("【独立杠区】", " | ".join(
                        label(group["tile"]) + " ×4（不可操作）"
                        for group in state["exposed_kongs"]
                    ))
                if state["phase"] == "offer_win":
                    accept = True if args.auto else ask_yes_no(
                        "系统判断现在已经胡牌！是否胡牌？ [y/n]："
                    )
                    result = game.decide_win(accept)
                    if accept:
                        print("确认胡牌：", result["win_type"])
                    else:
                        print("本次放弃胡牌，继续处理杠牌或切牌。")
                    state = game.public_state()
                elif state["phase"] == "offer_kong":
                    print("可开暗杠：", "、".join(label(t)
                                           for t in state["kong_options"]))
                    accept = args.auto_kong if args.auto else ask_yes_no(
                        "是否开杠？[y/n]："
                    )
                    if accept:
                        tile = state["kong_options"][0]
                        state = game.decide_kong(tile)
                        print("确认暗杠：", label(tile), "×4")
                        print("牌墙尾部补牌：", label(state["drawn_tile"]))
                    else:
                        state = game.decide_kong(None)

            if game.finished:
                break
            print("理牌：", format_hand(state["hand"]))
            if state["exposed_kongs"]:
                print("【独立杠区】", " | ".join(
                    label(group["tile"]) + "×4"
                    for group in state["exposed_kongs"]
                ))
            print("可切牌：", " ".join(
                f"{t}({label(t)})" for t in state["choices"]
            ))
            if args.auto:
                analysis = analyze_discards(
                    state["hand"],
                    game._melds,
                    missing_suit=game.missing_suit,
                    visible_tiles=state["discard_history"],
                )
                cut = analysis["best_discards"][0]
                print("自动切牌：", label(cut))
            else:
                cut = input("点击版尚未联网；请输入切牌编号 (m1/s2/p9)：").strip()
            while True:
                try:
                    result = game.submit(cut)
                    break
                except ValueError as exc:
                    if args.auto:
                        raise
                    print("非法切牌：", exc)
                    cut = input("请重新选择手牌中的一张：").strip()
            print("本轮：", "正确" if result["correct"] else "有改进空间")
            print(result["explanation"])
            print("局部最优：", "、".join(
                "胡牌" if tile == "win" else label(tile)
                for tile in result["best_actions"]
            ))
    except (KeyboardInterrupt, EOFError):
        print("\n训练已中断。")
        return 1

    report = game.report()
    print("\n===== 训练总结 =====")
    print("结束原因：", report["finished_reason"])
    print("已完成轮数：", report["completed_rounds"])
    print("最优选择率：", f"{report['accuracy']:.1%}")
    print("退向听次数：", report["shanten_regression_rounds"])
    print("暗杠次数：", report["kong_count"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
