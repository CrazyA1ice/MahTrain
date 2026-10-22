"""M4.01: 108-physical-tile official multi-ron/rob stress, not prevalence."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mahtrain_core.ai_rob_physical_scenarios import (
    PROTOCOL,SCENARIOS,TILE,build_physical_scenario,
    verify_constructed_scenario,stress_report,
)
from mahtrain_core.ai_public_bugang_rob_pilot import (
    public_bugang_features,_sealed_potential_robbers,
)


class M401PhysicalRobScenarioTests(unittest.TestCase):
    def test_all_scenarios_use_exact_108_physical_tiles_and_legal_kong(self):
        for name in SCENARIOS:
            with self.subTest(name=name):
                g,owner,designated=build_physical_scenario(name)
                self.assertEqual(g.debug_tile_counts()["total"],108)
                self.assertEqual(len(g._wall),11 if
                                 name=="critical_wall_positive" else 55)
                self.assertIn({"type":"bu_gang","tile":TILE},g.kong_options(owner))
                self.assertEqual(g._effective(owner),14)
                for s in range(4):
                    if s!=owner:self.assertEqual(g._effective(s),13)
                state=g.public_state()
                self.assertEqual(state["hand_counts"][owner],11)
                self.assertEqual(state["wall_count"],len(g._wall))
                self.assertEqual(
                    _sealed_potential_robbers(g,owner,TILE),
                    sum(s!=owner and not g._won[s] and
                        g.missing_suits[s]!=TILE[0] and
                        __import__("mahtrain_core.rules",fromlist=["is_legal_win"])
                          .is_legal_win(
                            [*g._hands[s],TILE],g._melds[s],g.missing_suits[s])
                        for s in range(4)))

    def test_exact_positive_negative_and_actual_outcome_truth_table(self):
        expectations={
            "one_robber":("unresolved",1,1,0,1),
            "two_robbers":("unresolved",2,2,0,1),
            "decline_legal_hu":("unresolved",1,0,1,0),
            "all_dingque_excluded":("dingque_excluded",0,0,1,0),
            "focused_positive":("same_suit_focus",1,1,0,1),
            "focused_false_alarm":("same_suit_focus",0,0,1,0),
            "mixed_meld_positive":("exposed_pressure",1,1,0,1),
            "critical_wall_positive":("unresolved",1,1,0,1),
        }
        for name,(band,legal,chosen,success,robbed) in expectations.items():
            with self.subTest(name=name):
                r=verify_constructed_scenario(name)
                self.assertEqual(r["public_band"],band)
                self.assertEqual(r["sealed_eligible_robbers"],legal)
                self.assertEqual(r["official_legal_robbers"],legal)
                self.assertEqual(r["actually_chose_rob_hu"],chosen)
                self.assertEqual(r["attempted"],1)
                self.assertEqual(r["successful"],success)
                self.assertEqual(r["robbed"],robbed)
                self.assertEqual(r["rob_hu_winners"],chosen)
                self.assertEqual(r["physical_tiles"],108)
                self.assertTrue(r["official_zero_sum"])

    def test_public_signals_fail_safe_without_secret_access(self):
        original,owner,_=build_physical_scenario("focused_positive")
        negative,owner2,_=build_physical_scenario("focused_false_alarm")
        a=public_bugang_features(original.public_state(),owner,TILE)
        b=public_bugang_features(negative.public_state(),owner2,TILE)
        self.assertEqual(a["band"],"same_suit_focus")
        self.assertEqual(b["band"],"same_suit_focus")
        self.assertEqual(_sealed_potential_robbers(original,owner,TILE),1)
        self.assertEqual(_sealed_potential_robbers(negative,owner2,TILE),0)
        public=copy.deepcopy(original.public_state())
        public["_hands"]=[["m9"]*13]*4
        public["opponent_hands"]=[["m9"]*13]*4
        public["future_wall"]=["m9"]*55
        self.assertEqual(public_bugang_features(public,owner,TILE),a)
        raw=json.dumps(a)
        self.assertNotIn("opponent_hands",raw)
        self.assertNotIn("future_wall",raw)

    def test_dingque_mask_excludes_revealed_robber_even_if_hand_is_ready(self):
        g,owner,des=build_physical_scenario("all_dingque_excluded")
        self.assertTrue(des)
        self.assertEqual(_sealed_potential_robbers(g,owner,TILE),0)
        feature=public_bugang_features(g.public_state(),owner,TILE)
        self.assertEqual(feature["dingque_eligible_opponents"],0)
        self.assertEqual(feature["active_opponents"],3)
        report=verify_constructed_scenario("all_dingque_excluded")
        self.assertEqual(report["successful"],1)

    def test_two_robbers_one_declaration_two_winners_original_peng_remains(self):
        g,owner,_=build_physical_scenario("two_robbers")
        self.assertEqual(_sealed_potential_robbers(g,owner,TILE),2)
        g.declare_kong(owner,"bu_gang",TILE)
        robbers=[s for s in range(4) if s!=owner and "hu" in g.rob_options(s)]
        self.assertEqual(len(robbers),2)
        for s in range(4):
            if s!=owner:
                g.respond_rob_kong(s,"hu" if s in robbers else "pass")
        board=g.public_state()
        self.assertEqual(g._melds[owner],[{"type":"peng","tile":TILE}])
        self.assertEqual(sum(w["kind"]=="rob_kong" for w in board["winners"]),2)
        self.assertEqual(g.debug_tile_counts()["total"],108)
        self.assertEqual(sum(board["settled_balances"]),0)

    def test_constructed_positive_does_not_invent_population_probability(self):
        data=stress_report()
        self.assertEqual(data["protocol"],PROTOCOL)
        self.assertFalse(data["live_policy_modified"])
        self.assertEqual(data["scenario_count"],len(SCENARIOS))
        self.assertIsNone(data["calibrated_rob_probability"])
        self.assertEqual({r["scenario"] for r in data["constructed_cases"]},
                         set(SCENARIOS))
        self.assertTrue(all(
            r["origin"]=="constructed_fixture_not_natural_sample"
            for r in data["constructed_cases"]))
        raw=json.dumps(data)
        for blocked in ("future_wall","opponent_hands","hidden_tile_hash"):
            self.assertNotIn(blocked,raw)


if __name__=="__main__":
    unittest.main()
