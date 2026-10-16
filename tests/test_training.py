"""M2 first step: seeded questions, correct-answer isolation, feedback.

Run: python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mahtrain_core.training import (  # noqa: E402
    MODES,
    generate_question,
    grade_answer,
)
from mahtrain_core.efficiency import analyze_discards  # noqa: E402
from mahtrain_core.rules import winning_tiles, is_legal_win  # noqa: E402


class TrainingQuestionCases(unittest.TestCase):
    def test_four_modes_are_reproducible_and_public_does_not_leak_answers(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                q = generate_question(mode, 1)
                self.assertEqual(q, generate_question(mode, 1))
                self.assertEqual(q["mode"], mode)
                self.assertEqual(q["rule_version"], "sichuan_blood_battle_v0.4")
                self.assertNotIn("seed", q)
                self.assertFalse(q["reveals_answer"])
                self.assertFalse(
                    {"correct_tiles", "best_discards", "analysis", "correct_answer"}
                    & set(q)
                )
                self.assertEqual(len(q["concealed"]), 13 if mode == "pure_suit_waits" else 14)
                self.assertTrue(all(count <= 4 for count in Counter(q["concealed"]).values()))
                if mode.startswith("pure_suit"):
                    self.assertEqual(len({tile[0] for tile in q["concealed"]}), 1)
                    self.assertNotEqual(q["concealed"][0][0], q["missing_suit"])

    def test_ordinary_question_categories_exact(self):
        for mode, expected in (("one_shanten", 1), ("tenpai_discard", 0)):
            with self.subTest(mode=mode):
                q = generate_question(mode, 0)
                ranked = analyze_discards(q["concealed"], missing_suit=q["missing_suit"])
                self.assertEqual(ranked["status"], "choose_discard")
                self.assertEqual(ranked["minimum_shanten"], expected)
                self.assertTrue(ranked["best_discards"])
                self.assertTrue(all(
                    entry["shanten"] >= expected
                    for entry in ranked["candidates"]
                ))

    def test_discard_feedback_and_all_tied_answers(self):
        q = generate_question("tenpai_discard", 0)
        ranked = analyze_discards(q["concealed"], missing_suit=q["missing_suit"])
        for choice in ranked["best_discards"]:
            with self.subTest(choice=choice):
                feedback = grade_answer(
                    "tenpai_discard", 0, choice, question_id=q["question_id"]
                )
                self.assertTrue(feedback["correct"])
                self.assertEqual(feedback["best_actions"], ranked["best_discards"])
                self.assertEqual(
                    feedback["selected_candidate"]["discard"], choice
                )
        losing = [
            entry["discard"] for entry in ranked["candidates"]
            if entry["discard"] not in ranked["best_discards"]
        ]
        if losing:
            feedback = grade_answer(
                "tenpai_discard", 0, losing[0], question_id=q["question_id"]
            )
            self.assertFalse(feedback["correct"])
            self.assertIn("reason", feedback)

    def test_pure_suit_waits_uses_exact_set(self):
        q = generate_question("pure_suit_waits", 2)
        true_set = winning_tiles(q["concealed"], missing_suit=q["missing_suit"])
        self.assertTrue(true_set)
        feedback = grade_answer(
            "pure_suit_waits", 2, list(reversed(true_set)),
            question_id=q["question_id"]
        )
        self.assertTrue(feedback["correct"])
        self.assertEqual(feedback["correct_tiles"], true_set)
        self.assertFalse(feedback["missed_tiles"])
        self.assertFalse(feedback["extra_tiles"])
        result = grade_answer(
            "pure_suit_waits", 2, [], question_id=q["question_id"]
        )
        self.assertFalse(result["correct"])
        self.assertEqual(result["missed_tiles"], true_set)

    def test_pure_suit_winning_action_not_discard(self):
        q = generate_question("pure_suit_discard", 0)
        self.assertTrue(is_legal_win(q["concealed"], missing_suit=q["missing_suit"]))
        self.assertTrue(grade_answer(
            "pure_suit_discard", 0, "win", question_id=q["question_id"]
        )["correct"])
        first_tile = q["concealed"][0]
        got = grade_answer(
            "pure_suit_discard", 0, first_tile, question_id=q["question_id"]
        )
        self.assertFalse(got["correct"])
        self.assertEqual(got["best_actions"], ["win"])

    def test_pure_suit_discard_unsolved_question(self):
        q = generate_question("pure_suit_discard", 1)
        self.assertFalse(is_legal_win(q["concealed"], missing_suit=q["missing_suit"]))
        ranked = analyze_discards(q["concealed"], missing_suit=q["missing_suit"])
        self.assertEqual(ranked["minimum_shanten"], 0)
        self.assertTrue(grade_answer(
            "pure_suit_discard", 1, ranked["best_discards"][0]
        )["correct"])
        self.assertFalse(grade_answer(
            "pure_suit_discard", 1, "win"
        )["correct"])

    def test_wrong_id_and_malformed_answers_rejected(self):
        q = generate_question("tenpai_discard", 0)
        with self.assertRaises(ValueError):
            grade_answer("tenpai_discard", 0, q["choices"][0],
                         question_id="not-this-question")
        with self.assertRaises(ValueError):
            grade_answer("tenpai_discard", 0, "s100")
        with self.assertRaises(ValueError):
            grade_answer("pure_suit_waits", 2, ["m1", "m1"])
        with self.assertRaises(ValueError):
            generate_question("unsupported", 0)
        with self.assertRaises(ValueError):
            generate_question("tenpai_discard", True)
        with self.assertRaises(ValueError):
            generate_question("tenpai_discard", -1)


    def test_seed_sweep_produces_legal_and_mode_consistent_questions(self):
        # Prevent accidental random-only generation and category drift.
        for seed in range(6):
            for mode in MODES:
                with self.subTest(seed=seed, mode=mode):
                    q = generate_question(mode, seed)
                    hand = q["concealed"]
                    missing = q["missing_suit"]
                    self.assertTrue(q["question_id"])
                    self.assertTrue(all(n <= 4 for n in Counter(hand).values()))
                    if mode == "pure_suit_waits":
                        self.assertTrue(winning_tiles(hand, missing_suit=missing))
                    elif mode == "pure_suit_discard" and seed % 5 == 0:
                        self.assertTrue(is_legal_win(hand, missing_suit=missing))
                    else:
                        self.assertFalse(is_legal_win(hand, missing_suit=missing))
                        expected = 1 if mode == "one_shanten" else 0
                        result = analyze_discards(hand, missing_suit=missing)
                        self.assertEqual(result["minimum_shanten"], expected)

    def test_seeded_answer_replay_never_trusts_modified_question(self):
        # Caller submits only mode/seed/answer/id, NOT a possibly edited hand.
        q0 = generate_question("tenpai_discard", 0)
        q1 = generate_question("tenpai_discard", 1)
        self.assertNotEqual(q0["question_id"], q1["question_id"])
        with self.assertRaises(ValueError):
            grade_answer(
                "tenpai_discard", 0, q0["choices"][0],
                question_id=q1["question_id"]
            )

    def test_different_seed_produces_different_question(self):
        a = generate_question("pure_suit_waits", 0)
        b = generate_question("pure_suit_waits", 1)
        self.assertNotEqual(a["question_id"], b["question_id"])


if __name__ == "__main__":
    unittest.main()
