"""M4.20 exact tests for bounded, legal, public-only second-draw search."""
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
from mahtrain_core.ai_bounded_public_lookahead_paired import (
    PROTOCOL,ARMS,MAX_INITIAL_CUTS,MAX_DRAW_TYPES_PER_CUT,
    MAX_RESEARCH_WINDOWS_PER_MATCH,MIN_PUBLIC_WALL,
    MIN_EFFECTIVE_COPIES_RETENTION,MAX_PUBLIC_THREAT_INCREASE,
    MIN_PROJECTED_SCORE_GAIN,next_discard_wait_value,
    projected_branch_score,frozen_lookahead_decision,
    BoundedLookaheadResearchAgent,paired_position,cohort,study,
)
from test_ai_calls import offer_kongs


def sample_view():
    return {
        "hand":["m1","m2","m3","m4","m5","m6","m7","m8","m9",
                "s1","s2","s3","s4","s5"],
        "wall_count":35,"seat":0,"tian_ting":{"eligible":False},
        "win_ledger":{"fan_cap":3},
    }


def ranked():
    return [
        {"discard":"m1","shanten":1,"effective_tile_count":16,
         "table_threat_index":.20},
        {"discard":"m2","shanten":1,"effective_tile_count":13,
         "table_threat_index":.25},
        {"discard":"m3","shanten":1,"effective_tile_count":9,
         "table_threat_index":.18},
    ]


def branch(proxy):
    return {
        "proxy":proxy,"draw_types":4,"draw_copy_mass":11,
        "all_effective_copies":16,"second_cuts_checked":32,
        "coverage_fraction":.6875,
    }


