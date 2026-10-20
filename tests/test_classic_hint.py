"""Read-only classic shanten hints: legal dingque, public visibility, security."""
from __future__ import annotations
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT))
from mahtrain_core.classic_hint import classic_hand_hint  # noqa: E402
import web_server  # noqa: E402

READY="m1 m1 m1 m4 m4 m4 p1 p1 p1 p4 p4 p4 m9".split()


def view(hand=None,missing="s"):
    h=list(hand if hand is not None else [*READY,"p9"])
    return {"seat":0,"phase":"await_discard","turn":0,
            "hand":h,"own_melds":[],"missing_suits":[missing,"p","m","p"],
            "discards":[],"melds":[[],[],[],[]],"wall_count":42}


class ClassicHintTests(unittest.TestCase):
    def test_tenpai_candidates_use_actual_shanten_and_remaining_public_unknown(self):
        state=view()
        before=deepcopy(state)
        hint=classic_hand_hint(state)
        self.assertEqual(hint["status"],"choose_discard")
        self.assertEqual(hint["interpretation"],"structural_only")
        rows={c["discard"]:c for c in hint["candidates"]}
        self.assertEqual(rows["p9"]["shanten"],0)
        self.assertEqual(rows["p9"]["effective_details"],
                         [{"tile":"m9","unknown_copies_upper_bound":3}])
        self.assertEqual(rows["p9"]["effective_tile_count_upper_bound"],3)
        self.assertEqual(state,before,"reference must not mutate the match")

    def test_public_discard_reduces_upper_bound_but_no_wall_or_ai_hand_access(self):
        state=view()
        state["discards"]=[{"seat":1,"tile":"m9"}]
        state["wall"]=["m9"]*27
        state["opponent_private_hands"]=[["m9"]*13]
        got=classic_hand_hint(state)
        row=next(c for c in got["candidates"] if c["discard"]=="p9")
        self.assertEqual(row["effective_details"],
                         [{"tile":"m9","unknown_copies_upper_bound":2}])
        altered=deepcopy(state)
        altered["wall"]=["p1"]*27
        altered["opponent_private_hands"]=[["p1"]*13]
        self.assertEqual(got,classic_hand_hint(altered),
            "hidden wall/other player hands never enter reference analysis")
        self.assertNotIn("wall",str(got).lower())
        self.assertNotIn("opponent",str(got).lower())

    def test_missing_suit_must_be_cut_first(self):
        h=classic_hand_hint(view([*READY,"s1"]))
        self.assertTrue(h["forced_missing"])
        self.assertEqual([x["discard"] for x in h["candidates"]],["s1"])
        self.assertEqual(h["candidates"][0]["shanten"],0)

    def test_no_availability_during_other_players_turn_or_pre_dingque(self):
        for change in ({"turn":1},{"phase":"claim_window"},
                       {"missing_suits":None},{"seat":2}):
            with self.subTest(change=change):
                v=view()
                v.update(change)
                with self.assertRaises(ValueError):
                    classic_hand_hint(v)

    def test_completed_hand_advises_server_hu_instead_of_inventing_discard(self):
        out=classic_hand_hint(view([*READY,"m9"]))
        self.assertEqual(out["status"],"already_winning")
        self.assertEqual(out["candidates"],[])

    def test_match_hint_authorization_does_not_advance_game_or_rng(self):
        state=view()
        class FakeGame:
            def __init__(self):self.calls=0
            def private_view(self,seat):
                self.calls+=1
                self.last_seat=seat
                return deepcopy(state)
        game=FakeGame()
        with patch.dict(web_server._MATCH_SESSIONS,{"hint-token":game}), \
             patch.dict(web_server._MATCH_AGENTS,{"hint-token":{1:object()} }):
            result=web_server._process("match_hint",{"match_token":"hint-token"})
            self.assertEqual(result["match_token"],"hint-token")
            self.assertEqual(result["hint"]["status"],"choose_discard")
            self.assertEqual(game.last_seat,0)
            self.assertEqual(game.calls,1)
            self.assertNotIn("match",result,"no game state or private wall returned")
            self.assertNotIn("match_token",result["hint"])
            with self.assertRaises(ValueError):
                web_server._process("match_hint",{"match_token":"wrong"})
        self.assertNotIn("hint-token",web_server._MATCH_SESSIONS)

if __name__=="__main__":
    unittest.main()
