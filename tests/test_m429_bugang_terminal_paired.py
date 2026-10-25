"""M4.29 freeze 5 physically constructed cashless-bu-gang outcome contrasts."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]

from mahtrain_core.ai_delayed_bugang_terminal_paired import (
    PROTOCOL,CASES,REPLICAS,ARMS,METRICS,LEDGER_PARTS,LINEUP,
    _world,_agents,_run_arm,paired_case,run_shard,combine_shards,SHARDS
)


def _sample(case_id,replica,first=10,second=5):
    def score(v):
        return {
            "official_net":v,"win_points":v,"kong_points":0,
            "exhaustive_points":0,"wins":1,"deal_ins":0,
            "own_realized_kongs":0,"own_robbed_kongs":0,
            "terminal_phase":"finished",
            "actions_after_checkpoint":20,
        }
    return {
        "case_id":case_id,"replica":replica,
        "exposed_peng":__import__(
            "mahtrain_core.ai_delayed_bugang_targeted",fromlist=["SPECS"]
        ).SPECS[case_id][0],
        "cash_rule":"current_m423","actor_seat":0,
        "interventions":{ARMS[0]:score(first),ARMS[1]:score(second)},
        "forced_minus_hold":{
            k:score(first)[k]-score(second)[k] for k in METRICS
        },
        "same_initial_wall_and_hidden_hands":True,
        "complete_games":2,"natural_random_games":0,
    }


def _fake_shards():
    return {name:{
        "protocol":PROTOCOL,"shard":name,"case_id":case_id,
        "replicas":list(REPLICAS),"arms":list(ARMS),
        "rows":[_sample(case_id,r) for r in REPLICAS],
        "only_constructed_worlds":True,"no_population_EV_claim":True,
    } for name,case_id in SHARDS.items()}


class CashlessBuGangTerminalPairTests(unittest.TestCase):
    def test_selection_is_prior_observed_five_not_new_winner_picked(self):
        self.assertEqual(CASES,(10,12,18,20,22))
        self.assertEqual(REPLICAS,(0,1,2))
        self.assertEqual(set(SHARDS.values()),set(CASES))
        self.assertEqual(len(SHARDS),5)
        self.assertEqual(LINEUP,("challenge","basic","advanced","baseline"))
        for invalid in (-1,0,4,6,True,10.0,"10"):
            with self.subTest(case=invalid),self.assertRaises(ValueError):
                _world(invalid,0)
        for invalid in (-1,3,True,1.0,"1"):
            with self.subTest(replica=invalid),self.assertRaises(ValueError):
                _world(10,invalid)

    def test_frozen_actor_view_and_genuine_cashless_legal_option(self):
        for case_id in CASES:
            with self.subTest(case=case_id):
                world=_world(case_id,0)
                view=world.private_view(0)
                self.assertFalse(view["legacy_bugang_cash_rule"])
                self.assertNotEqual(view["drawn_tile"],
                                    __import__(
                                      "mahtrain_core.ai_delayed_bugang_targeted",
                                      fromlist=["SPECS"]).SPECS[case_id][0])
                self.assertIn(
                    {"type":"bu_gang","tile":__import__(
                        "mahtrain_core.ai_delayed_bugang_targeted",
                        fromlist=["SPECS"]).SPECS[case_id][0]},
                    view["kong_options"])
                self.assertFalse(view["can_self_draw_win"])
                self.assertEqual(world.debug_tile_counts()["total"],108)
                self.assertNotIn("hand",world.public_state())
                self.assertNotIn("drawn_tile",world.public_state())

    def test_same_world_seed_deterministic_but_different_future_walls(self):
        a=_world(10,0)
        b=_world(10,0)
        c=_world(10,1)
        self.assertEqual(a.private_view(0),b.private_view(0))
        self.assertEqual(a._wall,b._wall)
        self.assertNotEqual(a._wall,c._wall)
        self.assertEqual(a.private_view(0),c.private_view(0))
        self.assertEqual(a.debug_tile_counts()["total"],108)

    def test_true_terminal_official_payoffs_two_interventions(self):
        result=paired_case(10,0)
        self.assertEqual(result["complete_games"],2)
        self.assertEqual(result["natural_random_games"],0)
        self.assertTrue(result["same_initial_wall_and_hidden_hands"])
        for arm in ARMS:
            x=result["interventions"][arm]
            self.assertIn(x["terminal_phase"],("finished","wall_exhausted"))
            self.assertEqual(x["official_net"],
                             sum(x[p] for p in LEDGER_PARTS))
            self.assertNotIn("opponent_hands",x)
            self.assertNotIn("future_wall",x)
            self.assertNotIn("public_replay",x)
        diff=result["forced_minus_hold"]
        self.assertEqual(diff["official_net"],
                         sum(diff[p] for p in LEDGER_PARTS))
        self.assertNotIn("rob_probability",result)
        self.assertNotIn("population_EV",result)

    def test_aggregation_never_calls_synthetic_rows_observed_evidence(self):
        output=combine_shards(_fake_shards())
        self.assertEqual(output["complete_terminal_games"],30)
        self.assertEqual(output["paired_conditional_worlds"],15)
        self.assertEqual(output["selected_conditional_case_clusters"],5)
        self.assertEqual(output["independent_natural_shuffle_seeds"],0)
        self.assertEqual(output["weighted_difference_means_for_constructed_cases"]
                         ["official_net"],5)
        self.assertEqual(output["positive_conditional_world_deltas"],15)
        self.assertFalse(output["online_policy_changed"])
        self.assertIsNone(output["natural_game_EV_estimate"])
        self.assertEqual(len(output["per_case"]),5)

    def test_reject_missing_or_fabricated_terminal_components(self):
        source=_fake_shards()
        bad=deepcopy(source); del bad["case_22"]
        with self.assertRaises(ValueError):
            combine_shards(bad)
        for kind in ("incorrect_seed","phony_official_score","incomplete",
                     "invented_decomposition","wrong_history","new_cash"):
            candidate=deepcopy(source)
            item=candidate["case_10"]["rows"][0]
            if kind=="incorrect_seed":
                item["replica"]=2
            elif kind=="phony_official_score":
                item["interventions"][ARMS[0]]["official_net"]=123456
            elif kind=="incomplete":
                item["interventions"][ARMS[0]]["terminal_phase"]="await_discard"
            elif kind=="invented_decomposition":
                item["forced_minus_hold"]["kong_points"]=22
            elif kind=="wrong_history":
                candidate["case_10"]["no_population_EV_claim"]=False
            else:
                item["cash_rule"]="frozen_pre_m423"
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                combine_shards(candidate)

    def test_bad_shard_never_runs_slow_games(self):
        with patch(
            "mahtrain_core.ai_delayed_bugang_terminal_paired.paired_case"
        ) as f:
            for name in ("other","",None,True,1):
                with self.subTest(shard=name),self.assertRaises(ValueError):
                    run_shard(name)
            f.assert_not_called()


if __name__=="__main__":
    unittest.main()
