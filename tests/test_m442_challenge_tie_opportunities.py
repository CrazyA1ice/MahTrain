"""M4.42: Challenge safe-discard tie space, seed provenance and resume tests.

The fast trial fixtures stand in for already-settled full Challenge games.
A separate M4.36 integration test plays real authoritative four-seat games.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]
from mahtrain_core.ai import MahjongAgent
from mahtrain_core.ai_shadow_headtohead import (
    PROTOCOL as OLD_MATCH, SHARD_PROTOCOL as OLD_SHARD,
)
from mahtrain_core.ai_shadow_action_diagnostics import PROTOCOL as OLD_ACTOR
from mahtrain_core.ai_shadow_guarded_trial import PROTOCOL as OLD_GUARD
from mahtrain_core.ai_challenge_tie_opportunities import (
    METRICS, PROTOCOL, SUMMARY, ChallengeTieProbe, _shard_file,
    run_new_seed_tie_audit,
)
from mahtrain_core.ai_selfplay_local_batch import _get_json


def _real_game_shape(seed):
    values={
        "discard_decisions":3,
        "single_policy_choice_decisions":1,
        "multichoice_minimum_shanten_decisions":2,
        "decisions_with_equal_ukeire_alternative":1,
        "decisions_with_higher_ukeire_alternative":1,
        "baseline_max_ukeire_decisions":2,
        "equal_ukeire_alternative_cuts":2,
        "higher_ukeire_alternative_cuts":1,
        "equal_ukeire_alternatives_different_score":1,
        "equal_ukeire_alternatives_different_fan_value":1,
        "equal_ukeire_alternatives_different_public_pressure":1,
        "equal_ukeire_alternatives_different_public_risk_index":1,
    }
    assert set(values)==set(METRICS)
    return {
        "private_original_shuffle_seed":seed,
        "official_complete_baseline_games":1,
        "terminal_phase":"finished",
        "official_net_by_seat":[-30,-10,40,0],
        "per_seat_actor_choice_counts":[dict(values) for _ in range(4)],
        "unchanged_live_challenge_choices":True,
        "no_hidden_opponent_hand_or_future_wall_collected":True,
    }


class ChallengeTieOpportunityTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.train=self.root/"m434"
        self.old437=self.root/"m437"
        self.old439=self.root/"m439"
        self.old441=self.root/"m441"
        self.out=self.root/"m442"
        self.prov={
            "model_sha256":"a"*64,
            "source_m434_train_seed_start":89800,
            "source_m434_seed_end_exclusive":89804,
            "trained_original_shuffle_clusters":2,
        }
        for path in (self.old437,self.old439,self.old441):
            path.mkdir()
        (self.old437/"PRIVATE_frozen_benchmark_plan.json").write_text(
            json.dumps({
                "protocol":OLD_MATCH,
                "resumable_shards_protocol":OLD_SHARD,
                "private_source_training_directory":str(self.train.resolve()),
                "private_frozen_model_sha256":"a"*64,
                "private_evaluation_seed_start":91100,
                "private_eval_original_shuffle_count":2,
            }),encoding="utf8")
        (self.old439/"PRIVATE_actor_diagnostic_plan.json").write_text(
            json.dumps({
                "protocol":OLD_ACTOR,
                "private_source_training_directory":str(self.train.resolve()),
                "private_source_m437_directory":str(self.old437.resolve()),
                "private_frozen_model_sha256":"a"*64,
                "online_policy_changed":False,
                "private_eval_seed_start":91300,
                "private_eval_seed_count":2,
            }),encoding="utf8")
        (self.old441/"PRIVATE_guard_trial_plan.json").write_text(
            json.dumps({
                "protocol":OLD_GUARD,
                "private_training_dir":str(self.train.resolve()),
                "private_prior_m437_dir":str(self.old437.resolve()),
                "private_prior_m439_dir":str(self.old439.resolve()),
                "frozen_model_sha256":"a"*64,
                "live_online_promotion":False,
                "private_seed_start":91500,
                "original_shuffle_clusters":2,
            }),encoding="utf8")

    def _run(self,*,seed_start=91700,seeds=2,resume=False,effect=_real_game_shape,
             model=None):
        with patch("mahtrain_core.ai_challenge_tie_opportunities.load_frozen_local_model",
                   return_value=((-.1,-.02,-.01),model or self.prov)), \
             patch("mahtrain_core.ai_challenge_tie_opportunities.play_one_challenge_baseline",
                   side_effect=effect) as played:
            safe=run_new_seed_tie_audit(
                training_dir=self.train,
                prior_m437_dir=self.old437,
                prior_m439_dir=self.old439,
                prior_m441_dir=self.old441,
                seed_start=seed_start,seeds=seeds,out_dir=self.out,
                resume=resume,
            )
        return safe,played.call_count

    def test_safe_tie_opportunities_from_four_actor_seats(self):
        safe,played=self._run()
        self.assertEqual(played,2)
        self.assertEqual(safe["protocol"],PROTOCOL)
        self.assertEqual(safe["independent_original_shuffle_clusters"],2)
        self.assertEqual(safe["actual_complete_four_challenge_games"],2)
        self.assertEqual(safe["sampled_actor_discard_opportunities"],24)
        self.assertEqual(safe["counts"]["decisions_with_equal_ukeire_alternative"],8)
        self.assertEqual(safe["counts"]["higher_ukeire_alternative_cuts"],8)
        self.assertEqual(safe["counts"]["equal_ukeire_alternative_cuts"],16)
        self.assertEqual(safe[
            "independent_shuffles_with_at_least_one_equal_ukeire_alternative"],2)
        self.assertTrue(safe["original_challenge_policy_unmodified"])
        self.assertTrue(safe["no_candidate_policy_trained_or_tested"])
        self.assertEqual(_get_json(self.out/SUMMARY),safe)
        before=json.dumps(safe)
        for word in ('"hand":',"91700","91701","91100","91300","91500",
                     "PRIVATE_","a"*64,str(self.train)):
            self.assertNotIn(word,before)
        self.assertEqual(_get_json(_shard_file(self.out,0))[
            "private_case"]["private_original_shuffle_seed"],91700)

    def test_no_replay_of_completed_seed_and_crash_resume(self):
        calls=[]
        def fail_after_first(seed):
            calls.append(seed)
            if len(calls)>1:
                raise RuntimeError("crash during second baseline")
            return _real_game_shape(seed)
        with self.assertRaisesRegex(RuntimeError,"crash during"):
            self._run(effect=fail_after_first)
        self.assertTrue(_shard_file(self.out,0).is_file())
        self.assertFalse(_shard_file(self.out,1).exists())
        result,count=self._run(resume=True)
        self.assertEqual(count,1)
        self.assertEqual(result["reused_already_finished_original_seed_shards"],1)
        done,again=self._run(resume=True,effect=AssertionError("must not replay"))
        self.assertEqual(again,0)
        self.assertEqual(done["reused_already_finished_original_seed_shards"],2)

    def test_strict_prior_seed_exclusion_and_frozen_model_source(self):
        for seed in (89800,91100,91300,91501):
            with self.subTest(seed=seed),self.assertRaisesRegex(ValueError,
                                                              "overlap"):
                self._run(seed_start=seed,seeds=1)
        self.assertFalse(self.out.exists())
        self._run()
        with self.assertRaisesRegex(ValueError,"new/empty"):
            self._run()
        with self.assertRaisesRegex(ValueError,"resume plan"):
            self._run(resume=True,seeds=1)
        changed=dict(self.prov,model_sha256="b"*64)
        with self.assertRaisesRegex(ValueError,"does not match frozen source"):
            self._run(resume=True,model=changed)

    def test_reject_missing_five_seat_counts_or_forged_checksum(self):
        self._run()
        file=_shard_file(self.out,0)
        envelope=_get_json(file)
        envelope["private_case"]["per_seat_actor_choice_counts"].pop()
        from mahtrain_core.ai_shadow_headtohead import _paired_digest
        envelope["sha256_case"]=_paired_digest(envelope["private_case"])
        file.write_text(json.dumps(envelope),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"incomplete four-seat"):
            self._run(resume=True)

    def test_reject_checksum_corruption_without_replaying(self):
        self._run()
        file=_shard_file(self.out,0)
        envelope=_get_json(file)
        envelope["sha256_case"]="0"*64
        file.write_text(json.dumps(envelope),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"checksum"):
            self._run(resume=True,effect=AssertionError("no replay"))

    def test_actual_challenge_agent_tie_probe_does_not_alter_action_or_rng(self):
        probe=ChallengeTieProbe(seed=91701,seat=0)
        original=MahjongAgent("challenge",seed=91701,seat=0)
        ranked=[
            {"discard":"m1","effective_tile_count":10,"score":12.,
             "expected_fan_weighted_copies":13.,
             "public_pressure":0,"table_threat_index":.1},
            {"discard":"m2","effective_tile_count":10,"score":11.,
             "expected_fan_weighted_copies":11.,
             "public_pressure":2,"table_threat_index":.2},
            {"discard":"m3","effective_tile_count":15,"score":9.,
             "expected_fan_weighted_copies":8.,
             "public_pressure":0,"table_threat_index":.4},
        ]
        def mock_baseline(agent,view):
            agent._last_discard_scores=ranked
            return "m1"
        with patch.object(MahjongAgent,"discard",mock_baseline):
            self.assertEqual(probe.discard({"seat":0}),original.discard({"seat":0}))
        s=probe.totals
        self.assertEqual(s["discard_decisions"],1)
        self.assertEqual(s["decisions_with_equal_ukeire_alternative"],1)
        self.assertEqual(s["decisions_with_higher_ukeire_alternative"],1)
        self.assertEqual(s["equal_ukeire_alternatives_different_public_pressure"],1)
        self.assertEqual(s["equal_ukeire_alternatives_different_fan_value"],1)
        self.assertEqual(s["baseline_max_ukeire_decisions"],0)
        self.assertEqual(probe._rng.getstate(),original._rng.getstate())

    def test_single_forced_cut_has_no_safe_alternative(self):
        probe=ChallengeTieProbe(seed=91701,seat=1)
        with patch.object(MahjongAgent,"discard",lambda agent,view:"p1"):
            self.assertEqual(probe.discard({"seat":1}),"p1")
        self.assertEqual(probe.totals["single_policy_choice_decisions"],1)
        self.assertEqual(probe.totals["baseline_max_ukeire_decisions"],1)
        self.assertEqual(probe.totals["equal_ukeire_alternative_cuts"],0)

    def test_refuse_impossible_metric_cohort_even_with_correct_hash(self):
        self._run()
        path=_shard_file(self.out,1)
        envelope=_get_json(path)
        envelope["private_case"]["per_seat_actor_choice_counts"][0][
            "decisions_with_equal_ukeire_alternative"]=100
        from mahtrain_core.ai_shadow_headtohead import _paired_digest
        envelope["sha256_case"]=_paired_digest(envelope["private_case"])
        path.write_text(json.dumps(envelope),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"inconsistent or impossible"):
            self._run(resume=True)


if __name__=="__main__":
    unittest.main()
