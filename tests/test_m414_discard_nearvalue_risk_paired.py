"""M4.14: public-risk near-value discard shadow, strict shape and score guards."""
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
from mahtrain_core.ai_discard_nearvalue_risk_paired import (
    ARMS,PROTOCOL,MIN_PUBLIC_THREAT_REDUCTION,MIN_VALUE_RETENTION,
    MIN_UKEIRE_RETENTION,suggest_nearvalue_defense,
    NearValueDefenseResearchAgent,paired_position,cohort,study,
)
from test_ai_calls import offer_kongs

def row(tile,risk,value=12,ukeire=10,shanten=1):
    return {"discard":tile,"shanten":shanten,
            "table_threat_index":risk,
            "expected_fan_weighted_copies":value,
            "effective_tile_count":ukeire}

def view():
    return {"hand":["m1","m2","m3","m4","m5","p1"],
            "tian_ting":{"eligible":False}}

class M414NearvalueDiscardTests(unittest.TestCase):
    def test_authorized_lower_public_risk_reuses_same_shanten_candidates(self):
        rows=[row("m1",.45,12,10),row("m2",.28,10,9),
              row("m3",.12,7,10)]
        self.assertEqual(suggest_nearvalue_defense("m1",rows,view()),
                         ("m2","lower_public_threat_nearvalue"))
        self.assertEqual(MIN_PUBLIC_THREAT_REDUCTION,.08)
        self.assertEqual(MIN_VALUE_RETENTION,.80)
        self.assertEqual(MIN_UKEIRE_RETENTION,.85)

    def test_cannot_sacrifice_fan_weighted_value_or_effective_copies(self):
        pairs=[
            [row("m1",.4,20,10),row("m2",.1,15,10)],
            [row("m1",.4,20,10),row("m2",.1,19,8)],
            [row("m1",.4,20,10),row("m2",.35,20,10)],
        ]
        for rows in pairs:
            with self.subTest(rows=rows):
                self.assertEqual(
                    suggest_nearvalue_defense("m1",rows,view())[0],"m1")

    def test_equal_thresholds_included_and_absolute_risk_not_probability(self):
        rows=[row("m1",1.8,10,20),
              row("m2",1.72,8,17)]
        self.assertEqual(suggest_nearvalue_defense("m1",rows,view())[0],"m2")

    def test_single_choice_and_preexisting_tian_ting_unchanged(self):
        self.assertEqual(suggest_nearvalue_defense("m1",None,view())[0],"m1")
        self.assertEqual(suggest_nearvalue_defense("m1",[row("m1",.1)],view())[0],
                         "m1")
        v=view();v["tian_ting"]={"eligible":True,"initial_waits":["m9"]}
        self.assertEqual(suggest_nearvalue_defense(
            "m1",[row("m1",.9),row("m2",.1)],v),
            ("m1","tian_ting_protected"))

    def test_invalid_ranks_worse_shanten_hidden_tile_and_nan_rejected(self):
        for rows in (
            [row("m1",.4),row("m2",.1,shanten=2)],
            [row("m1",.4),row("p9",.1)],
            [row("m1",.4),row("m1",.3)],
            [row("m1",.4),row("m2",float("nan"))],
            [row("m1",.4),row("m2",float("inf"))],
        ):
            with self.subTest(rows=rows),self.assertRaises(RuntimeError):
                suggest_nearvalue_defense("m1",rows,view())
        with self.assertRaises(RuntimeError):
            suggest_nearvalue_defense("m2",[row("m1",.5),row("m2",.1)],
                                      view())

    def test_choose_deterministically_when_multiple_alternatives(self):
        rows=[row("m1",.5,10,10),row("m2",.2,10,10),
              row("m3",.2,9,10),row("m4",.21,10,10)]
        a=suggest_nearvalue_defense("m1",rows,view())
        self.assertEqual(a[0],"m2")
        self.assertEqual(a,suggest_nearvalue_defense("m1",rows,view()))

    def test_real_authorized_view_108_tiles_and_baseline_integrity(self):
        game,seat,v=offer_kongs()
        frozen=copy.deepcopy(v)
        a=NearValueDefenseResearchAgent(seed=42,seat=seat,arm="baseline")
        b=NearValueDefenseResearchAgent(seed=42,seat=seat,
                                        arm="nearvalue_defense")
        ref=MahjongAgent("challenge",seed=42,seat=seat).discard(v)
        self.assertEqual(a.discard(v),ref)
        chosen=b.discard(v)
        self.assertIn(chosen,v["hand"])
        self.assertEqual(game.debug_tile_counts()["total"],108)
        self.assertEqual(v,frozen)
        self.assertEqual(a.safe_counts().get("actual_changes",0),0)
        self.assertNotIn("opponent_hands",json.dumps(a.safe_counts()))

    def test_frozen_ranked_surrogate_shadows_no_extra_evaluation(self):
        v=view()
        with patch("mahtrain_core.ai.MahjongAgent.discard",
                   return_value="m1"):
            b=NearValueDefenseResearchAgent(seed=42,seat=0,
                                            arm="nearvalue_defense")
            b._last_discard_scores=[row("m1",.8),row("m2",.2)]
            self.assertEqual(b.discard(v),"m2")
        self.assertEqual(b.safe_counts()["actual_changes"],1)
        self.assertEqual(b.safe_counts()["discard_decisions"],1)
        self.assertEqual(b.safe_counts()["multiple_minimum_shanten_cuts"],1)

    def test_one_true_full_match_official_ledger_and_no_trace_export(self):
        p=paired_position(52000,0)
        self.assertEqual((p["seed"],p["rotation"]),(52000,0))
        for arm in ARMS:
            score=p["arms"][arm]["official"]
            self.assertEqual(score["official_net"],sum(score[k] for k in
                ("win_points","kong_points","exhaustive_points")))
            self.assertIn(p["arms"][arm]["terminal_phase"],
                          ("finished","wall_exhausted"))
        if p["actual_interventions"]==0:
            self.assertTrue(p["identical_if_untouched"])
            self.assertTrue(all(v==0 for v in p["paired_deltas"].values()))
        dumped=json.dumps(p)
        for unsafe in ('"tile"','"hand"','"opponent_hands"','"future_wall"',
                       '"_trace"','"_events"'):
            self.assertNotIn(unsafe,dumped)

    def test_four_seats_are_not_four_independent_shuffle_seeds(self):
        def fake(seed,r):
            altered=int(seed==54000 and r==1)
            d={"official_net":altered*4,"win_points":altered*4,
               "kong_points":0,"exhaustive_points":0,
               "win_events":0,"deal_in_events":0,"realized_kongs":0}
            return {"seed":seed,"rotation":r,"challenge_seat":r,
                    "actual_interventions":altered,
                    "paired_deltas":d,
                    "arms":{"baseline":{"counts":{
                        "discard_decisions":3,
                        "multiple_minimum_shanten_cuts":2}},
                        "nearvalue_defense":{"counts":{
                            "actual_changes":altered,
                            "discard_decisions":3}}}}
        with patch("mahtrain_core.ai_discard_nearvalue_risk_paired.paired_position",
                   side_effect=fake) as run:
            report=cohort(54000,2)
        self.assertEqual(run.call_count,8)
        self.assertEqual(report["independent_shuffle_seeds"],2)
        self.assertEqual(report["complete_games"],16)
        self.assertEqual(report["actual_discard_interventions"],1)
        self.assertEqual(report["seeds_with_interventions"],1)
        self.assertEqual(report["mean_four_seat_official_net_delta"],.5)
        self.assertEqual(report["total_baseline_discards"],24)

    def test_new_disjoint_cohorts_and_full_offline_status(self):
        for kwargs in ({"seeds":0},{"seeds":9},{"seeds":True},
                       {"development":True},{"holdout":52000},
                       {"holdout":52003},{"holdout":2**32-1}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                study(**kwargs)
        with patch("mahtrain_core.ai_discard_nearvalue_risk_paired.cohort",
                   return_value={"independent_shuffle_seeds":4}) as call:
            report=study()
        self.assertEqual([c.args for c in call.call_args_list],
                         [(52000,4),(53000,4)])
        self.assertEqual(report["protocol"],PROTOCOL)
        self.assertFalse(report["online_policy_modified"])


if __name__=="__main__":
    unittest.main()
