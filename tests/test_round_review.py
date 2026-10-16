"""Completed-round efficiency review: no future-wall data and correct deltas."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core import SoloTrainingSession  # noqa: E402
from mahtrain_core.review import build_round_review  # noqa: E402


def discard(round_no,chosen,eff,prob,shanten,best=("m1",),
            selected_good=True,shanten_loss=0,ukeire_loss=0):
    return {
        "round":round_no,
        "drawn_tile":"s5",
        "choice":chosen,
        "correct":selected_good,
        "best_actions":list(best),
        "hand_before":["m1"]*13+["s5"],
        "selected_candidate":{
            "discard":chosen,"shanten":shanten,"effective_tile_count":eff,
            "next_draw_probability":prob,"effective_details":[{"tile":"p3","remaining":eff}],
        },
        "analysis":{
            "status":"choose_discard",
            "candidates":[
                {"discard":best[0],"shanten":shanten-(shanten_loss or 0),
                 "effective_tile_count":eff+ukeire_loss,
                 "next_draw_probability":prob+.01}
            ],
        },
        "shanten_loss":shanten_loss,"ukeire_loss":ukeire_loss,
        "explanation":"判题说明",
    }


class ReviewTests(unittest.TestCase):
    def test_empty_review_is_explicitly_empty(self):
        result=build_round_review([])
        self.assertEqual(result["rounds"],[])
        self.assertEqual(result["progress"]["discard_rounds"],0)
        self.assertIsNone(result["progress"]["shanten_change"])

    def test_round_changes_compare_previous_completed_discard(self):
        h=[
            discard(1,"m1",4,.04,2),
            discard(2,"m2",8,.08,1,best=("m1",),selected_good=False,shanten_loss=0,ukeire_loss=3),
            discard(3,"m1",6,.06,1),
        ]
        got=build_round_review(h)
        self.assertEqual(len(got["rounds"]),3)
        self.assertIsNone(got["rounds"][0]["change_from_previous_discard"])
        self.assertEqual(got["rounds"][1]["change_from_previous_discard"]["shanten"],-1)
        self.assertEqual(got["rounds"][1]["change_from_previous_discard"]["effective_tile_count"],4)
        self.assertAlmostEqual(got["rounds"][1]["change_from_previous_discard"]["next_draw_probability"],.04)
        summary=got["progress"]
        self.assertEqual(summary["shanten_change"],-1)
        self.assertEqual(summary["effective_tile_count_change"],2)
        self.assertEqual(summary["shanten_improved_rounds"],1)
        self.assertEqual(summary["shanten_unchanged_rounds"],1)
        self.assertEqual(summary["shanten_worsened_rounds"],0)
        self.assertEqual(summary["missed_ukeire_total_at_same_shanten"],3)
        self.assertEqual(summary["discard_rounds"],3)

    def test_win_is_a_separate_turn_not_zero_shanten_discard(self):
        h=[discard(1,"m1",5,.05,0),{
            "round":2,"drawn_tile":"p9","choice":"win","correct":True,
            "best_actions":["win"],"selected_candidate":None,
            "win_type":"self_draw","explanation":"胡牌","hand_before":["m1"]*14,
            "analysis":{"status":"already_winning","candidates":[]},
        }]
        got=build_round_review(h)
        self.assertEqual(got["progress"]["discard_rounds"],1)
        self.assertEqual(got["progress"]["win_rounds"],1)
        self.assertIsNone(got["rounds"][1]["shanten"])
        self.assertIsNone(got["rounds"][1]["next_draw_probability"])
        self.assertEqual(got["rounds"][1]["best_actions"],["win"])
        self.assertEqual(got["progress"]["shanten_change"],0)

    def test_ignored_win_is_counted_without_breaking_trend(self):
        h=[discard(1,"m1",4,.04,1),discard(2,"m9",7,.07,0,best=("win",),selected_good=False,
                                         shanten_loss=None,ukeire_loss=None)]
        review=build_round_review(h)
        self.assertEqual(review["progress"]["missed_win_rounds"],1)
        self.assertEqual(review["progress"]["shanten_improved_rounds"],1)

    def test_live_session_report_includes_only_finished_turns(self):
        game=SoloTrainingSession(17,rounds=2)
        self.assertEqual(game.report()["round_review"],[])
        state=game.draw_next()
        self.assertEqual(game.report()["round_review"],[])
        while state["phase"] in ("offer_win","offer_kong"):
            state=(game.decide_win(False) if state["phase"]=="offer_win"
                   else game.decide_kong(None))
        feedback=game.submit(state["choices"][0])
        report=game.report()
        self.assertEqual(len(report["round_review"]),1)
        first=report["round_review"][0]
        self.assertEqual(first["choice"],feedback["choice"])
        self.assertEqual(first["shanten"],feedback["selected_candidate"]["shanten"])
        self.assertEqual(first["effective_tile_count"],
                         feedback["selected_candidate"]["effective_tile_count"])
        self.assertNotIn("wall",report)
        self.assertNotIn("future_wall",report)
        self.assertFalse(report["finished"])


if __name__=="__main__":
    unittest.main()
