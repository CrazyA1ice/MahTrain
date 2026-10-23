"""M4.07: real physical dual-claim risk envelope, safety and seed clusters."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]

from mahtrain_core.ai import MahjongAgent
from mahtrain_core.ai_minggang_public_risk_audit import (
    PROTOCOL, PublicMingGangRiskObserver, public_minggang_exit_risk,
    paired_position, cohort, study,
)
from test_m405_dual_claim_fastpath import real_dual_offer
from test_ai_calls import offer_peng


class PublicMingGangRiskTests(unittest.TestCase):
    def test_true_physical_108_dual_offer_and_private_snapshot_unchanged(self):
        game,seat,view=real_dual_offer()
        original=copy.deepcopy(view)
        risk=public_minggang_exit_risk(view)
        self.assertEqual(game.debug_tile_counts()["total"],108)
        self.assertEqual(original,view)
        self.assertGreater(risk["pre_tail_candidate_kinds"],0)
        self.assertLessEqual(risk["min_existing_cut_threat_index"],
                             risk["max_existing_cut_threat_index"])
        self.assertLessEqual(risk["min_candidate_threatening_seats"],
                             risk["max_candidate_threatening_seats"])
        self.assertFalse(risk["supplement_tile_known"])
        self.assertFalse(risk["risk_index_is_probability"])
        self.assertIsNone(risk["forecast_official_net"])
        self.assertIsNone(risk["nominal_reversible_minggang_payment"])
        self.assertEqual(
            risk["max_ron_per_opponent_fan_cap"],
            view["win_ledger"]["room_coefficient"]*2**view["win_ledger"]["fan_cap"])
        self.assertEqual(risk["extreme_all_active_opponents_ron_cap"],
                         risk["active_opponents"]*risk["max_ron_per_opponent_fan_cap"])
        data=json.dumps(risk)
        for private in ('"hand"','"tile"','"future_wall"','"opponent_hands"','"oracle_ron"'):
            self.assertNotIn(private,data)

    def test_cash_price_is_independent_of_win_ceiling(self):
        _,_,view=real_dual_offer()
        view["kong_ledger"]["base"]=7
        view["win_ledger"]["room_coefficient"]=30
        view["win_ledger"]["fan_cap"]=4
        risk=public_minggang_exit_risk(view)
        self.assertEqual(risk["nominal_reversible_minggang_payment"],14)
        self.assertEqual(risk["max_ron_per_opponent_fan_cap"],480)
        self.assertIsNone(risk["forecast_official_net"])
        view["kong_ledger"]["base"]=True
        with self.assertRaises(ValueError):
            public_minggang_exit_risk(view)
        view["kong_ledger"]["base"]=None
        view["win_ledger"]["fan_cap"]=True
        with self.assertRaises(ValueError):
            public_minggang_exit_risk(view)

    def test_authorized_window_and_physical_wall_guards(self):
        _,_,single=offer_peng()
        with self.assertRaises(ValueError):
            public_minggang_exit_risk(single)
        _,_,view=real_dual_offer()
        view["wall_count"]=0
        with self.assertRaises(ValueError):
            public_minggang_exit_risk(view)
        view["wall_count"]=10
        tile=view["pending_discard"]["tile"]
        view["hand"]=[x for x in view["hand"] if x!=tile]
        with self.assertRaises(ValueError):
            public_minggang_exit_risk(view)

    def test_injected_hidden_opponent_and_future_wall_never_change_result(self):
        _,_,view=real_dual_offer()
        before=public_minggang_exit_risk(view)
        hidden=copy.deepcopy(view)
        hidden["opponent_hands"]=[["m1"]*13]*3
        hidden["future_wall"]=["s9"]*30
        hidden["oracle_ron"]=1
        self.assertEqual(public_minggang_exit_risk(hidden),before)

    def test_observer_retains_original_decision_and_fastpaths(self):
        _,seat,view=real_dual_offer()
        expected=MahjongAgent("challenge",seed=42,seat=seat).response(view)
        agent=PublicMingGangRiskObserver(seed=42,seat=seat)
        self.assertEqual(agent.response(view),expected)
        self.assertEqual(agent.public_counts()["dual_windows"],1)
        _,seat,single=offer_peng()
        with patch("mahtrain_core.ai_minggang_public_risk_audit.public_minggang_exit_risk",
                   side_effect=AssertionError("must skip non-dual calls")):
            agent=PublicMingGangRiskObserver(seed=42,seat=seat)
            self.assertIn(agent.response(single),single["claim_options"])
            self.assertEqual(agent.public_counts().get("dual_windows",0),0)

    def test_mandatory_hu_and_rob_hu_never_trigger_optional_audit(self):
        _,seat,view=real_dual_offer()
        hu=copy.deepcopy(view);hu["claim_options"].append("hu")
        rob=copy.deepcopy(view)
        rob["phase"]="rob_kong_window";rob["rob_options"]=["pass","hu"]
        with (patch("mahtrain_core.ai.MahjongAgent.response",return_value="hu"),
              patch("mahtrain_core.ai_minggang_public_risk_audit.public_minggang_exit_risk",
                    side_effect=AssertionError("must never audit Hu"))):
            agent=PublicMingGangRiskObserver(seed=42,seat=seat)
            self.assertEqual(agent.response(hu),"hu")
            self.assertEqual(agent.response(rob,rob=True),"hu")

    def test_real_one_position_official_terminal_identical(self):
        result=paired_position(38000,0)
        self.assertTrue(result["unchanged_official"])
        self.assertEqual(result["baseline_official"],result["observer_official"])
        base=result["baseline_official"]
        self.assertEqual(base["official_net"],sum(base[x] for x in (
            "win_points","kong_points","exhaustive_points")))
        serialized=json.dumps(result)
        for secret in ("future_wall","opponent_hands","full_wall","oracle_ron"):
            self.assertNotIn(secret,serialized)

    def test_cluster_math_and_distinct_preregistered_seed_blocks(self):
        def fake(seed,rotation):
            return {"seed":seed,"rotation":rotation,
                    "challenge_seat":(4-rotation)%4,
                    "risk_counts":{"dual_windows":1,"candidate_kinds_total":3},
                    "unchanged_official":True}
        with patch("mahtrain_core.ai_minggang_public_risk_audit.paired_position",
                   side_effect=fake) as mocked:
            x=cohort(40000,2)
        self.assertEqual(mocked.call_count,8)
        self.assertEqual(x["paired_seat_positions"],8)
        self.assertEqual(x["complete_games"],16)
        self.assertEqual(x["natural_dual_windows"],8)
        self.assertEqual(x["risk_counters"]["candidate_kinds_total"],24)
        self.assertEqual(x["policy_interventions"],0)
        self.assertIsNone(x["confidence_interval"])
        for bad in ({"holdout":38000},{"holdout":38003},
                    {"seeds":0},{"seeds":9},{"seeds":True},
                    {"development":True},{"holdout":2**32-1}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                study(**bad)
        with patch("mahtrain_core.ai_minggang_public_risk_audit.cohort",
                   return_value={"independent_initial_shuffle_seeds":4}) as fn:
            s=study()
        self.assertEqual(fn.call_args_list[0].args,(38000,4))
        self.assertEqual(fn.call_args_list[1].args,(39000,4))
        self.assertEqual(s["protocol"],PROTOCOL)
        self.assertFalse(s["online_policy_modified"])


if __name__=="__main__":
    unittest.main()
