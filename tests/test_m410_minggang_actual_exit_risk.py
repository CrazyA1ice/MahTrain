"""M4.10: actual authorized after-supplement cut, no future-wall oracle."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]
from mahtrain_core.ai import MahjongAgent
from mahtrain_core.ai_minggang_actual_exit_risk import (
    PROTOCOL, AfterTailCutObserver, reconcile_after_tail_cuts,
    natural_position, cohort, study,
)
from test_m405_dual_claim_fastpath import real_dual_offer
from test_m408_minggang_ledger_followthrough import terminal_case


def synthetic(*, post=1.15, pre=.10, voided=False, exit_=True):
    agent=AfterTailCutObserver(seed=42,seat=1)
    agent._dual_windows=[{
        "discard_index":1,"choice":"ming_gang",
        "pre_tail_min_threat":pre,"wall_band":"early",
    }]
    agent._risk_counts=Counter({"dual_windows":1,"original_ming_gang":1})
    outcome,board=terminal_case(voided=voided)
    outcome["public_events"].insert(0,{"type":"discard","index":1,"seat":0})
    board["discards"].insert(0,{"seat":0,"index":1})
    board["discards"][1]["index"]=2
    if exit_:
        agent._after_tail_exits=[{
            "claim_discard_index":1,"post_discard_index":2,"risk_index":post,
        }]
    else:
        board["discards"].pop()
        outcome["public_events"]=[{"type":"discard","index":1,"seat":0},
                                  {"type":"ming_gang","seat":1,"source":0}]
        board["kong_ledger"]["events"][0]["status"]="posted"
        board["kong_ledger"]["events"][0]["reason"]="simulation_using_explicit_kong_base"
        board["kong_ledger"]["balances"]=[-2,2,0,0]
        board["kong_ledger"]["entries"]=board["kong_ledger"]["entries"][:1]
        outcome["official_kong_balances"]=[-2,2,0,0]
    return agent,outcome,board


class M410ActualPostTailTests(unittest.TestCase):
    def test_real_108_physical_supplement_and_true_baseline_discard(self):
        game,seat,view=real_dual_offer()
        player=AfterTailCutObserver(seed=42,seat=seat)
        for other in range(4):
            if other != view["pending_discard"]["seat"] and other != seat:
                game.respond_discard(other,"pass")
        game.respond_discard(seat,"ming_gang")
        self.assertEqual(game.phase,"await_discard")
        own=game.private_view(seat)
        self.assertEqual(own["events"][-1]["type"],"kong_supplement")
        self.assertEqual(own["events"][-2]["type"],"ming_gang")
        frozen=copy.deepcopy(own)
        original=MahjongAgent("challenge",seed=42,seat=seat).discard(own)
        cut=player.discard(own)
        self.assertEqual(cut,original)
        self.assertEqual(own,frozen)
        self.assertEqual(len(player._after_tail_exits),1)
        self.assertNotIn("tile",player._after_tail_exits[0])
        self.assertNotIn("drawn_tile",player._after_tail_exits[0])
        self.assertEqual(game.debug_tile_counts()["total"],108)
        game.discard(seat,cut)
        self.assertTrue(game.public_state()["discards"][-1]["after_kong"])
        self.assertEqual(player._after_tail_exits[0]["post_discard_index"],
                         game.public_state()["discards"][-1]["index"])

    def test_high_actual_cut_index_not_forced_to_probability(self):
        agent,outcome,board=synthetic()
        actual=reconcile_after_tail_cuts(agent,outcome,board)
        c=actual["post_tail_counts"]
        self.assertEqual(c["real_exits"],1)
        self.assertEqual(c["transition_low_to_high"],1)
        self.assertEqual(c["upshift"],1)
        self.assertEqual(c["post_high_exits"],1)
        self.assertEqual(c.get("ron",0),0)
        self.assertIsNone(actual["readiness"]["calibrated_ron_probability"])

    def test_real_ron_multiwinner_cancels_only_one_kong_cash(self):
        agent,outcome,board=synthetic(post=.35,pre=.7,voided=True)
        x=reconcile_after_tail_cuts(agent,outcome,board)
        c=x["post_tail_counts"]
        self.assertEqual(c["transition_high_to_mid"],1)
        self.assertEqual(c["downshift"],1)
        self.assertEqual(c["ron"],1)
        self.assertEqual(c["post_mid_ron"],1)
        self.assertEqual(c["ron_winners"],2)
        self.assertEqual(x["pre_tail_counts"].get("awarded_final_cash",0),0)

    def test_own_kong_without_actual_discard_is_censored_not_safe_exit(self):
        agent,outcome,board=synthetic(exit_=False)
        x=reconcile_after_tail_cuts(agent,outcome,board)
        self.assertEqual(x["post_tail_counts"]["awarded_without_exit"],1)
        self.assertEqual(x["post_tail_counts"].get("real_exits",0),0)
        self.assertEqual(x["pre_tail_counts"]["awarded"],1)

    def test_missing_extra_wrong_actual_cut_diagnostic_rejected(self):
        for issue in ("missing","wrong_index","wrong_claim","duplicate"):
            agent,outcome,board=synthetic()
            if issue=="missing":agent._after_tail_exits=[]
            if issue=="wrong_index":
                agent._after_tail_exits[0]["post_discard_index"]=8
            if issue=="wrong_claim":
                agent._after_tail_exits[0]["claim_discard_index"]=3
            if issue=="duplicate":
                agent._after_tail_exits.append(dict(agent._after_tail_exits[0]))
            with self.subTest(issue=issue),self.assertRaises(RuntimeError):
                reconcile_after_tail_cuts(agent,outcome,board)

    def test_preclaim_cannot_read_tail_and_observer_does_not_consume_opponent(self):
        game,seat,view=real_dual_offer()
        a=AfterTailCutObserver(seed=42,seat=seat)
        original=MahjongAgent("challenge",seed=42,seat=seat).response(view)
        original_view=copy.deepcopy(view)
        self.assertEqual(a.response(view),original)
        self.assertEqual(view,original_view)
        self.assertEqual(a._after_tail_exits,[])
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_one_real_match_terminal_and_anonymous(self):
        p=natural_position(44000,0)
        self.assertEqual(p["seed"],44000)
        self.assertIn(p["terminal_phase"],("finished","wall_exhausted"))
        self.assertEqual(p["official"]["official_net"],sum(
            p["official"][k] for k in
            ("win_points","kong_points","exhaustive_points")))
        raw=json.dumps(p)
        for key in ('"tile"','"hand"',"opponent_hands","future_wall"):
            self.assertNotIn(key,raw)

    def test_seat_cluster_validation_and_nonoverlapping_holdout(self):
        from unittest.mock import patch
        def fake(seed,rotation):
            return {
                "seed":seed,"rotation":rotation,"challenge_seat":rotation,
                "pre_tail_counts":{"awarded":1},
                "post_tail_counts":{"real_exits":1,"same_band":1},
            }
        with patch("mahtrain_core.ai_minggang_actual_exit_risk.natural_position",
                   side_effect=fake) as called:
            report=cohort(44000,2)
        self.assertEqual(called.call_count,8)
        self.assertEqual(report["complete_games"],8)
        self.assertEqual(report["seeds_with_actual_exit"],2)
        self.assertIsNone(report["uncertainty_interval"])
        with patch("mahtrain_core.ai_minggang_actual_exit_risk.cohort",
                   return_value={"independent_shuffle_seeds":8}) as mocked:
            x=study()
        self.assertEqual([c.args for c in mocked.call_args_list],
                         [(44000,8),(45000,8)])
        self.assertEqual(x["protocol"],PROTOCOL)
        self.assertFalse(x["online_policy_modified"])
        for bad in ({"seeds":0},{"seeds":13},{"seeds":True},
                    {"holdout":44000},{"holdout":44007},
                    {"development":True},{"holdout":2**32-1}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                study(**bad)


if __name__=="__main__":
    unittest.main()
