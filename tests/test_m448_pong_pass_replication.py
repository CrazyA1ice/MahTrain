"""M4.48 frozen replication contracts. CI fixture is synthetic, NOT 120 real games."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]

from mahtrain_core.ai_selfplay_local_batch import _get_json
from mahtrain_core.ai_shadow_headtohead import _paired_digest
from mahtrain_core.ai_pong_pass_branch_rollouts import (
    PLAN as M447_PLAN, PROTOCOL as M447_PROTOCOL,
    SUMMARY as M447_SUMMARY, SHARD_PROTOCOL as M447_SHARD_PROTOCOL,
    _private_shard, _aggregate as m447_summary, WORLDS
)
from mahtrain_core.ai_pong_pass_replication import (
    BOOTSTRAPS, SEED_COUNT, SUMMARY, PROTOCOL, _additional_statistics,
    _frozen_m447_sha256, _prior_provenance
)
from mahtrain_core.ai_pong_pass_replication_run import run_independent_branch_replication
from test_m447_pong_pass_branch_rollouts import fake_case


class M448ReplicationTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.train=self.root/"train"
        self.prior=self.root/"prior-m447"
        self.old446=self.root/"prior-m446"
        self.out=self.root/"new-m448"
        self.prior.mkdir()
        self.old446.mkdir()
        self.meta={
            "model_sha256":"a"*64,
            "source_m434_train_seed_start":89800,
            "source_m434_seed_end_exclusive":89804,
            "trained_original_shuffle_clusters":2,
        }
        previous=[]
        for i in range(8):
            case=fake_case(92800+i)
            previous.append(case)
            dest=_private_shard(self.prior,i)
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(json.dumps({
                "protocol":M447_SHARD_PROTOCOL,
                "index":i,"model_sha256":"a"*64,
                "case_sha256":_paired_digest(case),
                "private_case":case,
            }),encoding="utf8")
        safe=m447_summary(previous)
        safe["verified_original_seed_shards_reused_on_resume"]=0
        (self.prior/M447_SUMMARY).write_text(json.dumps(safe),encoding="utf8")
        plan={
            "protocol":M447_PROTOCOL,
            "private_model_source":str(self.train.resolve()),
            "model_sha256_provenance_only":"a"*64,
            "frozen_m447_protocol_source_sha256":_frozen_m447_sha256(),
            "no_new_policy_or_refit":True,
            "worlds":list(WORLDS),
            "max_first_checkpoints_per_shuffle":1,
            "private_natural_shuffle_start":92800,
            "private_independent_shuffle_count":8,
            "private_m446_source":str(self.old446.resolve()),
            "private_m444_source":"old-444",
            "private_m445_source":"old-445",
        }
        (self.prior/M447_PLAN).write_text(json.dumps(plan),encoding="utf8")

    def _run(self,*,start=93000,resume=False,effect=fake_case):
        with patch("mahtrain_core.ai_pong_pass_replication_run.load_frozen_local_model",
                   return_value=((0,0,0),self.meta)), \
             patch("mahtrain_core.ai_pong_pass_replication._source_plan_and_exclusion",
                   return_value={
                       "private_m444_source":"old-444",
                       "private_m445_source":"old-445",
                   }), \
             patch("mahtrain_core.ai_pong_pass_replication_run.one_natural_shuffle",
                   side_effect=effect) as played:
            safe=run_independent_branch_replication(
                training_dir=self.train,prior_m447_dir=self.prior,
                seed_start=start,seeds=SEED_COUNT,out_dir=self.out,resume=resume)
        return safe,played.call_count

    def test_24_new_independent_shuffles_with_actual_branch_accounting_contract(self):
        safe,n=self._run()
        self.assertEqual(n,24)
        self.assertEqual(safe["protocol"],PROTOCOL)
        self.assertEqual(safe["new_independent_original_shuffle_clusters"],24)
        self.assertEqual(safe["previous_m447_original_shuffles_audited_but_not_pooled"],True)
        self.assertEqual(safe["real_natural_challenge_baseline_games"],24)
        self.assertEqual(safe["real_terminal_branch_games"],96)
        self.assertEqual(safe["total_true_complete_paid_games"],120)
        self.assertEqual(safe["two_world_matched_branch_pairs"],48)
        self.assertEqual(safe["mean_forced_peng_minus_pass_official_net_points"],0)
        self.assertEqual(safe["original_shuffles_equal"],24)
        self.assertEqual(safe["first_eligible_actor_seat_histogram"],[0,24,0,0])
        self.assertEqual(safe["seed_cluster_bootstrap_resamples"],BOOTSTRAPS)
        self.assertEqual(safe["seed_cluster_bootstrap_mean_delta_percentile_95_exploratory"],[0,0])
        self.assertEqual(safe,_get_json(self.out/SUMMARY))
        serialized=json.dumps(safe,ensure_ascii=False)
        for forbidden in ('"hand":','"private_first_actor_seat"',
                          "93000","92800","PRIVATE_","a"*64,str(self.train)):
            self.assertNotIn(forbidden,serialized)

    def test_resume_full_24_never_replays_old_or_new_shuffles(self):
        self._run()
        safe,n=self._run(resume=True,effect=AssertionError("no paid replay"))
        self.assertEqual(n,0)
        self.assertEqual(safe["verified_original_clusters_reused_on_resume"],24)

    def test_interrupted_shard_replays_only_23_remaining_orig_shuffles(self):
        def interrupted(seed):
            if seed==93001:
                raise RuntimeError("simulated interrupted future world")
            return fake_case(seed)
        with self.assertRaisesRegex(RuntimeError,"simulated"):
            self._run(effect=interrupted)
        batch=self.out/"PRIVATE_m448_original_shuffle_branch_checkpoints"
        self.assertTrue(_private_shard(batch,0).exists())
        self.assertFalse(_private_shard(batch,1).exists())
        safe,n=self._run(resume=True)
        self.assertEqual(n,23)
        self.assertEqual(safe["verified_original_clusters_reused_on_resume"],1)

    def test_strict_train_overlap_and_previous_m447_shuffle_separation(self):
        for seed in (89800,92800,92807):
            with self.subTest(seed=seed):
                with self.assertRaisesRegex(ValueError,"overlap"):
                    self._run(start=seed)
        self.assertFalse(self.out.exists())

    def test_reject_modified_prior_m447_public_result(self):
        prior_file=self.prior/M447_SUMMARY
        data=_get_json(prior_file)
        data["mean_forced_peng_minus_pass_all_seed_clusters"]=999
        prior_file.write_text(json.dumps(data),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"disagrees with paid"):
            self._run()
        self.assertFalse(self.out.exists())

    def test_reject_prior_m447_private_shard_checksum(self):
        f=_private_shard(self.prior,0)
        env=_get_json(f)
        env["case_sha256"]="0"*64
        f.write_text(json.dumps(env),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            self._run()

    def test_reject_modified_prior_m447_source_digest(self):
        f=self.prior/M447_PLAN
        x=_get_json(f)
        x["frozen_m447_protocol_source_sha256"]="0"*64
        f.write_text(json.dumps(x),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"prior M4.47"):
            self._run()

    def test_resume_plan_mutation_refused(self):
        self._run()
        with self.assertRaisesRegex(ValueError,"empty"):
            self._run()
        with self.assertRaisesRegex(ValueError,"frozen source"):
            self._run(start=93001,resume=True)
        plan=self.out/"PRIVATE_m448_precommitted_24_shuffle_plan.json"
        data=_get_json(plan)
        data["precommitted_bootstrap_seed"]=1000
        plan.write_text(json.dumps(data),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"frozen source"):
            self._run(resume=True)

    def test_real_independent_seed_bootstrap_direction_uses_clusters_only(self):
        cases=[fake_case(93000+i) for i in range(SEED_COUNT)]
        for i,case in enumerate(cases):
            for world,branch in enumerate(case["private_matched_branches"]):
                delta=20 if i%2==0 else -20
                branch["official_actor_net_delta"]=delta
                branch["forced_peng_terminal_actor_net"]=delta
                branch["win_actor_delta"]=delta
        stats=_additional_statistics(cases)
        self.assertEqual(stats["independent_cluster_median_net_delta"],0)
        self.assertEqual(stats["mean_world0_net_delta_across_all_original_shuffles"],0)
        self.assertEqual(stats["mean_world1_net_delta_across_all_original_shuffles"],0)
        self.assertEqual(stats["covered_shuffles_world0_world1_sign_disagree"],0)
        self.assertEqual(stats["first_eligible_actor_seat_histogram"],[0,24,0,0])
        low,high=stats["seed_cluster_bootstrap_mean_delta_percentile_95_exploratory"]
        self.assertLess(low,0)
        self.assertGreater(high,0)


if __name__=="__main__":
    unittest.main()
