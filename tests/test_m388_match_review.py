"""M3.88: historical filter and terminal-only real-hand review contracts."""
from __future__ import annotations
import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT))
from mahtrain_core.four_player import FourPlayerOpening
from mahtrain_core.match_archive import MatchArchive, sanitize_private_review
import web_server


class HistoryReviewTests(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.archive=MatchArchive(Path(self.dir.name)/"history.sqlite3")
    def tearDown(self):
        self.dir.cleanup()
    def test_all_periods_validate_and_do_not_mislabel_truncated_trends(self):
        game=FourPlayerOpening(77)
        start=game.public_state()
        done={**start,"phase":"wall_exhausted"}
        for i in range(5):
            self.archive.save_completed(done,[],start,["basic"]*3)
        all_rows=self.archive.list_completed(period="all")
        self.assertEqual(all_rows["summary"]["games"],5)
        self.assertEqual(len(all_rows["scorecard"]["trend"]),5)
        self.assertEqual(self.archive.list_completed(period="week")["summary"]["games"],5)
        self.assertEqual(self.archive.list_completed(period="month")["summary"]["games"],5)
        self.assertEqual(self.archive.list_completed(period="year")["summary"]["games"],5)
        with sqlite3.connect(self.archive.path) as db:
            db.execute("UPDATE completed_matches SET created_at='2020-01-01T00:00:00+00:00' WHERE archive_id=?",
                       (all_rows["matches"][-1]["archive_id"],))
        self.assertEqual(self.archive.list_completed(period="week")["summary"]["games"],4)
        self.assertEqual(self.archive.list_completed(period="all")["summary"]["games"],5)
        self.assertEqual(len(self.archive.four_seat_scorecard(period="all")["trend"]),5)
        self.assertEqual(len(self.archive.four_seat_scorecard(period="year")["trend"]),4)
        for invalid in ("today","decade","",None,False,4):
            with self.assertRaises(ValueError):
                self.archive.list_completed(period=invalid)

    def test_terminality_and_exact_four_hand_history_is_never_live_payload(self):
        game=FourPlayerOpening(87)
        initial=game.public_state()
        reviewer={
            "opening":[list(x) for x in game._hands],
            "steps":[{
                "hands_before":[list(x) for x in game._hands],
                "hands_after":[list(x) for x in game._hands],
                "events":[{"type":"discard","seat":0,"tile":"p4"}],
            }]
        }
        snap={"phase":"finished",**initial}
        snap["phase"]="finished"
        with self.assertRaises(ValueError):
            self.archive.save_completed(initial,[],initial,["basic"]*3,
                                        private_review=reviewer)
        archive_id=self.archive.save_completed(
            snap,[],initial,["basic"]*3,private_review=reviewer)
        report=self.archive.detail(archive_id)["report"]
        self.assertEqual(report["version"],2)
        self.assertEqual(report["terminal_review"]["opening"],reviewer["opening"])
        self.assertEqual(report["terminal_review"]["steps"][0]["hands_after"],
                         reviewer["steps"][0]["hands_after"])
        self.assertNotIn("terminal_review",game.private_view(0))
        self.assertNotIn("terminal_review",game.public_state())
        self.assertNotIn("future_wall",json.dumps(report))
        self.assertNotIn("match_token",json.dumps(report))
        self.assertNotIn("seed",report)

    def test_legacy_archives_remain_public_only(self):
        game=FourPlayerOpening(87)
        start=game.public_state()
        done={**start,"phase":"finished"}
        archive_id=self.archive.save_completed(done,[],start,["basic"]*3)
        legacy=self.archive.detail(archive_id)["report"]
        self.assertEqual(legacy["version"],1)
        self.assertNotIn("terminal_review",legacy)

    def test_reject_fake_hands_and_invalid_alternatives(self):
        game=FourPlayerOpening(87)
        hands=[list(h) for h in game._hands]
        plain={"opening":hands,"steps":[]}
        self.assertEqual(sanitize_private_review(plain)["opening"],hands)
        for bad in (
            {"opening":[["not-tile"]]*4,"steps":[]},
            {"opening":hands,"steps":[{"hands_before":hands,"hands_after":hands,
                "events":[],"cut_review":{"seat":0,"discard":"m1",
                    "top3":[{"tile":"ILLEGAL"}]}}]},
            {"opening":hands,"steps":[{"hands_before":hands,"hands_after":hands,
                "events":[],"cut_review":{"seat":1,"discard":"m1","top3":[]}}]},
        ):
            with self.assertRaises(ValueError):
                sanitize_private_review(bad)


if __name__=="__main__":
    unittest.main()
