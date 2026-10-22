"""M3.99: prevent repeated-bu-gang pseudo samples and reconcile robbed kongs."""
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
from mahtrain_core.ai_bugang_repeat_risk import (
    PROTOCOL, SameTileAuditAgent, _audited_public_bugang,
    natural_position, natural_cohort, first_own_kong_cohort, study,
)
from mahtrain_core.ai_challenge_action_counterfactual import METRICS
from test_ai_calls import offer_kongs


def view_for_repeat():
    _,seat,view=offer_kongs()
    v=copy.deepcopy(view)
    v["kong_options"]=[
        {"type":"bu_gang","tile":"p4"},
        {"type":"an_gang","tile":"m1"},
    ]
    v["can_self_draw_win"]=False
    return seat,v


class M399RepeatAndRobAuditTests(unittest.TestCase):
    def test_same_tile_repeat_counts_across_turns_and_return_after_gap(self):
        seat,view=view_for_repeat()
        agent=SameTileAuditAgent(seed=42,seat=seat)
        before=copy.deepcopy(view)
        # Focus on *observation*, not on synthetic private-hand scoring.
        with patch.object(MahjongAgent,"kong",return_value=None):
            for _ in range(3):
                agent.kong(view)
            other=copy.deepcopy(view)
            other["kong_options"]=[]
            agent.kong(other)
            agent.kong(view)
        c=agent.counts
        self.assertEqual(c["distinct_bu_gang_tiles"],1)
        self.assertEqual(c["distinct_an_gang_tiles"],1)
        self.assertEqual(c["repeat_bu_gang_candidate_windows"],3)
        self.assertEqual(c["repeat_an_gang_candidate_windows"],3)
        self.assertEqual(c["returned_after_gap_bu_gang"],1)
        self.assertEqual(c["returned_after_gap_an_gang"],1)
        self.assertEqual(c["own_kong_offer_bu_gang"],4)
        self.assertEqual(c["own_kong_offer_an_gang"],4)
        self.assertEqual(c["own_kong_windows"],4)
        self.assertEqual(view,before)
        self.assertNotIn("p4",str(c))
        self.assertNotIn("m1",str(c))
        self.assertNotIn("opponent_hands",str(c))

    def test_hu_opportunity_never_inflates_optional_kong_counts(self):
        seat,view=view_for_repeat()
        agent=SameTileAuditAgent(seed=42,seat=seat)
        winning=copy.deepcopy(view)
        winning["can_self_draw_win"]=True
        with patch.object(MahjongAgent,"kong",return_value=None):
            agent.kong(winning)
        self.assertEqual(agent.counts["distinct_bu_gang_tiles"],0)
        self.assertEqual(agent.counts["own_kong_windows"],0)

    def test_rob_bugang_is_not_successfully_posted_and_multi_ron_is_one_attempt(self):
        rows=[
            {"type":"bu_gang_declared","seat":1,"tile":"p4"},
            {"type":"rob_kong","seat":1,"tile":"p4","seats":[0,3]},
            {"type":"bu_gang_declared","seat":1,"tile":"p5"},
            {"type":"bu_gang","seat":1,"tile":"p5"},
        ]
        game={"public_events":rows,
              "winners":[
                 {"seat":0,"source":1,"kind":"rob_kong"},
                 {"seat":3,"source":1,"kind":"rob_kong"},
              ]}
        self.assertEqual(_audited_public_bugang(game,1),{
            "attempted_bu_gang":2,
            "successful_bu_gang":1,
            "robbed_bu_gang":1,
            "rob_kong_winners":2,
        })
        with self.assertRaisesRegex(RuntimeError,"settle"):
            _audited_public_bugang(
                {**game,"public_events":rows[:1]},1)
        with self.assertRaisesRegex(RuntimeError,"reconcile"):
            _audited_public_bugang(
                {**game,"winners":[]},1)
        self.assertEqual(
            _audited_public_bugang(game,2)["attempted_bu_gang"],0)

    def test_rob_hu_only_counts_authorized_active_own_view(self):
        seat,view=view_for_repeat()
        agent=SameTileAuditAgent(seed=42,seat=seat)
        rob=copy.deepcopy(view)
        rob["phase"]="rob_kong_window"
        rob["rob_options"]=["pass","hu"]
        with patch.object(MahjongAgent,"response",return_value="hu"):
            chosen=agent.response(rob,rob=True)
        self.assertEqual(chosen,"hu")
        self.assertEqual(agent.counts["opponent_bugang_rob_hu_available"],1)
        self.assertEqual(agent.counts["opponent_bugang_rob_hu_taken"],1)
        self.assertEqual(agent.counts["claim_windows"],0)

    def test_one_natural_game_official_ledger_and_zero_private_export(self):
        trial=natural_position(20000,0)
        self.assertEqual(trial,natural_position(20000,0))
        self.assertEqual(trial["challenge_seat"],0)
        score=trial["official_score"]
        self.assertEqual(score["official_net"],
                         score["win_points"]+score["kong_points"]+
                         score["exhaustive_points"])
        c=trial["counts"]
        for kind in ("an_gang","bu_gang"):
            self.assertEqual(c.get("own_kong_offer_"+kind,0),
                             c.get("distinct_"+kind+"_tiles",0)+
                             c.get("repeat_"+kind+"_candidate_windows",0))
        self.assertEqual(c.get("attempted_bu_gang",0),
                         c.get("successful_bu_gang",0)+
                         c.get("robbed_bu_gang",0))
        self.assertNotIn("future_wall",json.dumps(trial))
        self.assertNotIn("opponent_hands",json.dumps(trial))
        self.assertNotIn("p4",json.dumps(trial))

    def test_complete_four_seat_natural_seed_group_is_unselected(self):
        mock=[]
        def fake(seed,rotation):
            seat=(4-rotation)%4
            c={
                "own_kong_offer_bu_gang":4,
                "distinct_bu_gang_tiles":1,
                "repeat_bu_gang_candidate_windows":3,
                "returned_after_gap_bu_gang":1,
                "own_kong_windows":4,
                "attempted_bu_gang":1,
                "successful_bu_gang":1,
            } if seat==0 else {}
            mock.append((seed,rotation))
            return {"seed":seed,"rotation":rotation,"challenge_seat":seat,
                    "counts":c,"official_score":{},"terminal_phase":"finished"}
        with patch("mahtrain_core.ai_bugang_repeat_risk.natural_position",
                   side_effect=fake):
            cohort=natural_cohort(24000,2)
        self.assertEqual(len(mock),8)
        self.assertEqual(cohort["four_seat_positions"],8)
        self.assertEqual(cohort["total_counts"]["own_kong_offer_bu_gang"],8)
        self.assertEqual(cohort["total_counts"]["distinct_bu_gang_tiles"],2)
        self.assertEqual(cohort["total_counts"]["repeat_bu_gang_candidate_windows"],6)
        self.assertEqual([x["seed"] for x in cohort["per_seed"]],
                         [24000,24001])

    def test_first_kong_paired_cohort_seed_cluster_reporting_and_missing_opps(self):
        def fake(seed,rotation,target):
            self.assertEqual(target,"own_kong")
            offered=rotation==0
            base={"score":{metric:0 for metric in METRICS},
                  "opportunity":{"options":["pass","bu_gang#1"],
                                 "original_is_pass":True} if offered else None}
            alts={}
            if offered:
                for arm in ("force_pass","force_active"):
                    pts=5 if arm=="force_active" else 0
                    score={metric:0 for metric in METRICS}
                    score["official_net"]=score["win_points"]=pts
                    alts[arm]={
                        "delta":score,"changed":arm=="force_active",
                    }
            return {
                "seed":seed,"rotation":rotation,
                "challenge_seat":(4-rotation)%4,
                "target":target,"offered":offered,
                "baseline":base,"alternatives":alts,
            }
        with patch("mahtrain_core.ai_bugang_repeat_risk._one",
                   side_effect=fake) as run:
            cohort=first_own_kong_cohort(25000,3)
        self.assertEqual(run.call_count,12)
        self.assertEqual(cohort["four_seat_positions"],12)
        self.assertEqual(cohort["arms"]["force_active"]["offered_positions"],3)
        self.assertEqual(cohort["arms"]["force_active"]["changed_positions"],3)
        self.assertEqual(cohort["arms"]["force_active"]["mean_seed_cluster_net_delta"],1.25)
        self.assertEqual(
            cohort["arms"]["force_active"]["candidate_types"],
            {"first_active_offer_bu_gang":3,
             "changed_first_active_offer_bu_gang":3})
        self.assertIsNone(cohort["arms"]["force_active"]["confidence_interval_95pct"])

    def test_seed_ranges_disjoint_and_not_curated_for_bugang_presence(self):
        for kwargs in (
            {"natural_development":21000},
            {"paired_development":21000},
            {"paired_holdout":22000},
            {"natural_development":2**32-3},
            {"seeds_per_group":17},{"seeds_per_group":0},
            {"seeds_per_group":True},{"mode":"wrong"},
        ):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                study(**kwargs)
        with patch("mahtrain_core.ai_bugang_repeat_risk.natural_cohort",
                   return_value={"independent_seeds":8}) as natural,patch(
                "mahtrain_core.ai_bugang_repeat_risk.first_own_kong_cohort",
                return_value={"independent_seeds":8}) as paired:
            report=study(mode="all")
        self.assertEqual(natural.call_count,2)
        self.assertEqual(paired.call_count,2)
        self.assertFalse(report["live_ai_modified"])
        self.assertEqual(report["protocol"],PROTOCOL)


if __name__=="__main__":
    unittest.main()
