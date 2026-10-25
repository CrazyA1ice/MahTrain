"""M4.32 genuine multi-checkpoint self-play and seed-cluster diagnostics."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]

from mahtrain_core.ai_selfplay_learning import _assert_public
from mahtrain_core.ai_selfplay_multicheckpoint import (
    PROTOCOL,MODEL_PROTOCOL,MAX_CHECKPOINTS,_signed_consensus,_safe_seed_labels,
    _validate,fit_seed_weighted_model,evaluate_unseen_seed_clusters,
    run_natural_seed,natural_multi_checkpoint_game,run_study,
)


def synthetic_case(seed: int, *, labels: list[int]) -> dict:
    """Integrity-filter testing only. NEVER exported as research results."""
    def ledger(n: int) -> dict:
        return {
            "official_net":n,"win_points":n,
            "kong_points":0,"exhaustive_points":0,
            "physical_tiles":108,"terminal_phase":"finished",
            "actions_after_forced_discard":10,
        }
    cases=[]
    for i,value in enumerate(labels):
        view={
            "seat":i,
            "minimum_shanten":2,
            "baseline":"m1", "alternative":"m2",
            "features":{
                "m1":[0.2,0.1,0.1],
                "m2":[0.4,0.2,0.1],
            },
        }
        worlds=[]
        for world in (0,1):
            ref=ledger(0)
            alt=ledger(value)
            worlds.append({
                "world_index":world,"same_actor_authorized_view":True,
                "first_action_challenge":ref,
                "first_action_alternative":alt,
                "alternative_minus_original":{
                    "official_net":value, "win_points":value,
                    "kong_points":0,"exhaustive_points":0,
                },
            })
        cases.append({
            "checkpoint_index":i,"seat":i,
            "actor_observation":view,
            "physical_worlds":worlds,
            "paired_real_terminal_games":4,
            "mean_conditional_net_delta":value,
            "two_world_sign_consensus":(
                "alternative_better_in_all_test_worlds" if value>0 else
                "original_better_in_all_test_worlds" if value<0 else
                "mixed_or_tied_world_outcomes"
            ),
            "eligible_as_exploratory_training_label":value!=0,
            "not_unbiased_action_EV":True,
        })
    return {
        "protocol":PROTOCOL,
        "private_shuffle_seed":seed,
        "actor_only_observations":True,
        "checkpoints":cases,
        "captured_decisions":len(cases),
        "conditional_rollout_games":4*len(cases),
        "original_natural_games":1,
    }


class M432NaturalMultiCheckpointTests(unittest.TestCase):
    def test_max_two_distinct_seats_per_natural_game(self):
        public,private=run_natural_seed(89605)
        _assert_public(public)
        self.assertEqual(public["protocol"],PROTOCOL)
        self.assertEqual(public["players"] if "players" in public else
                         public["official_final_balances"] is not None,True)
        self.assertEqual(public["terminal_phase"] in
                         ("finished","wall_exhausted"),True)
        self.assertEqual(sum(public["official_final_balances"]),0)
        self.assertGreater(len(public["public_frames"]),20)
        self.assertNotIn("89605",str(public))
        self.assertTrue(private["actor_only_observations"])
        self.assertEqual(private["private_shuffle_seed"],89605)
        self.assertLessEqual(private["captured_decisions"],2)
        self.assertEqual(len({x["seat"] for x in private["checkpoints"]}),
                         private["captured_decisions"])
        self.assertEqual(private["conditional_rollout_games"],
                         private["captured_decisions"]*4)
        for item in private["checkpoints"]:
            self.assertEqual(len(item["physical_worlds"]),2)
            self.assertIn(item["two_world_sign_consensus"],(
                "alternative_better_in_all_test_worlds",
                "original_better_in_all_test_worlds",
                "mixed_or_tied_world_outcomes",
            ))
            for w in item["physical_worlds"]:
                self.assertTrue(w["same_actor_authorized_view"])
                for key in ("first_action_challenge","first_action_alternative"):
                    arm=w[key]
                    self.assertEqual(arm["physical_tiles"],108)
                    self.assertEqual(arm["official_net"],
                        arm["win_points"]+arm["kong_points"]+
                        arm["exhaustive_points"])
        self.assertIsInstance(_safe_seed_labels(private),list)

    def test_fixed_sign_nonzero_consensus_and_neutral(self):
        self.assertEqual(_signed_consensus([100,1]),
                         "alternative_better_in_all_test_worlds")
        self.assertEqual(_signed_consensus([-4,-3]),
                         "original_better_in_all_test_worlds")
        for values in ([0,0],[-1,1],[0,1],[-1,0]):
            self.assertEqual(_signed_consensus(values),
                             "mixed_or_tied_world_outcomes")
        for invalid in ([1],[],[1,2,3],[True,2],[1,2.5]):
            with self.subTest(values=invalid),self.assertRaises(ValueError):
                _signed_consensus(invalid)

    def test_seed_clustering_does_not_treat_two_cuts_as_independent_seeds(self):
        a=synthetic_case(10,labels=[100,300])
        b=synthetic_case(11,labels=[-200])
        model=fit_seed_weighted_model([a,b])
        self.assertEqual(model["protocol"],MODEL_PROTOCOL)
        self.assertEqual(model["seed_clusters_seen"],2)
        self.assertEqual(model["independent_seed_clusters_with_labels"],2)
        self.assertEqual(model["total_action_labels"],3)
        self.assertEqual(len(model["weights"]),3)
        self.assertTrue(all(abs(v)<=.2 for v in model["weights"]))
        self.assertFalse(model["online_promotion_allowed"])
        with self.assertRaises(ValueError):
            fit_seed_weighted_model([a,a])
        with self.assertRaises(ValueError):
            fit_seed_weighted_model([])

    def test_zero_or_opposite_wall_differences_fail_closed(self):
        a=synthetic_case(12,labels=[0,0])
        result=fit_seed_weighted_model([a])
        self.assertEqual(result["status"],"no_consistent_action_labels")
        self.assertEqual(result["total_action_labels"],0)
        self.assertIsNone(result["weights"])
        held=evaluate_unseen_seed_clusters([a],result)
        self.assertEqual(held["natural_covered_decisions"],2 if
                         "natural_covered_decisions" in held else
                         held["total_natural_checkpoints"],2)
        self.assertEqual(held["scored_decisions"],0)
        self.assertFalse(held["evidence_of_population_strength"])

    def test_guard_rejects_tampered_terminal_and_leaky_training_shards(self):
        a=synthetic_case(21,labels=[200])
        cases=[]
        b=deepcopy(a)
        b["checkpoints"][0]["physical_worlds"][0][
            "first_action_alternative"]["official_net"]=99999
        cases.append(b)
        b=deepcopy(a)
        b["checkpoints"][0]["physical_worlds"][1][
            "alternative_minus_original"]["kong_points"]=15
        cases.append(b)
        b=deepcopy(a)
        b["checkpoints"][0]["two_world_sign_consensus"] = (
            "mixed_or_tied_world_outcomes"
        )
        cases.append(b)
        b=deepcopy(a)
        b["captured_decisions"]=999
        cases.append(b)
        b=deepcopy(a)
        b["checkpoints"][0]["physical_worlds"][0][
            "same_actor_authorized_view"]=False
        cases.append(b)
        for i,bad in enumerate(cases):
            with self.subTest(i=i),self.assertRaises(ValueError):
                fit_seed_weighted_model([bad])

    def test_train_holdout_parameter_boundaries_before_any_simulation(self):
        for args in (
            (-1,1,1,2),(True,1,1,2),(2**32-1,1,1,2),
            (1,0,1,2),(1,1,0,2),(1,5,1,2),(1,1,5,2),
            (1,1,1,0),(1,1,1,3),(1,1,1,True),
        ):
            with self.subTest(args=args),self.assertRaises(ValueError):
                _validate(*args)
        with patch(
            "mahtrain_core.ai_selfplay_multicheckpoint.run_natural_seed"
        ) as f:
            with self.assertRaises(ValueError):
                run_study(1,0,1)
            f.assert_not_called()


if __name__=="__main__":
    unittest.main()
