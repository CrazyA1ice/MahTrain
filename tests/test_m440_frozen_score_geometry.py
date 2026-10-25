"""M4.40: exact signed-feature margin verification without rerunning games."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"tests"),str(ROOT)]

from test_m439_actor_discard_diagnostics import _fake_match
from mahtrain_core.ai_shadow_headtohead import (
    PROTOCOL as M436_PROTOCOL, SHARD_PROTOCOL as M437_SHARD,
    _paired_digest,
)
from mahtrain_core.ai_shadow_action_diagnostics import (
    _case_path, run_actor_diagnostics,
)
from mahtrain_core.ai_shadow_score_geometry import (
    PROTOCOL, SUMMARY, audit_frozen_score_geometry,
)

W=(-.1,-.02,-.01)


def correct_margin_case(seed,weights,*,capture_diagnostics=False):
    """Fixture from M4.39 plus true, mathematically reconstructed margins."""
    obj=_fake_match(seed,weights,capture_diagnostics=capture_diagnostics)
    for row in obj["seat_rotation_results"]:
        step=row["private_actor_discard_trace"][0]
        baseline=[round(step["baseline_effective_tile_count"]/40,7),
                  round(step["baseline_next_draw_probability"],7),
                  round(step["baseline_effective_types_count"]/27,7)]
        chosen=[round(step["chosen_effective_tile_count"]/40,7),
                round(step["chosen_next_draw_probability"],7),
                round(step["chosen_effective_types_count"]/27,7)]
        step["model_margin"]=sum(w*(a-b) for w,a,b in zip(W,chosen,baseline))
    return obj


class ScoreGeometryTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.train=self.root/"m434-training"
        self.prev=self.root/"m437-completed"
        self.eval=self.root/"m439-frozen-actor"
        self.report=self.root/"m440-score"
        self.prev.mkdir()
        self.meta={
            "model_sha256":"b"*64,
            "source_m434_train_seed_start":89800,
            "source_m434_seed_end_exclusive":89804,
        }
        self.prev.joinpath("PRIVATE_frozen_benchmark_plan.json").write_text(
            json.dumps({
                "protocol":M436_PROTOCOL,
                "resumable_shards_protocol":M437_SHARD,
                "private_source_training_directory":str(self.train.resolve()),
                "private_frozen_model_sha256":self.meta["model_sha256"],
                "private_evaluation_seed_start":91100,
                "private_eval_original_shuffle_count":2,
            }),encoding="utf8")
        with patch("mahtrain_core.ai_shadow_action_diagnostics.load_frozen_local_model",
                   return_value=(W,self.meta)), \
             patch("mahtrain_core.ai_shadow_action_diagnostics.evaluate_one_seed",
                   side_effect=correct_margin_case) as play:
            self.original=run_actor_diagnostics(
                training_dir=self.train,prior_evaluation_dir=self.prev,
                seed_start=91300,seeds=2,out_dir=self.eval
            )
        self.assertEqual(play.call_count,2)

    def _audit(self,model=None):
        with patch("mahtrain_core.ai_shadow_score_geometry.load_frozen_local_model",
                   return_value=(W,model or self.meta)), \
             patch("mahtrain_core.ai_shadow_action_diagnostics.evaluate_one_seed",
                   side_effect=AssertionError("M4.40 MUST NOT replay")):
            return audit_frozen_score_geometry(
                training_dir=self.train,actor_evaluation_dir=self.eval,
                report_dir=self.report,
            )

    def test_exact_frozen_score_decomposition_and_privacy(self):
        before={str(p.relative_to(self.eval)):p.read_bytes()
                for p in self.eval.rglob("*") if p.is_file()}
        info=self._audit()
        self.assertEqual(info["protocol"],PROTOCOL)
        self.assertEqual(info["original_independent_shuffle_seed_clusters"],2)
        self.assertEqual(info["real_finished_games_already_reused"],10)
        self.assertEqual(info["overrides_verified_against_exact_frozen_weights"],8)
        self.assertEqual(info["baseline_kept_decisions"],8)
        self.assertEqual(info["cut_effective_tile_count_decreased"],8)
        self.assertEqual(info["would_abstain_if_effective_tile_count_must_not_decrease"],8)
        self.assertEqual(info["would_still_be_eligible_under_non_decrease_guard"],0)
        self.assertTrue(info["zero_override_expected_if_guard_blocks_all_recorded_cuts"])
        self.assertEqual(info["frozen_weight_signs_only"],{
            "effective_tile_count":"negative",
            "next_draw_probability":"negative",
            "effective_tile_types":"negative",
        })
        self.assertEqual(info["mean_model_margin_component_on_override"][
            "effective_tile_count"],.005)
        self.assertEqual(info["positive_negative_zero_feature_contributions"][
            "next_draw_probability"]["positive"],8)
        self.assertEqual(info["source_paired_mean_official_net_delta_points"],-250)
        public=(self.report/SUMMARY).read_text(encoding="utf8")
        for secret in ('"hand":',"91300","91100","m1","m2",
                       '"private_actor_discard_trace"', '"private_eval_seed_start"',
                       '"private_frozen_model_sha256"', str(self.train),"b"*64):
            self.assertNotIn(secret,public)
        self.assertEqual(json.loads(public),info)
        self.assertEqual(before,{str(p.relative_to(self.eval)):p.read_bytes()
                                 for p in self.eval.rglob("*") if p.is_file()})

    def test_reject_model_hash_mismatch(self):
        with self.assertRaisesRegex(ValueError,"plan/model mismatch"):
            self._audit(model=dict(self.meta,model_sha256="a"*64))
        self.assertFalse(self.report.exists())

    def test_refuse_tampered_positive_margin_even_with_updated_checksum(self):
        path=_case_path(self.eval,0)
        raw=json.loads(path.read_text())
        raw["private_case"]["seat_rotation_results"][0][
            "private_actor_discard_trace"][0]["model_margin"]+=0.02
        raw["sha256_case"]=_paired_digest(raw["private_case"])
        path.write_text(json.dumps(raw),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"margin does not match"):
            self._audit()
        self.assertFalse(self.report.exists())

    def test_refuse_incomplete_source_and_original_summary_tampering(self):
        _case_path(self.eval,1).unlink()
        with self.assertRaisesRegex(ValueError,"incomplete"):
            self._audit()
        self.assertFalse(self.report.exists())

    def test_refuse_inconsistent_source_safe_summary(self):
        p=self.eval/"safe_actor_decision_diagnostics.json"
        safe=json.loads(p.read_text())
        safe["actual_model_override_count"]=1234
        p.write_text(json.dumps(safe),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"no longer matches"):
            self._audit()

    def test_output_cannot_overwrite_prior_evidence(self):
        self._audit()
        with self.assertRaisesRegex(ValueError,"new or empty"):
            self._audit()
        with patch("mahtrain_core.ai_shadow_score_geometry.load_frozen_local_model",
                   return_value=(W,self.meta)):
            with self.assertRaisesRegex(ValueError,"separate"):
                audit_frozen_score_geometry(
                    training_dir=self.train,
                    actor_evaluation_dir=self.eval,report_dir=self.eval,
                )


if __name__=="__main__":
    unittest.main()
