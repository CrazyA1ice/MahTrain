"""M3.96: operation-window advisor and terminal privacy regression."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]

from mahtrain_core.ai import MahjongAgent
from mahtrain_core.classic_operation_hint import (
    classic_operation_hint, classic_live_operation_hint,
)
from mahtrain_core.match_archive import sanitize_private_review
from test_ai_calls import offer_peng, offer_kongs
from test_four_player_claims import staged_game
import web_server


class M396OperationHintTests(unittest.TestCase):
    def test_actual_peng_opportunity_ranks_all_authorized_actions_without_mutation(self):
        game,seat,view=offer_peng()
        before=copy.deepcopy(view)
        report=classic_operation_hint(view,seat)
        self.assertEqual(view,before)
        self.assertEqual(report["status"],"choose_operation")
        self.assertEqual(report["seat"],seat)
        candidates=report["candidates"]
        self.assertEqual(sum(x["reference_best"] for x in candidates),1)
        self.assertEqual({x["action"] for x in candidates},set(view["claim_options"]))
        self.assertEqual(report["recommended"]["action"],
                         next(c["action"] for c in candidates if c["reference_best"]))
        self.assertTrue(all(x["effective_copies"] is None or
                            x["effective_copies"]>=0 for x in candidates))
        self.assertEqual(game.debug_tile_counts()["total"],108)
        self.assertNotIn("opponent_hands",str(report))
        self.assertNotIn("future_wall",str(report))
        self.assertNotIn("hand",str(report))
        injected=copy.deepcopy(view)
        injected["opponent_hands"]=[["s9"]*13]*3
        injected["future_wall"]=["m1"]*50
        self.assertEqual(report,classic_operation_hint(injected,seat))
        if seat!=0:
            with self.assertRaises(ValueError):
                classic_live_operation_hint(view)

    def test_real_two_kong_offer_includes_decline_and_each_own_kong(self):
        game,seat,view=offer_kongs()
        before=copy.deepcopy(view)
        report=classic_operation_hint(view,seat)
        self.assertEqual(view,before)
        names={(x["action"],x["tile"]) for x in report["candidates"]}
        self.assertIn(("pass",None),names)
        for k in view["kong_options"]:
            self.assertIn((k["type"],k["tile"]),names)
        self.assertEqual(sum(row["reference_best"] for row in report["candidates"]),1)
        self.assertEqual(game.debug_tile_counts()["total"],108)
        self.assertEqual({x["tile"] for x in report["candidates"] if x["tile"]},
                         {k["tile"] for k in view["kong_options"]})

    def test_hu_priority_rob_and_own_self_win_cannot_be_omitted(self):
        _,seat,view=offer_peng()
        hu=copy.deepcopy(view)
        hu["claim_options"]=["pass","hu","peng"]
        response=classic_operation_hint(hu,seat)
        self.assertEqual(response["recommended"],{"action":"hu","tile":None})
        self.assertEqual(sum(x["reference_best"] for x in response["candidates"]),1)
        rob=copy.deepcopy(view)
        rob["phase"]="rob_kong_window"
        rob["pending_rob_kong"]={"seat":view["pending_discard"]["seat"],
                                 "tile":view["pending_discard"]["tile"]}
        rob["rob_options"]=["pass","hu"]
        response=classic_operation_hint(rob,seat)
        self.assertEqual(response["recommended"],{"action":"hu","tile":None})
        self.assertEqual({x["action"] for x in response["candidates"]},
                         {"pass","hu"})
        _,owner,own=offer_kongs()
        own["can_self_draw_win"]=True
        self.assertEqual(classic_operation_hint(own,owner)["recommended"],
                         {"action":"hu","tile":None})

    def test_only_acting_seat_may_ask_live_and_no_unoffered_actions(self):
        _,seat,view=offer_peng()
        own=copy.deepcopy(view)
        own["seat"]=0
        if seat!=0:
            with self.assertRaises(ValueError):
                classic_operation_hint(view,0)
        else:
            self.assertEqual(classic_live_operation_hint(view)["seat"],0)
        single=copy.deepcopy(view)
        single["claim_options"]=["pass"]
        with self.assertRaises(ValueError):
            classic_operation_hint(single,seat)
        done=copy.deepcopy(view)
        done["claim_submitted"]=[seat]
        with self.assertRaises(ValueError):
            classic_operation_hint(done,seat)
        no_turn=copy.deepcopy(view)
        no_turn["phase"]="await_discard"
        no_turn["turn"]=(seat+1)%4
        with self.assertRaises(ValueError):
            classic_operation_hint(no_turn,seat)
        with self.assertRaises(ValueError):
            classic_operation_hint(view,True)
        with self.assertRaises(ValueError):
            classic_operation_hint(view,4)

    def test_http_read_only_only_seat_zero_auth_state(self):
        _,seat,view=offer_kongs()
        self.assertEqual(view["seat"],seat)
        # HTTP endpoint always asks private_view(0), never trusts payload seat.
        class ReadOnly:
            def __init__(self,v):
                self.v=copy.deepcopy(v);self.calls=[]
            def private_view(self,index):
                self.calls.append(index)
                return copy.deepcopy(self.v)
        authorized=copy.deepcopy(view)
        authorized["seat"]=0
        authorized["turn"]=0
        authorized["missing_suits"][0]=view["missing_suits"][seat]
        game=ReadOnly(authorized)
        with patch.dict(web_server._MATCH_SESSIONS,{"m396":game}),patch.dict(
                web_server._MATCH_AGENTS,{"m396":{1:object()} }):
            result=web_server._process("match_operation_hint",{
                "match_token":"m396","seat":seat,"phase":"finished"})
            self.assertEqual(result["match_token"],"m396")
            self.assertEqual(game.calls,[0])
            self.assertNotIn("match",result)
            self.assertEqual(result["hint"]["status"],"choose_operation")
            with self.assertRaises(ValueError):
                web_server._process("match_operation_hint",{
                    "match_token":"unknown","seat":0})

    def test_terminal_allowlist_preserves_pass_and_rejects_forged_actions(self):
        hands=[["m1","m2"],["p1"],["s1"],["m9"]]
        option=lambda action,label,best: {
            "action":action,"tile":None,"label":label,
            "shanten":1,"effective_copies":5,
            "fan_weighted":5,"reason":"公开牌效参考",
            "reference_best":best,
        }
        review={"opening":hands,"steps":[],
                "operation_reviews":[{
                    "seat":0,"sequence":1,
                    "actual":{"action":"pass","tile":None},
                    "recommended":{"action":"peng","tile":None},
                    "candidates":[option("pass","过",False),
                                  option("peng","碰",True)],
                    "opponent_hands":[["m9"]*13],
                }]}
        clean=sanitize_private_review(review)
        self.assertEqual(clean["operation_reviews"][0]["actual"]["action"],"pass")
        self.assertNotIn("opponent_hands",str(clean))
        malicious=copy.deepcopy(review)
        malicious["operation_reviews"][0]["recommended"]={"action":"hu","tile":None}
        with self.assertRaises(ValueError):
            sanitize_private_review(malicious)
        malicious=copy.deepcopy(review)
        malicious["operation_reviews"][0]["candidates"][0]["effective_copies"]=-1
        with self.assertRaises(ValueError):
            sanitize_private_review(malicious)
        malicious=copy.deepcopy(review)
        malicious["operation_reviews"][0]["seat"]=True
        with self.assertRaises(ValueError):
            sanitize_private_review(malicious)

    def test_actual_pass_response_without_public_event_still_records_review(self):
        game,seat,view=offer_peng()
        game._terminal_review_trace=[]
        game._terminal_operation_reviews=[]
        before_events=len(game._events)
        result=[]
        web_server._match_record(
            game,result,lambda: game.respond_discard(seat,"pass"),
            decision=(seat,"pass",None))
        self.assertEqual(game._terminal_operation_reviews[0]["seat"],seat)
        self.assertEqual(game._terminal_operation_reviews[0]["actual"]["action"],"pass")
        self.assertEqual(game._terminal_operation_reviews[0]["sequence"],2)
        self.assertIn("recommended",game._terminal_operation_reviews[0])
        self.assertGreaterEqual(len(game._events),before_events)


    def test_actual_discard_records_rejected_own_kong_offer(self):
        game,seat,view=offer_kongs()
        self.assertGreater(len(view["kong_options"]),0)
        game._terminal_review_trace=[]
        game._terminal_operation_reviews=[]
        web_server._match_record(
            game,[],lambda: game.discard(seat,"p4"),
            decision=(seat,"pass",None))
        self.assertEqual(len(game._terminal_operation_reviews),1)
        review=game._terminal_operation_reviews[0]
        self.assertEqual(review["seat"],seat)
        self.assertEqual(review["actual"],{"action":"pass","tile":None})
        self.assertTrue(any(row["action"]=="an_gang" for row in review["candidates"]))
        self.assertIn("cut_review",game._terminal_review_trace[-1])



if __name__=="__main__":
    unittest.main()
