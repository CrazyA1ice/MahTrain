"""Prompt-specific tests: automatic win offers, immutable concealed kongs,
tail replacement, 108-tile conservation and no premature answers."""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mahtrain_core import SoloTrainingSession, sort_hand  # noqa: E402
from mahtrain_core.rules import TILES  # noqa: E402


def prepare_opening(first_13: list[str], draw: str, *, tail: str | None = None):
    """Inject a legal fixed physical shuffled wall into a fresh test session."""
    game = SoloTrainingSession(100, missing_suit="s")
    deck = Counter({t: 4 for t in TILES})
    for t in first_13 + [draw] + ([tail] if tail else []):
        deck[t] -= 1
        if deck[t] < 0:
            raise ValueError("fixture consumes more than four tiles")
    remaining = [
        t for t in TILES for _ in range(deck[t])
    ]
    game._hand = list(first_13)
    game._wall = [draw, *remaining, *([tail] if tail else [])]
    game._assert_deck()
    return game


# 13 ready: four triplets + singleton m9.
READY = ["m1"] * 3 + ["m4"] * 3 + ["p1"] * 3 + ["p4"] * 3 + ["m9"]


class WinAndKongPrompts(unittest.TestCase):
    def test_detect_win_and_prompt_yes_no_then_early_finish(self):
        game = prepare_opening(READY, "m9")
        state = game.draw_next()
        self.assertEqual(state["phase"], "offer_win")
        self.assertTrue(state["win_offered"])
        self.assertEqual(state["choices"], [])
        self.assertEqual(state["kong_options"], [])
        self.assertNotIn("best_actions", state)
        with self.assertRaises(ValueError):
            game.submit("m9")
        with self.assertRaises(ValueError):
            game.decide_kong(None)
        result = game.decide_win(True)
        self.assertTrue(result["correct"])
        self.assertEqual(result["win_type"], "self_draw")
        self.assertTrue(game.finished)
        self.assertEqual(game.report()["finished_reason"], "self_drawn_win")
        self.assertEqual(game.report()["completed_rounds"], 1)
        self.assertEqual(len(game.public_state()["hand"]), 14)
        with self.assertRaises(ValueError):
            game.draw_next()

    def test_decline_win_then_discard_is_allowed_but_not_optimal(self):
        game = prepare_opening(READY, "m9")
        game.draw_next()
        state = game.decide_win(False)
        self.assertEqual(state["phase"], "await_discard")
        self.assertNotIn("win", state["choices"])
        feedback = game.submit("m9")
        self.assertFalse(feedback["correct"])
        self.assertEqual(feedback["best_actions"], ["win"])
        self.assertEqual(len(feedback["hand_after"]), 13)

    def test_kong_moves_four_cards_to_immutable_separate_area_and_replaces(self):
        game = prepare_opening(READY, "m1", tail="m9")
        first = game.draw_next()
        self.assertEqual(first["phase"], "offer_kong")
        self.assertEqual(first["kong_options"], ["m1"])
        self.assertEqual(first["wall_remaining_count"], 94)
        with self.assertRaises(ValueError):
            game.submit("m1")  # must respond to gang prompt first
        with self.assertRaises(ValueError):
            game.decide_kong("p9")
        after = game.decide_kong("m1")
        self.assertEqual(after["phase"], "offer_win")
        self.assertEqual(after["wall_remaining_count"], 93)
        self.assertEqual(after["drawn_tile"], "m9")  # replacement from wall tail
        self.assertEqual(len(after["hand"]), 11)
        self.assertNotIn("m1", after["hand"])
        self.assertEqual(after["exposed_kongs"], [
            {"type": "an_gang", "tile": "m1", "tiles": ["m1"] * 4}
        ])
        self.assertEqual(after["kong_count"], 1)
        with self.assertRaises(ValueError):
            game.submit("m1")
        win = game.decide_win(True)
        self.assertEqual(win["win_type"], "kong_bloom")
        report = game.report()
        self.assertEqual(report["kong_count"], 1)
        self.assertEqual(report["kong_history"][0]["replacement_source"], "wall_tail")
        self.assertEqual(report["remaining_wall_count"], 93)

    def test_decline_kong_keeps_tiles_in_hand(self):
        game = prepare_opening(READY, "m1", tail="m9")
        original = game.draw_next()["hand"]
        after = game.decide_kong(None)
        self.assertEqual(after["phase"], "await_discard")
        self.assertEqual(after["hand"], original)
        self.assertEqual(after["exposed_kongs"], [])
        self.assertEqual(after["wall_remaining_count"], 94)
        self.assertIn("m1", after["choices"])
        game.submit("m1")
        self.assertEqual(game.report()["kong_count"], 0)

    def test_declined_win_after_supplement_still_locked_kong_area(self):
        game = prepare_opening(READY, "m1", tail="m9")
        game.draw_next()
        game.decide_kong("m1")
        after = game.decide_win(False)
        self.assertEqual(after["phase"], "await_discard")
        self.assertEqual(len(after["hand"]), 11)
        self.assertNotIn("m1", after["choices"])
        cut = next(iter(after["choices"]))
        game.submit(cut)
        state = game.public_state()
        self.assertEqual(len(state["hand"]), 10)
        self.assertEqual(len(state["exposed_kongs"]), 1)
        self.assertEqual(state["wall_remaining_count"], 93)

    def test_invalid_prompt_responses_leave_state_unchanged(self):
        game = prepare_opening(READY, "m1")
        opening = game.draw_next()
        for invalid in ("m9", True, 0):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    game.decide_kong(invalid)
                self.assertEqual(game.public_state(), opening)
        with self.assertRaises(ValueError):
            game.decide_win(True)
        self.assertEqual(game.public_state(), opening)

    def test_kong_already_locked_never_enters_sort_or_public_choices(self):
        game = prepare_opening(READY, "m1", tail="m9")
        game.draw_next()
        state = game.decide_kong("m1")
        self.assertEqual(state["hand"], sort_hand(state["hand"]))
        self.assertEqual(state["exposed_kongs"][0]["tiles"], ["m1"] * 4)
        self.assertNotIn("m1", state["hand"])
        self.assertNotIn("m1", state["choices"])


if __name__ == "__main__":
    unittest.main()
