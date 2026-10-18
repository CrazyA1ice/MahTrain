"""M3.12 public-pressure same-state shadow checks and aggregate privacy."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.ai_pressure_diagnostics import diagnose_pressure_tiebreak
from mahtrain_core.ai_ablation_benchmark import (
    _pressure_totals, PRESSURE_POLICIES, PRESSURE_FIELDS,
    ablation_benchmark, ablation_lineup,
)
from mahtrain_core.ai_tournament import simulate_match


def view_and_oracle():
    hand = ["m1","m2","m3","m4","m5","m6","m7",
            "s1","s2","s3","s4","s5","s6","s7"]
    view = {
        "seat": 0, "hand": hand, "own_melds": [],
        "missing_suits": ["p","s","p","p"], "won": [False]*4,
        "melds": [[], [], [], []], "discards": [],
    }
    # All cuts have equal minimum shanten; m1,m2 have equal max ukeire.
    oracle = {"candidates": [
        {"discard": tile, "shanten": 0,
         "effective_tile_count": 10 if tile in ("m1","m2") else 1}
        for tile in hand
    ]}
    return view, oracle


class PressureDiagnosticsTests(unittest.TestCase):
    def test_shadow_ev_risk_changes_choice_without_exposing_alternative(self):
        view,oracle=view_and_oracle()
        ranked=[
            {"discard":"m2","expected_fan_weighted_copies":10.0,
             "effective_tile_count":10,"public_pressure":0,"score":10.0},
            {"discard":"m1","expected_fan_weighted_copies":10.0,
             "effective_tile_count":10,"public_pressure":2,"score":9.5},
        ]
        with patch("mahtrain_core.ai_pressure_diagnostics.challenge_discard_scores",
                   return_value=ranked):
            normal=diagnose_pressure_tiebreak(
                view,oracle,"m2",policy="challenge")
            disabled=diagnose_pressure_tiebreak(
                view,oracle,"m1",policy="challenge_no_pressure")
            with self.assertRaises(RuntimeError):
                diagnose_pressure_tiebreak(view,oracle,"m1",policy="challenge")
        self.assertEqual(normal,{
            "effective_tie":True,"public_pressure_present":True,
            "public_pressure_discriminates":True,
            "choice_would_change":True,"actual_choice_changed":True,
        })
        self.assertTrue(disabled["choice_would_change"])
        self.assertFalse(disabled["actual_choice_changed"])
        self.assertNotIn("alternative_tile",normal)

    def test_raw_ev_advantage_can_dominate_weak_public_risk(self):
        view,oracle=view_and_oracle()
        ranked=[
            {"discard":"m2","expected_fan_weighted_copies":20.0,
             "effective_tile_count":10,"public_pressure":1,"score":19.0},
            {"discard":"m1","expected_fan_weighted_copies":10.0,
             "effective_tile_count":10,"public_pressure":1,"score":9.5},
        ]
        with patch("mahtrain_core.ai_pressure_diagnostics.challenge_discard_scores",
                   return_value=ranked):
            normal=diagnose_pressure_tiebreak(
                view,oracle,"m2",policy="challenge")
            self.assertFalse(normal["effective_tie"])
            self.assertTrue(normal["public_pressure_present"])
            self.assertFalse(normal["public_pressure_discriminates"])
            self.assertFalse(normal["choice_would_change"])
            with self.assertRaises(ValueError):
                diagnose_pressure_tiebreak(view,oracle,"m2",policy="baseline")

    def test_aggregate_counts_and_observed_wins_are_not_claimed_causal(self):
        assignment=ablation_lineup(0)
        challenge_seat=assignment.index("challenge") if "challenge" in assignment else None
        # Rotation 0 excludes last policy, so use rotation with challenge.
        assignment=ablation_lineup(1)
        challenge_seat=assignment.index("challenge")
        no_pressure_seat=assignment.index("challenge_no_pressure")
        def event(seat,changed,actual):
            return {"action":"discard","seat":seat,"pressure_probe":{
                "effective_tie":True,
                "public_pressure_present":changed,
                "public_pressure_discriminates":changed,
                "choice_would_change":changed,
                "actual_choice_changed":actual,
            }}
        game={
            "assignment":assignment,
            "winners":[{"seat":challenge_seat,
                        "source":no_pressure_seat,"kind":"ron"}],
            "trace":[event(challenge_seat,True,True),
                     event(challenge_seat,False,False),
                     event(no_pressure_seat,True,False)],
        }
        totals=_pressure_totals([game])
        self.assertEqual(totals["challenge"]["decisions"],2)
        self.assertEqual(totals["challenge"]["would_change"],1)
        self.assertEqual(totals["challenge"]["actual_changed"],1)
        self.assertEqual(totals["challenge"]["games_with_would_change"],1)
        self.assertEqual(totals["challenge"]["wins_in_changed_games"],1)
        self.assertEqual(totals["challenge_no_pressure"]["deal_ins_in_changed_games"],1)
        self.assertEqual(totals["challenge_no_pressure"]["actual_changed"],0)
        self.assertEqual(set(totals["challenge"]),set(PRESSURE_FIELDS))
        self.assertEqual(set(totals),set(PRESSURE_POLICIES))

    def test_actual_closed_loop_trace_keeps_shadow_tile_private(self):
        # This also detects disagreement between the state-level oracle and
        # both actual discard policies, without modifying game outcomes.
        game=simulate_match(11,rotation=1,lineup=ablation_lineup(1))
        self.assertEqual(game["physical_count"],108)
        probes=[action["pressure_probe"] for action in game["trace"]
                if action.get("action")=="discard" and
                action.get("level") in PRESSURE_POLICIES]
        self.assertGreater(len(probes),0)
        self.assertTrue(all(set(p)=={
            "effective_tie","public_pressure_present",
            "public_pressure_discriminates","choice_would_change",
            "actual_choice_changed"} for p in probes))
        for frame in game["public_replay"]:
            self.assertNotIn("pressure_probe",frame["action"])
            self.assertNotIn("alternative_tile",str(frame))
        for action in game["trace"]:
            self.assertNotIn("alternative_tile",action)
            self.assertNotIn("shadow_tile",action)


if __name__=="__main__":
    unittest.main()
