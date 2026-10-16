"""Presentation and solo 14-round state machine regression tests."""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mahtrain_core import (  # noqa: E402
    SoloTrainingSession, analyze_discards, format_hand, generate_question,
    grouped_hand, sort_hand,
)
from mahtrain_core.rules import TILES  # noqa: E402
from mahtrain_core.efficiency import analyze_discards  # noqa: E402


class HandSortingTests(unittest.TestCase):
    def test_ascending_suit_groups_and_copy_count(self):
        unsorted = ["p1", "m3", "m9", "s2", "m3", "s9", "p8"]
        copy = list(unsorted)
        expected = ["m3", "m3", "m9", "s2", "s9", "p1", "p8"]
        self.assertEqual(sort_hand(unsorted), expected)
        self.assertEqual(unsorted, copy, "sorting must not mutate game state")
        self.assertEqual(Counter(expected), Counter(unsorted))
        self.assertEqual(format_hand(unsorted),
                         "万[3 3 9] | 条[2 9] | 筒[1 8]")
        groups = grouped_hand(unsorted)
        self.assertEqual([g["suit"] for g in groups], ["m", "s", "p"])
        self.assertEqual([g["tiles"] for g in groups], [
            ["m9", "m3", "m3"], ["s9", "s2"], ["p8", "p1"]
        ])

    def test_single_suit_and_bad_tiles(self):
        self.assertEqual(sort_hand([]), [])
        self.assertEqual(sort_hand(["p1", "p9", "p3", "p9"]),
                         ["p1", "p3", "p9", "p9"])
        with self.assertRaises(ValueError):
            sort_hand(["m10"])

    def test_four_generated_modes_sorted_and_still_gradeable(self):
        for mode in (
            "one_shanten", "tenpai_discard",
            "pure_suit_waits", "pure_suit_discard",
        ):
            with self.subTest(mode=mode):
                q = generate_question(mode, 42)
                self.assertEqual(q["concealed"], sort_hand(q["concealed"]))
                self.assertEqual(
                    q["hand_groups"], grouped_hand(q["concealed"])
                )
                tiles_only = [t for t in q["choices"] if t in TILES]
                self.assertEqual(tiles_only, sort_hand(tiles_only))


class SoloSessionTests(unittest.TestCase):
    def test_initial_state_public_only(self):
        session = SoloTrainingSession(42)
        before = session.public_state()
        self.assertEqual(before["completed_rounds"], 0)
        self.assertEqual(before["phase"], "ready_to_draw")
        self.assertEqual(len(before["hand"]), 13)
        self.assertEqual(before["wall_remaining_count"], 95)
        self.assertEqual(before["hand"], sort_hand(before["hand"]))
        self.assertEqual(before["hand_groups"], grouped_hand(before["hand"]))
        self.assertNotIn("seed", before)
        self.assertNotIn("wall", before)
        self.assertNotIn("best_actions", before)
        self.assertNotIn("analysis", before)
        self.assertFalse(before["choices"])

    def test_single_round_grade_then_move(self):
        session = SoloTrainingSession(7, missing_suit="p", rounds=2)
        first = session.draw_next()
        self.assertEqual(first["phase"], "await_discard")
        self.assertEqual(len(first["hand"]), 14)
        self.assertEqual(first["wall_remaining_count"], 94)
        self.assertEqual(first["hand"], sort_hand(first["hand"]))
        self.assertTrue(first["correct_answers_hidden"])
        with self.assertRaises(ValueError):
            session.draw_next()
        with self.assertRaises(ValueError):
            session.submit("m100")
        self.assertEqual(session.public_state(), first)
        action = first["choices"][0]
        result = session.submit(action)
        self.assertEqual(result["choice"], action)
        self.assertEqual(result["round"], 1)
        self.assertEqual(result["session_phase"], "ready_to_draw")
        self.assertEqual(len(result["hand_after"]), 13)
        self.assertEqual(session.public_state()["completed_rounds"], 1)
        self.assertEqual(session.public_state()["discard_history"], [action])
        self.assertEqual(session.public_state()["wall_remaining_count"], 94)
        with self.assertRaises(ValueError):
            session.submit(action)
        second = session.draw_next()
        self.assertEqual(second["wall_remaining_count"], 93)
        self.assertEqual(second["current_round"], 2)

    def test_14_rounds_reproducible_and_wall_conserved(self):
        def play(seed):
            session = SoloTrainingSession(seed, rounds=14)
            choices, drawn = [], []
            while not session.finished:
                state = session.draw_next()
                self.assertEqual(len(state["hand"]), 14)
                self.assertEqual(state["hand"], sort_hand(state["hand"]))
                self.assertFalse(any(
                    x in state for x in ("next_wall_tile", "future_wall", "analysis")
                ))
                drawn.append(state["drawn_tile"])
                # Even if a natural win is possible, test choosing to cut,
                # which is allowed but marked suboptimal.
                while state["phase"] in ("offer_win", "offer_kong"):
                    state = (session.decide_win(False) if state["phase"] == "offer_win"
                             else session.decide_kong(None))
                choice = state["choices"][0]
                feedback = session.submit(choice)
                self.assertIsInstance(feedback["correct"], bool)
                self.assertEqual(len(feedback["hand_after"]), 13)
                choices.append(choice)
            report = session.report()
            self.assertEqual(report["completed_rounds"], 14)
            self.assertEqual(report["finished_reason"], "round_limit_reached")
            self.assertTrue(report["finished"])
            self.assertEqual(len(report["history"]), 14)
            self.assertEqual(len(report["visible_discards"]), 14)
            self.assertEqual(report["remaining_wall_count"], 81)
            self.assertGreaterEqual(report["accuracy"], 0)
            self.assertLessEqual(report["accuracy"], 1)
            with self.assertRaises(ValueError):
                session.draw_next()
            return drawn, choices, report["correct_rounds"]
        self.assertEqual(play(17), play(17))

    def test_independent_seed_and_selection_reflects_live_state(self):
        a = SoloTrainingSession(5, missing_suit="p", rounds=1)
        b = SoloTrainingSession(5, missing_suit="p", rounds=1)
        qa = a.draw_next()
        qb = b.draw_next()
        self.assertEqual(qa, qb)
        analysis = analyze_discards(qa["hand"], missing_suit="p")
        if qa["phase"] == "offer_win":
            result = a.decide_win(True)
            answer = "win"
        else:
            while qa["phase"] == "offer_kong":
                qa = a.decide_kong(None)
            analysis = analyze_discards(qa["hand"], missing_suit="p")
            answer = analysis["best_discards"][0]
            result = a.submit(answer)
        self.assertTrue(result["correct"])
        self.assertEqual(result["best_actions"], [answer] if answer == "win"
                         else analysis["best_discards"])
        self.assertNotEqual(a.report()["completed_rounds"],
                            b.report()["completed_rounds"])

    def test_reject_bad_init(self):
        for kwargs in (
            {"seed": -1}, {"seed": True}, {"seed": 3, "rounds": 0},
            {"seed": 3, "rounds": 15}, {"seed": 3, "missing_suit": "x"},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    SoloTrainingSession(**kwargs)


if __name__ == "__main__":
    unittest.main()
