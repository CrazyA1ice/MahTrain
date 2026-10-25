"""M4.41: explicit conservative cut veto and original-shuffle trial integrity."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]
from mahtrain_core.ai_shadow_headtohead import (
    PROTOCOL as OLD_GAME_PROTOCOL, SHARD_PROTOCOL as OLD_SHARD,
    FrozenShadowAgent, _paired_digest,
)
from mahtrain_core.ai_shadow_action_diagnostics import PROTOCOL as M439_PROTOCOL
from mahtrain_core.ai_shadow_guarded_trial import (
    PROTOCOL, SUMMARY, _path, run_guarded_trial,
)
from mahtrain_core.ai_selfplay_local_batch import _get_json


def _actual_ledger_stub(seed,seat,weights,*,minimum_ukeire_guard=False,
                        capture_diagnostics=False):
    net=[0]*4
    if seat is not None and not minimum_ukeire_guard:
        net[seat]=-100
        net[(seat+1)%4]=100
    return {
        "phase":"finished",
        "official_net_by_seat":net,
        "win_points_by_seat":list(net),
        "kong_points_by_seat":[0]*4,
        "exhaustive_points_by_seat":[0]*4,
        "shadow_discard_decisions":3 if seat is not None else 0,
        "shadow_override_count":(
            2 if seat is not None and not minimum_ukeire_guard else 0),
        **({"shadow_guard_blocked_count":2}
           if seat is not None and minimum_ukeire_guard else {}),
    }


class GuardedFrozenTrialTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.train=self.root/"m434"
        self.p437=self.root/"old-m437"
        self.p439=self.root/"old-m439"
        self.out=self.root/"new-m441"
        self.p437.mkdir()
        self.p439.mkdir()
        self.prov={
            "model_sha256":"b"*64,
            "source_m434_train_seed_start":89800,
            "source_m434_seed_end_exclusive":89804,
            "trained_original_shuffle_clusters":2,
        }
        self.weights=(-.1,-.02,-.01)
        (self.p437/"PRIVATE_frozen_benchmark_plan.json").write_text(
            json.dumps({
                "protocol":OLD_GAME_PROTOCOL,
                "resumable_shards_protocol":OLD_SHARD,
                "private_source_training_directory":str(self.train.resolve()),
                "private_frozen_model_sha256":"b"*64,
                "private_evaluation_seed_start":91100,
                "private_eval_original_shuffle_count":2,
            }),encoding="utf8")
        (self.p439/"PRIVATE_actor_diagnostic_plan.json").write_text(
            json.dumps({
                "protocol":M439_PROTOCOL,
                "private_source_training_directory":str(self.train.resolve()),
                "private_source_m437_directory":str(self.p437.resolve()),
                "private_frozen_model_sha256":"b"*64,
                "online_policy_changed":False,
                "private_eval_seed_start":91300,
                "private_eval_seed_count":2,
            }),encoding="utf8")

    def _run(self,*,resume=False,seeds=2,seed_start=91500,game=None):
        with patch("mahtrain_core.ai_shadow_guarded_trial.load_frozen_local_model",
                   return_value=(self.weights,self.prov)), \
             patch("mahtrain_core.ai_shadow_guarded_trial._finish_real_full_game",
                   side_effect=game or _actual_ledger_stub) as played:
            result=run_guarded_trial(
                training_dir=self.train,
                prior_m437_dir=self.p437,
                prior_m439_dir=self.p439,
                seed_start=seed_start,seeds=seeds,
                out_dir=self.out,resume=resume,
            )
        return result,played.call_count

    def test_nine_full_paid_games_per_original_seed_and_public_data(self):
        result,calls=self._run()
        self.assertEqual(calls,18)
        self.assertEqual(result["protocol"],PROTOCOL)
        self.assertEqual(result["completed_original_shuffle_clusters"],2)
        self.assertEqual(result["actual_complete_paid_games"],18)
        self.assertEqual(result["guarded"]["actual_model_overrides"],0)
        self.assertEqual(result["guarded"]["guard_blocked_lower_ukeire_overrides"],16)
        self.assertEqual(result["guarded"]["mean_paired_official_net_delta_points"],0)
        self.assertEqual(result["unguarded"]["actual_model_overrides"],16)
        self.assertEqual(result["unguarded"]["mean_paired_official_net_delta_points"],-100)
        self.assertEqual(result["unguarded"]["candidate_discard_opportunities"],24)
        self.assertEqual(result["guarded"]["candidate_discard_opportunities"],24)
        self.assertTrue(result["insufficient_original_shuffles_for_exploratory_comparison"])
        self.assertTrue(result["online_challenge_ai_unchanged"])
        self.assertEqual(_get_json(self.out/SUMMARY),result)
        self.assertEqual(
            _get_json(_path(self.out,0))["private_case"]["complete_authoritative_games"],9)
        public=json.dumps(result)
        for token in ("91500","91501","91100","91300",
                      "PRIVATE_",'"hand":',"b"*64,str(self.train)):
            self.assertNotIn(token,public)

    def test_durable_checkpoints_zero_replay_on_resume(self):
        self._run()
        result,calls=self._run(resume=True,game=AssertionError("no replay"))
        self.assertEqual(calls,0)
        self.assertEqual(result["completed_seed_shards_reused_on_resume"],2)

    def test_interrupted_second_seed_replays_only_missing_nine_games(self):
        calls=[]
        def fail_on_new_cluster(seed,seat,weights,*,minimum_ukeire_guard=False,
                                capture_diagnostics=False):
            calls.append(seed)
            if seed==91501:
                raise RuntimeError("simulated crash")
            return _actual_ledger_stub(
                seed,seat,weights,minimum_ukeire_guard=minimum_ukeire_guard)
        with self.assertRaisesRegex(RuntimeError,"simulated crash"):
            self._run(game=fail_on_new_cluster)
        self.assertTrue(_path(self.out,0).is_file())
        self.assertFalse(_path(self.out,1).exists())
        result,calls=self._run(resume=True)
        self.assertEqual(calls,9)
        self.assertEqual(result["completed_seed_shards_reused_on_resume"],1)

    def test_no_historical_seed_overlap_and_no_plan_mutations(self):
        for seed in (89801,91100,91101,91300,91301):
            with self.subTest(seed=seed):
                with self.assertRaisesRegex(ValueError,"overlap"):
                    self._run(seed_start=seed,seeds=1)
        self.assertFalse(self.out.exists())
        self._run()
        with self.assertRaisesRegex(ValueError,"empty"):
            self._run()
        with self.assertRaisesRegex(ValueError,"resume plan"):
            self._run(resume=True,seeds=1)

    def test_corrupt_digest_rejected_prior_to_new_games(self):
        self._run()
        shard=_path(self.out,0)
        record=_get_json(shard)
        record["private_case"]["seat_rotation_results"][0]["policies"][
            "guarded"]["blocked_lower_effective_tiles"]=99
        record["sha256_case"]=_paired_digest(record["private_case"])
        shard.write_text(json.dumps(record),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"impossible guard"):
            self._run(resume=True,game=AssertionError("must not play"))

    def test_genuine_checksum_flip_fails_closed(self):
        self._run()
        shard=_path(self.out,0)
        record=_get_json(shard)
        record["sha256_case"]="0"*64
        shard.write_text(json.dumps(record),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"checksum mismatch"):
            self._run(resume=True,game=AssertionError("must not play"))

    def test_true_actor_only_minimum_ukeire_guard_vetoes_regression(self):
        view={
            "seat":0,"hand":["m1","m2"],
            "own_melds":[],
            "missing_suits":["s"]*4,
        }
        oracle={
            "status":"choose_discard","minimum_shanten":1,
            "candidates":[
                {"discard":"m1","shanten":1,"effective_tile_count":12,
                 "next_draw_probability":.3,"effective_types":["p1","p2"]},
                {"discard":"m2","shanten":1,"effective_tile_count":4,
                 "next_draw_probability":.1,"effective_types":["p1"]},
            ],
        }
        with patch("mahtrain_core.ai_shadow_headtohead.analyze_discards",
                   return_value=oracle), \
             patch("mahtrain_core.ai_shadow_headtohead.visible_tiles",
                   return_value=[]):
            guard=FrozenShadowAgent(seed=91500,seat=0,weights=self.weights,
                                    minimum_ukeire_guard=True)
            raw=FrozenShadowAgent(seed=91500,seat=0,weights=self.weights)
            with patch.object(guard._delegate,"discard",return_value="m1"), \
                 patch.object(raw._delegate,"discard",return_value="m1"):
                self.assertEqual(guard.discard(view),"m1")
                self.assertEqual(raw.discard(view),"m2")
            self.assertEqual(guard.override_count,0)
            self.assertEqual(guard.rejected_ukeire_regressions,1)
            self.assertEqual(raw.override_count,1)

    def test_guard_allows_equal_effective_tile_cut_with_positive_score(self):
        view={
            "seat":0,"hand":["m1","m2"],"own_melds":[],
            "missing_suits":["s"]*4,
        }
        oracle={
            "status":"choose_discard","minimum_shanten":1,
            "candidates":[
                {"discard":"m1","shanten":1,"effective_tile_count":10,
                 "next_draw_probability":.25,"effective_types":["p1","p2"]},
                {"discard":"m2","shanten":1,"effective_tile_count":10,
                 "next_draw_probability":.25,"effective_types":["p1"]},
            ],
        }
        agent=FrozenShadowAgent(seed=91500,seat=0,weights=self.weights,
                                minimum_ukeire_guard=True)
        with patch("mahtrain_core.ai_shadow_headtohead.analyze_discards",
                   return_value=oracle), \
             patch("mahtrain_core.ai_shadow_headtohead.visible_tiles",
                   return_value=[]), \
             patch.object(agent._delegate,"discard",return_value="m1"):
            self.assertEqual(agent.discard(view),"m2")
        self.assertEqual(agent.override_count,1)
        self.assertEqual(agent.rejected_ukeire_regressions,0)


if __name__=="__main__":
    unittest.main()
