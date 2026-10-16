"""Three levels × four modes: verify every visible problem against kernel."""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core.efficiency import analyze_discards  # noqa: E402
from mahtrain_core.rules import is_legal_win, winning_tiles  # noqa: E402
from mahtrain_core.training import MODES, generate_question, grade_answer  # noqa: E402
from mahtrain_core.training_levels import DIFFICULTIES  # noqa: E402


class DifficultyQuestionTests(unittest.TestCase):
    def test_cross_mode_and_level_kernel_validation(self):
        for difficulty in DIFFICULTIES:
            for mode in MODES:
                for seed in (0, 2):
                    with self.subTest(difficulty=difficulty, mode=mode, seed=seed):
                        q=generate_question(mode, seed, difficulty=difficulty)
                        self.assertEqual(q,generate_question(
                            mode, seed, difficulty=difficulty
                        ))
                        self.assertEqual(q["difficulty"],difficulty)
                        self.assertNotIn("seed",q)
                        self.assertFalse(q["reveals_answer"])
                        for forbidden in ("correct_tiles","best_actions",
                                          "correct_answer","construction_family",
                                          "analysis","winning_tiles"):
                            self.assertNotIn(forbidden,q)
                        hand=q["concealed"]
                        missing=q["missing_suit"]
                        counts=Counter(hand)
                        self.assertTrue(all(v<=4 for v in counts.values()))
                        self.assertEqual(len(hand),
                                         13 if mode=="pure_suit_waits" else 14)
                        if mode.startswith("pure_suit"):
                            self.assertEqual(len({t[0] for t in hand}),1)
                        if mode=="pure_suit_waits":
                            waits=winning_tiles(hand,missing_suit=missing)
                            self.assertTrue(waits)
                            graded=grade_answer(mode,seed,waits,
                                difficulty=difficulty,question_id=q["question_id"])
                            self.assertTrue(graded["correct"])
                            self.assertEqual(graded["correct_tiles"],waits)
                        else:
                            win=is_legal_win(hand,missing_suit=missing)
                            action="win" if win else None
                            if not win:
                                analysis=analyze_discards(hand,missing_suit=missing)
                                wanted=1 if mode=="one_shanten" else 0
                                self.assertEqual(analysis["minimum_shanten"],wanted)
                                action=analysis["best_discards"][0]
                            graded=grade_answer(mode,seed,action,
                                difficulty=difficulty,question_id=q["question_id"])
                            self.assertTrue(graded["correct"])
                            self.assertIn("construction_family",graded)
                            self.assertEqual(graded["difficulty"],difficulty)

    def test_difficulty_affects_question_identity_and_grading(self):
        q0=generate_question("tenpai_discard",2,difficulty="basic")
        q1=generate_question("tenpai_discard",2,difficulty="intermediate")
        self.assertNotEqual(q0["question_id"],q1["question_id"])
        with self.assertRaises(ValueError):
            grade_answer("tenpai_discard",2,q0["choices"][0],
                question_id=q0["question_id"],difficulty="intermediate")

    def test_reject_invalid_difficulty(self):
        for level in (None,"hard","",7,True):
            with self.subTest(level=level),self.assertRaises(ValueError):
                generate_question("tenpai_discard",2,difficulty=level)

    def test_challenge_can_generate_seven_pair_competition(self):
        families=set()
        for seed in range(5):
            q=generate_question("one_shanten",seed,difficulty="challenge")
            best=analyze_discards(q["concealed"],
                missing_suit=q["missing_suit"])["best_discards"][0]
            result=grade_answer("one_shanten",seed,best,difficulty="challenge")
            families.add(result["construction_family"])
        self.assertIn("seven_pairs_race",families)


if __name__=="__main__":
    unittest.main()
