"""M4.09: authorized prospective risk strata and real terminal Kong outcomes."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]
from mahtrain_core.ai import MahjongAgent
from mahtrain_core.ai_minggang_ledger_followthrough import MingGangFollowThroughAgent
from mahtrain_core.ai_minggang_prospective_strata import (
    PROTOCOL, cohort, natural_position, reconcile_prospective_risk, risk_band, study,
)
from test_m405_dual_claim_fastpath import real_dual_offer
from test_m408_minggang_ledger_followthrough import terminal_case


def offered(*, risk: float, choice: str, voided: bool = False,
            realized: bool = True):
    observer = MingGangFollowThroughAgent(seed=1234,seat=1)
    observer._dual_windows = [{
        "discard_index":1,"choice":choice,"wall_band":"early",
        "pre_tail_min_threat":risk,
    }]
    observer._risk_counts=Counter({"dual_windows":1,"original_"+choice:1})
    if realized:
        outcome,board=terminal_case(voided=voided)
        outcome["public_events"].insert(0,{
            "type":"discard","seat":0,"index":1,
        })
        board["discards"].insert(0,{"seat":0,"index":1})
    else:
        outcome={
            "terminal_phase":"wall_exhausted",
            "public_events":[{"type":"discard","seat":0,"index":1},
                             {"type":"all_pass"}],
            "official_kong_balances":[0]*4,
        }
        board={
            "phase":"wall_exhausted","discards":[{"seat":0,"index":1}],
            "kong_ledger":{"base":1,"zero_sum":True,"events":[],
                           "entries":[],"balances":[0]*4},
        }
    return observer,outcome,board


class M409ProspectiveMingGangTests(unittest.TestCase):
    def test_predeclared_boundary_bins_are_not_ron_probability(self):
        self.assertEqual([risk_band(v) for v in (0.0,.249,.25,.499,.5,1,2.46)],
                         ["low","low","mid","mid","high","high","high"])
        for v in (-.01,float("inf"),float("nan"),True,"0.2"):
            with self.subTest(v=v), self.assertRaises(ValueError):
                risk_band(v)

    def test_observed_low_bin_posts_exact_cash_when_no_actual_ron(self):
        a,g,b=offered(risk=.24,choice="ming_gang")
        c=reconcile_prospective_risk(a,g,b)
        self.assertEqual(c["dual_low"],1)
        self.assertEqual(c["low_awarded"],1)
        self.assertEqual(c["low_after_kong_discard"],1)
        self.assertEqual(c.get("low_actual_ron",0),0)
        self.assertEqual(c["awarded_nominal_cash"],2)
        self.assertEqual(c["awarded_final_cash"],2)
        self.assertEqual(c.get("selected_preempted",0),0)
        self.assertNotIn("tile",json.dumps(c))

    def test_actual_multi_ron_cancels_one_cash_not_two(self):
        a,g,b=offered(risk=.25,choice="ming_gang",voided=True)
        c=reconcile_prospective_risk(a,g,b)
        self.assertEqual(c["dual_mid"],1)
        self.assertEqual(c["mid_actual_ron"],1)
        self.assertEqual(c["actual_ron_winners"],2)
        self.assertEqual(c["awarded_nominal_cash"],2)
        self.assertEqual(c.get("awarded_final_cash",0),0)

    def test_no_award_cannot_be_conflated_with_safe_kong_exit(self):
        a,g,b=offered(risk=.52,choice="pass",realized=False)
        c=reconcile_prospective_risk(a,g,b)
        self.assertEqual(c["high_offer"],1)
        self.assertEqual(c.get("high_awarded",0),0)
        self.assertEqual(c.get("high_actual_ron",0),0)
        self.assertEqual(c["original_pass"],1)
        self.assertEqual(c.get("after_kong_discard",0),0)

    def test_selected_but_preempted_is_not_an_actual_kong(self):
        a,g,b=offered(risk=.1,choice="ming_gang",realized=False)
        c=reconcile_prospective_risk(a,g,b)
        self.assertEqual(c["selected"],1)
        self.assertEqual(c["selected_preempted"],1)
        self.assertEqual(c.get("awarded",0),0)

    def test_illegal_award_without_selection_and_fake_terminal_fail(self):
        a,g,b=offered(risk=.1,choice="peng",realized=True)
        with self.assertRaises(RuntimeError):
            reconcile_prospective_risk(a,g,b)
        a,g,b=offered(risk=.26,choice="ming_gang",voided=True)
        b["discards"][-1].pop("won_by")
        with self.assertRaises(RuntimeError):
            reconcile_prospective_risk(a,g,b)
        a,g,b=offered(risk=.26,choice="ming_gang")
        g["public_events"][1]["source"]=2
        with self.assertRaises(RuntimeError):
            reconcile_prospective_risk(a,g,b)

    def test_real_108_tile_dual_offer_unchanged_by_risk_observation(self):
        game,seat,view=real_dual_offer()
        initial=copy.deepcopy(view)
        a=MingGangFollowThroughAgent(seed=51,seat=seat)
        expected=MahjongAgent("challenge",seed=51,seat=seat).response(view)
        self.assertEqual(a.response(view),expected)
        self.assertEqual(view,initial)
        self.assertEqual(game.debug_tile_counts()["total"],108)
        self.assertEqual(len(a._dual_windows),1)

    def test_real_terminal_seed_reconciles_without_hidden_wall_export(self):
        pos=natural_position(42000,0)
        self.assertEqual(pos["seed"],42000)
        self.assertEqual(pos["rotation"],0)
        self.assertIn(pos["terminal_phase"],("finished","wall_exhausted"))
        self.assertEqual(pos["official"]["official_net"],sum(
            pos["official"][x] for x in
            ("win_points","kong_points","exhaustive_points")))
        raw=json.dumps(pos)
        for field in ('"hand"','"tile"',"opponent_hands","future_wall"):
            self.assertNotIn(field,raw)

    def test_independent_shuffle_cohort_and_disjoint_predeclared_ranges(self):
        def stub(s,r):
            return {"seed":s,"rotation":r,"challenge_seat":r,
                    "counts":{"dual_total":1,"low_offer":1,
                              "low_awarded":1,"awarded":1,
                              "low_after_kong_discard":1,
                              "after_kong_discard":1,
                              "low_actual_ron":int(r==0),
                              "actual_ron":int(r==0)}}
        with patch("mahtrain_core.ai_minggang_prospective_strata.natural_position",
                   side_effect=stub) as mocked:
            data=cohort(42000,2)
        self.assertEqual(mocked.call_count,8)
        self.assertEqual(data["independent_shuffle_seeds"],2)
        self.assertEqual(data["four_seat_positions"],8)
        self.assertEqual(data["distinct_seeds_with_actual_ron"],2)
        self.assertIsNone(data["calibrated_ron_probability"])
        for invalid in (
            {"seeds":0},{"seeds":13},{"seeds":True},
            {"holdout":42000},{"holdout":42007},
            {"development":True},{"holdout":2**32-1},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                study(**invalid)
        with patch("mahtrain_core.ai_minggang_prospective_strata.cohort",
                   return_value={"independent_shuffle_seeds":8}) as mocked:
            out=study()
        self.assertEqual([x.args for x in mocked.call_args_list],
                         [(42000,8),(43000,8)])
        self.assertFalse(out["online_policy_modified"])
        self.assertEqual(out["protocol"],PROTOCOL)


if __name__=="__main__":
    unittest.main()
