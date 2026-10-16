"""M2.9 authentic completed-round error diagnosis and historical reports."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.review import (  # noqa: E402
    build_round_review, diagnose_solo_round, summarize_solo_errors,
)
from mahtrain_core import SoloTrainingSession  # noqa: E402
from mahtrain_core.history import HistoryStore  # noqa: E402


def example(round_no, *, correct=False, choice="m1", best=None,
            shanten_loss=None, ukeire_loss=None, status="choose_discard"):
    best=best or ["m2"]
    chosen={"discard":choice,"shanten":1,
            "effective_tile_count":4,"next_draw_probability":.04}
    return {
        "round":round_no,"choice":choice,"correct":correct,
        "drawn_tile":"s1","hand_before":["m1"]*14,
        "best_actions":best,"selected_candidate":chosen,
        "analysis":{"status":status,"minimum_shanten":1,
                    "candidates":[{"discard":"m2","shanten":1,
                                   "effective_tile_count":8,
                                   "next_draw_probability":.08}]},
        "shanten_loss":shanten_loss,"ukeire_loss":ukeire_loss,
        "explanation":"historical completed turn",
    }


class SoloErrorReviewTests(unittest.TestCase):
    def test_precedence_missed_win_vs_ordinary_discard_losses(self):
        row=example(1,best=["win"],shanten_loss=2,ukeire_loss=9)
        self.assertEqual(diagnose_solo_round(row),["missed_win"])
        row["correct"]=True
        self.assertEqual(diagnose_solo_round(row),[])
        self.assertEqual(diagnose_solo_round({
            **row,"choice":"win","selected_candidate":None
        }),[])

    def test_shanten_beats_ukeire_and_same_level_is_distinct(self):
        row=example(1,shanten_loss=1,ukeire_loss=9)
        self.assertEqual(diagnose_solo_round(row),["shanten_regression"])
        self.assertEqual(diagnose_solo_round(example(1,ukeire_loss=4)),
                         ["ukeire_loss"])
        # Backfill old history that lacks loss summary but has old ranking.
        row=example(1,ukeire_loss=None)
        self.assertEqual(diagnose_solo_round(row),["ukeire_loss"])
        row["selected_candidate"]["shanten"]=2
        self.assertEqual(diagnose_solo_round(row),["shanten_regression"])
        row["analysis"]["candidates"][0]["effective_tile_count"]=4
        row["selected_candidate"]["shanten"]=1
        self.assertEqual(diagnose_solo_round(row),["other_error"])

    def test_summary_counts_rounds_and_maps_supported_drills(self):
        rows=[
            example(1,best=["win"]),
            example(2,shanten_loss=2),
            example(3,ukeire_loss=4),
            example(4,correct=True,choice="win",best=["win"]),
            example(5,ukeire_loss=2),
            {**example(6), "analysis":{"status":"choose_discard",
                "candidates":[],"minimum_shanten":None},
                "selected_candidate":None},
        ]
        review=build_round_review(rows)
        err=review["errors"]
        self.assertEqual(err["error_rounds"],5)
        self.assertEqual(err["correct_rounds"],1)
        self.assertEqual(err["counts"]["missed_win"]["rounds"],[1])
        self.assertEqual(err["counts"]["shanten_regression"]["count"],1)
        self.assertEqual(err["counts"]["ukeire_loss"]["rounds"],[3,5])
        self.assertEqual(err["counts"]["other_error"]["count"],1)
        self.assertEqual(err["primary_error"],"ukeire_loss")
        self.assertEqual(err["recommendations"][0]["mode"],"tenpai_discard")
        self.assertEqual(err["recommendations"][0]["focus"],"ukeire_loss")
        self.assertTrue(all(
            row["error_types"]==[] if row["correct"] else bool(row["error_types"])
            for row in review["rounds"]
        ))

    def test_correct_only_has_no_weakness_or_fictitious_drills(self):
        row=example(1,correct=True,choice="win",best=["win"])
        error=summarize_solo_errors([
            {"round":1,"correct":True,"error_types":[]}
        ])
        self.assertIsNone(error["primary_error"])
        self.assertEqual(error["error_rounds"],0)
        self.assertEqual(error["recommendations"],[])
        self.assertEqual(build_round_review([row])["rounds"][0]["error_types"],[])

    def test_completed_rounds_only_and_legacy_sqlite_read_backfill(self):
        game=SoloTrainingSession(17,missing_suit="p",rounds=1)
        state=game.draw_next()
        self.assertEqual(game.report()["error_summary"]["error_rounds"],0)
        self.assertEqual(game.report()["round_review"],[])
        while state["phase"] in ("offer_win","offer_kong"):
            state=(game.decide_win(False) if state["phase"]=="offer_win"
                   else game.decide_kong(None))
        feedback=game.submit(state["choices"][0])
        report=game.report()
        self.assertTrue(report["finished"])
        self.assertEqual(report["completed_rounds"],1)
        self.assertEqual(report["round_review"][0]["error_types"],
                         diagnose_solo_round(feedback))
        self.assertEqual(report["error_summary"]["error_rounds"],
                         int(not feedback["correct"]))
        with tempfile.TemporaryDirectory() as folder:
            db=HistoryStore(Path(folder)/"history.sqlite3")
            archive=db.save_finished(game)
            old_report=json.loads(json.dumps(report))
            del old_report["error_summary"]
            for round_data in old_report["round_review"]:
                round_data.pop("error_types")
                round_data.pop("error_labels")
            # Emulate a pre-M2.9 completed report in an existing SQLite file.
            with db._connect() as connection:
                connection.execute(
                    "UPDATE local_history SET report_json=? WHERE archive_id=?",
                    (json.dumps(old_report),archive),
                )
            stored=db.detail(archive)["report"]
            self.assertEqual(stored["error_summary"],report["error_summary"])
            self.assertEqual(stored["round_review"][0]["error_types"],
                             report["round_review"][0]["error_types"])
            self.assertEqual(stored["accuracy"],old_report["accuracy"])
            with db._connect() as connection:
                kept=json.loads(connection.execute(
                    "SELECT report_json FROM local_history WHERE archive_id=?",
                    (archive,),
                ).fetchone()[0])
            self.assertNotIn("error_summary",kept,
                             "legacy scores must be enriched read-only")
            self.assertNotIn("wall",stored)
            self.assertNotIn("future_wall",stored)


if __name__=="__main__":
    unittest.main()
