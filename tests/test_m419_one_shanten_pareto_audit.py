"""M4.19 strict Pareto dominance and real authorized baseline-only study."""
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
from mahtrain_core.ai_one_shanten_pareto_audit import (
    PROTOCOL,OBJECTIVES,dominates,one_shanten_pareto,ParetoObservationAgent,
    audited_position,cohort,study,
)
from test_ai_calls import offer_kongs


def view():
    return {"hand":["m1","m2","m3","m4","m5","s1","s2","s3",
                    "s4","s5","s6","s7","s8","s9"]}


def cut(tile,copies=10,weighted=12.0,risk=.30,shanten=1):
    return {
        "discard":tile,"effective_tile_count":copies,
        "expected_fan_weighted_copies":weighted,
        "table_threat_index":risk,"shanten":shanten,
    }


class M419ParetoTests(unittest.TestCase):
    def test_three_proxy_directions_exact_no_threshold(self):
        self.assertEqual(OBJECTIVES,{
            "effective_tile_count":"maximize",
            "expected_fan_weighted_copies":"maximize",
            "table_threat_index":"minimize",
        })
        a=cut("m2",12,13,.29)
        b=cut("m1",10,12,.30)
        self.assertTrue(dominates(a,b))
        self.assertFalse(dominates(b,a))
        self.assertFalse(dominates(a,dict(a)))
        self.assertFalse(dominates(cut("m3",15,8,.20),b))

    def test_strictly_dominated_original_and_anonymous_margin(self):
        rows=[cut("m1"),cut("m2",12,13,.27),cut("m3",9,16,.22)]
        x=one_shanten_pareto("m1",rows,view())
        self.assertFalse(x["selected_nondominated"])
        self.assertEqual(x["dominating_alternatives"],1)
        self.assertEqual(x["pareto_frontier_count"],2)
        self.assertEqual(x["candidate_count"],3)
        self.assertEqual(x["maximum_dominator_copy_gain"],2)
        self.assertAlmostEqual(x["maximum_dominator_weighted_gain"],1)
        self.assertAlmostEqual(x["maximum_dominator_threat_reduction"],.03)
        for secret in ('"m1"','"m2"','"m3"','"discard"','"hand"'):
            self.assertNotIn(secret,json.dumps(x))

    def test_tradeoff_choices_are_nondominated_not_full_strict_improvement(self):
        rows=[cut("m1",10,12,.30),cut("m2",13,11,.31),
              cut("m3",8,15,.2),cut("m4",10,12,.30)]
        x=one_shanten_pareto("m1",rows,view())
        self.assertTrue(x["selected_nondominated"])
        self.assertEqual(x["dominating_alternatives"],0)
        self.assertEqual(x["pareto_frontier_count"],4)
        self.assertTrue(x["any_more_copies"])
        self.assertTrue(x["any_more_weighted_value"])
        self.assertTrue(x["any_lower_threat"])
        self.assertEqual(x["maximum_dominator_copy_gain"],0)

    def test_strict_gain_can_be_only_risk_or_only_weighted_value(self):
        for contender in (cut("m2",10,12,.29),cut("m2",10,13,.30),
                          cut("m2",11,12,.30)):
            with self.subTest(contender=contender):
                result=one_shanten_pareto(
                    "m1",[cut("m1"),contender],view())
                self.assertFalse(result["selected_nondominated"])
                self.assertEqual(result["dominating_alternatives"],1)

    def test_reject_noncurrent_rank_illegal_cut_or_noninteger_copies(self):
        invalid=[
            [cut("m1"),cut("m1",12,13,.1)],
            [cut("m1"),cut("p9",12,13,.1)],
            [cut("m1"),cut("m2",12,13,.1,shanten=2)],
            [cut("m1"),cut("m2",12.2,13,.1)],
            [cut("m1"),cut("m2",True,13,.1)],
            [cut("m1"),cut("m2",12,float("nan"),.1)],
            [cut("m1"),cut("m2",12,13,float("inf"))],
            [cut("m1"),cut("m2",12,13,-.01)],
        ]
        for rows in invalid:
            with self.subTest(rows=rows),self.assertRaises(RuntimeError):
                one_shanten_pareto("m1",rows,view())
        for original,rows in (
            ("m2",[cut("m1"),cut("m2")]),
            ("m1",[cut("m1",shanten=0),cut("m2",shanten=0)]),
            ("m1",[cut("m1")]),
        ):
            with self.assertRaises(ValueError):
                one_shanten_pareto(original,rows,view())

    def test_observation_preserves_original_cut_and_no_hidden_tiles(self):
        v=view()
        frozen=copy.deepcopy(v)
        agent=ParetoObservationAgent(seed=99,seat=0)
        agent._last_discard_scores=[cut("m1"),cut("m2",12,13,.27)]
        with patch("mahtrain_core.ai.MahjongAgent.discard",return_value="m1"):
            self.assertEqual(agent.discard(v),"m1")
        report=agent.safe_report()
        self.assertEqual(report["counts"]["one_shanten_multi"],1)
        self.assertEqual(report["counts"]["dominated"],1)
        self.assertEqual(report["counts"]["nondominated"],0)
        self.assertEqual(report["max_dominator_copy_gain"],2)
        self.assertEqual(v,frozen)
        for forbidden in ('"tile"','"hand"','"opponent_hands"',
                          '"_trace"','"future_wall"'):
            self.assertNotIn(forbidden,json.dumps(report))

    def test_no_cached_rank_early_singleton_creates_phantom_windows(self):
        agent=ParetoObservationAgent(seed=1,seat=0)
        v=view()
        agent._last_discard_scores=None
        with patch("mahtrain_core.ai.MahjongAgent.discard",return_value="m1"):
            self.assertEqual(agent.discard(v),"m1")
        summary=agent.safe_report()
        self.assertEqual(summary["counts"]["no_challenge_rank"],1)
        self.assertEqual(summary["counts"].get("one_shanten_multi",0),0)

    def test_true_108_physical_tiles_and_same_unmodified_challenge_cut(self):
        game,seat,v=offer_kongs()
        frozen=copy.deepcopy(v)
        agent=ParetoObservationAgent(seed=33,seat=seat)
        observed=agent.discard(v)
        reference=MahjongAgent("challenge",seed=33,seat=seat).discard(v)
        self.assertEqual(reference,observed)
        self.assertEqual(game.debug_tile_counts()["total"],108)
        self.assertEqual(v,frozen)
        self.assertEqual(agent.safe_report()["counts"]["total_cuts"],1)

    def test_one_actual_full_game_official_ledger_and_no_original_trace_export(self):
        p=audited_position(56000,0)
        self.assertEqual(p["seed"],56000)
        self.assertEqual(p["rotation"],0)
        self.assertEqual(p["candidate_actions_changed"],0)
        official=p["official"]
        self.assertEqual(official["official_net"],sum(official[k] for k in (
            "win_points","kong_points","exhaustive_points")))
        for forbidden in ('"hand"','"tile"','"future_wall"',
                          '"opponent_hands"','"_trace"','"_events"'):
            self.assertNotIn(forbidden,json.dumps(p))

    def test_synthetic_seed_cluster_dominated_fraction_not_4_independent(self):
        def fake(seed,rotation):
            dominated=int(seed==60000 and rotation==2)
            return {
                "seed":seed,"rotation":rotation,"challenge_seat":rotation,
                "observed":{
                    "counts":{
                        "total_cuts":4,"one_shanten_multi":2,
                        "dominated":dominated,"nondominated":2-dominated,
                        "total_legal_ranked_options":6,
                        "total_pareto_frontier_options":5,
                        "total_dominating_alternatives":dominated,
                    },
                    "max_dominator_copy_gain":dominated*3,
                    "max_dominator_weighted_gain":dominated*2.4,
                    "max_dominator_threat_reduction":dominated*.06,
                },
                "candidate_actions_changed":0,
            }
        with patch("mahtrain_core.ai_one_shanten_pareto_audit.audited_position",
                   side_effect=fake) as call:
            report=cohort(60000,2)
        self.assertEqual(call.call_count,8)
        self.assertEqual(report["independent_shuffle_seeds"],2)
        self.assertEqual(report["audited_real_games"],8)
        self.assertEqual(report["baseline_one_shanten_multiple_cut_windows"],16)
        self.assertEqual(report["selected_dominated_windows"],1)
        self.assertEqual(report["selected_nondominated_windows"],15)
        self.assertEqual(report["dominated_window_fraction"],round(1/16,5))
        self.assertEqual(report["per_seed"][0]["selected_dominated_windows"],1)
        self.assertEqual(report["per_seed"][1]["selected_dominated_windows"],0)
        self.assertEqual(report["largest_observed_dominator_margins"][
            "max_dominator_copy_gain"],3)

    def test_historical_and_new_blocks_are_distinct_and_observational(self):
        for kwargs in (
            {"seeds":True},{"seeds":0},{"seeds":9},
            {"fresh_development":56000},{"fresh_holdout":58003},
            {"historical_development":True},
            {"fresh_holdout":2**32-1},
        ):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                study(**kwargs)
        with patch("mahtrain_core.ai_one_shanten_pareto_audit.cohort",
                   side_effect=lambda start,seeds:{"start":start,
                                                    "seeds":seeds}) as run:
            report=study()
        self.assertEqual([x.args for x in run.call_args_list],[
            (56000,4),(57000,4),(58000,4),(59000,4)])
        self.assertEqual(report["protocol"],PROTOCOL)
        self.assertTrue(report["observational_only"])
        self.assertFalse(report["online_ai_modified"])


if __name__=="__main__":
    unittest.main()
