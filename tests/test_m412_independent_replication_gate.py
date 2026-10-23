"""M4.12: fail-closed independent-seed replication / non-deployment."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from statistics import mean
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]
from mahtrain_core.ai_minggang_preclaim_paired import METRICS,PUBLIC_THREAT_GATE
from mahtrain_core.ai_minggang_replication_gate import (
    PROTOCOL, MIN_INTERVENTIONS_PER_BLOCK,MIN_TREATED_SEED_CLUSTERS,
    MIN_POSITIVE_SEED_CLUSTERS,evaluate_block,study,
)


def fake_block(start=48000,seeds=8,changes=None,deltas=None):
    """Full official M4.11 shape; fabricated only for validator unit tests."""
    if changes is None: changes=[1]*seeds
    if deltas is None:
        deltas=[2 if i<5 else -2 for i in range(seeds)]
    assert len(changes)==len(deltas)==seeds
    positions=[];per_seed=[]
    totals={x:0 for x in METRICS}
    total_changes=0
    for i in range(seeds):
        seed=start+i
        total_changes+=changes[i]
        for rotation in range(4):
            changed=changes[i] if rotation==0 else 0
            net=deltas[i] if rotation==0 else 0
            one={x:0 for x in METRICS}
            one["official_net"]=net
            one["win_points"]=net
            for metric,value in one.items():
                totals[metric]+=value
            base={x:0 for x in METRICS}
            new=copy.deepcopy(base)
            new["official_net"]=net
            new["win_points"]=net
            positions.append({
                "seed":seed,"rotation":rotation,"challenge_seat":rotation,
                "arms":{
                    "baseline":{"counts":{"actual_changes":0},"official":base},
                    "risk_peng":{"counts":{"actual_changes":changed},"official":new},
                },
                "paired_deltas":one,"actual_interventions":changed,
                "same_state_when_unchanged":changed==0,
            })
        per_seed.append({
            "seed":seed,
            "mean_four_seat_net_delta":round(deltas[i]/4,4),
            "actual_interventions":changes[i],
        })
    signs=[r["mean_four_seat_net_delta"] for r in per_seed]
    return {
        "independent_shuffle_seeds":seeds,
        "paired_seat_positions":4*seeds,
        "complete_games":8*seeds,
        "public_threat_gate":PUBLIC_THREAT_GATE,
        "risk_is_probability":False,
        "candidate_real_policy_changes":total_changes,
        "confidence_interval":None,
        "seed_mean_official_net_delta":round(mean(signs),4),
        "positive_delta_seeds":sum(x>0 for x in signs),
        "negative_delta_seeds":sum(x<0 for x in signs),
        "unchanged_delta_seeds":sum(x==0 for x in signs),
        "per_seed":per_seed,"positions":positions,
        "counts_by_arm":{"baseline":{},"risk_peng":{
            "actual_changes":total_changes}},
        "official_component_deltas":totals,
    }


class M412IndependentReplicationTests(unittest.TestCase):
    def test_synthetic_sufficient_block_allows_research_not_deployment(self):
        data=evaluate_block(fake_block(),start=48000,seeds=8)
        self.assertEqual(data["actual_interventions"],8)
        self.assertEqual(data["independent_seeds_with_interventions"],8)
        self.assertEqual(data["positive_seed_clusters"],5)
        self.assertEqual(data["negative_seed_clusters"],3)
        self.assertTrue(data["predeclared_more_research_gate_passed"])
        self.assertFalse(data["policy_deployable"])
        self.assertFalse(data["study_is_causal_local_claim_value"])
        self.assertIsNone(data["calibrated_ron_probability"])
        self.assertNotIn("positions",data)
        self.assertNotIn("arms",json.dumps(data))

    def test_no_real_changes_are_reported_insufficient_not_false_success(self):
        data=evaluate_block(
            fake_block(changes=[0]*8,deltas=[0]*8),start=48000,seeds=8)
        self.assertEqual(data["actual_interventions"],0)
        self.assertEqual(data["mean_four_seat_official_net_delta"],0)
        self.assertFalse(data["predeclared_more_research_gate_passed"])
        self.assertIn("insufficient_actual_policy_changes",data["blockers"])
        self.assertIn(
            "too_few_independent_shuffle_clusters_with_changes",
            data["blockers"])
        self.assertIn(
            "no_replicated_positive_independent_seed_effect",data["blockers"])

    def test_eight_interventions_but_only_one_seed_does_not_pass(self):
        x=fake_block(changes=[8]+[0]*7,deltas=[8]+[0]*7)
        result=evaluate_block(x,start=48000,seeds=8)
        self.assertEqual(result["actual_interventions"],8)
        self.assertEqual(result["independent_seeds_with_interventions"],1)
        self.assertFalse(result["predeclared_more_research_gate_passed"])

    def test_all_negative_clusters_fail_even_if_exposure_is_high(self):
        x=fake_block(changes=[1]*8,deltas=[-2]*8)
        r=evaluate_block(x,start=48000,seeds=8)
        self.assertEqual(r["negative_seed_clusters"],8)
        self.assertFalse(r["predeclared_more_research_gate_passed"])

    def test_zero_change_must_have_zero_official_difference(self):
        x=fake_block()
        x["positions"][1]["paired_deltas"]["official_net"]=1
        with self.assertRaises(RuntimeError):
            evaluate_block(x,start=48000,seeds=8)

    def test_double_counted_seat_or_bad_cluster_metric_fails_closed(self):
        for variant in ("duplicate_seat","wrong_mean","missing_position",
                        "wrong_total_changes","wrong_priced_net",
                        "bad_baseline","bad_counter","bad_seed","wrong_threshold"):
            x=fake_block()
            if variant=="duplicate_seat":
                x["positions"][1]["rotation"]=0
            elif variant=="wrong_mean":
                x["per_seed"][0]["mean_four_seat_net_delta"]=77
            elif variant=="missing_position":
                x["positions"].pop()
            elif variant=="wrong_total_changes":
                x["candidate_real_policy_changes"]=4
            elif variant=="wrong_priced_net":
                x["official_component_deltas"]["kong_points"]=23
            elif variant=="bad_baseline":
                x["positions"][0]["arms"]["baseline"]["counts"]["actual_changes"]=1
            elif variant=="bad_counter":
                x["positions"][0]["arms"]["risk_peng"]["counts"]["actual_changes"]=8
            elif variant=="bad_seed":
                x["positions"][0]["seed"]=50000
            elif variant=="wrong_threshold":
                x["public_threat_gate"]=.35
            with self.subTest(variant=variant),self.assertRaises(RuntimeError):
                evaluate_block(x,start=48000,seeds=8)

    def test_partial_four_position_block_is_invalid(self):
        with self.assertRaises(RuntimeError):
            evaluate_block(fake_block(seeds=7),start=48000,seeds=8)
        with self.assertRaises(ValueError):
            evaluate_block(fake_block(),start=True,seeds=8)

    def test_study_requires_disjoint_new_seed_blocks(self):
        for bad in (
            {"seeds":0},{"seeds":9},{"seeds":True},
            {"development":True},{"holdout":48000},{"holdout":48007},
            {"holdout":2**32-1},
        ):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                study(**bad)

    def test_one_qualified_one_unqualified_holdout_cannot_promote(self):
        def subcall(start,seeds):
            if start==48000:
                return fake_block(start,seeds)
            return fake_block(start,seeds,changes=[0]*seeds,deltas=[0]*seeds)
        with patch("mahtrain_core.ai_minggang_replication_gate.original_paired_cohort",
                   side_effect=subcall) as run:
            report=study()
        self.assertEqual([x.args for x in run.call_args_list],
                         [(48000,8),(49000,8)])
        self.assertEqual(report["protocol"],PROTOCOL)
        self.assertTrue(report["development"][
            "predeclared_more_research_gate_passed"])
        self.assertFalse(report["holdout"][
            "predeclared_more_research_gate_passed"])
        self.assertFalse(report["decision"][
            "eligible_for_larger_fresh_seed_study"])
        self.assertFalse(report["decision"]["deploy_live_policy"])
        self.assertFalse(report["online_policy_modified"])
        self.assertTrue(report["candidate_only_offline"])
        self.assertEqual(report["evidence_thresholds"],{
            "min_changes_per_block":MIN_INTERVENTIONS_PER_BLOCK,
            "min_treated_seed_clusters":MIN_TREATED_SEED_CLUSTERS,
            "min_positive_seed_clusters":MIN_POSITIVE_SEED_CLUSTERS,
            "both_blocks_required":True,
        })

    def test_strong_both_blocks_only_authorizes_new_research(self):
        with patch("mahtrain_core.ai_minggang_replication_gate.original_paired_cohort",
                   side_effect=lambda start,n:fake_block(start,n)):
            out=study()
        self.assertTrue(out["decision"][
            "eligible_for_larger_fresh_seed_study"])
        self.assertFalse(out["decision"]["deploy_live_policy"])


if __name__=="__main__":
    unittest.main()