class M420BoundedPublicSearchTests(unittest.TestCase):
    def test_all_resource_budgets_are_frozen_and_finite(self):
        self.assertEqual(MAX_INITIAL_CUTS,2)
        self.assertEqual(MAX_DRAW_TYPES_PER_CUT,6)
        self.assertEqual(MAX_RESEARCH_WINDOWS_PER_MATCH,2)
        self.assertEqual(MIN_PUBLIC_WALL,12)
        self.assertEqual(MIN_EFFECTIVE_COPIES_RETENTION,.70)
        self.assertEqual(MAX_PUBLIC_THREAT_INCREASE,.12)
        self.assertEqual(MIN_PROJECTED_SCORE_GAIN,1.12)

    def test_isolated_better_second_step_scores_without_future_wall(self):
        v=sample_view()
        saved=copy.deepcopy(v)
        with patch(
            "mahtrain_core.ai_bounded_public_lookahead_paired.projected_branch_score",
            side_effect=lambda _,cut:branch(115 if cut=="m2" else 100)
        ) as call:
            selected,why,work=frozen_lookahead_decision(v,ranked(),"m1")
        self.assertEqual((selected,why),
                         ("m2","better_bounded_next_wait_proxy"))
        self.assertEqual(call.call_count,2)
        self.assertEqual(work,{"evaluated_first_cuts":2,
                               "draw_branches":8,"second_cuts":64})
        self.assertEqual(v,saved)

    def test_requires_explicit_gain_and_no_regressing_public_copy_or_risk(self):
        v=sample_view()
        for gain,expected in ((111,"m1"),(112,"m2"),(150,"m2")):
            with self.subTest(gain=gain),patch(
                "mahtrain_core.ai_bounded_public_lookahead_paired.projected_branch_score",
                side_effect=lambda _,cut:branch(gain if cut=="m2" else 100)
            ):
                self.assertEqual(
                    frozen_lookahead_decision(v,ranked(),"m1")[0],expected)
        rows=ranked()
        rows[1]["effective_tile_count"]=10
        with patch(
            "mahtrain_core.ai_bounded_public_lookahead_paired.projected_branch_score",
            side_effect=AssertionError("candidate fails filter")
        ):
            self.assertEqual(frozen_lookahead_decision(
                v,rows,"m1")[1],"no_publicly_guarded_second_cut")
        rows=ranked()
        rows[1]["table_threat_index"]=.34
        with patch(
            "mahtrain_core.ai_bounded_public_lookahead_paired.projected_branch_score",
            side_effect=AssertionError("candidate fails risk")
        ):
            self.assertEqual(frozen_lookahead_decision(
                v,rows,"m1")[0],"m1")

    def test_tian_ting_and_wall_exhaustion_guard_against_any_search(self):
        v=sample_view()
        for change,expected in (
            ({"wall_count":11},"short_wall"),
            ({"tian_ting":{"eligible":True}},"verified_tian_ting"),
        ):
            now=dict(v,**change)
            with patch(
                "mahtrain_core.ai_bounded_public_lookahead_paired.projected_branch_score",
                side_effect=AssertionError("forbidden")
            ):
                self.assertEqual(
                    frozen_lookahead_decision(now,ranked(),"m1")[1],expected)

    def test_wrong_stage_and_single_ranking_skip_all_branches(self):
        v=sample_view()
        rows=ranked()
        rows[0]["shanten"]=0
        self.assertEqual(frozen_lookahead_decision(
            v,rows,"m1")[1],"not_one_shanten")
        self.assertEqual(frozen_lookahead_decision(
            v,ranked()[:1],"m1")[1],"no_multi_minimum_rank")

    def test_bounded_first_two_cut_source_validated_no_illegal_deeper_row(self):
        v=sample_view()
        for issue in (
            dict(ranked()[2],discard="p9"),
            dict(ranked()[2],discard="m1"),
            dict(ranked()[2],shanten=2),
            dict(ranked()[2],effective_tile_count=3.5),
            dict(ranked()[2],table_threat_index=float("nan")),
        ):
            with self.subTest(issue=issue),self.assertRaises(RuntimeError):
                frozen_lookahead_decision(
                    v,[*ranked()[:2],issue],"m1")
        with self.assertRaises(RuntimeError):
            frozen_lookahead_decision(v,ranked(),"m2")

    def test_branch_uses_sorted_visible_copy_weights_with_six_type_cap(self):
        v=sample_view()
        v["own_melds"]=[]
        v["missing_suits"]=["p","p","p","p"]
        v["melds"]=[[],[],[],[]]
        v["discards"]=[]
        v["won"]=[False]*4
        effective={
            "shanten":1,
            "effective_tile_count":18,
            "effective_details":[
                {"tile":f"m{x}","remaining":4} for x in range(1,8)
            ],
        }
        # Here the mocked effective_tile_count has to match physical weight
        # budget; coverage=24 and total count 28 for seven types.
        effective["effective_tile_count"]=28
        with patch(
            "mahtrain_core.ai_bounded_public_lookahead_paired.effective_draws",
            return_value=effective
        ),patch(
            "mahtrain_core.ai_bounded_public_lookahead_paired.next_discard_wait_value",
            return_value=(5.0,7)
        ) as next_cut:
            x=projected_branch_score(v,"s5")
        self.assertEqual(next_cut.call_count,6)
        self.assertEqual(x["draw_types"],6)
        self.assertEqual(x["draw_copy_mass"],24)
        self.assertEqual(x["second_cuts_checked"],42)
        self.assertEqual(x["proxy"],120.0)
        self.assertAlmostEqual(x["coverage_fraction"],round(24/28,5))

    def test_best_next_cut_uses_real_scoring_multiplier_without_oracle(self):
        first=["m1"]*1 + ["m2"]*2+["m3"]*2 + ["s1"]*2+[
            "s2","s3","s4","s5","s6","s7"]
        self.assertEqual(len(first),13)
        with patch(
            "mahtrain_core.ai_bounded_public_lookahead_paired.shanten_13",
            side_effect=lambda remaining,*args:(
                0 if remaining.count("m1")==0 else 1)
        ),patch(
            "mahtrain_core.ai_bounded_public_lookahead_paired.effective_draws",
            return_value={"effective_details":[
                {"tile":"m9","remaining":3}]}
        ),patch(
            "mahtrain_core.ai_bounded_public_lookahead_paired.score_win",
            return_value={"legal":True,"multiplier":4}
        ):
            value,cuts=next_discard_wait_value(
                first,"s9",[],"p",["m8"],3)
        self.assertGreaterEqual(cuts,1)
        self.assertEqual(value,12.0)

    def test_agent_stays_offline_baseline_exact_ranking_and_match_budget(self):
        v=sample_view()
        a=BoundedLookaheadResearchAgent(seed=9,seat=0,arm="baseline")
        b=BoundedLookaheadResearchAgent(
            seed=9,seat=0,arm="bounded_two_transition")
        with patch("mahtrain_core.ai.MahjongAgent.discard",return_value="m1"), \
             patch(
                "mahtrain_core.ai_bounded_public_lookahead_paired.projected_branch_score",
                side_effect=lambda _,cut:branch(140 if cut=="m2" else 100)
            ):
            for index in range(4):
                a._last_discard_scores=ranked()
                b._last_discard_scores=ranked()
                self.assertEqual(a.discard(v),"m1")
                outcome=b.discard(v)
                self.assertEqual(outcome,"m2" if index<2 else "m1")
        self.assertEqual(a.safe_counts().get("actual_changes",0),0)
        self.assertEqual(b.safe_counts()["actual_changes"],2)
        self.assertEqual(b.safe_counts()["budget_skips"],2)
        self.assertLessEqual(b.safe_counts()["first_cuts_checked"],4)
        self.assertLessEqual(b.safe_counts()["draw_branches"],24)
        self.assertTrue(b._offline_reference_cut)

    def test_real_108_tile_unchanged_authorized_challenge(self):
        game,seat,view=offer_kongs()
        probe=BoundedLookaheadResearchAgent(
            seed=72,seat=seat,arm="baseline")
        result=probe.discard(view)
        reference=MahjongAgent("challenge",seed=72,seat=seat).discard(view)
        self.assertEqual(result,reference)
        self.assertIn(result,view["hand"])
        self.assertEqual(game.debug_tile_counts()["total"],108)
        self.assertNotIn('"future_wall"',json.dumps(probe.safe_counts()))

    def test_one_real_paired_official_game_and_no_secret_export(self):
        result=paired_position(60000,0)
        for arm in ARMS:
            money=result["arms"][arm]["official"]
            self.assertEqual(money["official_net"],sum(money[k] for k in
                            ("win_points","kong_points","exhaustive_points")))
        if not result["actual_interventions"]:
            self.assertEqual(result["official_deltas"]["official_net"],0)
        raw=json.dumps(result)
        for forbidden in ('"hand"','"tile"','"future_wall"',
                          '"opponent_hands"','"_trace"','"_events"'):
            self.assertNotIn(forbidden,raw)

    def test_independent_cluster_aggregation_with_frozen_study_seeds(self):
        def fake(seed,rotation):
            value=1 if seed==62000 and rotation==1 else 0
            d=dict.fromkeys(
                ("official_net","win_points","kong_points",
                 "exhaustive_points","win_events",
                 "deal_in_events","realized_kongs"),0)
            d["official_net"]=200*value
            d["win_points"]=200*value
            return {
                "seed":seed,"rotation":rotation,
                "challenge_seat":rotation,"actual_interventions":value,
                "official_deltas":d,
                "arms":{"baseline":{"counts":{"total_discards":8}},
                        "bounded_two_transition":{"counts":{
                            "actual_changes":value}}},
            }
        with patch("mahtrain_core.ai_bounded_public_lookahead_paired.paired_position",
                   side_effect=fake) as run:
            data=cohort(62000,2)
        self.assertEqual(run.call_count,8)
        self.assertEqual(data["independent_shuffles"],2)
        self.assertEqual(data["complete_official_games"],16)
        self.assertEqual(data["candidate_action_changes"],1)
        self.assertEqual(data["affected_seed_clusters"],1)
        self.assertEqual(data["per_seed"][0]["mean_seat_net_delta"],50)
        with patch("mahtrain_core.ai_bounded_public_lookahead_paired.cohort",
                   side_effect=lambda a,b:{"start":a,"seeds":b}) as cohort_run:
            research=study()
        self.assertEqual([x.args for x in cohort_run.call_args_list],
                         [(60000,3),(61000,3)])
        self.assertEqual(research["protocol"],PROTOCOL)
        self.assertFalse(research["online_ai_modified"])

    def test_invalid_seed_or_research_arm_rejected(self):
        with self.assertRaises(ValueError):
            BoundedLookaheadResearchAgent(seed=42,seat=0,arm="unsafe")
        for seed,rotation in ((True,0),(-1,0),(2**32,0),
                              (60000,4),(60000,True)):
            with self.subTest(seed=seed,rotation=rotation),self.assertRaises(ValueError):
                paired_position(seed,rotation)
        for seed,count in ((True,3),(60000,True),(60000,0),
                           (60000,7),(2**32-2,3)):
            with self.subTest(seed=seed,count=count),self.assertRaises(ValueError):
                cohort(seed,count)


if __name__=="__main__":
    unittest.main()
