"""M2.7 SQLite quiz scoring, v1 migration, no-answer leak and level advice."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mahtrain_core.history import HistoryStore
from mahtrain_core.training import generate_question, grade_answer


def sample(difficulty="basic"):
    mode="pure_suit_discard"
    q=generate_question(mode,1,difficulty=difficulty)
    wrong=grade_answer(mode,1,"win",difficulty=difficulty,
                       question_id=q["question_id"])
    assert not wrong["correct"]
    correct=grade_answer(mode,1,wrong["best_actions"][0],
                         difficulty=difficulty,question_id=q["question_id"])
    assert correct["correct"]
    return q, wrong, correct


class QuizProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.file=Path(self.temp.name)/"legacy.sqlite3"
        self.store=HistoryStore(self.file)

    def tearDown(self):
        self.temp.cleanup()

    def test_successful_results_persist_through_reopen_and_retries(self):
        q,wrong,right=sample()
        archive=self.store.save_quiz_answer(q,wrong,"win")
        self.assertNotIn("seed",self.store.quiz_detail(archive)["question"])
        self.assertNotIn("token",self.store.quiz_detail(archive)["question"])
        self.assertEqual(self.store.quiz_detail(archive)["selection"],"win")
        self.assertFalse(self.store.quiz_detail(archive)["correct"])
        second=HistoryStore(self.file)
        original=second.quiz_detail(archive)
        self.assertEqual(original["result"],wrong)
        retry_question=second.quiz_retry_question(archive)["question"]
        self.assertNotIn("best_actions",retry_question)
        self.assertNotIn("correct_tiles",retry_question)
        with self.assertRaises(ValueError):
            second.quiz_retry_submit(archive,"fake99")
        self.assertEqual(second.quiz_retry_status(archive)["attempts"],0)
        bad=second.quiz_retry_submit(archive,"win")
        self.assertFalse(bad["result"]["correct"])
        good=second.quiz_retry_submit(archive,right["best_actions"][0])
        self.assertTrue(good["result"]["correct"])
        third=HistoryStore(self.file)
        self.assertEqual(third.quiz_retry_status(archive)["attempts"],2)
        self.assertTrue(third.quiz_retry_status(archive)["latest_correct"])
        self.assertEqual(third.quiz_detail(archive)["result"],wrong)
        result=third.quiz_progress(q["mode"],q["difficulty"])
        self.assertEqual(result["level_totals"]["basic"]["total"],1)
        self.assertEqual(result["level_totals"]["basic"]["correct"],0)
        self.assertEqual(result["recent"]["attempts"],1)
        self.assertEqual(result["recommendation"]["decision"],"insufficient")
        third.delete_quiz_attempt(archive)
        with self.assertRaises(ValueError):
            third.quiz_retry_status(archive)
        self.assertEqual(third.quiz_progress(q["mode"],q["difficulty"])["recent"]["attempts"],0)

    def test_recommendation_uses_same_mode_and_same_level(self):
        q,wrong,right=sample("basic")
        for _ in range(4):
            self.store.save_quiz_answer(q,right,right["best_actions"][0])
        p=self.store.quiz_progress(q["mode"],"basic")
        self.assertEqual(p["recommendation"]["decision"],"insufficient")
        self.store.save_quiz_answer(q,right,right["best_actions"][0])
        p=self.store.quiz_progress(q["mode"],"basic")
        self.assertEqual(p["recent"]["attempts"],5)
        self.assertEqual(p["recommendation"]["level"],"intermediate")
        self.assertEqual(p["recommendation"]["decision"],"promote")
        q_c,w_c,r_c=sample("challenge")
        for _ in range(5):
            self.store.save_quiz_answer(q_c,w_c,"win")
        down=self.store.quiz_progress(q["mode"],"challenge")
        self.assertEqual(down["recommendation"]["decision"],"demote")
        self.assertEqual(down["recommendation"]["level"],"intermediate")
        self.assertEqual(self.store.quiz_progress(q["mode"],"basic")["recent"]["correct"],5)
        empty=self.store.quiz_progress("tenpai_discard","basic")
        self.assertEqual(empty["recent"]["attempts"],0)
        self.assertEqual(empty["level_totals"]["challenge"]["total"],0)
        middle_q,middle_wrong,middle_right=sample("intermediate")
        for _ in range(3):
            self.store.save_quiz_answer(middle_q,middle_right,middle_right["best_actions"][0])
        for _ in range(2):
            self.store.save_quiz_answer(middle_q,middle_wrong,"win")
        steady=self.store.quiz_progress(q["mode"],"intermediate")
        self.assertEqual(steady["recent"]["accuracy"],.6)
        self.assertEqual(steady["recommendation"]["decision"],"hold")
        self.assertEqual(steady["recommendation"]["level"],"intermediate")

    def test_invalid_input_does_not_write(self):
        q,wrong,right=sample()
        for invalid in ("win","p100",None):
            # "win" is valid for pure_suit_discard but valid+wrong is storable.
            if invalid=="win":
                continue
            with self.assertRaises(ValueError):
                self.store.save_quiz_answer(q,right,invalid)
        forged={**q,"seed":77}
        with self.assertRaises(ValueError):
            self.store.save_quiz_answer(forged,wrong,"win")
        with self.assertRaises(ValueError):
            self.store.save_quiz_answer(q,{**wrong,"question_id":"different"},"win")
        for level in ("hard",None,""):
            with self.assertRaises(ValueError):
                self.store.quiz_progress(q["mode"],level)
        for limit in (0,101,True,None):
            with self.assertRaises(ValueError):
                self.store.quiz_progress(q["mode"],"basic",limit=limit)
        self.assertEqual(self.store.quiz_progress(q["mode"],"basic")["recent"]["attempts"],0)

    def test_v1_archive_migrates_without_deleting_solo_data(self):
        other=Path(self.temp.name)/"old.sqlite3"
        with sqlite3.connect(other) as db:
            db.execute("""CREATE TABLE local_history(
                archive_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                session_id TEXT NOT NULL,missing_suit TEXT NOT NULL,
                completed_rounds INTEGER NOT NULL,correct_rounds INTEGER NOT NULL,
                mistake_count INTEGER NOT NULL,accuracy REAL NOT NULL,
                report_json TEXT NOT NULL
            )""")
            db.execute("""INSERT INTO local_history
                VALUES('old','2026-10-16','sid','p',14,10,4,.714,'{}')""")
            db.execute("PRAGMA user_version=1")
        migrated=HistoryStore(other)
        self.assertEqual(migrated.list_history()["summary"]["session_count"],1)
        with sqlite3.connect(other) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0],2)
        q,wrong,right=sample()
        id=migrated.save_quiz_answer(q,wrong,"win")
        self.assertEqual(migrated.quiz_progress(q["mode"],"basic")["recent"]["attempts"],1)
        self.assertEqual(HistoryStore(other).list_history()["sessions"][0]["archive_id"],"old")
        self.assertEqual(HistoryStore(other).quiz_detail(id)["question"],q)

    def test_correct_question_not_eligible_for_retry(self):
        q,wrong,right=sample()
        key=self.store.save_quiz_answer(q,right,right["best_actions"][0])
        with self.assertRaises(ValueError):
            self.store.quiz_retry_question(key)
        with self.assertRaises(ValueError):
            self.store.quiz_retry_submit(key,right["best_actions"][0])


if __name__=="__main__":
    unittest.main()
