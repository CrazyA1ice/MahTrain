"""A reproducible, isolated 14-round draw/discard training session.

This simulates ONE learner from a fixed 108-tile wall; it is not a four-player
match. The shuffled future wall stays private. The learner's own 13/14 tiles
and already-discarded tiles are the only knowledge used for ukeire/probability.

The session must live in trusted Python/server state, not client-side JSON.
"""
from __future__ import annotations

import hashlib
import random
from collections import Counter
from typing import Any

from .efficiency import analyze_discards, effective_draws, shanten_13
from .presentation import grouped_hand, sort_hand
from .rules import SUITS, TILES, is_legal_win


class SoloTrainingSession:
    """Up to 14 consecutive draw-and-cut decisions on a single physical deck."""

    def __init__(
        self,
        seed: int,
        missing_suit: str | None = None,
        rounds: int = 14,
    ) -> None:
        if type(seed) is not int or seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        if type(rounds) is not int or not 1 <= rounds <= 14:
            raise ValueError("rounds must be 1 through 14")
        if missing_suit is not None and missing_suit not in SUITS:
            raise ValueError("missing_suit must be m/s/p or None")
        deck = [tile for tile in TILES for _ in range(4)]
        random.Random(seed).shuffle(deck)
        self._hand = deck[:13]
        self._wall = deck[13:]
        self._discards: list[str] = []
        self._history: list[dict[str, Any]] = []
        self._pending_tile: str | None = None
        self._finished_reason: str | None = None
        self._rounds = rounds
        self._seed = seed
        self.missing_suit = (
            missing_suit if missing_suit is not None else
            min(SUITS, key=lambda suit: (
                sum(t[0] == suit for t in self._hand), SUITS.index(suit)
            ))
        )
        self.session_id = hashlib.sha256(
            f"MahTrain:solo:v1:{seed}:{self.missing_suit}:{rounds}".encode()
        ).hexdigest()[:20]
        self._assert_deck()

    @property
    def finished(self) -> bool:
        return self._finished_reason is not None

    def _assert_deck(self) -> None:
        physical = Counter([*self._hand, *self._wall, *self._discards])
        expected = Counter({tile: 4 for tile in TILES})
        if physical != expected:
            raise AssertionError("deck conservation failed")

    def public_state(self) -> dict[str, Any]:
        """Only currently visible learner information; no future wall tiles."""
        hand = sort_hand(self._hand)
        return {
            "session_id": self.session_id,
            "ruleset": "sichuan_blood_battle_v0.4",
            "mode": "solo_14_rounds",
            "round_limit": self._rounds,
            "completed_rounds": len(self._history),
            "current_round": (
                len(self._history) + 1 if self._pending_tile is not None
                else None
            ),
            "phase": (
                "finished" if self.finished else
                "await_discard" if self._pending_tile is not None
                else "ready_to_draw"
            ),
            "missing_suit": self.missing_suit,
            "hand": hand,
            "hand_groups": grouped_hand(hand),
            "drawn_tile": self._pending_tile,
            "discard_history": list(self._discards),
            "wall_remaining_count": len(self._wall),
            "choices": (
                [*sort_hand(set(hand)), *(
                    ["win"] if is_legal_win(hand, missing_suit=self.missing_suit)
                    else []
                )]
                if self._pending_tile is not None else []
            ),
            "correct_answers_hidden": True,
        }

    def draw_next(self) -> dict[str, Any]:
        """Draw exactly once per turn; reject drawing twice without cutting."""
        if self.finished:
            raise ValueError("session has finished")
        if self._pending_tile is not None:
            raise ValueError("submit the current round before drawing again")
        if len(self._history) >= self._rounds or not self._wall:
            raise ValueError("session has no further rounds")
        self._pending_tile = self._wall.pop()
        self._hand.append(self._pending_tile)
        self._assert_deck()
        return self.public_state()

    def submit(self, action: str) -> dict[str, Any]:
        """Grade and APPLY one valid decision; cannot grade the same turn twice."""
        if self.finished or self._pending_tile is None:
            raise ValueError("no active draw awaiting a choice")
        if type(action) is not str:
            raise ValueError("action must be a tile or 'win'")
        legal_win = is_legal_win(self._hand, missing_suit=self.missing_suit)
        if action == "win":
            if not legal_win:
                raise ValueError("cannot declare win with this hand")
        elif action not in self._hand:
            raise ValueError("discard must be a tile in the current hand")

        round_number = len(self._history) + 1
        before = sort_hand(self._hand)
        just_drawn = self._pending_tile
        analysis = analyze_discards(
            self._hand,
            missing_suit=self.missing_suit,
            visible_tiles=self._discards,
        )
        best = (
            ["win"] if legal_win else list(analysis["best_discards"])
        )
        correct = action in best
        chosen_row = next((
            row for row in analysis["candidates"]
            if row["discard"] == action
        ), None)
        shanten_loss = (
            chosen_row["shanten"] - analysis["minimum_shanten"]
            if chosen_row is not None else None
        )
        ukeire_loss = (
            max(row["effective_tile_count"] for row in analysis["candidates"]
                if row["shanten"] == analysis["minimum_shanten"])
            - chosen_row["effective_tile_count"]
            if chosen_row is not None and shanten_loss == 0 else None
        )

        if action == "win":
            explanation = "手牌已合法胡牌，立即胡牌正确；训练提前结束。"
        elif legal_win:
            explanation = "当前已经能胡牌，放弃胡牌并切牌；该动作不属于本轮最优答案。"
        elif shanten_loss:
            explanation = "本轮存在更低向听的切法；此切牌不符合局部最优切。"
        elif correct:
            explanation = "未退向听且有效进张枚数达到本轮最大；并列最优均认可。"
        else:
            explanation = "保持了最低可达向听，但有效进张枚数少于局部最优切。"

        feedback = {
            "round": round_number,
            "drawn_tile": just_drawn,
            "hand_before": before,
            "choice": action,
            "correct": correct,
            "best_actions": best,
            "selected_candidate": chosen_row,
            "shanten_loss": shanten_loss,
            "ukeire_loss": ukeire_loss,
            "explanation": explanation,
            "analysis": analysis,  # Reveal only after the learner's answer.
        }
        self._history.append(feedback)
        self._pending_tile = None
        if action == "win":
            self._finished_reason = "self_drawn_win"
        else:
            self._hand.remove(action)
            self._discards.append(action)
            if len(self._history) >= self._rounds:
                self._finished_reason = "round_limit_reached"
            elif not self._wall:
                self._finished_reason = "wall_empty"
        self._assert_deck()
        return {
            **feedback,
            "session_phase": "finished" if self.finished else "ready_to_draw",
            "wall_remaining_count": len(self._wall),
            "hand_after": sort_hand(self._hand),
        }

    def report(self) -> dict[str, Any]:
        """Accuracy and regrets for COMPLETED rounds, without hidden wall."""
        count = len(self._history)
        correct = sum(row["correct"] for row in self._history)
        comparable = [
            row["ukeire_loss"] for row in self._history
            if row["ukeire_loss"] is not None
        ]
        return {
            "session_id": self.session_id,
            "completed_rounds": count,
            "round_limit": self._rounds,
            "finished": self.finished,
            "finished_reason": self._finished_reason,
            "correct_rounds": correct,
            "accuracy": correct / count if count else 0.0,
            "shanten_regression_rounds": sum(
                (row["shanten_loss"] or 0) > 0 for row in self._history
            ),
            "average_ukeire_loss_same_shanten": (
                sum(comparable) / len(comparable) if comparable else None
            ),
            "history": [dict(row) for row in self._history],
            "visible_discards": list(self._discards),
            "remaining_wall_count": len(self._wall),
        }
