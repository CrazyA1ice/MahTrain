"""Grounded error diagnosis and bounded focused question selection.

A focus drill is *verified* against the original solver before it is shown.
Its label describes an available decision trap; it never presupposes which
answer the player should select, and never sends a solution to the browser.
"""
from __future__ import annotations

from typing import Any

from .efficiency import analyze_discards
from .rules import is_legal_win
from .training import MODES, generate_question
from .training_levels import DIFFICULTIES

ERROR_LABELS = {
    "shanten_regression": "退向听",
    "ukeire_loss": "同向听少进张",
    "missed_win": "错过合法胡牌",
    "false_win": "未成胡误判胡牌",
    "missing_wait": "漏选合法听口",
    "extra_wait": "误选无效听口",
    "other_error": "其他非最优动作",
}
FOCUS_BY_MODE = {
    "one_shanten": ("shanten_regression", "ukeire_loss"),
    "tenpai_discard": ("shanten_regression", "ukeire_loss"),
    "pure_suit_waits": ("missing_wait", "extra_wait"),
    "pure_suit_discard": ("shanten_regression", "ukeire_loss", "missed_win", "false_win"),
}
MAX_FOCUS_CANDIDATES = 24


def diagnose_quiz(mode: str, result: dict[str, Any]) -> list[str]:
    """Diagnose a *graded* answer, not mere construction-family metadata."""
    if mode not in MODES:
        raise ValueError("unsupported training mode")
    if result["correct"]:
        return []
    if mode == "pure_suit_waits":
        missing = bool(result["missed_tiles"])
        extra = bool(result["extra_tiles"])
        causes = (["missing_wait"] if missing else []) + (
            ["extra_wait"] if extra else []
        )
        return causes or ["other_error"]
    analysis = result["analysis"]
    selected = result["your_selection"]
    if analysis["status"] == "already_winning":
        return ["missed_win"] if selected != "win" else []
    if selected == "win":
        return ["false_win"]
    candidate = result["selected_candidate"]
    if candidate is None:
        return ["other_error"]
    if candidate["shanten"] > analysis["minimum_shanten"]:
        return ["shanten_regression"]
    best = max(
        (row["effective_tile_count"] for row in analysis["candidates"]
         if row["shanten"] == analysis["minimum_shanten"]),
        default=0,
    )
    if candidate["effective_tile_count"] < best:
        return ["ukeire_loss"]
    return ["other_error"]


def supports_focus(mode: str, focus: str) -> bool:
    return type(mode) is str and type(focus) is str and (
        focus in FOCUS_BY_MODE.get(mode, ())
    )


def question_has_focus(question: dict[str, Any], focus: str) -> bool:
    """Check the generated 13/14-tile question actually permits this trap."""
    mode = question["mode"]
    if not supports_focus(mode, focus):
        return False
    if mode == "pure_suit_waits":
        # A legitimate nonempty listen set has missed-wait traps. Since the
        # choices include all nine ranks, extra wait traps also exist iff
        # at least one rank is not a winning tile.
        from .rules import winning_tiles
        waits = set(winning_tiles(
            question["concealed"], missing_suit=question["missing_suit"]
        ))
        return (bool(waits) if focus == "missing_wait" else
                len(waits) < len(question["choices"]))
    if focus in ("missed_win", "false_win"):
        win = is_legal_win(question["concealed"],
                           missing_suit=question["missing_suit"])
        return win == (focus == "missed_win")
    analysis = analyze_discards(
        question["concealed"], missing_suit=question["missing_suit"]
    )
    if analysis["status"] != "choose_discard":
        return False
    optimal = analysis["minimum_shanten"]
    if focus == "shanten_regression":
        return any(c["shanten"] > optimal for c in analysis["candidates"])
    if focus == "ukeire_loss":
        best = max((c["effective_tile_count"]
                    for c in analysis["candidates"] if c["shanten"] == optimal),
                   default=0)
        return any(c["shanten"] == optimal
                   and c["effective_tile_count"] < best
                   for c in analysis["candidates"])
    return False


def select_focused_question(
    mode: str, difficulty: str, focus: str, start_seed: int,
) -> tuple[int, dict[str, Any]]:
    """Try bounded private seeds; never silently mislabel an unrelated item."""
    if mode not in MODES or difficulty not in DIFFICULTIES:
        raise ValueError("invalid quiz mode or difficulty")
    if not supports_focus(mode, focus):
        raise ValueError("所选训练模式不支持此错因专项")
    if type(start_seed) is not int or not 0 <= start_seed <= 2**32 - MAX_FOCUS_CANDIDATES:
        raise ValueError("invalid private question seed")
    for offset in range(MAX_FOCUS_CANDIDATES):
        seed = start_seed + offset
        question = generate_question(mode, seed, difficulty=difficulty)
        if question_has_focus(question, focus):
            # Practice label is public; the best answer is still private.
            return seed, {**question, "focus":focus,
                          "focus_label":ERROR_LABELS[focus]}
    raise ValueError("当前难度暂时无法生成可核验的专项题，请换难度再试")
