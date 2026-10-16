"""Interactive console trainer (stdlib only).

Examples:
  python examples/training_quiz.py --mode tenpai_discard --seed 42
  python examples/training_quiz.py --mode pure_suit_waits --seed 42
  python examples/training_quiz.py --mode pure_suit_discard --seed 0
  python examples/training_quiz.py --mode one_shanten --seed 9 --print-only

Modes: one_shanten / tenpai_discard / pure_suit_waits / pure_suit_discard.
Inputs: m1..m9=万, s1..s9=条, p1..p9=筒; 'win' means 胡牌.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core import MODES, generate_question, grade_answer, format_hand, sort_hand  # noqa: E402

CHINESE = {"m": "万", "s": "条", "p": "筒"}
TITLES = {
    "one_shanten": "一向听何切",
    "tenpai_discard": "听牌何切",
    "pure_suit_waits": "清一色听牌选择（多选）",
    "pure_suit_discard": "清一色何切／识别已胡",
}


def label(tile: str) -> str:
    if tile == "win":
        return "胡牌"
    return tile[1:] + CHINESE[tile[0]]


def display_result(mode: str, report: dict) -> None:
    print("\n判题：", "正确" if report["correct"] else "未答对")
    print("解析：", report["reason"])
    if mode == "pure_suit_waits":
        print("完整听口：", "、".join(label(t) for t in sort_hand(report["correct_tiles"])))
        if report["missed_tiles"]:
            print("漏选：", "、".join(label(t) for t in sort_hand(report["missed_tiles"])))
        if report["extra_tiles"]:
            print("多选：", "、".join(label(t) for t in sort_hand(report["extra_tiles"])))
        e = report["effective_draws"]
        print("剩余可胡枚数：", e["effective_tile_count"])
        print("下一摸和牌概率：", f"{e['next_draw_probability']:.2%}")
        return

    print("正确动作：", "、".join(label(t) for t in (["win"] if "win" in report["best_actions"] else sort_hand(report["best_actions"]))))
    if report["analysis"]["status"] == "already_winning":
        return
    print("\n切牌对照（向听数越小越好，进张枚数越多越好）：")
    print("切牌　向听　进张枚数　下摸概率　局部最优")
    for candidate in report["analysis"]["candidates"]:
        print(
            f"{label(candidate['discard']):4}　"
            f"{candidate['shanten']:>2}　　 "
            f"{candidate['effective_tile_count']:>3}　　 "
            f"{candidate['next_draw_probability']:.2%}　　 "
            f"{'★' if candidate['local_optimal'] else '-'}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MahTrain 简易命令行训练")
    parser.add_argument("--mode", choices=MODES, default="tenpai_discard")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--print-only", action="store_true",
        help="只输出公开题目，适合 CI 演示；不泄露答案且不等待输入",
    )
    args = parser.parse_args(argv)
    try:
        question = generate_question(args.mode, args.seed)
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))

    print("MahTrain：", TITLES[args.mode])
    print("题号：", question["question_id"])
    print("规则：", question["rule_version"])
    print("定缺：", CHINESE[question["missing_suit"]])
    print("理牌：", format_hand(question["concealed"]))
    print("可选：", " ".join(
        f"{option}({label(option)})" for option in question["choices"]
    ))
    if args.print_only:
        return 0

    try:
        if question["answer_type"] == "tile_set":
            raw = input("选择所有听牌（例如 m1,m4,m7；可留空）：").strip()
            selection = (
                raw.replace("，", ",").replace(",", " ").split() if raw else []
            )
        else:
            selection = input("请选择切牌（例如 m9）或输入 win 胡牌：").strip()
        report = grade_answer(
            args.mode, args.seed, selection, question_id=question["question_id"]
        )
    except (EOFError, KeyboardInterrupt):
        print("\n已退出")
        return 1
    except ValueError as exc:
        print("答案格式不正确：", exc)
        return 2

    display_result(args.mode, report)
    return 0 if report["correct"] else 1


if __name__ == "__main__":
    sys.exit(main())
