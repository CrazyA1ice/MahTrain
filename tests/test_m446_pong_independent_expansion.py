"""M4.46: frozen original policy, independent-shuffle inference and resume."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]
import test_m445_pong_threshold_trial as old_fixture
from mahtrain_core.ai_pong_independent_expansion import (
    FROZEN_SEED_COUNT, PROTOCOL, SUMMARY, PRIVATE_BATCH,
    run_independent_pong_expansion,
)
from mahtrain_core.ai_pong_threshold_trial import _path as m445_shard
from mahtrain_core.ai_selfplay_local_batch import _get_json


class IndependentExpansionTests(unittest.TestCase):
    def setUp(self):
        self.old=old_fixture.PongThresholdTests(
            methodName="test_two_new_seeds_ten_paid_games_and_safe_aggregation"
        )
        self.old.setUp()
        self.addCleanup(self.old.doCleanups)
        self.old._run()  # two COMPLETE prior real-game-contract seed shards
        self.output=self.old.root/"m446"

    def run_trial(self,*,start=92500,resume=False,game=old_fixture.fake_full_game):
        with patch("mahtrain_core.ai_pong_independent_expansion.load_frozen_local_model",
                   return_value=((-.1,-.02,-.01),self.old.meta)), \
             patch("mahtrain_core.ai_pong_threshold_trial.load_frozen_local_model",
                   return_value=((-.1,-.02,-.01),self.old.meta)), \
             patch("mahtrain_core.ai_pong_threshold_trial._one_game",
                   side_effect=game) as played:
            safe=run_independent_pong_expansion(
                training_dir=self.old.train,
                prior_m445_dir=self.old.out,
                seed_start=start,seeds=FROZEN_SEED_COUNT,
                out_dir=self.output,resume=resume,
            )
        return safe,played.call_count

    def test_20_new_independent_shuffles_and_100_actual_game_contracts(self):
        report,played=self.run_trial()
        self.assertEqual(played,100)
        self.assertEqual(report["protocol"],PROTOCOL)
        self.assertEqual(report["independent_original_shuffle_clusters"],20)
        self.assertEqual(report["real_complete_paid_games"],100)
        self.assertEqual(report["actual_rotated_candidate_games"] if
                         "actual_rotated_candidate_games" in report else
                         report["candidate_four_seat_rotated_games"],80)
        self.assertEqual(report["actual_peng_overrides"],80)
        self.assertEqual(report["original_shuffles_with_actual_peng_override"],20)
        self.assertEqual(report["independent_shuffles_positive"],20)
        self.assertEqual(report["mean_official_net_delta_points"],20)
        self.assertTrue(report["old_pilot_not_pooled_with_new_evaluation"])
        self.assertTrue(report["frozen_original_m445_policy_used_without_retraining"])
        self.assertEqual(_get_json(self.output/SUMMARY),report)
        s=json.dumps(report,ensure_ascii=False)
        for forbidden in ("92500","92300","PRIVATE_",
                          '"hand":',"b"*64,str(self.old.train)):
            self.assertNotIn(forbidden,s)
        self.assertTrue(m445_shard(self.output/PRIVATE_BATCH,0).is_file())

    def test_resume_finished_twenty_clust_and_never_replay(self):
        self.run_trial()
        report,n=self.run_trial(resume=True,game=AssertionError("not replayed"))
        self.assertEqual(n,0)
        self.assertEqual(report["completed_original_shuffles_reused_on_resume"],20)

    def test_interrupted_seed_replays_only_unfinished_five_games(self):
        def crash(seed,seat):
            if seed==92501:
                raise RuntimeError("simulated full-game interruption")
            return old_fixture.fake_full_game(seed,seat)
        with self.assertRaisesRegex(RuntimeError,"simulated"):
            self.run_trial(game=crash)
        self.assertTrue(m445_shard(self.output/PRIVATE_BATCH,0).is_file())
        self.assertFalse(m445_shard(self.output/PRIVATE_BATCH,1).exists())
        report,n=self.run_trial(resume=True)
        self.assertEqual(n,95)
        self.assertEqual(report["completed_original_shuffles_reused_on_resume"],1)

    def test_reject_prior_pilot_and_train_seed_reuse(self):
        for seed in (89800,92300,92301):
            with self.subTest(seed=seed):
                with self.assertRaisesRegex(ValueError,"overlap"):
                    self.run_trial(start=seed)
        self.assertFalse(self.output.exists())

    def test_refuse_modified_frozen_plan_and_same_dir_without_resume(self):
        self.run_trial()
        with self.assertRaisesRegex(ValueError,"new empty"):
            self.run_trial()
        with self.assertRaisesRegex(ValueError,"frozen source, seeds, or plan changed"):
            self.run_trial(start=92501,resume=True)
        plan=self.output/"PRIVATE_m446_frozen_expansion_plan.json"
        payload=_get_json(plan)
        payload["unchanged_m445_source_sha256"]="0"*64
        plan.write_text(json.dumps(payload),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"frozen source"):
            self.run_trial(resume=True)

    def test_reject_corrupt_old_m445_summary_and_private_shards(self):
        summary=self.old.out/"safe_pong_threshold_trial.json"
        data=_get_json(summary)
        data["mean_official_net_delta_points"]=999
        summary.write_text(json.dumps(data),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"does not match private"):
            self.run_trial()
        data["mean_official_net_delta_points"]=20
        summary.write_text(json.dumps(data),encoding="utf8")
        shard=m445_shard(self.old.out,0)
        bad=_get_json(shard)
        bad["sha256_case"]="0"*64
        shard.write_text(json.dumps(bad),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            self.run_trial()


if __name__=="__main__":
    unittest.main()
