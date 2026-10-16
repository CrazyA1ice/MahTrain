"""Persistent SQLite completed-session histories and retry regression cases."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sys import path
path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core import SoloTrainingSession, analyze_discards  # noqa: E402
from mahtrain_core.history import HistoryStore  # noqa: E402


def completed_mistake(seed=17):
    game=SoloTrainingSession(seed,missing_suit="p",rounds=1)
    state=game.draw_next()
    while state["phase"] in ("offer_win","offer_kong"):
        state=(game.decide_win(False) if state["phase"]=="offer_win"
               else game.decide_kong(None))
    analysis=analyze_discards(state["hand"],missing_suit="p")
    if analysis["status"]=="already_winning":
        wrong=state["choices"][0]
    else:
        wrong=next(t for t in state["choices"]
                   if t not in analysis["best_discards"])
    feedback=game.submit(wrong)
    if feedback["correct"]:
        raise AssertionError("the fixture must choose a known wrong cut")
    return game


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db_path=Path(self.temp.name)/"sessions.sqlite3"
        self.store=HistoryStore(self.db_path)

    def tearDown(self):
        self.temp.cleanup()

    def test_only_finished_training_can_be_archived(self):
        game=SoloTrainingSession(17,missing_suit="p",rounds=1)
        with self.assertRaises(ValueError):
            self.store.save_finished(game)
        self.assertEqual(self.store.list_history()["sessions"],[])

    def test_unique_playthrough_ids_even_when_seed_is_repeated(self):
        one=completed_mistake()
        two=completed_mistake()
        self.assertEqual(one.session_id,two.session_id)
        first=self.store.save_finished(one)
        second=self.store.save_finished(two)
        self.assertNotEqual(first,second)
        self.assertEqual(len(self.store.list_history()["sessions"]),2)
        self.assertEqual(self.store.list_history()["summary"]["rounds_total"],2)

    def test_reopen_file_preserves_summary_report_and_retries(self):
        original=completed_mistake()
        before=json.dumps(original.report(),sort_keys=True)
        archive=self.store.save_finished(original)
        restarted=HistoryStore(self.db_path)
        listing=restarted.list_history()
        self.assertEqual(listing["summary"]["session_count"],1)
        self.assertEqual(listing["summary"]["mistake_total"],1)
        self.assertEqual(listing["summary"]["rounds_total"],1)
        self.assertEqual(listing["summary"]["correct_total"],0)
        self.assertEqual(listing["sessions"][0]["archive_id"],archive)
        detail=restarted.detail(archive)
        self.assertEqual(detail["report"],original.report())
        self.assertNotIn("seed",detail["report"])
        self.assertNotIn("wall",detail["report"])
        self.assertNotIn("_wall",detail["report"])
        q=restarted.retry_question(archive,1)
        self.assertNotIn("best_actions",q)
        self.assertNotIn("correct",q)
        self.assertNotIn("analysis",q)
        result=restarted.retry_submit(
            archive,1,original._history[0]["best_actions"][0]
        )
        self.assertTrue(result["result"]["correct"])
        self.assertTrue(result["result"]["improved"])
        restarted_again=HistoryStore(self.db_path)
        info=restarted_again.retry_list(archive)
        self.assertEqual(info["questions"][0]["attempt_count"],1)
        self.assertTrue(info["questions"][0]["latest_correct"])
        self.assertEqual(restarted_again.retry_question(archive,1)["attempt_number"],2)
        self.assertEqual(json.dumps(original.report(),sort_keys=True),before)
        self.assertEqual(restarted_again.detail(archive)["report"],original.report())

    def test_wrong_retry_and_invalid_id_dont_change_archive(self):
        original=completed_mistake()
        archive=self.store.save_finished(original)
        wrong=original._history[0]["choice"]
        result=self.store.retry_submit(archive,1,wrong)
        self.assertFalse(result["result"]["correct"])
        with self.assertRaises(ValueError):
            self.store.retry_submit(archive,1,"not-a-tile")
        with self.assertRaises(ValueError):
            self.store.retry_question(archive,2)
        with self.assertRaises(ValueError):
            self.store.detail("non-existent")
        self.assertEqual(self.store.retry_list(archive)["questions"][0]["attempt_count"],1)

    def test_delete_cascades_to_attempts(self):
        original=completed_mistake()
        archive=self.store.save_finished(original)
        self.store.retry_submit(archive,1,original._history[0]["choice"])
        self.store.delete_history(archive)
        self.assertEqual(self.store.list_history()["summary"]["session_count"],0)
        with self.assertRaises(ValueError):
            self.store.retry_question(archive,1)
        with self.assertRaises(ValueError):
            self.store.delete_history(archive)

    def test_limits_are_restricted(self):
        for bad in (None,0,-3,1001,True,"30"):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                self.store.list_history(bad)
        for archive in ("",None,"x"*101):
            with self.subTest(archive=archive),self.assertRaises(ValueError):
                self.store.detail(archive)


if __name__=="__main__":
    unittest.main()
