"""M4.04: joint legal call selection, Hu protection, full-settlement pairing."""
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
from mahtrain_core.ai_joint_optional_action_slate import (
    ARMS,PROTOCOL,JointSlateResearchAgent,optional_claim_slate,
    preferred_from_slate,preferred_optional_claim,_one,cohort,study,
)
from test_ai_calls import offer_peng


def dual_claim():
    g,seat,v=offer_peng()
    # The authoritative private view supports legal peng. This synthetic
    # option expansion merely isolates ranking between two authorized types
    # in a full-unit input; real official games are tested separately.
    view=copy.deepcopy(v)
    target=view["pending_discard"]["tile"]
    view["hand"].append(target)
    view["hand"].remove("m1")
    view["claim_options"]=["pass","peng","ming_gang"]
    return g,seat,view


class M404JointActionTests(unittest.TestCase):
    def test_real_peng_offer_outputs_only_legal_and_immutable_inputs(self):
        g,seat,v=offer_peng()
        before=copy.deepcopy(v)
        slate=optional_claim_slate(v)
        self.assertEqual(v,before)
        self.assertEqual({x["action"] for x in slate},{"pass","peng"})
        self.assertEqual(preferred_optional_claim(v),
                         preferred_from_slate(slate))
        self.assertIn(preferred_optional_claim(v),v["claim_options"])
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_hu_and_rob_hu_are_always_accepted(self):
        _,seat,v=offer_peng()
        v["claim_options"]=["pass","hu","peng"]
        self.assertEqual(preferred_optional_claim(v),"hu")
        self.assertEqual(optional_claim_slate(v),[{
            "action":"hu","admissible":True,"mandatory_win":True,
        }])
        with patch.object(MahjongAgent,"response",return_value="hu"):
            for arm in ARMS:
                agent=JointSlateResearchAgent(seed=42,seat=seat,arm=arm)
                self.assertEqual(agent.response(v),"hu")
                rob=copy.deepcopy(v)
                rob["phase"]="rob_kong_window"
                rob["rob_options"]=["pass","hu"]
                self.assertEqual(agent.response(rob,rob=True),"hu")
                self.assertEqual(agent.counts["selected_changed"],0)

    def test_both_peng_and_minggang_ranked_not_first_option_priority(self):
        _,seat,v=dual_claim()
        before=copy.deepcopy(v)
        def mocked(hand,melds,missing,public,cap,tian):
            if not melds:
                return {"shanten":1,"ukeire":8,"value":8,"tian_kept":False}
            if melds[-1]["type"]=="ming_gang":
                return {"shanten":1,"ukeire":7,"value":7,"tian_kept":False}
            return {"shanten":1,"ukeire":15,"value":15,"tian_kept":False}
        with patch("mahtrain_core.ai_joint_optional_action_slate._call_outlook",
                   side_effect=mocked),patch(
                   "mahtrain_core.ai_joint_optional_action_slate._cut_shanten",
                   return_value=1):
            slate=optional_claim_slate(v)
        self.assertEqual(v,before)
        self.assertEqual({x["action"] for x in slate},
                         {"pass","peng","ming_gang"})
        self.assertEqual(preferred_from_slate(slate),"peng")
        self.assertTrue(next(x for x in slate if x["action"]=="ming_gang")[
            "admissible"])
        self.assertTrue(next(x for x in slate if x["action"]=="peng")[
            "admissible"])

    def test_conservative_pass_when_kong_loses_shape_value(self):
        _,_,v=dual_claim()
        def fake(hand,melds,missing,public,cap,tian):
            if not melds:
                return {"shanten":1,"ukeire":10,"value":10,"tian_kept":False}
            if melds[-1]["type"]=="ming_gang":
                return {"shanten":1,"ukeire":8,"value":8,"tian_kept":False}
            return {"shanten":1,"ukeire":10,"value":10,"tian_kept":False}
        with patch("mahtrain_core.ai_joint_optional_action_slate._call_outlook",
                   side_effect=fake),patch(
                   "mahtrain_core.ai_joint_optional_action_slate._cut_shanten",
                   return_value=1):
            slate=optional_claim_slate(v)
        self.assertEqual(preferred_from_slate(slate),"pass")
        self.assertTrue(next(x for x in slate if x["action"]=="ming_gang")[
            "admissible"])
        # New surrogate prefers retaining more copies over unpriced Kong.
        self.assertGreater(next(x for x in slate if x["action"]=="pass")[
            "relative_value"],next(x for x in slate if x["action"]=="ming_gang")[
            "relative_value"])

    def test_tian_ting_never_surrenders_waits_for_peng(self):
        _,_,v=dual_claim()
        v["tian_ting"]={"eligible":True,"initial_waits":["m1"]}
        def fake(hand,melds,missing,public,cap,tian):
            return {"shanten":1,"ukeire":10,"value":10,"tian_kept":False}
        with patch("mahtrain_core.ai_joint_optional_action_slate._call_outlook",
                   side_effect=fake),patch(
                   "mahtrain_core.ai_joint_optional_action_slate._cut_shanten",
                   return_value=0):
            slate=optional_claim_slate(v)
        self.assertEqual(preferred_from_slate(slate),"pass")
        self.assertFalse(next(x for x in slate if x["action"]=="peng")[
            "admissible"])
        self.assertFalse(next(x for x in slate if x["action"]=="ming_gang")[
            "admissible"])

    def test_no_fake_hidden_future_wall_weight(self):
        _,_,v=offer_peng()
        before=preferred_optional_claim(v)
        polluted=copy.deepcopy(v)
        polluted["future_wall"]=["s9"]*50
        polluted["opponent_hands"]=[["s9"]*13]*3
        polluted["full_wall"]=["m1"]*55
        self.assertEqual(preferred_optional_claim(polluted),before)

    def test_own_kong_multiple_legal_choices_keep_proven_ranker(self):
        from test_ai_calls import offer_kongs
        g,seat,v=offer_kongs()
        for arm in ARMS:
            model=JointSlateResearchAgent(seed=42,seat=seat,arm=arm)
            decision=model.kong(v)
            reference=MahjongAgent("challenge",seed=42,seat=seat).kong(v)
            self.assertEqual(decision,reference)
            self.assertIn(decision,([None]+v["kong_options"]))
            self.assertEqual(model.counts["own_kong_candidates"],2)
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_real_paired_match_reconciles_official_ledger(self):
        row=_one(32000,0)
        self.assertEqual(set(row["arms"]),set(ARMS))
        for arm in ARMS:
            score=row["arms"][arm]["official"]
            self.assertEqual(score["official_net"],sum(score[k] for k in (
                "win_points","kong_points","exhaustive_points")))
            self.assertGreaterEqual(
                row["arms"][arm]["evaluation_elapsed_ms"],0)
        raw=json.dumps(row)
        for private in ("future_wall","opponent_hands","full_wall",
                        "offer_signature"):
            self.assertNotIn(private,raw)

    def test_independent_cluster_aggregation_does_not_create_false_interval(self):
        fake=[]
        def one(seed,rotation):
            a={"official":{k:0 for k in (
                "official_net","win_points","kong_points",
                "exhaustive_points","win_events","deal_in_events",
                "realized_kongs")},"counts":{}}
            b=copy.deepcopy(a)
            b["official"]["official_net"]=4
            b["official"]["win_points"]=4
            return {"seed":seed,"rotation":rotation,
                    "challenge_seat":(4-rotation)%4,
                    "arms":{"baseline":a,"joint_slate":b}}
        with patch("mahtrain_core.ai_joint_optional_action_slate._one",
                   side_effect=one) as run:
            result=cohort(35000,3)
        self.assertEqual(run.call_count,12)
        self.assertEqual(result["independent_shuffle_seeds"],3)
        self.assertEqual(result["full_games"],24)
        self.assertEqual(result["four_seat_pairs"],12)
        self.assertEqual(result["counterfactual_mean_seed_delta"],4)
        self.assertEqual(result["sum_official_component_deltas"]["official_net"],48)
        self.assertIsNone(result["confidence_interval_95pct"])

    def test_cohort_fixed_disjoint_even_when_just_testing_one_arm(self):
        for kwargs in (
            {"holdout":32000},{"holdout":32003},
            {"development":33000},{"seeds":0},{"seeds":9},
            {"seeds":True},{"development":True},
            {"holdout":2**32-2},
        ):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                study(**kwargs)
        with patch("mahtrain_core.ai_joint_optional_action_slate.cohort",
                   return_value={"independent_shuffle_seeds":4}) as run:
            report=study()
        self.assertEqual(run.call_count,2)
        self.assertEqual(report["protocol"],PROTOCOL)
        self.assertFalse(report["live_policy_modified"])


if __name__=="__main__":
    unittest.main()
