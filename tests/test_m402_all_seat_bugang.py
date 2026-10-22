"""M4.02: all-seat first/latest labels matched to actual official rob resolution."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_all_seat_bugang_audit import (
    PROTOCOL,observe_game,aggregate,study,
)
from mahtrain_core.ai_tournament import simulate_match


class M402AllSeatRiskAuditTests(unittest.TestCase):
    def _synthetic(self, *, first:int, last:int, robbed:bool,
                   two_winners:bool=False):
        """One physical public bu-gang; observer sees same key on two turns."""
        key={"type":"bu_gang","tile":"m9"}
        game=SimpleNamespace(
            phase="await_discard",turn=0,_won=[False]*4,
            kong_options=lambda seat:[key] if seat==0 else [],
            private_view=lambda seat:{
                "can_self_draw_win":False,"kong_options":[key],
            },
            public_state=lambda:{"phase":"await_discard","turn":0},
        )
        events=[{"type":"bu_gang_declared","seat":0,"tile":"m9"}]
        if robbed:
            events.append({"type":"rob_kong","seat":0,"tile":"m9",
                           "seats":[1,2] if two_winners else [1]})
        else:
            events.append({"type":"bu_gang","seat":0,"tile":"m9"})
        outcome={
            "public_events":events,
            "winners":([{"kind":"rob_kong","source":0,"seat":s}
                       for s in ([1,2] if two_winners else [1])]
                       if robbed else []),
            "official_settled_balances":[0,0,0,0],
            "partial_win_balances":[0,0,0,0],
            "official_kong_balances":[0,0,0,0],
            "official_exhaustive_balances":[0,0,0,0],
            "physical_count":108,"terminal_phase":"wall_exhausted",
        }
        band={"band":"unresolved","dingque_eligible_opponents":3}
        calls=[]
        def runner(seed,*,offline_observer,**kwargs):
            offline_observer(game)
            offline_observer(game)
            calls.append((seed,kwargs))
            return copy.deepcopy(outcome)
        with (patch("mahtrain_core.ai_all_seat_bugang_audit.simulate_match",
                    side_effect=runner),
              patch("mahtrain_core.ai_all_seat_bugang_audit.public_bugang_features",
                    return_value=band),
              patch("mahtrain_core.ai_all_seat_bugang_audit._sealed_potential_robbers",
                    side_effect=[first,last])):
            report=observe_game(28000,0)
        self.assertEqual(len(calls),1)
        return report

    def test_first_label_may_change_and_actual_uses_latest_prechoice_truth(self):
        row=self._synthetic(first=1,last=0,robbed=False)
        self.assertEqual(row["counts"]["first_distinct"],1)
        self.assertEqual(row["counts"]["repeated_candidate_windows"],1)
        self.assertEqual(row["counts"]["repeat_label_differs_from_first"],1)
        self.assertEqual(row["first_candidates"][0]["potential_robbers"],1)
        self.assertEqual(row["actual_bugang_decisions"][0]["potential_robbers"],0)
        self.assertEqual(row["actual_bugang_decisions"][0]["actual_robbed"],0)
        self.assertEqual(row["settlement_by_seat"][0]["successful_bu_gang"],1)
        raw=json.dumps(row)
        for leak in ("m9","opponent_hands","future_wall","_hands","offer_signature"):
            self.assertNotIn(leak,raw)

    def test_real_multi_ron_cannot_exceed_sealed_legal_opponents(self):
        row=self._synthetic(first=0,last=2,robbed=True,two_winners=True)
        self.assertEqual(row["first_candidates"][0]["rob_possible"],0)
        self.assertEqual(row["actual_bugang_decisions"][0]["rob_possible"],1)
        self.assertEqual(row["actual_bugang_decisions"][0]["actual_rob_winners"],2)
        self.assertEqual(row["settlement_by_seat"][0]["robbed_bu_gang"],1)
        with self.assertRaisesRegex(RuntimeError,"contradicts legal"):
            self._synthetic(first=0,last=1,robbed=True,two_winners=True)

    def test_actual_robbed_requires_preaction_positive_label(self):
        with self.assertRaisesRegex(RuntimeError,"contradicts legal"):
            self._synthetic(first=0,last=0,robbed=True)

    def test_actual_legal_robber_may_pass_in_real_game(self):
        row=self._synthetic(first=1,last=1,robbed=False)
        self.assertEqual(row["actual_bugang_decisions"][0][
            "legal_rob_possible_but_not_realized"],1)
        self.assertEqual(row["settlement_by_seat"][0]["successful_bu_gang"],1)

    def test_real_natural_game_is_readonly_and_uses_official_zero_sum(self):
        row=observe_game(28000,0)
        baseline=simulate_match(
            28000,rotation=0,
            lineup=row["seat_level"],offline_kong_base=1)
        self.assertEqual(row["official_net_by_seat"],
                         baseline["official_settled_balances"])
        self.assertEqual(row["terminal_phase"],baseline["terminal_phase"])
        self.assertEqual(len(row["actual_bugang_decisions"]),
                         sum(x["type"]=="bu_gang_declared"
                             for x in baseline["public_events"]))
        self.assertEqual(sum(row["official_net_by_seat"]),0)
        self.assertEqual(row["counts"].get("eligible_candidate_windows",0),
                         row["counts"].get("first_distinct",0)+
                         row["counts"].get("repeated_candidate_windows",0))
        raw=json.dumps(row,ensure_ascii=False)
        for private in ("opponent_hands","future_wall","_hands",
                        "offer_signature"):
            self.assertNotIn(private,raw)

    def test_all_seat_unselected_seed_clustering_is_explicit(self):
        def fake(seed,rotation):
            level=["challenge","advanced","basic","baseline"]
            return {
                "seed":seed,"rotation":rotation,
                "challenge_seat":(4-rotation)%4,
                "seat_level":level,"counts":{},
                "first_candidates":[],
                "actual_bugang_decisions":[],
                "settlement_by_seat":[],
                "official_net_by_seat":[0]*4,
                "terminal_phase":"wall_exhausted",
            }
        with patch("mahtrain_core.ai_all_seat_bugang_audit.observe_game",
                   side_effect=fake) as fn:
            x=aggregate(30000,2)
        self.assertEqual(fn.call_count,8)
        self.assertEqual(x["completed_games"],8)
        self.assertEqual(x["observed_seat_positions"],32)
        self.assertEqual(x["independent_initial_shuffle_seeds"],2)
        self.assertEqual(x["status"],"unestimable_no_candidates")
        self.assertEqual(x["counts"],{})
        self.assertEqual(x["estimated_rob_probability"],None)

    def test_four_seat_cohorts_strict_disjoint_and_not_exposure_selected(self):
        for kwargs in (
            {"holdout":28000},{"holdout":28007},
            {"development":29000},{"development":-1},
            {"seeds":0},{"seeds":13},{"seeds":True},
            {"development":True},{"holdout":2**32-2},
        ):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                study(**kwargs)
        with patch("mahtrain_core.ai_all_seat_bugang_audit.aggregate",
                   return_value={"independent_initial_shuffle_seeds":8}) as run:
            report=study()
        self.assertEqual(run.call_count,2)
        self.assertEqual(report["protocol"],PROTOCOL)
        self.assertEqual(report["sample_unit"],"independent_initial_shuffle_seed")
        self.assertFalse(report["live_policy_modified"])
        self.assertTrue(report["all_seats_observed"])
        self.assertEqual(report["development_seed_range"],[28000,28008])
        self.assertEqual(report["holdout_seed_range"],[29000,29008])


if __name__=="__main__":
    unittest.main()
