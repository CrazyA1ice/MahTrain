"""M4.34 REAL full-game, resumable, privacy-audited Windows-local batch."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]

from mahtrain_core.ai_selfplay_local_batch import (
    PROTOCOL, BatchPlan, _audit_record, _get_json, _limited_model,
    _private_location, _shard, run_local_batch,
)
from mahtrain_core.ai_selfplay_multicheckpoint import fit_seed_weighted_model


class M434LocalBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Two genuine independent natural shuffles, 4 seated challenge AIs,
        # with real official 108-tile ledger and legal two-wall action forks.
        cls.tempdir=tempfile.TemporaryDirectory()
        cls.plan=BatchPlan(89823,1,1,1)
        cls.out=Path(cls.tempdir.name)/"private_research"
        cls.first=run_local_batch(cls.plan,cls.out,workers=1,resume=False)

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def test_real_two_seed_shards_and_all_true_official_components(self):
        data=self.first
        self.assertEqual(data["protocol"],PROTOCOL)
        self.assertEqual(data["natural_full_games"],2)
        self.assertEqual(data["train_independent_seed_clusters"],1)
        self.assertEqual(data["holdout_independent_seed_clusters"],1)
        self.assertEqual(data["total_true_completed_games"],
                         2+data["terminal_paired_branch_games"])
        self.assertEqual(data["terminal_paired_branch_games"]%4,0)
        self.assertTrue(data["terminal_paired_branch_games"]>=0)
        self.assertFalse(data["online_policy_promoted"])
        self.assertFalse(data["proof_of_increased_ai_strength"])
        self.assertFalse(data["uncertainty_estimate_valid_for_population"])
        self.assertFalse(data["private_seed_ids_exported"])
        self.assertIsNone(data["holdout_accuracy_if_at_least_five"])
        for i in range(2):
            raw=_get_json(_shard(self.out,i))
            audited=_audit_record(raw,self.plan,i)
            self.assertEqual(raw["private_shuffle_seed"],89823+i)
            self.assertEqual(raw["index"],i)
            self.assertEqual(raw["split"],"train" if i==0 else "holdout")
            self.assertEqual(raw["public"]["players"],["challenge"]*4)
            self.assertEqual(
                len(raw["actor_private"]["checkpoints"]),
                audited["natural_decisions"],
            )
            self.assertEqual(
                audited["terminal_counterfactual_games"],
                4*audited["natural_decisions"],
            )

    def test_resume_skips_completed_real_games_and_does_not_mix_plans(self):
        with patch(
            "mahtrain_core.ai_selfplay_local_batch._worker",
            side_effect=AssertionError("must skip both finished shards"),
        ):
            second=run_local_batch(self.plan,self.out,workers=1,resume=True)
        self.assertEqual(self.first,second)
        with self.assertRaises(ValueError):
            run_local_batch(self.plan,self.out,workers=1,resume=False)
        with self.assertRaises(ValueError):
            run_local_batch(
                BatchPlan(89824,1,1,1),self.out,workers=1,resume=True
            )
        with self.assertRaises(ValueError):
            run_local_batch(
                BatchPlan(89823,1,1,2),self.out,workers=1,resume=True
            )

    def test_streaming_model_is_identical_to_original_seed_weighted_fit(self):
        rows=[_get_json(_shard(self.out,i))["actor_private"] for i in range(2)]
        streaming=_limited_model(iter(rows),2)
        frozen=fit_seed_weighted_model(rows)
        self.assertEqual(streaming,frozen)

    def test_safe_summary_does_not_contain_private_actor_or_seed_identity(self):
        summary=json.loads(
            (self.out/"safe_aggregate_summary.json").read_text(encoding="utf8")
        )
        self.assertEqual(summary,self.first)
        public=(self.out/"public_four_challenge_replays.jsonl.gz")
        self.assertTrue(public.is_file())
        import gzip
        with gzip.open(public,"rt",encoding="utf8") as handle:
            public_text=handle.read()
        self.assertNotIn("private_shuffle_seed",public_text)
        self.assertNotIn("89823",public_text)
        self.assertNotIn("89824",public_text)
        safe=json.dumps(summary)
        for secret in ("private_shuffle_seed","actor_observation",
                       "PRIVATE_actor_train","89823","89824",
                       "private_view"):
            self.assertNotIn(secret,safe)
        # Exact private state keys, not fragments of legitimate aggregate
        # fields such as two_wall_mixed_or_tied_points.
        for forbidden_key in ("_hands","_wall","opponent_hands",
                              "future_wall"):
            self.assertNotIn(forbidden_key,summary)
        self.assertEqual(
            summary["paired_world_delta_count"],
            summary["natural_legal_decision_points"],
        )
        self.assertEqual(
            summary["training_legal_decision_points"]+
            summary["holdout_legal_decision_points"],
            summary["natural_legal_decision_points"],
        )
        self.assertEqual(
            summary["two_wall_mixed_or_tied_points"]+
            summary["training_consensus_labels"]+
            summary["holdout_consensus_labels"],
            summary["natural_legal_decision_points"],
        )

    def test_modifying_terminal_points_in_shard_fails_closed(self):
        original=_get_json(_shard(self.out,0))
        changed=deepcopy(original)
        changed["public"]["official_final_balances"][0]+=1
        with self.assertRaises(ValueError):
            _audit_record(changed,self.plan,0)
        changed=deepcopy(original)
        changed["private_shuffle_seed"]+=1
        with self.assertRaises(ValueError):
            _audit_record(changed,self.plan,0)
        changed=deepcopy(original)
        changed["public"]["hand"]=["m1"]
        with self.assertRaises((RuntimeError,ValueError)):
            _audit_record(changed,self.plan,0)

    def test_invalid_plans_unsafe_directories_and_workers_blocked(self):
        for args in (
            (-1,1,1,2),(True,1,1,2),(2**32-1,1,1,2),
            (1,0,1,2),(1,1,0,2),(1,1,100001,2),
            (1,1,1,0),(1,1,1,3),(1,1,1,True),
        ):
            with self.subTest(args=args),self.assertRaises(ValueError):
                BatchPlan(*args)
        for n in (0,17,True,1.5,"2"):
            with self.subTest(workers=n),self.assertRaises(ValueError):
                run_local_batch(self.plan,self.out,workers=n,resume=True)
        with self.assertRaises(ValueError):
            _private_location(ROOT/"docs"/"exposed-private-data")
        with self.assertRaises(ValueError):
            _private_location(ROOT/"src")


if __name__=="__main__":
    unittest.main()
