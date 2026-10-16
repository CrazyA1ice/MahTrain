"""Regression for user screenshot: completed-looking hand containing dingque suit."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mahtrain_core.rules import diagnose_win,is_legal_win  # noqa: E402
from mahtrain_core import SoloTrainingSession  # noqa: E402


class WinDiagnosisTests(unittest.TestCase):
    def test_screenshot_like_hand_has_structure_but_cannot_hu_with_missing_wan(self):
        # 123万 + 66万 as pair; 123/456/789条; 14 physical cards.
        hand=["m1","m2","m3","m6","m6"] + [
            "s1","s2","s3","s4","s5","s6","s7","s8","s9"
        ]
        d=diagnose_win(hand,missing_suit="m")
        self.assertTrue(d["structural_win"])
        self.assertEqual(d["missing_suit_tile_count"],5)
        self.assertEqual(d["reason_code"],"missing_suit_not_cleared")
        self.assertFalse(d["legal_win"])
        self.assertFalse(is_legal_win(hand,missing_suit="m"))
        self.assertTrue(is_legal_win(hand,missing_suit="p"))

    def test_completion_without_declared_missing_suit_prompts(self):
        hand=["m1","m2","m3","m6","m6"]+["s1","s2","s3","s4","s5","s6","s7","s8","s9"]
        d=diagnose_win(hand,missing_suit="p")
        self.assertEqual(d["reason_code"],"legal_win")
        self.assertEqual(d["missing_suit_tile_count"],0)
        self.assertTrue(d["legal_win"])

    def test_incomplete_after_dingque_cleared(self):
        cards=["m1","m2","m4","m6","m6"]+["s1","s2","s3","s4","s5","s6","s7","s8","s9"]
        result=diagnose_win(cards,missing_suit="p")
        self.assertFalse(result["structural_win"])
        self.assertFalse(result["legal_win"])
        self.assertEqual(result["reason_code"],"incomplete_hand")

    def test_seven_pairs_detected_without_melds(self):
        cards=["m1","m1","m2","m2","m3","m3","m4","m4",
               "s1","s1","s2","s2","s3","s3"]
        result=diagnose_win(cards,missing_suit="p")
        self.assertTrue(result["structural_win"])
        self.assertTrue(result["legal_win"])

    def test_visible_session_status_never_reveals_future_wall(self):
        game=SoloTrainingSession(17,missing_suit="m")
        state=game.public_state()
        self.assertIn("win_status",state)
        self.assertEqual(
            state["win_status"]["missing_suit_tile_count"],
            sum(t.startswith("m") for t in state["hand"])
        )
        self.assertNotIn("wall",state)
        self.assertNotIn("best_actions",state)
        game.draw_next()
        state=game.public_state()
        self.assertEqual(
            state["win_status"]["legal_win"],
            state["phase"]=="offer_win"
        )


if __name__=="__main__":
    unittest.main()
