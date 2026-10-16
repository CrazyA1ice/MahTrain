"""MahTrain continuous 14-round solo drill; no third-party dependencies.

Examples:
  python examples/solo_14_rounds.py --seed 17
  python examples/solo_14_rounds.py --seed 17 --auto
  python examples/solo_14_rounds.py --seed 17 --rounds 2 --auto
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core import (  # noqa: E402
    SoloTrainingSession, analyze_discards, format_hand
)

SUIT_NAMES = {"m": "万", "s": "条", "p": "筒"}


def name(tile: str) -> str:
    return "胡牌" if tile == "win" else tile[1:] + SUIT_NAMES[tile[0]]


def choose_auto(session: SoloTrainingSession, state: dict) -> str:
    """Reference autograder demo; used in --auto mode, not a four-player AI."""
    analysis = analyze_discards(
        state["hand"], missing_suit=state["missing_suit"],
        visible_tiles=state["discard_history"],
    )
    if analysis["status"] == "already_winning":
        return "win"
    return analysis["best_discards"][0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MahTrain 连续摸切训练")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--rounds", type=int, default=14)
    parser.add_argument("--missing-suit", choices=("m", "s", "p"), default=None)
    parser.add_argument(
        "--auto", action="store_true",
        help="自动选择局部最优切，验证端到端运行，不需要交互",
    )
    args = parser.parse_args(argv)
    try:
        session = SoloTrainingSession(
            args.seed, missing_suit=args.missing_suit, rounds=args.rounds
        )
    except ValueError as err:
        parser.error(str(err))

    opening = session.public_state()
    print(f"MahTrain 连续{args.rounds}轮摸切训练")
    print("定缺：", SUIT_NAMES[opening["missing_suit"]])
    print("初始13张：", format_hand(opening["hand"]))
    print("说明：同花色9→1降序；每种牌最多4张；未知墙牌不会用于推断有效进张。")
    while not session.finished:
        state = session.draw_next()
        print(f"\\n第{state['current_round']}轮 · 摸到 {name(state['drawn_tile'])}")
        print("理牌：", format_hand(state["hand"]))
        print("已打出的牌：", format_hand(state["discard_history"]) or "（无）")
        print("可选动作：", " ".join(
            f"{tile}({name(tile)})" for tile in state["choices"]
        ))
        if args.auto:
            choice = choose_auto(session, state)
            print("自动选择：", name(choice))
        else:
            try:
                choice = input("请选择要打的牌（m9/s8/p7）或输入win胡牌：").strip()
            except (EOFError, KeyboardInterrupt):
                print("\\n已退出，未提交本轮。")
                return 1
        try:
            feedback = session.submit(choice)
        except ValueError as err:
            print("输入无效：", err)
            if args.auto:
                return 2
            # Prompt again on the same round without drawing twice.
            while True:
                try:
                    choice = input("请重新提交本轮动作：").strip()
                    feedback = session.submit(choice)
                    break
                except ValueError as retry_err:
                    print("输入无效：", retry_err)
                except (EOFError, KeyboardInterrupt):
                    print("\\n已退出，未提交本轮。")
                    return 1
        print(
            "判定：", "正确" if feedback["correct"] else "需改进",
            "| 最优：", "、".join(name(t) for t in feedback["best_actions"])
        )
        print("解析：", feedback["explanation"])

    report = session.report()
    print("\\n===== 连续训练总结 =====")
    print("结束原因：", report["finished_reason"])
    print("训练轮数：", report["completed_rounds"])
    print("正确轮数：", report["correct_rounds"])
    print("最优选择率：", f"{report['accuracy']:.1%}")
    print("退向听次数：", report["shanten_regression_rounds"])
    v = report["average_ukeire_loss_same_shanten"]
    print("同向听层平均进张损失：", f"{v:.2f}" if v is not None else "无可比样本")
    return 0


if __name__ == "__main__":
    sys.exit(main())
