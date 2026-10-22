"""M3.97: no-oracle, first-decision, exact-rule multi-step comparisons."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"tests")]

from mahtrain_core.ai import MahjongAgent
from mahtrain_core.ai_challenge_action_counterfactual import (
    PROTOCOL,TARGETS,POLICIES,FirstOpportunityAgent,_decision_space,
    _signature,_one,study,
)
from test_ai_calls import offer_peng,offer_kongs


class M397CounterfactualTests(unittest.TestCase):
    def test_predeclared_eligible_claim_and_own_kong_choices(self):
        _,seat,peng=offer_peng()
        options=_decision_space("claim",peng)
        self.assertIn("pass",options)
        self.assertIn("peng",options)
        self.assertTrue(set(options)<=set(peng["claim_options"]))
        hu=copy.deepcopy(peng)
        hu["claim_options"]=[*hu["claim_options"],"hu"]
        self.assertEqual(_decision_space("claim",hu),())
        rob=copy.deepcopy(peng)
        rob["phase"]="rob_kong_window"
        self.assertEqual(_decision_space("claim",rob),())
        _,seat,own=offer_kongs()
        kongs=_decision_space("own_kong",own)
        self.assertIsNone(kongs[0])
        self.assertEqual(list(kongs[1:]),own["kong_options"])
        own["can_self_draw_win"]=True
        self.assertEqual(_decision_space("own_kong",own),())

    def test_first_claim_branches_once_and_must_match_same_preaction_view(self):
        _,seat,view=offer_peng()
        unchanged=copy.deepcopy(view)
        base=FirstOpportunityAgent(seed=42,seat=seat,target="claim")
        baseline_action=base.response(view)
        self.assertEqual(view,unchanged)
        self.assertIn(baseline_action,view["claim_options"])
        self.assertTrue(base.offer)
        self.assertEqual(base.offer["chosen_choice"],base.offer["baseline_choice"])
        self.assertNotIn("hand",json.dumps(base.offer))
        forced=FirstOpportunityAgent(
            seed=42,seat=seat,target="claim",policy="force_active",
            expected_signature=base.offer_signature)
        self.assertEqual(forced.response(view),
                         next(x for x in ("ming_gang","peng")
                              if x in view["claim_options"]))
        forced.validate_branch(base)
        self.assertEqual(forced.response(view),baseline_action,
                         "do not force later calls after the first decision")
        wrong=copy.deepcopy(view)
        wrong["hand"]=wrong["hand"][:-1]
        mismatch=FirstOpportunityAgent(
            seed=42,seat=seat,target="claim",policy="force_active",
            expected_signature=base.offer_signature)
        with self.assertRaisesRegex(RuntimeError,"SAME"):
            mismatch.response(wrong)

    def test_own_kong_alternatives_are_distinguished_without_tile_leak(self):
        _,seat,view=offer_kongs()
        original=copy.deepcopy(view)
        base=FirstOpportunityAgent(seed=42,seat=seat,target="own_kong")
        existing=base.kong(view)
        self.assertEqual(view,original)
        self.assertEqual(base.offer["candidate_count"],3)
        self.assertEqual(len(set(base.offer["options"])),3)
        self.assertNotIn("m1",str(base.offer))
        self.assertNotIn("m9",str(base.offer))
        active=FirstOpportunityAgent(
            seed=42,seat=seat,target="own_kong",policy="force_active",
            expected_signature=base.offer_signature)
        self.assertEqual(active.kong(view),view["kong_options"][0])
        active.validate_branch(base)
        self.assertEqual(active.kong(view),existing)
        passive=FirstOpportunityAgent(
            seed=42,seat=seat,target="own_kong",policy="force_pass",
            expected_signature=base.offer_signature)
        self.assertIsNone(passive.kong(view))
        passive.validate_branch(base)

    def test_no_hidden_wall_or_opponent_hand_affects_decision_pairing(self):
        _,seat,view=offer_kongs()
        a=copy.deepcopy(view)
        b=copy.deepcopy(view)
        a["future_wall"]=["m1"]*30
        b["future_wall"]=["s9"]*30
        a["opponent_hands"]=[["m1"]*13]*3
        b["opponent_hands"]=[["s9"]*13]*3
        self.assertEqual(_signature(a),_signature(b))
        agent_a=FirstOpportunityAgent(
            seed=12,seat=seat,target="own_kong",policy="force_active")
        agent_b=FirstOpportunityAgent(
            seed=12,seat=seat,target="own_kong",policy="force_active")
        self.assertEqual(agent_a.kong(a),agent_b.kong(b))
        self.assertEqual(agent_a.offer,agent_b.offer)

    def test_refusal_to_override_verified_ron_and_rob_hu(self):
        _,seat,view=offer_peng()
        view["claim_options"]=[*view["claim_options"],"hu"]
        bot=FirstOpportunityAgent(
            seed=42,seat=seat,target="claim",policy="force_pass")
        self.assertEqual(bot.response(view),"hu")
        self.assertIsNone(bot.offer)
        rob=copy.deepcopy(view)
        rob["phase"]="rob_kong_window"
        rob["rob_options"]=["pass","hu"]
        self.assertEqual(bot.response(rob,rob=True),"hu")
        self.assertIsNone(bot.offer)

    def test_single_real_match_tracks_original_official_components(self):
        row=_one(14000,0,"claim")
        self.assertEqual(row["seed"],14000)
        self.assertEqual(row["challenge_seat"],0)
        report=row["baseline"]["score"]
        self.assertEqual(
            report["official_net"],
            report["win_points"]+report["kong_points"]+
            report["exhaustive_points"])
        if row["offered"]:
            for policy in POLICIES[1:]:
                candidate=row["alternatives"][policy]
                for metric in ("official_net","win_points","kong_points",
                               "exhaustive_points"):
                    self.assertEqual(candidate["delta"][metric],
                                     candidate["score"][metric]-report[metric])
                self.assertEqual(
                    candidate["delta"]["official_net"],
                    candidate["delta"]["win_points"]+
                    candidate["delta"]["kong_points"]+
                    candidate["delta"]["exhaustive_points"])
            self.assertNotIn("hand",str(row))
            self.assertNotIn("future_wall",str(row))
            self.assertNotIn("opponent_hands",json.dumps(row))
        else:
            self.assertEqual(row["alternatives"],{})

    def test_cohorts_predeclared_disjoint_and_seat_clustered_without_fake_CI(self):
        for kw in (
            {"seeds_per_group":0},{"seeds_per_group":5},
            {"seeds_per_group":True},{"development_start":True},
            {"development_start":-1},{"holdout_start":2**32-1},
            {"development_start":14000,"holdout_start":14001,
             "seeds_per_group":2},
        ):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                study(**kw)
        def fake_one(seed,rotation,target):
            seat=(4-rotation)%4
            report={
                "official_net":0,"win_points":0,"kong_points":0,
                "exhaustive_points":0,"win_events":0,
                "deal_in_events":0,"realized_kongs":0,
            }
            base={"score":report,"actions_until_terminal":50,
                  "terminal_phase":"wall_exhausted",
                  "opportunity":None}
            offered=target=="claim"
            options={}
            if offered:
                for policy in POLICIES[1:]:
                    sc=dict(report)
                    sc["official_net"]=4 if policy=="force_active" else 0
                    sc["win_points"]=sc["official_net"]
                    options[policy]={
                        "score":sc,"delta":{
                            k:sc[k]-report[k] for k in report},
                        "changed":policy=="force_active",
                        "reused_unchanged_baseline":policy=="force_pass",
                    }
            return {"seed":seed,"rotation":rotation,"challenge_seat":seat,
                    "target":target,"offered":offered,
                    "baseline":base,"alternatives":options}
        with patch(
            "mahtrain_core.ai_challenge_action_counterfactual._one",
            side_effect=fake_one):
            result=study(seeds_per_group=2)
        self.assertEqual(result["protocol"],PROTOCOL)
        self.assertFalse(result["live_policy_changed"])
        self.assertEqual(result["frozen_policies"],list(POLICIES))
        for cohort in ("development","holdout"):
            data=result[cohort]
            self.assertEqual(data["independent_seeds"],2)
            self.assertEqual(data["four_seat_positions"],8)
            self.assertEqual(data["target_positions"],16)
            self.assertEqual(data["targets"]["claim"]["offered_positions"],8)
            self.assertEqual(data["targets"]["own_kong"]["offered_positions"],0)
            a=data["targets"]["claim"]["policy_comparisons"]["force_active"]
            self.assertEqual(a["mean_seed_cluster_net_delta"],4)
            self.assertEqual(a["changed_positions"],8)
            self.assertIsNone(a["interval_95pct"])
            self.assertEqual(len(data["targets"]["claim"]["per_seed"]),2)


if __name__=="__main__":
    unittest.main()
