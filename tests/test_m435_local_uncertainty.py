"""M4.35 real locally stored games and ALL lawful noisy action labels."""
from __future__ import annotations

from copy import deepcopy
import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]

from mahtrain_core.ai_selfplay_local_batch import (
    BatchPlan, _get_json, _shard, run_local_batch
)
from mahtrain_core.ai_selfplay_uncertainty import (
    PROTOCOL, _case_metrics, _records, analyze_saved_local_batch,
    fit_all_conditional_actions
)


class M435UncertaintyAwareLocalStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.output=Path(cls.tmp.name)/"PRIVATE_saved_games"
        cls.plan=BatchPlan(89823,1,1,1)
        cls.prior=run_local_batch(cls.plan,cls.output,workers=1)
        cls.report=analyze_saved_local_batch(cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_existing_real_games_reused_without_running_new_matches(self):
        with patch(
            "mahtrain_core.ai_selfplay_local_batch._worker",
            side_effect=AssertionError("should never generate new game")
        ), patch(
            "mahtrain_core.ai_selfplay_uncertainty.run_local_batch",
            create=True,
            side_effect=AssertionError("should never launch self-play")
        ):
            repeat=analyze_saved_local_batch(self.output)
        self.assertEqual(repeat,self.report)
        self.assertEqual(repeat["protocol"],PROTOCOL)
        self.assertEqual(repeat["original_natural_seed_clusters"],2)
        self.assertEqual(
            repeat["all_natural_legal_actions_retained"],
            self.prior["natural_legal_decision_points"]
        )
        self.assertEqual(
            repeat["new_offline_train_points"],
            self.prior["training_legal_decision_points"]
        )
        self.assertEqual(
            repeat["train_points_excluded_due_to_world_sign_disagreement"],0
        )
        self.assertFalse(repeat["online_ai_modified"])
        self.assertFalse(repeat["population_effect_or_q_value_established"])
        self.assertFalse(repeat["actual_live_head_to_head_benchmark_completed"])
        self.assertIsNone(repeat["heldout_direction_accuracy_if_at_least_five"])

    def test_opposite_sign_real_terminal_actions_are_not_thrown_away(self):
        # Deterministically selected natural train seed has one mixed/tied
        # branch. It was excluded under the old strict two-wall policy.
        self.assertEqual(
            self.prior["training_consensus_labels"],0
        )
        self.assertEqual(
            self.report["train"]["world_signs_conflict_or_tie"],1
        )
        self.assertEqual(
            self.report["train"]["all_natural_legal_actions"],1
        )
        self.assertEqual(
            self.report["new_offline_train_points"],1
        )
        model=_get_json(self.output/"PRIVATE_uncertainty_offline_model.json")
        self.assertEqual(model["all_legal_train_action_points"],1)
        self.assertEqual(
            model["strict_sign_mixed_or_tied_but_retained"],1
        )
        self.assertFalse(model["online_policy_promotion_allowed"])

    def test_conditional_mean_gap_and_shrinkage_computed_from_real_scores(self):
        natural=_get_json(_shard(self.output,0))
        checkpoint=natural["actor_private"]["checkpoints"][0]
        item=_case_metrics(checkpoint)
        official=[
            w["alternative_minus_original"]["official_net"]
            for w in checkpoint["physical_worlds"]
        ]
        self.assertEqual(item["paired_conditional_deltas"],official)
        self.assertEqual(
            item["conditional_mean_net_delta"],sum(official)/2
        )
        self.assertEqual(
            item["conditional_world_abs_gap"],abs(official[0]-official[1])
        )
        self.assertGreaterEqual(item["attenuation"],0)
        self.assertLess(item["attenuation"],1)
        self.assertLessEqual(abs(item["bounded_training_target"]),1)

    def test_fixed_heldout_never_participates_in_model_fit(self):
        exact=fit_all_conditional_actions(
            _records(self.plan,self.output,0,1),1
        )
        model=_get_json(self.output/"PRIVATE_uncertainty_offline_model.json")
        self.assertEqual(exact,model)
        self.assertEqual(model["train_seed_clusters"],1)
        self.assertTrue(model["no_test_labels_used_for_training"])
        self.assertIsNone(
            self.report["heldout_direction_accuracy_if_at_least_five"]
        )

    def test_research_summary_and_public_tapes_have_no_secret_tiles_or_ids(self):
        summary=json.loads(
            (self.output/"safe_uncertainty_summary.json").read_text("utf8")
        )
        self.assertEqual(summary,self.report)
        public=gzip.open(
            self.output/"public_four_challenge_replays.jsonl.gz",
            "rt",encoding="utf8"
        ).read()
        text=json.dumps(summary)
        for secret in ("89823","89824","private_shuffle_seed",
                       "actor_observation","PRIVATE_actor_train",
                       "private_view","paired_conditional_deltas"):
            self.assertNotIn(secret,text)
        self.assertNotIn("89823",public)
        self.assertNotIn("89824",public)
        self.assertTrue(
            (self.output/"PRIVATE_uncertainty_holdout_diagnostics.jsonl.gz").is_file()
        )
        self.assertTrue(
            (self.output/"PRIVATE_uncertainty_offline_model.json").is_file()
        )

    def test_invalid_plan_missing_shard_corrupted_official_score_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/"copy"
            shutil.copytree(self.output,dest)
            (dest/"PRIVATE_plan.json").unlink()
            with self.assertRaises(ValueError):
                analyze_saved_local_batch(dest)
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/"copy"
            shutil.copytree(self.output,dest)
            _shard(dest,1).unlink()
            with self.assertRaises(ValueError):
                analyze_saved_local_batch(dest)
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/"copy"
            shutil.copytree(self.output,dest)
            path=_shard(dest,0)
            tampered=_get_json(path)
            tampered["public"]["official_final_balances"][0]+=1
            path.write_text(json.dumps(tampered),encoding="utf8")
            with self.assertRaises(ValueError):
                analyze_saved_local_batch(dest)

    def test_opposing_two_wall_scores_are_attenuated_not_discarded(self):
        actor={
            "checkpoint_index":0,
            "actor_observation":{
                "baseline":"m1","alternative":"m2",
                "features":{"m1":[0.,0.,0.],"m2":[1.,0.5,0.3]}
            },
            "physical_worlds":[
                {"alternative_minus_original":{"official_net":300}},
                {"alternative_minus_original":{"official_net":-100}},
            ],
        }
        x=_case_metrics(actor)
        self.assertEqual(x["paired_conditional_deltas"],[300,-100])
        self.assertEqual(x["conditional_mean_net_delta"],100)
        self.assertEqual(x["conditional_world_abs_gap"],400)
        self.assertFalse(x["world_signs_agree_nonzero"])
        self.assertTrue(x["conditional_mean_nonzero"])
        self.assertAlmostEqual(x["attenuation"],100/400)
        self.assertAlmostEqual(x["bounded_training_target"],0.025)
        self.assertEqual(x["feature_difference"],[1.,0.5,0.3])
        y=deepcopy(actor)
        y["physical_worlds"][1]["alternative_minus_original"]["official_net"]=-300
        tied=_case_metrics(y)
        self.assertEqual(tied["bounded_training_target"],0)
        self.assertEqual(tied["attenuation"],0)

if __name__=="__main__":
    unittest.main()
