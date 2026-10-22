"""M3.88 all local score dashboards use the SAME UTC rolling windows."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.history import HistoryStore

class HistoryPeriodCoverage(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=HistoryStore(Path(self.tmp.name)/"history.sqlite")
        now=datetime.now(timezone.utc)
        with self.store._connect() as db:
            for i,days in enumerate((500,20,2)):
                date=(now-timedelta(days=days)).isoformat(timespec="seconds")
                db.execute("""
                  INSERT INTO local_history(archive_id,created_at,session_id,
                    missing_suit,completed_rounds,correct_rounds,mistake_count,
                    accuracy,report_json)
                  VALUES(?,?,?,?,?,?,?,?,?)""",
                    ("hist-"+str(i),date,"session-"+str(i),"m",14,
                     4+i,10-i,(4+i)/14,json.dumps({})))
                db.execute("""
                  INSERT INTO quiz_attempts(answer_id,created_at,mode,
                    difficulty,question_id,rule_version,correct,family,
                    question_json,selection_json,result_json)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    ("quiz-"+str(i),date,"one_shanten","basic",
                     "question-"+str(i),"local",int(i>0),"",
                     "{}","\"m1\"","{}"))

    def tearDown(self):self.tmp.cleanup()

    def test_training_full_history_and_three_windows(self):
        for p,n in (("all",3),("year",2),("month",2),("week",1)):
            with self.subTest(period=p):
                result=self.store.list_history(1,period=p)
                self.assertEqual(result["summary"]["session_count"],n)
                self.assertEqual(result["summary"]["rounds_total"],14*n)
                self.assertEqual(len(result["trend"]),n)
                self.assertEqual(len(result["sessions"]),1)
                self.assertEqual(result["has_more"],n>1)
        last=self.store.list_history(1,period="all",offset=2)
        self.assertFalse(last["has_more"])
        with self.assertRaises(ValueError):self.store.list_history(1,period="invalid")
        with self.assertRaises(ValueError):self.store.list_history(1,offset=-1)

    def test_all_quiz_stats_history_and_page_use_same_period(self):
        for p,n in (("all",3),("year",2),("month",2),("week",1)):
            with self.subTest(period=p):
                result=self.store.quiz_progress("one_shanten","basic",limit=1,
                                                period=p)
                self.assertEqual(result["level_totals"]["basic"]["total"],n)
                self.assertEqual(len(result["trend"]),n)
                self.assertEqual(result["total_attempts"],n)
                self.assertEqual(len(result["attempts"]),1)
                self.assertEqual(result["has_more"],n>1)
                self.assertEqual(result["recent"]["attempts"],n)
        page=self.store.quiz_progress("one_shanten","basic",limit=1,offset=2)
        self.assertFalse(page["has_more"])
        with self.assertRaises(ValueError):
            self.store.quiz_progress("one_shanten","basic",period="invalid")

if __name__=="__main__":unittest.main()
