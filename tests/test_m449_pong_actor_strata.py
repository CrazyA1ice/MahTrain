"""M4.49: genuine own-view features; old M4.48 proof, crash resume, safe strata."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]

import test_m448_pong_pass_replication as previous_fixture
from test_m447_pong_pass_branch_rollouts import fake_case
from mahtrain_core.ai_pong_actor_strata import (
    SEED_COUNT, PROTOCOL, safe_actor_strata, one_actor_stratified_shuffle,
    validate_case,
)
from mahtrain_core.ai_pong_actor_strata_run import (
    SUMMARY, _shard, _check_previous, run_actor_strata,
)
from mahtrain_core.ai_selfplay_local_batch import _get_json
from mahtrain_core.ai_shadow_headtohead import _paired_digest

CATEGORIES={
    "shanten_change":"same",
    "effective_copies_change":"loss",
    "public_wall_segment":"middle",
    "opponents_open_melds_count_band":"one",
    "verified_tian_ting":"no",
}


def aggregate_game(seed:int):
    row=fake_case(seed)
    row["private_actor_only_pre_action_categories"]=dict(CATEGORIES)
    return row


class M449ActorStratificationTests(unittest.TestCase):
    def setUp(self):
        test=previous_fixture.M448ReplicationTests(
            "test_24_new_independent_shuffles_with_actual_branch_accounting_contract"
        )
        test.setUp()
        self.addCleanup(test.doCleanups)
        test._run()  # complete previous 24 private signed branch clusters
        self.old=test
        self.output=test.root/"m449"

    def _run(self,*,start=93300,resume=False,func=aggregate_game):
        with patch("mahtrain_core.ai_pong_actor_strata_run.load_frozen_local_model",
                   return_value=((0,0,0),self.old.meta)), \
             patch("mahtrain_core.ai_pong_actor_strata_run.prior_m447_provenance",
                   return_value={"private_m446_source":str(self.old.old446.resolve())}), \
             patch("mahtrain_core.ai_pong_actor_strata_run.one_actor_stratified_shuffle",
                   side_effect=func) as actor:
            safe=run_actor_strata(
                training_dir=self.old.train,prior_m448_dir=self.old.out,
                seed_start=start,seeds=SEED_COUNT,
                out_dir=self.output,resume=resume,
            )
        return safe,actor.call_count

    def test_24_independent_new_synthetic_game_contracts_and_private_suppression(self):
        safe,n=self._run()
        self.assertEqual(n,24)
        self.assertEqual(safe["protocol"],PROTOCOL)
        self.assertEqual(safe["independent_original_shuffle_clusters"],24)
        self.assertEqual(safe["true_full_terminal_branch_games"],96)
        self.assertEqual(safe["all_shuffle_mean_peng_minus_pass_points"],0)
        self.assertEqual(safe["pre_action_actor_only_strata"]["shanten_change"]["same"]
                         ["independent_original_shuffles"],24)
        self.assertTrue(safe["original_challenge_agent_unchanged"])
        self.assertEqual(safe,_get_json(self.output/SUMMARY))
        text=json.dumps(safe)
        for secret in ("93300","93000","92800","PRIVATE_","a"*64,
                       '"hand":','"private_first_actor_seat"'):
            self.assertNotIn(secret,text)

    def test_restart_reuses_verified_24_full_original_shuffles(self):
        self._run()
        result,n=self._run(resume=True,func=AssertionError("should not replay"))
        self.assertEqual(n,0)
        self.assertEqual(result["verified_original_shuffle_clusters_reused_on_resume"],24)

    def test_interrupted_original_seed_recovers_only_unfinished_cluster(self):
        def fail(seed):
            if seed==93301:
                raise RuntimeError("simulated interruption")
            return aggregate_game(seed)
        with self.assertRaisesRegex(RuntimeError,"simulated"):
            self._run(func=fail)
        self.assertTrue(_shard(self.output,0).is_file())
        self.assertFalse(_shard(self.output,1).exists())
        result,n=self._run(resume=True)
        self.assertEqual(n,23)
        self.assertEqual(result["verified_original_shuffle_clusters_reused_on_resume"],1)

    def test_training_old_seed_overlap_and_prior_m448_seed_overlap(self):
        for seed in (89800,93000,93010,93023):
            with self.subTest(seed=seed):
                with self.assertRaisesRegex(ValueError,"overlap"):
                    self._run(start=seed)
        self.assertFalse(self.output.exists())

    def test_reject_tampered_old_safe_report_and_paid_shard(self):
        original=self.old.out/SUMMARY
        old=_get_json(original)
        altered=dict(old)
        altered["mean_forced_peng_minus_pass_official_net_points"]=1234
        original.write_text(json.dumps(altered),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"mismatches"):
            self._run()
        original.write_text(json.dumps(old),encoding="utf8")
        from mahtrain_core.ai_pong_pass_branch_rollouts import _private_shard
        shard=_private_shard(self.old.out/"PRIVATE_m448_original_shuffle_branch_checkpoints",0)
        env=_get_json(shard)
        env["case_sha256"]="0"*64
        shard.write_text(json.dumps(env),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            self._run()

    def test_invalid_new_shard_and_precommitted_plan_rejected(self):
        self._run()
        with self.assertRaisesRegex(ValueError,"empty"):
            self._run()
        shard=_shard(self.output,0)
        env=_get_json(shard)
        env["case_sha256"]="0"*64
        shard.write_text(json.dumps(env),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            self._run(resume=True)
        env["private_case"]["private_actor_only_pre_action_categories"]["shanten_change"]="invented"
        env["case_sha256"]=_paired_digest(env["private_case"])
        shard.write_text(json.dumps(env),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"categorical"):
            self._run(resume=True)

    def test_suppress_any_stratum_with_fewer_than_three_independent_seed_clusters(self):
        rows=[aggregate_game(93300+i) for i in range(4)]
        rows[0]["private_actor_only_pre_action_categories"]["shanten_change"]="improve"
        rows[1]["private_actor_only_pre_action_categories"]["shanten_change"]="regress"
        result=safe_actor_strata(rows)
        for kind in ("improve","regress"):
            row=result["pre_action_actor_only_strata"]["shanten_change"][kind]
            self.assertEqual(row["independent_original_shuffles"],1)
            self.assertTrue(row["small_group_outcomes_suppressed"])
            self.assertNotIn("mean_peng_minus_pass_points_exploratory",row)
        self.assertEqual(result["pre_action_actor_only_strata"]["shanten_change"]
                         ["same"]["independent_original_shuffles"],2)

    def test_m449_true_four_player_first_pass_peng_and_actor_view_categories(self):
        # Fixed test-only coverage, not a branch-profit-driven selection.
        found=None
        for seed in range(90411,90431):
            case=one_actor_stratified_shuffle(seed)
            validate_case(case,seed)
            if case["first_natural_challenge_pass_with_peng_found"]:
                found=case
                break
        self.assertIsNotNone(found,"no genuine eligible first pass/peng in frozen test range")
        self.assertEqual(len(found["private_matched_branches"]),2)
        self.assertEqual(found["private_matched_branches"][0]["world"],0)
        self.assertEqual(found["private_matched_branches"][1]["world"],1)
        self.assertEqual(safe_actor_strata([found])["true_full_terminal_branch_games"],4)
        self.assertTrue(found["private_actor_only_pre_action_categories"]["shanten_change"]
                        in ("improve","same","regress"))


if __name__=="__main__":
    unittest.main()
