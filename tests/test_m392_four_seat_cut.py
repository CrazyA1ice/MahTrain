"""M3.92 four-seat cut reference, seat isolation, and terminal-only storage."""
from __future__ import annotations

from copy import deepcopy
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]

from mahtrain_core.classic_hint import (
    classic_hand_hint, classic_archive_seat_hint,
)
from mahtrain_core.four_player import FourPlayerOpening
from mahtrain_core.match_archive import sanitize_private_review
from test_four_player_claims import staged_game
import web_server


HAND=["m1","m2","m4","m6","m8",
      "p1","p2","p4","p6","p8",
      "s1","s3","s5","s8"]


def turn_game(seat: int):
    seed=next(i for i in range(100) if FourPlayerOpening(i).dealer==seat)
    return staged_game({seat:list(HAND)},{seat:"p"},seed=seed)


class FourSeatTerminalCutTests(unittest.TestCase):

    def test_private_ai_view_is_not_available_to_live_hint(self):
        for seat in (1,2,3):
            game=turn_game(seat)
            private=game.private_view(seat)
            with self.subTest(seat=seat):
                with self.assertRaises(ValueError):
                    classic_hand_hint(private)
                report=classic_archive_seat_hint(private,seat)
                self.assertTrue(report["candidates"])
                with self.assertRaises(ValueError):
                    classic_archive_seat_hint(private,(seat+1)%4)
                with self.assertRaises(ValueError):
                    classic_archive_seat_hint(private,True)

    def test_advice_does_not_use_other_hands_or_hidden_wall(self):
        game=turn_game(2)
        view=game.private_view(2)
        first=classic_archive_seat_hint(view,2)
        changed=deepcopy(view)
        changed["wall"]=["m9"]*40
        changed["opponent_private_hands"]=[["m9"]*14]*3
        self.assertEqual(first,classic_archive_seat_hint(changed,2))

    def test_each_seat_records_exact_contemporaneous_ranking(self):
        for seat in range(4):
            with self.subTest(seat=seat):
                game=turn_game(seat)
                game._terminal_review_trace=[]
                old=game.private_view(seat)
                expected=classic_archive_seat_hint(old,seat)
                chosen=expected["candidates"][-1]
                steps=[]
                web_server._match_record(
                    game,steps,lambda:game.discard(seat,chosen["discard"]))
                self.assertEqual(len(game._terminal_review_trace),1)
                entry=game._terminal_review_trace[0]
                recorded=entry["cut_review"]
                self.assertEqual(recorded["seat"],seat)
                self.assertEqual(recorded["discard"],chosen["discard"])
                self.assertEqual(recorded["played_candidate"]["shanten"],
                                 chosen["shanten"])
                self.assertEqual(
                    recorded["played_candidate"]["effective_copies"],
                    chosen["effective_tile_count_upper_bound"])
                self.assertEqual(
                    recorded["played_candidate"]["fan_weighted"],
                    chosen["fan_weighted_unknown_copies"])
                self.assertEqual(recorded["top3"][0]["tile"],
                                 expected["candidates"][0]["discard"])
                self.assertEqual(recorded["optimal"],chosen["reference_best"])
                self.assertEqual(entry["hands_before"][seat],list(HAND))
                self.assertEqual(game.debug_tile_counts()["total"],108)
                sanitized=sanitize_private_review({
                    "opening":entry["hands_before"],
                    "steps":[entry],
                })
                self.assertEqual(
                    sanitized["steps"][0]["cut_review"]["seat"],seat)
                self.assertNotIn("terminal_review",game.public_state())
                self.assertNotIn("terminal_review",game.private_view(0))
                self.assertNotIn("cut_review",str(steps),
                    "public steps must contain no private review fields")
                self.assertNotIn("opponent_private_hands",str(sanitized))

    def test_reject_other_seats_tiles_and_invalid_seat(self):
        game=turn_game(2)
        game._terminal_review_trace=[]
        chosen=classic_archive_seat_hint(game.private_view(2),2)[
            "candidates"][0]["discard"]
        web_server._match_record(
            game,[],lambda:game.discard(2,chosen))
        snap=game._terminal_review_trace[0]
        assert snap["cut_review"]["seat"]==2
        other_tile=next(t for h in (snap["hands_before"][0],
                      snap["hands_before"][1],snap["hands_before"][3])
                        for t in h if t not in snap["hands_before"][2])
        for corrupt in (
            {**snap["cut_review"],"seat":4},
            {**snap["cut_review"],"seat":True},
            {**snap["cut_review"],"discard":other_tile},
            {**snap["cut_review"],"top3":[{
                **snap["cut_review"]["top3"][0],"tile":other_tile}]},
        ):
            with self.subTest(corrupt=corrupt),self.assertRaises(ValueError):
                sanitize_private_review({
                    "opening":snap["hands_before"],
                    "steps":[{**snap,"cut_review":corrupt}],
                })

    def test_pre_m392_human_only_archive_remains_seat_zero(self):
        game=turn_game(0)
        game._terminal_review_trace=[]
        chosen=classic_hand_hint(game.private_view(0))["candidates"][0]["discard"]
        web_server._match_record(game,[],lambda:game.discard(0,chosen))
        snap=game._terminal_review_trace[0]
        legacy={**snap["cut_review"]}
        del legacy["seat"]
        saved=sanitize_private_review({
            "opening":snap["hands_before"],
            "steps":[{**snap,"cut_review":legacy}],
        })
        self.assertEqual(saved["steps"][0]["cut_review"]["seat"],0)


if __name__=="__main__":
    unittest.main()
