"""M3.87: authoritative continuing-round dealer rule and token safety."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT))
from mahtrain_core.four_player import FourPlayerOpening
from mahtrain_core.next_dealer import next_dealer
import web_server


def board(*,dealer=0,events=(),wins=(),winners=(),phase="finished"):
    return {
        "phase":phase, "dealer":dealer,
        "events":list(events), "win_ledger":{"wins":list(wins)},
        "winners":list(winners),
    }


class DealerRuleTests(unittest.TestCase):
    def test_winner_is_not_next_dealer_if_single_discard_hit_two(self):
        snapshot=board(dealer=3,events=[{
            "type":"multi_ron","source":2,"seats":[0,1],"tile":"m2"}],
            wins=[{"winner":0,"payers":[2],"kind":"ron"},
                  {"winner":1,"payers":[2],"kind":"ron"}],
            winners=[{"seat":0},{"seat":1}])
        self.assertEqual(next_dealer(snapshot)["dealer"],2)
        self.assertEqual(next_dealer(snapshot)["reason"],"multi_ron")

    def test_multi_ron_still_precedes_other_losing_three_case(self):
        snapshot=board(dealer=1,events=[{
            "type":"multi_ron","source":3,"seats":[1,2]}],
            wins=[{"winner":1,"payers":[0]},
                  {"winner":2,"payers":[0]},
                  {"winner":3,"payers":[0]}],
            winners=[{"seat":1},{"seat":2},{"seat":3}])
        self.assertEqual(next_dealer(snapshot)["dealer"],3)

    def test_losing_three_counts_distinct_hu_winners_not_payment_count(self):
        snapshot=board(dealer=1,wins=[
            {"winner":1,"payers":[0],"kind":"ron"},
            {"winner":1,"payers":[0],"kind":"ron"},
            {"winner":2,"payers":[0,1,3],"kind":"self_draw"},
            {"winner":3,"payers":[0],"kind":"rob_kong"},
        ],winners=[{"seat":1},{"seat":2},{"seat":3}])
        self.assertEqual(next_dealer(snapshot)["dealer"],0)
        self.assertEqual(next_dealer(snapshot)["reason"],"lost_to_three")
        snapshot["win_ledger"]["wins"].pop()
        self.assertEqual(next_dealer(snapshot)["dealer"],1)
        self.assertEqual(next_dealer(snapshot)["reason"],"first_hu")

    def test_three_distinct_self_draw_payments_count_as_hu_losses(self):
        snapshot=board(dealer=3,wins=[
            {"winner":1,"payers":[0,2,3],"kind":"self_draw"},
            {"winner":2,"payers":[0,3],"kind":"self_draw"},
            {"winner":3,"payers":[0],"kind":"ron"},
        ],winners=[{"seat":1},{"seat":2},{"seat":3}])
        self.assertEqual(next_dealer(snapshot)["dealer"],0)

    def test_normal_first_hu_wins_even_if_original_dealer_is_different(self):
        snapshot=board(dealer=0,wins=[
            {"winner":3,"payers":[2],"kind":"ron"},
            {"winner":1,"payers":[2],"kind":"ron"},
        ],winners=[{"seat":3},{"seat":1}])
        self.assertEqual(next_dealer(snapshot)["dealer"],3)
        self.assertEqual(next_dealer(snapshot)["reason"],"first_hu")

    def test_wall_exhaustion_with_no_hu_keeps_original_dealer(self):
        self.assertEqual(next_dealer(board(dealer=2,phase="wall_exhausted")),
                         {"dealer":2,"reason":"draw_keep",
                          "label":"流局无人胡牌，原庄续庄"})

    def test_not_finished_cannot_preassign_next_dealer(self):
        with self.assertRaisesRegex(ValueError,"before round completes"):
            next_dealer(board(phase="await_draw"))
        with self.assertRaises(ValueError):
            next_dealer(board(dealer=True))

    def test_explicit_dealer_override_does_not_alter_random_wall(self):
        auto=FourPlayerOpening(41)
        chosen=(auto.dealer+2)%4
        linked=FourPlayerOpening(41,dealer_override=chosen)
        self.assertEqual(linked.dealer,chosen)
        self.assertEqual(linked.exchange_direction,auto.exchange_direction)
        self.assertEqual(sorted(linked._wall),sorted(auto._wall))
        self.assertEqual(linked.debug_tile_counts()["total"],108)
        for value in (-1,4,True,0.0,"1"):
            with self.subTest(value=value),self.assertRaises(ValueError):
                FourPlayerOpening(41,dealer_override=value)


class NextRoundServerTests(unittest.TestCase):
    def setUp(self):
        self.old_sessions=web_server._MATCH_SESSIONS.copy()
        self.old_agents=web_server._MATCH_AGENTS.copy()
        self.old_used=web_server._MATCH_USED_SEEDS.copy()
        self.old_successors=web_server._MATCH_SUCCESSORS.copy()
        self.old_history=web_server._MATCH_HISTORY.copy()
        self.old_opening=web_server._MATCH_OPENING.copy()
        self.old_archives=web_server._MATCH_ARCHIVE_IDS.copy()
        for value in (web_server._MATCH_SESSIONS,web_server._MATCH_AGENTS,
                      web_server._MATCH_SUCCESSORS,web_server._MATCH_HISTORY,
                      web_server._MATCH_OPENING,web_server._MATCH_ARCHIVE_IDS,
                      web_server._MATCH_USED_SEEDS):
            value.clear()

    def tearDown(self):
        for mapping,saved in (
            (web_server._MATCH_SESSIONS,self.old_sessions),
            (web_server._MATCH_AGENTS,self.old_agents),
            (web_server._MATCH_SUCCESSORS,self.old_successors),
            (web_server._MATCH_HISTORY,self.old_history),
            (web_server._MATCH_OPENING,self.old_opening),
            (web_server._MATCH_ARCHIVE_IDS,self.old_archives),
            (web_server._MATCH_USED_SEEDS,self.old_used),
        ):
            mapping.clear()
            mapping.update(saved)

    def new(self):
        return web_server._process("match_new",{
            "seed":87,"ai_levels":["basic","advanced","challenge"],
            "room_coefficient":150,"fan_cap":4,"kong_base":80,
            "self_draw_mode":"add_fan",
        })

    def test_initial_random_dealer_and_preterminal_refusal(self):
        initial=self.new()
        token=initial["match_token"]
        self.assertEqual(initial["match"]["series_round"],1)
        self.assertEqual(initial["match"]["dealer_origin"],"首局随机庄")
        self.assertEqual(initial["match"]["dealer"],FourPlayerOpening(87).dealer)
        self.assertNotIn("next_dealer",initial["match"])
        with self.assertRaisesRegex(ValueError,"尚未结束"):
            web_server._process("match_next",{"match_token":token})
        self.assertEqual(len(web_server._MATCH_SESSIONS),1)

    def test_first_winner_inherits_with_fresh_wall_and_preserved_rules(self):
        first=self.new()
        token=first["match_token"]
        game=web_server._MATCH_SESSIONS[token]
        game.phase="finished"
        game._winners=[{"seat":3,"kind":"ron","source":0}]
        old_seed=87
        resumed=web_server._process("match_next",{"match_token":token})
        child=resumed["match_token"]
        nxt=web_server._MATCH_SESSIONS[child]
        self.assertNotEqual(child,token)
        self.assertEqual(nxt.dealer,3)
        self.assertEqual(nxt.series_round,2)
        self.assertNotEqual(nxt.dealer_origin,"首局随机庄")
        self.assertEqual(resumed["match"]["hand_counts"][3],14)
        self.assertEqual(nxt.ledger.room_coefficient,150)
        self.assertEqual(nxt.ledger.fan_cap,4)
        self.assertEqual(nxt.kong_ledger.base,80)
        self.assertEqual(nxt.ledger.self_draw_mode,"add_fan")
        self.assertEqual([web_server._MATCH_AGENTS[child][i].level
                          for i in (1,2,3)],["basic","advanced","challenge"])
        self.assertEqual(nxt.debug_tile_counts()["total"],108)
        self.assertIn(old_seed,web_server._MATCH_USED_SEEDS)
        self.assertEqual(len(web_server._MATCH_USED_SEEDS),2)
        again=web_server._process("match_next",{"match_token":token})
        self.assertEqual(again["match_token"],child)
        self.assertEqual(len(web_server._MATCH_USED_SEEDS),2)

    def test_verified_multi_ron_overrides_initial_first_winner(self):
        first=self.new()
        game=web_server._MATCH_SESSIONS[first["match_token"]]
        game.phase="finished"
        game._winners=[{"seat":1},{"seat":2}]
        game._events=[{"type":"multi_ron","source":0,"seats":[1,2]}]
        result=web_server._process("match_next",{"match_token":first["match_token"]})
        self.assertEqual(result["match"]["dealer"],0)

    def test_server_rejects_client_forged_next_dealer_seed_and_rules(self):
        first=self.new()
        token=first["match_token"]
        game=web_server._MATCH_SESSIONS[token]
        game.phase="finished"
        for key,val in (("dealer",0),("dealer_override",3),("seed",100),
                        ("room_coefficient",1),("ai_levels",["basic"]*3)):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError,"服务器"):
                    web_server._process("match_next",
                                        {"match_token":token,key:val})
        with self.assertRaisesRegex(ValueError,"失效"):
            web_server._process("match_next",{"match_token":"forged"})
        self.assertEqual(len(web_server._MATCH_SESSIONS),1)

    def test_next_dealer_readonly_and_repeatable_in_finished_snapshot(self):
        first=self.new()
        token=first["match_token"]
        game=web_server._MATCH_SESSIONS[token]
        game.phase="finished"
        game._winners=[{"seat":1}]
        v1=web_server._process("match_resume",{"match_token":token})["match"]
        v2=web_server._process("match_resume",{"match_token":token})["match"]
        self.assertEqual(v1["next_dealer"],v2["next_dealer"])
        self.assertEqual(v1["next_dealer"]["dealer"],1)
        self.assertNotIn("_hands",v1)
        self.assertNotIn("_wall",v1)


if __name__=="__main__":
    unittest.main()
