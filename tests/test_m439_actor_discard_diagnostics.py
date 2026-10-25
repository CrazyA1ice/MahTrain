"""M4.39 fast regression: capture legal actor choices & audit NEW seeds.

Fast evaluation stubs satisfy paid-match contracts; the M4.36 integration
suite additionally tests real rule-engine completion with these diagnostics.
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

from mahtrain_core.ai_shadow_headtohead import (
    FrozenShadowAgent, SHARD_PROTOCOL as OLD_SHARD,
    PROTOCOL as OLD_PROTOCOL, _paired_digest,
)
from mahtrain_core.ai_shadow_action_diagnostics import (
    PROTOCOL, SHARD_PROTOCOL, MANIFEST, SUMMARY, _case_path,
    run_actor_diagnostics,
)

TARGET="mahtrain_core.ai_shadow_action_diagnostics"


def _fake_match(seed,weights,*,capture_diagnostics=False):
    if not capture_diagnostics:
        raise AssertionError("actor trace mode not enabled")
    by_seat=[]
    for seat in range(4):
        trace=[
            {"decision_ordinal":1,"overrode":True,
             "kept_minimum_shanten":True,
             "baseline_discard":"m1","chosen_discard":"m2",
             "reason":"positive_frozen_margin","model_margin":.02,
             "minimum_shanten":1,
             "baseline_effective_tile_count":6,
             "chosen_effective_tile_count":4,
             "baseline_next_draw_probability":.15,
             "chosen_next_draw_probability":.10,
             "baseline_effective_types_count":3,
             "chosen_effective_types_count":2,
             "eligible_minimum_shanten_cut_count":3},
            {"decision_ordinal":2,"overrode":False,
             "kept_minimum_shanten":True,
             "baseline_discard":"p5","chosen_discard":"p5",
             "reason":"no_better_frozen_margin","model_margin":0.},
        ]
        delta=-100*(seat+1)
        by_seat.append({
            "seat":seat,
            "challenge_baseline_official_net":0,
            "shadow_official_net":delta,
            "delta_shadow_minus_challenge":delta,
            "shadow_discard_decisions":2,
            "shadow_override_count":1,
            "challenge_baseline_game_phase":"finished",
            "shadow_game_phase":"finished",
            "real_win_delta":delta+10,
            "real_kong_delta":-10,
            "real_exhaustive_delta":0,
            "private_actor_discard_trace":trace,
        })
    return {
        "private_evaluation_shuffle_seed":seed,
        "seat_rotation_results":by_seat,
        "original_natural_shuffle_seed_is_one_statistical_cluster":True,
        "complete_authoritative_games":5,
        "same_opening_seed_per_comparison":True,
        "no_real_skill_claim":True,
    }


class FrozenDecisionDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.train=self.root/"m434"
        self.prior=self.root/"m437-prior"
        self.prior.mkdir()
        self.out=self.root/"m439-new"
        self.model={"model_sha256":"a"*64,
                    "source_m434_train_seed_start":89800,
                    "source_m434_seed_end_exclusive":89804}
        self.prior.joinpath("PRIVATE_frozen_benchmark_plan.json").write_text(
            json.dumps({
                "protocol":OLD_PROTOCOL,
                "resumable_shards_protocol":OLD_SHARD,
                "private_source_training_directory":str(self.train.resolve()),
                "private_frozen_model_sha256":"a"*64,
                "private_evaluation_seed_start":91100,
                "private_eval_original_shuffle_count":2,
            }),encoding="utf8")

    def _run(self,*,resume=False,seed_start=91300,seeds=2,
             effect=_fake_match,model=None):
        with patch(TARGET+".load_frozen_local_model",
                   return_value=((.1,.02,.01),model or self.model)), \
             patch(TARGET+".evaluate_one_seed",side_effect=effect) as played:
            result=run_actor_diagnostics(
                training_dir=self.train,prior_evaluation_dir=self.prior,
                seed_start=seed_start,seeds=seeds,
                out_dir=self.out,resume=resume,
            )
        return result,played.call_count

    def test_only_new_seeds_and_safe_aggregate(self):
        summary,played=self._run()
        self.assertEqual(played,2)
        self.assertEqual(summary["original_shuffle_seed_clusters"],2)
        self.assertEqual(summary["actual_real_complete_games"],10)
        self.assertEqual(summary["actor_discard_opportunities"],16)
        self.assertEqual(summary["actual_model_override_count"],8)
        self.assertEqual(summary["baseline_kept_discard_count"],8)
        self.assertEqual(summary["actor_visible_effective_tile_count_lower_on_override"],8)
        self.assertEqual(summary["actor_visible_effective_tile_count_higher_on_override"],0)
        self.assertEqual(summary["mean_actor_visible_effective_tile_delta_on_override"],-2)
        self.assertEqual(summary["paired_mean_official_net_delta_points"],-250)
        self.assertTrue(summary["diagnosed_cuts_are_not_single_action_counterfactual_effects"])
        self.assertEqual(summary["reused_completed_original_shuffle_clusters"],0)
        self.assertEqual(summary["per_seat_paired_mean_official_net_delta_points"],
                         [-100,-200,-300,-400])
        self.assertEqual(json.loads((self.out/SUMMARY).read_text()),summary)
        public=(self.out/SUMMARY).read_text()
        for secret in ("91300","91301","91100","m1","m2","hand",
                       "private_actor_discard_trace","a"*64):
            self.assertNotIn(secret,public)
        private=json.loads(_case_path(self.out,0).read_text())
        self.assertEqual(private["protocol"],SHARD_PROTOCOL)
        self.assertEqual(private["private_case"][
            "seat_rotation_results"][0]["private_actor_discard_trace"][0][
                "baseline_discard"],"m1")

    def test_resume_reuses_all_five_game_shards(self):
        self._run()
        summary,called=self._run(resume=True,effect=AssertionError("replayed old games"))
        self.assertEqual(called,0)
        self.assertEqual(summary["reused_completed_original_shuffle_clusters"],2)

    def test_interrupted_seed_resumes_only_unfinished_seed(self):
        ran=[]
        def interrupted(seed,weights,*,capture_diagnostics=False):
            ran.append(seed)
            if len(ran)==2:
                raise RuntimeError("Windows stopped")
            return _fake_match(seed,weights,capture_diagnostics=capture_diagnostics)
        with self.assertRaisesRegex(RuntimeError,"Windows stopped"):
            self._run(effect=interrupted)
        self.assertTrue(_case_path(self.out,0).is_file())
        self.assertFalse(_case_path(self.out,1).exists())
        summary,called=self._run(resume=True)
        self.assertEqual(called,1)
        self.assertEqual(summary["reused_completed_original_shuffle_clusters"],1)

    def test_disjoint_old_training_and_prior_seeds_enforced(self):
        with self.assertRaisesRegex(ValueError,"already seen"):
            self._run(seed_start=91101)
        with self.assertRaisesRegex(ValueError,"overlaps training"):
            self._run(seed_start=89801)
        with self.assertRaisesRegex(ValueError,"new diagnostic output"):
            self._run(seeds=0)

    def test_wrong_frozen_weights_manifest_or_resume_is_rejected(self):
        self._run()
        with self.assertRaisesRegex(ValueError,"must be empty"):
            self._run()
        with self.assertRaisesRegex(ValueError,"resume plan or model changed"):
            self._run(resume=True,seeds=1)
        mismatch=dict(self.model,model_sha256="b"*64)
        with self.assertRaisesRegex(ValueError,"does not match frozen source"):
            self._run(resume=True,model=mismatch)

    def test_reject_tampered_actor_trace_even_with_updated_digest(self):
        self._run()
        p=_case_path(self.out,0)
        envelope=json.loads(p.read_text())
        step=envelope["private_case"]["seat_rotation_results"][0][
            "private_actor_discard_trace"][0]
        step["opponent_hand"]=["s9"]
        envelope["sha256_case"]=_paired_digest(envelope["private_case"])
        p.write_text(json.dumps(envelope),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"invalid actor-only"):
            self._run(resume=True)

    def test_decision_no_model_does_not_leak_raw_view(self):
        a=FrozenShadowAgent(
            seed=90112,seat=0,weights=None,capture_diagnostics=True)
        view={"seat":0,"hand":["m1"],"hidden_future_wall":["p2"]}
        with patch.object(a._delegate,"discard",return_value="m1"):
            self.assertEqual(a.discard(view),"m1")
        self.assertEqual(a.private_actor_discard_trace,[{
            "decision_ordinal":1,
            "overrode":False,
            "kept_minimum_shanten":True,
            "baseline_discard":"m1",
            "reason":"no_frozen_weights",
            "model_margin":0.,
            "chosen_discard":"m1",
        }])
        self.assertNotIn("hidden_future_wall",
                         json.dumps(a.private_actor_discard_trace))

    def test_unmodified_default_agent_has_no_diagnostic_trace(self):
        a=FrozenShadowAgent(seed=90112,seat=0,weights=None)
        with patch.object(a._delegate,"discard",return_value="p3"):
            self.assertEqual(a.discard({"hand":["p3"]}),"p3")
        self.assertFalse(a.private_actor_discard_trace)
        self.assertEqual(a.override_count,0)


if __name__=="__main__":
    unittest.main()
