"""Single-player 14-round draw/discard practice with prompted wins and kongs.

A trusted state machine owns 108 physical tiles. Exposed kongs are immutable
groups shown beside concealed hand; gang replacement always draws from the
opposite (tail) end of the wall. This is NOT a four-player blood-battle match.
"""
from __future__ import annotations

import hashlib
import random
from collections import Counter
from typing import Any

from .efficiency import analyze_discards, effective_draws
from .review import build_round_review
from .presentation import grouped_hand, sort_hand
from .rules import SUITS, TILES, _meld_tiles, is_legal_win, diagnose_win


class SoloTrainingSession:
    """Maximum 14 draw/discard decisions; replacement draws do not add rounds."""

    def __init__(
        self, seed: int, missing_suit: str | None = None, rounds: int = 14
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
        self._melds: list[dict[str, str]] = []
        self._history: list[dict[str, Any]] = []
        self._kong_log: list[dict[str, Any]] = []
        self._pending_tile: str | None = None
        self._round_draw: str | None = None
        self._phase = "ready_to_draw"
        self._declined_win = False
        self._declined_kongs: set[str] = set()
        self._kong_this_turn = False
        self._finished_reason: str | None = None
        self._rounds = rounds
        self.missing_suit = (
            missing_suit if missing_suit is not None else
            min(SUITS, key=lambda suit: (
                sum(tile[0] == suit for tile in self._hand), SUITS.index(suit)
            ))
        )
        self.session_id = hashlib.sha256(
            f"MahTrain:solo:v2:{seed}:{self.missing_suit}:{rounds}".encode()
        ).hexdigest()[:20]
        self._assert_deck()

    @property
    def finished(self) -> bool:
        return self._finished_reason is not None

    def _physical_meld_tiles(self) -> list[str]:
        return [tile for meld in self._melds for tile in _meld_tiles(meld)]

    def _assert_deck(self) -> None:
        physical = Counter([
            *self._hand, *self._wall, *self._discards,
            *self._physical_meld_tiles(),
        ])
        if physical != Counter({tile: 4 for tile in TILES}):
            raise AssertionError("108-tile deck conservation failed")
        # 13 effective tiles between turns, 14 during win/kong/discard offers.
        effective = len(self._hand) + 3 * len(self._melds)
        expected = 13 if self._phase in ("ready_to_draw", "finished") else 14
        if self._finished_reason == "self_drawn_win":
            expected = 14
        if effective != expected:
            raise AssertionError("effective-tile count invalid for phase")

    def _available_kongs(self) -> list[str]:
        if not self._wall:
            return []  # cannot kong without a replacement tile
        counts = Counter(self._hand)
        # Do not make new declarations of the selected missing suit while
        # the blood-battle missing-suit kong boundary remains unresolved.
        return sort_hand([
            tile for tile, count in counts.items()
            if count == 4 and tile[0] != self.missing_suit
            and tile not in self._declined_kongs
        ])

    def _offer_next(self) -> None:
        if (
            not self._declined_win
            and is_legal_win(self._hand, self._melds, self.missing_suit)
        ):
            self._phase = "offer_win"
        elif self._available_kongs():
            self._phase = "offer_kong"
        else:
            self._phase = "await_discard"
        self._assert_deck()

    def public_state(self) -> dict[str, Any]:
        """Concealed, public melds and discards only; never reveal future wall."""
        hand = sort_hand(self._hand)
        return {
            "session_id": self.session_id,
            "ruleset": "sichuan_blood_battle_v0.4",
            "mode": "solo_14_rounds",
            "round_limit": self._rounds,
            "completed_rounds": len(self._history),
            "current_round": (
                len(self._history) + 1
                if self._phase not in ("ready_to_draw", "finished") else None
            ),
            "phase": self._phase,
            "missing_suit": self.missing_suit,
            "win_status": diagnose_win(self._hand, self._melds, self.missing_suit),
            "hand": hand,
            "hand_groups": grouped_hand(hand),
            "exposed_kongs": [
                {"type": meld["type"], "tile": meld["tile"],
                 "tiles": [meld["tile"]] * 4}
                for meld in self._melds
            ],
            "kong_count": len(self._melds),
            "drawn_tile": self._pending_tile,
            "discard_history": list(self._discards),
            "wall_remaining_count": len(self._wall),
            "choices": (
                sort_hand(set(hand)) if self._phase == "await_discard" else []
            ),
            "kong_options": (
                self._available_kongs() if self._phase == "offer_kong" else []
            ),
            "win_offered": self._phase == "offer_win",
            "correct_answers_hidden": True,
        }

    def draw_next(self) -> dict[str, Any]:
        if self._phase != "ready_to_draw":
            raise ValueError("finish all pending prompts and discard first")
        if self.finished or len(self._history) >= self._rounds or not self._wall:
            raise ValueError("session has no further rounds")
        self._pending_tile = self._wall.pop(0)  # normal draw from wall front
        self._round_draw = self._pending_tile
        self._hand.append(self._pending_tile)
        self._declined_win = False
        self._declined_kongs.clear()
        self._kong_this_turn = False
        self._offer_next()
        return self.public_state()

    def decide_win(self, accept: bool) -> dict[str, Any]:
        """Reply to AUTOMATIC win prompt; 'win' is not a discard action."""
        if self._phase != "offer_win" or type(accept) is not bool:
            raise ValueError("no legal win prompt awaiting a yes/no response")
        if accept:
            before = sort_hand(self._hand)
            feedback = {
                "round": len(self._history) + 1,
                "drawn_tile": self._round_draw,
                "hand_before": before,
                "choice": "win",
                "correct": True,
                "best_actions": ["win"],
                "selected_candidate": None,
                "shanten_loss": None,
                "ukeire_loss": None,
                "win_type": "kong_bloom" if self._kong_this_turn else "self_draw",
                "explanation": "系统已确认合法自摸，选择胡牌，训练结束。",
                "analysis": {"status": "already_winning", "candidates": []},
            }
            self._history.append(feedback)
            self._phase = "finished"
            self._finished_reason = "self_drawn_win"
            self._assert_deck()
            return {**feedback, "session_phase": self._phase,
                    "hand_after": before, "wall_remaining_count": len(self._wall)}
        self._declined_win = True
        self._offer_next()
        return self.public_state()

    def decide_kong(self, tile: str | None) -> dict[str, Any]:
        """Pick an offered concealed kong; None means decline the prompt."""
        if self._phase != "offer_kong":
            raise ValueError("no kong prompt is active")
        options = self._available_kongs()
        if tile is None:
            self._declined_kongs.update(options)
            self._offer_next()
            return self.public_state()
        if type(tile) is not str or tile not in options:
            raise ValueError("only offered four-of-a-kind tiles may be konged")
        for _ in range(4):
            self._hand.remove(tile)
        self._melds.append({"type": "an_gang", "tile": tile})
        self._kong_log.append({
            "round": len(self._history) + 1, "tile": tile,
            "type": "an_gang", "replacement_source": "wall_tail",
        })
        self._pending_tile = self._wall.pop()  # supplement from wall TAIL
        self._hand.append(self._pending_tile)
        self._kong_this_turn = True
        # Replacement draw is a new post-gang win/kong evaluation point.
        self._declined_win = False
        self._declined_kongs.clear()
        self._offer_next()
        return self.public_state()

    def submit(self, action: str) -> dict[str, Any]:
        """Cut a concealed tile ONLY after win/kong prompts have been resolved."""
        if self._phase != "await_discard":
            raise ValueError("answer win/kong prompts before selecting a discard")
        if type(action) is not str or action not in self._hand:
            raise ValueError("choose a tile in the concealed hand, not a kong tile")
        before = sort_hand(self._hand)
        legal_win = is_legal_win(self._hand, self._melds, self.missing_suit)
        analysis = analyze_discards(
            self._hand, self._melds, self.missing_suit,
            visible_tiles=self._discards,
        )
        best = ["win"] if legal_win else list(analysis["best_discards"])
        row = next((r for r in analysis["candidates"] if r["discard"] == action), None)
        if legal_win and row is None:
            # The learner declined a legal win and chose to cut. The ordinary
            # discard analyzer intentionally stops at a completed hand; still
            # record actual after-cut ukeire so the round isn't lost in review.
            remainder = list(self._hand)
            remainder.remove(action)
            row = {
                "discard": action,
                **effective_draws(
                    remainder, self._melds, self.missing_suit,
                    visible_tiles=[*self._discards, action],
                ),
            }
        loss = (
            row["shanten"] - analysis["minimum_shanten"]
            if row is not None and not legal_win else None
        )
        ukeire_loss = (
            max(r["effective_tile_count"] for r in analysis["candidates"]
                if r["shanten"] == analysis["minimum_shanten"])
            - row["effective_tile_count"]
            if row is not None and loss == 0 and not legal_win else None
        )
        correct = action in best
        if legal_win:
            explanation = "系统已提示可以胡牌；你选择过牌并切牌，本轮记为非最优。"
        elif loss:
            explanation = "此切牌导致向听数劣于本轮最优层级。"
        elif correct:
            explanation = "未退向听且有效进张枚数最大；并列最优均认可。"
        else:
            explanation = "未退向听，但有效进张枚数少于更好的切牌选项。"
        feedback = {
            "round": len(self._history) + 1,
            "drawn_tile": self._round_draw,
            "hand_before": before,
            "choice": action,
            "correct": correct,
            "best_actions": best,
            "selected_candidate": row,
            "shanten_loss": loss,
            "ukeire_loss": ukeire_loss,
            "explanation": explanation,
            "analysis": analysis,
        }
        self._history.append(feedback)
        self._hand.remove(action)
        self._discards.append(action)
        self._pending_tile = None
        self._round_draw = None
        if len(self._history) >= self._rounds:
            self._finished_reason = "round_limit_reached"
            self._phase = "finished"
        elif not self._wall:
            self._finished_reason = "wall_empty"
            self._phase = "finished"
        else:
            self._phase = "ready_to_draw"
        self._assert_deck()
        return {**feedback, "session_phase": self._phase,
                "wall_remaining_count": len(self._wall),
                "hand_after": sort_hand(self._hand)}

    def report(self) -> dict[str, Any]:
        total = len(self._history)
        successes = sum(row["correct"] for row in self._history)
        comparable = [row["ukeire_loss"] for row in self._history
                      if row["ukeire_loss"] is not None]
        review = build_round_review(self._history)
        return {
            "session_id": self.session_id,
            "round_review": review["rounds"],
            "progress_summary": review["progress"],
            "completed_rounds": total,
            "round_limit": self._rounds,
            "finished": self.finished,
            "finished_reason": self._finished_reason,
            "correct_rounds": successes,
            "accuracy": successes / total if total else 0.0,
            "shanten_regression_rounds": sum(
                (row["shanten_loss"] or 0) > 0 for row in self._history
            ),
            "average_ukeire_loss_same_shanten": (
                sum(comparable) / len(comparable) if comparable else None
            ),
            "kong_count": len(self._melds),
            "kong_history": [dict(row) for row in self._kong_log],
            "exposed_kongs": [
                {"type": meld["type"], "tile": meld["tile"],
                 "tiles": [meld["tile"]] * 4}
                for meld in self._melds
            ],
            "history": [dict(row) for row in self._history],
            "visible_discards": list(self._discards),
            "remaining_wall_count": len(self._wall),
        }
