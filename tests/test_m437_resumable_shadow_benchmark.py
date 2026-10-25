"""M4.37 regression: durable per-seed 5-game paired evaluation checkpoints.

These focused crash/restart tests mock expensive COMPLETE seed evaluation, not
the terminal rules. M4.36's real full-game integration suite covers that
engine separately. No offline candidate is promoted into the live AI.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]

from mahtrain_core.ai_selfplay_local_batch import _get_json
from mahtrain_core.ai_shadow_headtohead import (
    SHARD_DIR, SHARD_PROTOCOL, _cluster_path, _paired_digest,
    _resume_cases, evaluate_frozen_shadow,
)

TARGET="mahtrain_core.ai_shadow_headtohead"


def _dummy_real_five_game_seed(seed: int, weights: tuple[float,...]|None):
    """Contract-shaped test double: five reconciled games per one shuffle."""
    rows=[]
    for seat in range(4):
        delta=(seat+1)*10+(seed % 7) if weights else 0
        rows.append({
            "seat":seat,
            "challenge_baseline_official_net":0,
            "shadow_official_net":delta,
            "delta_shadow_minus_challenge":delta,
            "shadow_discard_decisions":2,
            "shadow_override_count":1 if weights else 0,
            "challenge_baseline_game_phase":"finished",
            "shadow_game_phase":"finished",
            "real_win_delta":delta,
            "real_kong_delta":0,
            "real_exhaustive_delta":0,
        })
    return {
        "private_evaluation_shuffle_seed":seed,
        "seat_rotation_results":rows,
        "original_natural_shuffle_seed_is_one_statistical_cluster":True,
        "complete_authoritative_games":5,
        "same_opening_seed_per_comparison":True,
        "no_real_skill_claim":True,
    }


class ResumableFourSeatBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.train=self.root/"m434-old-original-train"
        self.output=self.root/"m437-new-evaluation"
        self.seeds=3
        self.seed_start=90100
        self.weights=(0.08,0.01,0.02)
        self.provenance={
            "model_sha256":"a"*64,
            "source_m434_train_seed_start":89800,
            "source_m434_seed_end_exclusive":89804,
            "trained_original_shuffle_clusters":2,
        }

    def _call(self, *, resume=False, seeds=None, seed_start=None):
        return evaluate_frozen_shadow(
            training_dir=self.train,
            seed_start=self.seed_start if seed_start is None else seed_start,
            seeds=self.seeds if seeds is None else seeds,
            out_dir=self.output,
            resume=resume,
        )

    def _run(self, *, resume=False, game_effect=None, seeds=None,
             seed_start=None, provenance=None):
        with patch(TARGET+".load_frozen_local_model",
                   return_value=(self.weights,provenance or self.provenance)), \
             patch(TARGET+".evaluate_one_seed",
                   side_effect=game_effect or _dummy_real_five_game_seed) as play:
            value=self._call(resume=resume,seeds=seeds,seed_start=seed_start)
        return value,play.call_count

    def test_crash_after_first_finished_seed_then_resume_only_missing_seeds(self):
        calls=[]
        def interrupted(seed,weights):
            calls.append(seed)
            if len(calls)==2:
                raise RuntimeError("simulated Windows termination")
            return _dummy_real_five_game_seed(seed,weights)
        with self.assertRaisesRegex(RuntimeError,"Windows termination"):
            self._run(game_effect=interrupted)
        self.assertEqual(calls,[90100,90101])
        self.assertTrue(_cluster_path(self.output,0).is_file())
        self.assertFalse(_cluster_path(self.output,1).exists())
        self.assertFalse((self.output/"safe_four_seat_shadow_summary.json").exists())
        self.assertFalse((self.output/"PRIVATE_four_seat_paired_matches.jsonl.gz").exists())
        summary,played=self._run(resume=True)
        self.assertEqual(played,2)  # no re-running already paid five games
        self.assertEqual(summary["reused_prior_completed_seed_shards"],1)
        self.assertEqual(summary["interruption_safe_completed_seed_shards"],3)
        self.assertEqual(summary["actual_real_complete_games"],15)
        self.assertEqual(summary["candidate_legal_minimum_shanten_overrides"],12)
        self.assertEqual(summary["independent_initial_shuffle_seed_clusters"],3)
        self.assertTrue(summary["official_score_ledger_reconciled"])
        self.assertEqual(_get_json(self.output/"safe_four_seat_shadow_summary.json"),
                         summary)
        import gzip
        with gzip.open(self.output/"PRIVATE_four_seat_paired_matches.jsonl.gz",
                       "rt",encoding="utf8") as fp:
            rows=[json.loads(line) for line in fp]
        self.assertEqual([x["private_evaluation_shuffle_seed"] for x in rows],
                         [90100,90101,90102])
        self.assertEqual([len(x["seat_rotation_results"]) for x in rows],
                         [4,4,4])
        self.assertNotIn("90100",json.dumps(summary))
        self.assertNotIn(str(self.train),json.dumps(summary))
        self.assertNotIn("private_case",json.dumps(summary))
        again,no_replayed=self._run(resume=True)
        self.assertEqual(no_replayed,0)
        self.assertEqual(again["reused_prior_completed_seed_shards"],3)
        self.assertEqual(again["seat_rotated_seed_cluster_mean_delta_points"],
                         summary["seat_rotated_seed_cluster_mean_delta_points"])

    def test_refuse_non_resume_overwrite_and_plan_or_model_mismatch(self):
        self._run()
        with self.assertRaisesRegex(ValueError,"new/empty"):
            self._run()
        with self.assertRaisesRegex(ValueError,"plan differs"):
            self._run(resume=True,seeds=2)
        with self.assertRaisesRegex(ValueError,"plan differs"):
            self._run(resume=True,seed_start=90200)
        mismatch=dict(self.provenance,model_sha256="b"*64)
        with self.assertRaisesRegex(ValueError,"plan differs"):
            self._run(resume=True,provenance=mismatch)

    def test_reject_corrupt_checksum_before_cpu_replay(self):
        self._run()
        shard=_cluster_path(self.output,1)
        obj=_get_json(shard)
        obj["private_case"]["annotation"]="unaudited"
        shard.write_text(json.dumps(obj),encoding="utf8")
        with patch(TARGET+".evaluate_one_seed") as play, \
             patch(TARGET+".load_frozen_local_model",
                   return_value=(self.weights,self.provenance)):
            with self.assertRaisesRegex(ValueError,"checksum mismatch"):
                self._call(resume=True)
        play.assert_not_called()

    def test_reject_wrong_seed_even_with_recomputed_checksum(self):
        self._run()
        shard=_cluster_path(self.output,0)
        obj=_get_json(shard)
        obj["private_case"]["private_evaluation_shuffle_seed"]=90333
        obj["sha256_paired_seed"]=_paired_digest(obj["private_case"])
        shard.write_text(json.dumps(obj),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"mismatched paired shuffle"):
            self._run(resume=True)

    def test_reject_partial_or_nonreconciled_seat_results(self):
        self._run()
        shard=_cluster_path(self.output,2)
        obj=_get_json(shard)
        obj["private_case"]["seat_rotation_results"].pop()
        obj["sha256_paired_seed"]=_paired_digest(obj["private_case"])
        shard.write_text(json.dumps(obj),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"all four rotated seats"):
            self._run(resume=True)

    def test_do_not_use_forged_out_of_range_shards_or_unknown_files(self):
        self._run()
        rogue=self.output/SHARD_DIR/"index-00000008.json"
        rogue.write_text("{}",encoding="utf8")
        with self.assertRaisesRegex(ValueError,"out-of-plan"):
            self._run(resume=True)
        rogue.unlink()
        (self.output/"not_from_benchmark.txt").write_text("x",encoding="utf8")
        with self.assertRaisesRegex(ValueError,"unexpected files"):
            self._run(resume=True)

    def test_orphan_atomic_temp_is_never_loaded(self):
        self._run()
        orphan=self.output/SHARD_DIR/"index-00000000.json.tmp-crashed"
        orphan.write_text('{"incomplete":true',encoding="utf8")
        summary,played=self._run(resume=True)
        self.assertEqual(played,0)
        self.assertEqual(summary["reused_prior_completed_seed_shards"],3)
        self.assertEqual(_get_json(_cluster_path(self.output,0))["protocol"],
                         SHARD_PROTOCOL)

    def test_resume_rejects_absent_plan_and_seed_overlap(self):
        with self.assertRaisesRegex(ValueError,"existing M4.37"):
            self._run(resume=True)
        with self.assertRaisesRegex(ValueError,"overlap original"):
            self._run(seed_start=89803)
        with self.assertRaisesRegex(ValueError,"resume must be a boolean"):
            self._call(resume="true")

    def test_nonchange_shadow_is_zero_delta_in_verified_saved_case(self):
        no_weights=self.root/"no-weights"
        with patch(TARGET+".load_frozen_local_model",
                   return_value=(None,self.provenance)), \
             patch(TARGET+".evaluate_one_seed",
                   side_effect=_dummy_real_five_game_seed):
            summary=evaluate_frozen_shadow(
                training_dir=self.train,seed_start=90150,seeds=1,
                out_dir=no_weights,
            )
        self.assertFalse(summary["candidate_model_had_frozen_weights"])
        self.assertEqual(summary["candidate_legal_minimum_shanten_overrides"],0)
        self.assertEqual(summary["seat_rotated_seed_cluster_mean_delta_points"],0)


if __name__=="__main__":
    unittest.main()
