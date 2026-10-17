"""M3.22 completed public-match archive and strict SQLite privacy."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.four_player import FourPlayerOpening
from mahtrain_core.match_archive import MatchArchive, sanitize_board, sanitize_events
from mahtrain_core.settlement import WinLedger


class MatchArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Path(self.temp.name)/"local.sqlite3"
        self.store=MatchArchive(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self):
        game=FourPlayerOpening(17)
        before=game.public_state()
        finished={**before,"phase":"wall_exhausted",
                  "hand":["SECRET-SELF"],"future_wall":["SECRET-WALL"],
                  "drawn_tile":"SECRET-DRAW","match_token":"SECRET-TOKEN",
                  "seed":9876554321}
        return before,finished

    def test_finished_only_and_restart_persistence(self):
        before,finished=self.fixture()
        with self.assertRaisesRegex(ValueError,"completed"):
            self.store.save_completed(before,[],before,["basic"]*3)
        board={**before,
            "hand":["SECRET-HAND"],
            "melds":[[],[{"type":"an_gang","tile":"s9"}],[],[]],
            "discards":[{"seat":1,"tile":"p8","private":"SECRET-DISCARD"}]}
        steps=[{"events":[
            {"type":"draw","seat":1,"tile":"SECRET-DRAW"},
            {"type":"an_gang","seat":1,"tile":"s9"},
            {"type":"discard","seat":1,"tile":"p8","private":"SECRET-EVENT"},
        ],"board":board}]
        saved=self.store.save_completed(finished,steps,before,
                                        ["basic","advanced","challenge"])
        self.assertTrue(saved)
        restarted=MatchArchive(self.db)
        detail=restarted.detail(saved)
        report=detail["report"]
        self.assertEqual(report["privacy"],"public_board_only")
        self.assertEqual(report["steps"][0]["board"]["melds"][1][0]["tile"],None)
        self.assertEqual(report["steps"][0]["board"]["discards"][0]["tile"],"p8")
        self.assertEqual(report["steps"][0]["events"][0],{"type":"draw","seat":1})
        self.assertEqual(report["steps"][0]["events"][1],{"type":"an_gang","seat":1})
        self.assertEqual(report["steps"][0]["events"][2]["tile"],"p8")
        self.assertEqual(report["phase"],"wall_exhausted")
        self.assertEqual(len(restarted.list_completed()["matches"]),1)
        self.assertEqual(restarted.list_completed()["summary"]["games"],1)
        archive_bytes=self.db.read_bytes()
        for secret in (b"SECRET-SELF",b"SECRET-HAND",b"SECRET-WALL",
                       b"SECRET-DRAW",b"SECRET-TOKEN",b"SECRET-DISCARD",
                       b"SECRET-EVENT",b"9876554321"):
            self.assertNotIn(secret,archive_bytes)
        self.assertNotIn("seed",json.dumps(report))
        self.assertNotIn("future_wall",json.dumps(report))

    def test_bad_identifiers_and_bounded_list(self):
        for bad in ("", "x"*101, 42):
            with self.assertRaises(ValueError):
                self.store.detail(bad)
        with self.assertRaises(ValueError):
            self.store.detail("not-found")
        for bad in (0,101,1.5,True):
            with self.assertRaises(ValueError):
                self.store.list_completed(bad)

    def test_reject_malformed_board_and_hide_concealed_event(self):
        before,_=self.fixture()
        with self.assertRaises(ValueError):
            sanitize_board({**before,"hand_counts":[2]})
        with self.assertRaises(ValueError):
            sanitize_board({**before,"melds":[
                [{"type":"peng","tile":"SECRET"}],[],[],[]]})
        clean=sanitize_events([
            {"type":"kong_supplement","seat":2,"tile":"p9"},
            {"type":"an_gang","seat":1,"tile":"s4"},
            {"type":"win_settlement","seat":1,"amount":30,
             "effective_fan":2,"private":["m1"]}])
        self.assertNotIn("p9",json.dumps(clean))
        self.assertNotIn("s4",json.dumps(clean))
        self.assertNotIn("private",json.dumps(clean))
        self.assertEqual(clean[-1]["amount"],30)

    def test_real_win_ledger_is_archived_without_private_nested_fields(self):
        opening, finished = self.fixture()
        ledger = WinLedger(room_coefficient=100, fan_cap=3)
        score = {
            "legal": True, "main_pattern": "pure_seven_pairs",
            "raw_fan": 4, "effective_fan": 3, "multiplier": 8,
            "combinations": {"tian_ting": 2}, "bonuses": {"roots": 1},
        }
        ledger.pay_win(
            winner=0, payers=[1, 2, 3], source=0,
            kind="self_draw", tile="m1", score=score,
        )
        private = ledger.public_state()
        private["wins"][0]["combinations"]["private_future_tile"] = "SECRET-COMBINATION"
        private["wins"][0]["secret_private"] = {"wall": "SECRET-WALL"}
        private["wins"][0]["bonuses"] = {"roots": 1}
        private["other_private"] = {"wall": "SECRET-LEDGER"}
        completed = {**finished, "win_ledger": private}
        archive_id = self.store.save_completed(
            completed, [], opening, ["basic", "advanced", "challenge"]
        )
        report = self.store.detail(archive_id)["report"]
        self.assertEqual(report["win_ledger"]["balances"], [2400, -800, -800, -800])
        self.assertEqual(report["win_ledger"]["wins"][0]["payers"], [1, 2, 3])
        self.assertEqual(report["win_ledger"]["wins"][0]["bonuses"], {"roots": 1})
        serialized = json.dumps(report)
        for secret in ("SECRET-COMBINATION", "SECRET-WALL", "SECRET-LEDGER"):
            self.assertNotIn(secret, serialized)
            self.assertNotIn(secret.encode(), self.db.read_bytes())

    def test_reject_malformed_nested_payouts_before_writing_archive(self):
        opening, finished = self.fixture()
        ledger = WinLedger(room_coefficient=100, fan_cap=3)
        ledger.pay_win(
            winner=0, payers=[1, 2, 3], source=0, kind="self_draw",
            tile="m1",
            score={"legal": True, "main_pattern": "pure_seven_pairs",
                   "raw_fan": 4, "effective_fan": 3, "multiplier": 8,
                   "combinations": {}, "bonuses": {}},
        )
        good = ledger.public_state()
        import copy
        scenarios = []
        bad = copy.deepcopy(good)
        bad["wins"][0]["payers"][0] = {"private_tile": "SECRET-NESTED"}
        scenarios.append(bad)
        bad = copy.deepcopy(good)
        bad["wins"][0]["bonuses"] = {"roots": ["SECRET-ROOT"]}
        scenarios.append(bad)
        bad = copy.deepcopy(good)
        bad["wins"][0]["main_pattern"] = "SECRET-PATTERN"
        scenarios.append(bad)
        bad = copy.deepcopy(good)
        bad["wins"][0]["total_received"] += 1
        scenarios.append(bad)
        bad = copy.deepcopy(good)
        bad["balances"][0] += 1
        scenarios.append(bad)
        bad = copy.deepcopy(good)
        bad["wins"][0]["payers"] = [1, 1, 3]
        scenarios.append(bad)
        bad = copy.deepcopy(good)
        bad["zero_sum"] = False
        scenarios.append(bad)
        for candidate in scenarios:
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    self.store.save_completed(
                        {**finished, "win_ledger": candidate},
                        [], opening, ["basic", "advanced", "challenge"]
                    )
        for kong in (
            {"balances": [1, 0, 0, 0], "base": 100},
            {"balances": [True, 0, 0, 0], "base": None},
            {"balances": [0, 0, 0, 0], "base": True},
            {"balances": [0, 0, 0, 0], "base": -1},
        ):
            with self.subTest(kong=kong):
                with self.assertRaises(ValueError):
                    self.store.save_completed(
                        {**finished, "kong_ledger": kong},
                        [], opening, ["basic", "advanced", "challenge"]
                    )
        self.assertEqual(self.store.list_completed()["summary"]["games"], 0)
        assert_bytes = self.db.read_bytes()
        for private in (b"SECRET-NESTED", b"SECRET-ROOT", b"SECRET-PATTERN"):
            self.assertNotIn(private, assert_bytes)

    def test_does_not_change_legacy_history_schema_version(self):
        from mahtrain_core.history import HistoryStore
        old=HistoryStore(self.db)
        with sqlite3.connect(self.db) as db:
            before=db.execute("PRAGMA user_version").fetchone()[0]
        archive=MatchArchive(self.db)
        with sqlite3.connect(self.db) as db:
            after=db.execute("PRAGMA user_version").fetchone()[0]
            tables={r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(before,after)
        self.assertIn("completed_matches",tables)
        self.assertIn("local_history",tables)
        self.assertEqual(archive.list_completed()["summary"]["games"],0)


if __name__=="__main__":
    unittest.main()
