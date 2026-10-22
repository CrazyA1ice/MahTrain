"""M3.98: natural non-selected operation exposure and honest seed-cluster comparisons."""
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
from mahtrain_core.ai_action_extended_study import (
    PROTOCOL, NaturalOpportunityAgent, _coverage_pair,
    natural_coverage, paired_cohort, study,
)
from mahtrain_core.ai_challenge_action_counterfactual import (
    TARGETS,POLICIES,METRICS,
)
from test_ai_calls import offer_peng,offer_kongs


class M398UnselectedActionStudyTests(unittest.TestCase):
    def test_every_legal_claim_observed_but_original_action_not_mutated(self):
        _,seat,view=offer_peng()
        before=copy.deepcopy(view)
        policy=NaturalOpportunityAgent(seed=42,seat=seat)
        true_choice=MahjongAgent("challenge",seed=42,seat=seat).response(view)
        self.assertEqual(policy.response(view),true_choice)
        self.assertEqual(policy.response(view),true_choice)
        self.assertEqual(policy.counts["claim_windows"],2)
        self.assertEqual(policy.counts["claim_offer_peng"],2)
        self.assertEqual(view,before)
        self.assertNotIn("hand",str(policy.counts))
        self.assertNotIn("tile",str(policy.counts))
        self.assertNotIn("future_wall",str(policy.counts))
        self.assertNotIn("opponent_hands",str(policy.counts))
        hu=copy.deepcopy(view)
        hu["claim_options"]=[*hu["claim_options"],"hu"]
        self.assertEqual(policy.response(hu),"hu")
        self.assertEqual(policy.counts["claim_windows"],2,
                         "winning responses must NOT enter voluntary-claim sample")

    def test_track_each_own_kong_candidate_not_only_first(self):
        _,seat,view=offer_kongs()
        observer=NaturalOpportunityAgent(seed=42,seat=seat)
        baseline=MahjongAgent("challenge",seed=42,seat=seat).kong(view)
        self.assertEqual(observer.kong(view),baseline)
        self.assertEqual(observer.counts["own_kong_windows"],1)
        self.assertEqual(observer.counts["own_kong_offer_an_gang"],2)
        self.assertEqual(observer.counts["own_kong_window_with_an_gang"],1)
        self.assertEqual(observer.counts["own_kong_simultaneous_choices"],1)
        self.assertEqual(sum(observer.counts[
            "own_kong_original_"+k] for k in ("pass","an_gang","bu_gang")),1)
        winning=copy.deepcopy(view)
        winning["can_self_draw_win"]=True
        observer.kong(winning)
        self.assertEqual(observer.counts["own_kong_windows"],1)

    def test_one_actual_game_has_exact_authoritative_ledgers(self):
        result=_coverage_pair(16000,0)
        self.assertEqual(result,_coverage_pair(16000,0))
        self.assertEqual(result["challenge_seat"],0)
        self.assertEqual(result["official_score"]["official_net"],
                         sum(result["official_score"][key] for key in (
                             "win_points","kong_points","exhaustive_points")))
        self.assertNotIn("hand",json.dumps(result))
        self.assertNotIn("future_wall",json.dumps(result))
        self.assertNotIn("opponent_hands",json.dumps(result))

    def test_natural_consecutive_seeds_include_all_four_seats_and_zero_offer(self):
        def fake(seed,rotation):
            seat=(4-rotation)%4
            ct=({
                "claim_windows":1,"claim_early":1,"claim_original_pass":1,
                "claim_offer_peng":1,
            } if seat==0 else {
                "own_kong_windows":2 if seat==1 else 0,
                "own_kong_critical":2 if seat==1 else 0,
                "own_kong_original_pass":2 if seat==1 else 0,
                "own_kong_offer_an_gang":2 if seat==1 else 0,
            })
            return {
                "seed":seed,"rotation":rotation,"challenge_seat":seat,
                "counts":ct,
                "official_score":{"official_net":0},
                "terminal_phase":"wall_exhausted",
            }
        with patch("mahtrain_core.ai_action_extended_study._coverage_pair",
                   side_effect=fake) as mocked:
            result=natural_coverage(20000,3)
        self.assertEqual(mocked.call_count,12)
        self.assertEqual(result["positions_with_own_kong"],3)
        self.assertEqual(result["positions_with_claim"],3)
        self.assertEqual(result["four_seat_positions"],12)
        self.assertEqual([x["seed"] for x in result["per_seed"]],
                         [20000,20001,20002])
        self.assertEqual(result["total_counts"]["own_kong_windows"],6)
        self.assertTrue(all(x["with_own_kong_opportunity"]==1
                            for x in result["per_seed"]))

    def test_noncherry_picked_paired_seed_group_and_public_strata(self):
        def fake(seed,rotation,target):
            seat=(4-rotation)%4
            offered=target=="claim" and rotation in (0,2)
            before={
                "kind":"claim","wall_band":"late",
                "original_is_pass":True,
                "baseline_choice":"pass","options":["pass","peng"],
                "candidate_count":2,"chosen_choice":"pass",
                "remaining_opponents":3,"self_public_melds":0,
            } if offered else None
            outcome={metric:0 for metric in METRICS}
            alts={}
            if offered:
                for option in POLICIES[1:]:
                    changed=option=="force_active"
                    points=8 if changed else 0
                    score=dict(outcome);score["official_net"]=points
                    score["win_points"]=points
                    delta={metric:score[metric] for metric in METRICS}
                    alts[option]={
                        "score":score,"delta":delta,"changed":changed,
                        "reused_unchanged_baseline":not changed,
                    }
            return {
                "seed":seed,"rotation":rotation,"challenge_seat":seat,
                "target":target,"offered":offered,
                "baseline":{"score":outcome,"opportunity":before},
                "alternatives":alts,
            }
        with patch("mahtrain_core.ai_action_extended_study._one",
                   side_effect=fake) as mocked:
            r=paired_cohort(21000,3)
        self.assertEqual(mocked.call_count,24)
        self.assertEqual(r["target_positions"],24)
        self.assertEqual(r["target_summaries"]["claim"]["opportunities"],6)
        self.assertEqual(r["target_summaries"]["own_kong"]["opportunities"],0)
        claim=r["target_summaries"]["claim"]["policies"]["force_active"]
        self.assertEqual(claim["changed_positions"],6)
        self.assertEqual(claim["mean_seed_cluster_net_delta"],4)
        self.assertEqual(claim["cumulative_official_component_deltas"]["official_net"],48)
        self.assertEqual(claim["cumulative_official_component_deltas"]["win_points"],48)
        self.assertEqual(claim["public_prechoice_strata"],
                         {"late:pass":{"offered_positions":6,
                                       "changed_positions":6,
                                       "sum_realized_net_delta":48}})
        self.assertIsNone(claim["confidence_interval_95pct"])
        kong=r["target_summaries"]["own_kong"]["policies"]["force_active"]
        self.assertEqual(kong["changed_positions"],0)
        self.assertEqual(kong["mean_seed_cluster_net_delta"],0)

    def test_all_four_cohorts_nonoverlap_even_if_running_just_one_mode(self):
        for kwargs in (
            {"coverage_development":16000,"coverage_holdout":16006},
            {"coverage_development":17000,"coverage_holdout":16000},
            {"paired_development":17000},
            {"coverage_seeds":True},{"coverage_seeds":0},
            {"coverage_seeds":33},{"paired_seeds":17},
            {"paired_seeds":0},{"paired_seeds":True},
            {"coverage_development":True},{"paired_holdout":2**32-2},
            {"mode":"not_valid"},
        ):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                study(mode="coverage",**{**kwargs,
                    **({} if "mode" not in kwargs else {"mode":"not_valid"})})
        with patch("mahtrain_core.ai_action_extended_study.natural_coverage",
                   return_value={"independent_seeds":8}) as cov,patch(
                   "mahtrain_core.ai_action_extended_study.paired_cohort",
                   return_value={"independent_seeds":4}) as pair:
            result=study(mode="all")
        self.assertEqual(cov.call_count,2)
        self.assertEqual(pair.call_count,2)
        self.assertFalse(result["live_ai_modified"])
        self.assertEqual(result["protocol"],PROTOCOL)
        self.assertEqual(result["coverage_seed_ranges"],[[16000,16008],[17000,17008]]
                         if False else [(16000,16008),(17000,17008)])


if __name__=="__main__":
    unittest.main()
