"""Isolated mistake re-practice from a completed solo training session.

A retry is a replay of an ALREADY-GRADED frozen hand and its original visible
information, never a new wall draw. The retry question contains no solution.
The original training session, wall, and history are immutable during retries.
"""
from __future__ import annotations

from typing import Any

from .efficiency import effective_draws
from .presentation import grouped_hand, sort_hand


class MistakeRetry:
    def __init__(self, session: Any):
        self._session = session
        self._attempts: dict[int, list[dict[str, Any]]] = {}

    def _original(self, number: int) -> dict[str, Any]:
        if not self._session.finished:
            raise ValueError("请先完成本次连续训练，再进行错题重练")
        if type(number) is not int or number < 1:
            raise ValueError("回合编号必须是正整数")
        entries = self._session._history
        if number > len(entries):
            raise ValueError("指定回合不存在")
        original = entries[number - 1]
        if original["round"] != number or original["correct"]:
            raise ValueError("仅支持重练本次训练中答错的回合")
        return original

    def list(self) -> dict[str, Any]:
        if not self._session.finished:
            raise ValueError("训练尚未结束，暂不能重练")
        rows = []
        for original in self._session._history:
            if original["correct"]:
                continue
            number = original["round"]
            attempts = self._attempts.get(number, [])
            rows.append({
                "round": number,
                "drawn_tile": original["drawn_tile"],
                "attempt_count": len(attempts),
                "latest_correct": (
                    attempts[-1]["correct"] if attempts else None
                ),
            })
        return {
            "mistake_count": len(rows),
            "attempted_count": sum(r["attempt_count"] > 0 for r in rows),
            "corrected_count": sum(r["latest_correct"] is True for r in rows),
            "questions": rows,
        }

    def question(self, number: int) -> dict[str, Any]:
        original = self._original(number)
        hand = sort_hand(original["hand_before"])
        win_possible = "win" in original["best_actions"]
        choices = sort_hand(set(hand))
        if win_possible:
            choices.append("win")
        melds = list(original.get("melds_before", ()))
        return {
            "mode": "mistake_retry",
            "round": number,
            "missing_suit": self._session.missing_suit,
            "concealed": hand,
            "hand_groups": grouped_hand(hand),
            "drawn_tile": original["drawn_tile"],
            "exposed_kongs": [
                {"tile": meld["tile"], "type": meld["type"],
                 "tiles": [meld["tile"]] * 4}
                for meld in melds if meld["type"] == "an_gang"
            ],
            "choices": choices,
            "answer_hidden": True,
            "attempt_number": len(self._attempts.get(number, ())) + 1,
        }

    def grade(self, number: int, action: str) -> dict[str, Any]:
        original = self._original(number)
        question = self.question(number)
        if type(action) is not str or action not in question["choices"]:
            raise ValueError("只能选择该回合手中实际持有的牌，或已提示过的胡牌")
        solution = original["best_actions"]
        correct = action in solution
        candidate = next(
            (entry for entry in original["analysis"]["candidates"]
             if entry["discard"] == action),
            None,
        )
        if candidate is None and action != "win":
            # This branch exists when the player had a completed hand, chose
            # to pass a win, and originally cut a tile. No normal discard
            # candidates existed in the original analyzer at that time.
            after = list(original["hand_before"])
            after.remove(action)
            candidate = {
                "discard": action,
                **effective_draws(
                    after,
                    original.get("melds_before", ()),
                    self._session.missing_suit,
                    visible_tiles=[
                        *original.get("visible_tiles_before", ()), action
                    ],
                ),
            }
        original_candidate = original.get("selected_candidate")
        result = {
            "round": number,
            "attempt_number": question["attempt_number"],
            "original_choice": original["choice"],
            "original_correct": original["correct"],
            "retry_choice": action,
            "correct": correct,
            "improved": correct and not original["correct"],
            "best_actions": list(solution),
            "original_candidate": (
                {
                    "shanten": original_candidate["shanten"],
                    "effective_tile_count": original_candidate[
                        "effective_tile_count"
                    ],
                    "next_draw_probability": original_candidate[
                        "next_draw_probability"
                    ],
                } if original_candidate else None
            ),
            "retry_candidate": (
                {
                    "shanten": candidate["shanten"],
                    "effective_tile_count": candidate["effective_tile_count"],
                    "next_draw_probability": candidate["next_draw_probability"],
                } if candidate else None
            ),
            "explanation": (
                "重练答对：本次选择符合原回合所有并列局部最优判据。"
                if correct else
                "重练仍未达到当时的局部最优；请对照标准动作和牌效。"
            ),
        }
        attempts = self._attempts.setdefault(number, [])
        attempts.append(result)
        if len(attempts) > 20:
            del attempts[:-20]
        return result
