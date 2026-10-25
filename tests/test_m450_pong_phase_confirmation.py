"""M4.50: frozen M4.49 paid-source audit, independent phase contrast, true engine."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]
from test_m449_pong_actor_strata import (
    M449ActorStratificationTests, aggregate_game, CATEGORIES,
)
from mahtrain_core.ai_pong_actor_strata import one_actor_stratified_shuffle
from mahtrain_core.ai_pong_phase_confirmation import (
    PROTOCOL, SEED_COUNT, RESAMPLES, confirm_phase_contrast,
    audit_previous_m449,
)
from mahtrain_core.ai_pong_phase_confirmation_run import (
    _file, run_phase_confirmation,
)
from mahtrain_core.ai_selfplay_local_batch import _get_json
from mahtrain_core.ai_shadow_headtohead import _paired_digest


def middle_early_case(seed:int)->dict:
    c=aggregate_game(seed)
    # First 24 early lose 100; last 24 middle gain 100.
    middle=(seed-93600)>=24
    c["private_actor_only_pre_action_categories"]["public_wall_segment"]=(
        "middle" if middle else "early"
    )
    value=100 if middle else -100
    for branch in c["private_matched_branches"]:
        branch["official_actor_net_delta"]=value
        branch["forced_peng_terminal_actor_net"]=value
        branch["win_actor_delta"]=value
    return c


class M450NewIndependentTests(unittest.TestCase):
    def setUp(self):
        self.old=M449ActorStratificationTests(
            "test_24_independent_new_synthetic_game_contracts_and_private_suppression"
        )
        self.old.setUp()
        self.addCleanup(self.old.doCleanups)
        self.old._run()  # M4.49 full previous private 24-shuffle signed proof
        self.model=self.old.old.meta
        self.training=self.old.old.train
        self.previous=self.old.output
        self.output=self.old.old.root/"m450"

    def _run(self,*,start=93600,resume=False,game=middle_early_case):
        with patch("mahtrain_core.ai_pong_phase_confirmation_run.load_frozen_local_model",
                   return_value=((0,0,0),self.model)), \
             patch("mahtrain_core.ai_pong_phase_confirmation.audit_m448_history",
                   return_value={
                       "private_previous_m447_source":
                           str(self.old.old.prior.resolve())
                   }), \
             patch("mahtrain_core.ai_pong_phase_confirmation_run.one_actor_stratified_shuffle",
                   side_effect=game) as played:
            result=run_phase_confirmation(
                training_dir=self.training,
                prior_m449_dir=self.previous,
                seed_start=start,seeds=SEED_COUNT,
                out_dir=self.output,resume=resume,
            )
        return result,played.call_count

    def test_48_new_original_shuffles_paired_contract_and_frozen_contrast(self):
        safe,n=self._run()
        self.assertEqual(n,48)
        self.assertEqual(safe["protocol"],PROTOCOL)
        self.assertEqual(safe["independent_new_original_shuffle_clusters"],48)
        self.assertEqual(safe["actual_natural_challenge_games"],48)
        self.assertEqual(safe["actual_true_full_terminal_branch_games"],192)
        self.assertEqual(safe["actual_total_complete_paid_games"],240)
        self.assertEqual(safe["matched_real_two_world_action_pairs"],96)
        self.assertEqual(safe["comparison_status"],
                         "exploratory_independent_replication_complete")
        self.assertEqual(safe["middle_minus_early_mean_net_points"],200)
        self.assertEqual(safe["cluster_bootstrap_middle_minus_early_95_percentile_interval"],
                         [200,200])
        self.assertEqual(safe["precommitted_cluster_bootstrap_resamples"],RESAMPLES)
        self.assertTrue(safe["direction_supported_in_new_independent_shuffles"])
        self.assertEqual(safe["precommitted_public_wall_phase_groups"]["early"]
                         ["independent_original_shuffle_clusters"],24)
        self.assertEqual(safe["precommitted_public_wall_phase_groups"]["middle"]
                         ["independent_original_shuffle_clusters"],24)
        self.assertEqual(_get_json(self.output/"safe_pong_phase_confirmation.json"),safe)
        published=json.dumps(safe)
        for fragment in ("93600","93300","93000","PRIVATE_","a"*64,
                         '"hand":','"private_first_actor_seat"',str(self.training)):
            self.assertNotIn(fragment,published)

    def test_all_finished_48_reused_after_identical_resume(self):
        self._run()
        safe,n=self._run(resume=True,game=AssertionError("unexpected game replay"))
        self.assertEqual(n,0)
        self.assertEqual(safe["verified_original_shuffles_reused_after_resume"],48)

    def test_partial_failed_original_cluster_only_47_restarted(self):
        def interrupted(seed):
            if seed==93601:
                raise RuntimeError("simulated incomplete wall result")
            return middle_early_case(seed)
        with self.assertRaisesRegex(RuntimeError,"simulated"):
            self._run(game=interrupted)
        self.assertTrue(_file(self.output,0).is_file())
        self.assertFalse(_file(self.output,1).exists())
        safe,n=self._run(resume=True)
        self.assertEqual(n,47)
        self.assertEqual(safe["verified_original_shuffles_reused_after_resume"],1)

    def test_m434_and_m449_seeds_refused_and_no_output_created(self):
        for start in (89800,93300,93323):
            with self.subTest(start=start):
                with self.assertRaisesRegex(ValueError,"overlap"):
                    self._run(start=start)
        self.assertFalse(self.output.exists())

    def test_m449_public_report_and_signed_original_shards_must_agree(self):
        safe_file=self.previous/"safe_pong_actor_strata.json"
        previous=_get_json(safe_file)
        modified=dict(previous)
        modified["all_shuffle_mean_peng_minus_pass_points"]=999
        safe_file.write_text(json.dumps(modified),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"differs"):
            self._run()
        safe_file.write_text(json.dumps(previous),encoding="utf8")
        source=self.previous/"PRIVATE_m449_seed_cluster_shards"/"index-00000000.json"
        shard=_get_json(source)
        shard["case_sha256"]="0"*64
        source.write_text(json.dumps(shard),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            self._run()

    def test_frozen_prior_m449_source_or_new_resume_plan_changed(self):
        plan_file=self.previous/"PRIVATE_m449_actor_only_strata_plan.json"
        old=_get_json(plan_file)
        old["frozen_actor_strata_source_sha256"]="0"*64
        plan_file.write_text(json.dumps(old),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"frozen policy"):
            self._run()
        old["frozen_actor_strata_source_sha256"]=__import__(
            "mahtrain_core.ai_pong_phase_confirmation",fromlist=[
                "frozen_m449_source_digest"
            ]).frozen_m449_source_digest()
        plan_file.write_text(json.dumps(old),encoding="utf8")
        self._run()
        with self.assertRaisesRegex(ValueError,"empty"):
            self._run()
        with self.assertRaisesRegex(ValueError,"frozen protocol"):
            self._run(start=93601,resume=True)

    def test_new_sha_shard_integrity_and_type_safe_categories(self):
        self._run()
        shard_path=_file(self.output,0)
        stored=_get_json(shard_path)
        stored["case_sha256"]="0"*64
        shard_path.write_text(json.dumps(stored),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            self._run(resume=True)
        stored["private_case"]["private_actor_only_pre_action_categories"][
            "public_wall_segment"
        ]="unknown"
        stored["case_sha256"]=_paired_digest(stored["private_case"])
        shard_path.write_text(json.dumps(stored),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"categorical"):
            self._run(resume=True)

    def test_insufficient_middle_group_suppresses_all_claimed_contrast(self):
        cases=[middle_early_case(93600+i) for i in range(SEED_COUNT)]
        for i,case in enumerate(cases):
            case["private_actor_only_pre_action_categories"]["public_wall_segment"]=(
                "middle" if i<7 else "early"
            )
        summary=confirm_phase_contrast(cases)
        self.assertEqual(summary["comparison_status"],"insufficient_group_support")
        self.assertIsNone(summary["middle_minus_early_mean_net_points"])
        self.assertIsNone(summary["direction_supported_in_new_independent_shuffles"])
        self.assertTrue(summary["precommitted_public_wall_phase_groups"]["middle"]
                        ["mean_and_median_suppressed_insufficient_support"])
        self.assertEqual(summary["precommitted_public_wall_phase_groups"]["middle"]
                         ["independent_original_shuffle_clusters"],7)

    def test_true_four_player_actor_visible_first_peng_and_paid_branch_still_works(self):
        found=None
        for seed in range(90411,90431):
            record=one_actor_stratified_shuffle(seed)
            if record["first_natural_challenge_pass_with_peng_found"]:
                found=record
                break
        self.assertIsNotNone(found,"real first eligible Challenge pass/peng missing")
        self.assertEqual(len(found["private_matched_branches"]),2)
        self.assertEqual(found["private_matched_branches"][0]["world"],0)
        self.assertEqual(found["private_matched_branches"][1]["world"],1)
        self.assertIn(found["private_actor_only_pre_action_categories"]
                      ["public_wall_segment"],("early","middle","late"))


if __name__=="__main__":
    unittest.main()
