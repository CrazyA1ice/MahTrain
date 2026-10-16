"""M2.8 error causes, bounded genuinely focused drills and SQLite summaries."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core.error_focus import (
    ERROR_LABELS, diagnose_quiz, question_has_focus,
    select_focused_question, supports_focus,
)
from mahtrain_core.training import generate_question, grade_answer
from mahtrain_core.history import HistoryStore


class ErrorDiagnosisTests(unittest.TestCase):
    def test_tenpai_mistakes_classified_by_real_post_cut_metrics(self):
        base={
            "correct":False, "your_selection":"m1",
            "analysis":{"status":"choose_discard","minimum_shanten":0,
                "candidates":[
                    {"shanten":0,"effective_tile_count":9},
                    {"shanten":0,"effective_tile_count":5},
                ]},
            "selected_candidate":{"shanten":0,"effective_tile_count":5}
        }
        self.assertEqual(diagnose_quiz("tenpai_discard",base),["ukeire_loss"])
        self.assertEqual(diagnose_quiz("tenpai_discard",{
            **base,"selected_candidate":{"shanten":1,"effective_tile_count":24}
        }),["shanten_regression"])
        self.assertEqual(diagnose_quiz("tenpai_discard",{
            **base,"correct":True
        }),[])
        self.assertEqual(diagnose_quiz("pure_suit_discard",{
            **base,"your_selection":"win","selected_candidate":None
        }),["false_win"])
        self.assertEqual(diagnose_quiz("pure_suit_discard",{
            **base,"analysis":{"status":"already_winning","candidates":[]},
            "selected_candidate":None,
        }),["missed_win"])

    def test_pure_waits_supports_missing_extra_and_both(self):
        base={"correct":False,"missed_tiles":["m1"],"extra_tiles":[]}
        self.assertEqual(diagnose_quiz("pure_suit_waits",base),["missing_wait"])
        self.assertEqual(diagnose_quiz("pure_suit_waits",{
            **base,"missed_tiles":[],"extra_tiles":["m4"]
        }),["extra_wait"])
        self.assertEqual(diagnose_quiz("pure_suit_waits",{
            **base,"extra_tiles":["m4"]
        }),["missing_wait","extra_wait"])

    def test_focused_question_is_verified_and_keeps_answer_private(self):
        for mode,difficulty,focus,start in (
            ("pure_suit_waits","basic","missing_wait",0),
            ("pure_suit_waits","basic","extra_wait",0),
            ("pure_suit_discard","basic","missed_win",0),
            ("pure_suit_discard","basic","false_win",1),
        ):
            with self.subTest(mode=mode,focus=focus):
                seed,question=select_focused_question(mode,difficulty,focus,start)
                self.assertTrue(question_has_focus(question,focus))
                self.assertEqual(question["focus"],focus)
                self.assertEqual(question["focus_label"],ERROR_LABELS[focus])
                self.assertEqual(question["question_id"],
                    generate_question(mode,seed,difficulty=difficulty)["question_id"])
                self.assertNotIn("best_actions",question)
                self.assertNotIn("correct_tiles",question)
                self.assertNotIn("seed",question)
        self.assertFalse(supports_focus("pure_suit_waits","missed_win"))
        with self.assertRaises(ValueError):
            select_focused_question("pure_suit_waits","basic","missed_win",0)

    def test_database_weakness_counts_only_original_wrong_answers(self):
        with tempfile.TemporaryDirectory() as folder:
            db=HistoryStore(Path(folder)/"history.sqlite3")
            mode="pure_suit_waits"
            q=generate_question(mode,42)
            failed=grade_answer(mode,42,[],question_id=q["question_id"])
            self.assertFalse(failed["correct"])
            self.assertEqual(diagnose_quiz(mode,failed),["missing_wait"])
            key=db.save_quiz_answer(q,failed,[])
            stats=db.quiz_progress(mode,"basic")["weaknesses"]
            self.assertEqual(stats["counts"]["missing_wait"],1)
            self.assertEqual(stats["counts"]["extra_wait"],0)
            self.assertEqual(stats["top_focus"],"missing_wait")
            self.assertEqual(stats["sample_wrong"],1)
            # The user's retry does NOT artificially increase the historical
            # weakness or first-answer counts.
            right=failed["correct_tiles"]
            self.assertTrue(db.quiz_retry_submit(key,right)["result"]["correct"])
            stats2=db.quiz_progress(mode,"basic")
            self.assertEqual(stats2["weaknesses"],stats)
            self.assertEqual(stats2["recent"]["attempts"],1)
            self.assertEqual(db.quiz_progress("one_shanten","basic")[
                "weaknesses"]["sample_wrong"],0)


if __name__=="__main__":
    unittest.main()
