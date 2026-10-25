"""M4.43: bounded actor-only tie policies, new seeds, paired paid-ledger checks."""
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
    PROTOCOL as M437_PROTOCOL, SHARD_PROTOCOL as M437_SHARD,
)
from mahtrain_core.ai_shadow_action_diagnostics import PROTOCOL as M439_PROTOCOL
from mahtrain_core.ai_shadow_guarded_trial import PROTOCOL as M441_PROTOCOL
from mahtrain_core.ai_challenge_tie_opportunities import PROTOCOL as M442_PROTOCOL
from mahtrain_core.ai_safe_tie_policy_trial import (
    PROTOCOL, SUMMARY, SafeTiePolicyAgent, _shard, run_safe_tie_trial,
)
from mahtrain_core.ai_selfplay_local_batch import _get_json


def _mock_game(seed,seat,mode):
    net=[0,0,0,0]
    if seat is not None:
        delta=(-100 if mode=="risk_first" else 80)
        net[seat]=delta
        net[(seat+1)%4]=-delta
    return {
        "phase":"finished",
        "official_net_by_seat":net,
        "win_points_by_seat":list(net),
        "kong_points_by_seat":[0]*4,
        "exhaustive_points_by_seat":[0]*4,
        "discard_opportunities":3 if seat is not None else 0,
        "safe_tie_opportunities":2 if seat is not None else 0,
        "accepted_overrides":1 if seat is not None else 0,
        "blocked_by_criteria":1 if seat is not None else 0,
    }


def _ranking(*,fan=10.,risk=.40,other_fan=9.8,other_risk=.28,
             ukeire=12,other_ukeire=12):
    return [
        {
            "discard":"m1","shanten":1,"effective_tile_count":ukeire,
            "expected_fan_weighted_copies":fan,
            "table_threat_index":risk,
        },
        {
            "discard":"m2","shanten":1,"effective_tile_count":other_ukeire,
            "expected_fan_weighted_copies":other_fan,
            "table_threat_index":other_risk,
        },
    ]


class SafeTieTrialTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.train=self.root/"m434"
        self.old437=self.root/"m437"
        self.old439=self.root/"m439"
        self.old441=self.root/"m441"
        self.old442=self.root/"m442"
        self.out=self.root/"m443"
        self.meta={
            "model_sha256":"c"*64,
            "source_m434_train_seed_start":89800,
            "source_m434_seed_end_exclusive":89804,
            "trained_original_shuffle_clusters":2,
        }
        for p in (self.old437,self.old439,self.old441,self.old442):
            p.mkdir()
        def write(root,name,body):
            (root/name).write_text(json.dumps(body),encoding="utf8")
        write(self.old437,"PRIVATE_frozen_benchmark_plan.json",{
            "protocol":M437_PROTOCOL,
            "resumable_shards_protocol":M437_SHARD,
            "private_source_training_directory":str(self.train.resolve()),
            "private_frozen_model_sha256":"c"*64,
            "private_evaluation_seed_start":91100,
            "private_eval_original_shuffle_count":2,
        })
        write(self.old439,"PRIVATE_actor_diagnostic_plan.json",{
            "protocol":M439_PROTOCOL,
            "private_source_training_directory":str(self.train.resolve()),
            "private_source_m437_directory":str(self.old437.resolve()),
            "private_frozen_model_sha256":"c"*64,
            "online_policy_changed":False,
            "private_eval_seed_start":91300,
            "private_eval_seed_count":2,
        })
        write(self.old441,"PRIVATE_guard_trial_plan.json",{
            "protocol":M441_PROTOCOL,
            "private_training_dir":str(self.train.resolve()),
            "private_prior_m437_dir":str(self.old437.resolve()),
            "private_prior_m439_dir":str(self.old439.resolve()),
            "frozen_model_sha256":"c"*64,
            "live_online_promotion":False,
            "private_seed_start":91500,
            "original_shuffle_clusters":2,
        })
        write(self.old442,"PRIVATE_challenge_tie_probe_plan.json",{
            "protocol":M442_PROTOCOL,
            "model_sha256":"c"*64,
            "private_train_dir":str(self.train.resolve()),
            "private_prior_m437_dir":str(self.old437.resolve()),
            "private_prior_m439_dir":str(self.old439.resolve()),
            "private_prior_m441_dir":str(self.old441.resolve()),
            "private_original_seed_start":91700,
            "independent_seed_clusters":2,
            "challenge_behavior_unchanged":True,
        })

    def _run(self,*,seed_start=91900,seeds=2,resume=False,effect=_mock_game,model=None):
        with patch("mahtrain_core.ai_safe_tie_policy_trial.load_frozen_local_model",
                   return_value=((-.1,-.02,-.01),model or self.meta)), \
             patch("mahtrain_core.ai_safe_tie_policy_trial._finish_real_game",
                   side_effect=effect) as played:
            safe=run_safe_tie_trial(
                training_dir=self.train,
                prior_m437_dir=self.old437,prior_m439_dir=self.old439,
                prior_m441_dir=self.old441,prior_m442_dir=self.old442,
                seed_start=seed_start,seeds=seeds,
                out_dir=self.out,resume=resume,
            )
        return safe,played.call_count

    def test_full_nine_game_per_shuffle_and_safe_aggregates(self):
        safe,calls=self._run()
        self.assertEqual(calls,18)
        self.assertEqual(safe["protocol"],PROTOCOL)
        self.assertEqual(safe["independent_original_shuffle_seed_clusters"],2)
        self.assertEqual(safe["true_complete_official_games"],18)
        self.assertEqual(safe["risk_first"]["actual_safe_tie_overrides"],8)
        self.assertEqual(safe["fan_first"]["actual_safe_tie_overrides"],8)
        self.assertEqual(safe["risk_first"]["mean_paired_official_net_delta_points"],-100)
        self.assertEqual(safe["fan_first"]["mean_paired_official_net_delta_points"],80)
        self.assertEqual(safe["risk_first"]["eligible_same_shanten_same_ukeire_decisions"],16)
        self.assertEqual(safe["fan_first"]["eligible_tie_decisions_rejected_by_extra_constraints"],8)
        self.assertTrue(safe["same_minimum_shanten_and_equal_ukeire_enforced_at_every_override"])
        self.assertTrue(safe["no_live_challenge_ai_changes"])
        self.assertEqual(_get_json(self.out/SUMMARY),safe)
        public=json.dumps(safe,ensure_ascii=False)
        for token in ("91900","91901","91700","PRIVATE_",
                      '"hand":',"c"*64,str(self.train)):
            self.assertNotIn(token,public)
        self.assertEqual(_get_json(_shard(self.out,0))["private_case"]["real_completed_games"],9)

    def test_resume_only_missing_complete_original_shuffle(self):
        self._run()
        safe,calls=self._run(resume=True,effect=AssertionError("must not replay"))
        self.assertEqual(calls,0)
        self.assertEqual(safe["resumed_completed_original_shuffle_clusters"],2)

    def test_interruption_after_a_complete_nine_game_cluster(self):
        calls=[]
        def fail(seed,seat,mode):
            calls.append(seed)
            if seed==91901:
                raise RuntimeError("second original shuffle interrupted")
            return _mock_game(seed,seat,mode)
        with self.assertRaisesRegex(RuntimeError,"interrupted"):
            self._run(effect=fail)
        self.assertTrue(_shard(self.out,0).is_file())
        self.assertFalse(_shard(self.out,1).exists())
        report,n=self._run(resume=True)
        self.assertEqual(n,9)
        self.assertEqual(report["resumed_completed_original_shuffle_clusters"],1)

    def test_strict_prior_seed_isolation_and_immutable_plan(self):
        for seed in (89802,91100,91301,91500,91701):
            with self.subTest(seed=seed):
                with self.assertRaisesRegex(ValueError,"overlap"):
                    self._run(seed_start=seed,seeds=1)
        self.assertFalse(self.out.exists())
        self._run()
        with self.assertRaisesRegex(ValueError,"new empty"):
            self._run()
        with self.assertRaisesRegex(ValueError,"resume .* changed"):
            self._run(resume=True,seeds=1)

    def test_tampering_even_with_recalculated_checkpoint_hash_rejected(self):
        self._run()
        path=_shard(self.out,0)
        env=_get_json(path)
        env["private_case"]["seat_rotation_results"][0]["policies"]["risk_first"][
            "accepted_overrides"]=1000
        from mahtrain_core.ai_shadow_headtohead import _paired_digest
        env["sha256_case"]=_paired_digest(env["private_case"])
        path.write_text(json.dumps(env),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"unsafe or unreconciled"):
            self._run(resume=True,effect=AssertionError("no replay"))

    def test_checksum_mismatch_rejected_without_replay(self):
        self._run()
        path=_shard(self.out,0)
        env=_get_json(path)
        env["sha256_case"]="0"*64
        path.write_text(json.dumps(env),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"checksum"):
            self._run(resume=True,effect=AssertionError("no replay"))

    def test_risk_first_can_change_only_on_equally_effective_cut(self):
        agent=SafeTiePolicyAgent("risk_first",seed=91900,seat=1)
        ranking=_ranking(other_fan=9.7,other_risk=.28)
        def old_discard(self,view):
            self._last_discard_scores=ranking
            return "m1"
        with patch.object(MahjongAgent,"discard",old_discard):
            self.assertEqual(agent.discard({"seat":1}),"m2")
        self.assertEqual(agent.applied_overrides,1)
        self.assertEqual(agent.safe_tie_opportunities,1)
        self.assertTrue(agent._offline_reference_cut)

    def test_fan_first_requires_real_fan_gain_and_bounded_extra_risk(self):
        agent=SafeTiePolicyAgent("fan_first",seed=91900,seat=2)
        ranked=_ranking(other_fan=11.,other_risk=.43)
        def old_discard(self,view):
            self._last_discard_scores=ranked
            return "m1"
        with patch.object(MahjongAgent,"discard",old_discard):
            self.assertEqual(agent.discard({"seat":2}),"m2")
        self.assertEqual(agent.applied_overrides,1)
        ranked[1]["table_threat_index"]=.8
        with patch.object(MahjongAgent,"discard",old_discard):
            self.assertEqual(agent.discard({"seat":2}),"m1")
        self.assertEqual(agent.blocked_by_preregistered_criteria,1)

    def test_never_trade_away_one_effective_tile_copy(self):
        agent=SafeTiePolicyAgent("risk_first",seed=91900,seat=3)
        ranked=_ranking(other_fan=10.,other_risk=.05,other_ukeire=11)
        def old_discard(self,view):
            self._last_discard_scores=ranked
            return "m1"
        with patch.object(MahjongAgent,"discard",old_discard):
            self.assertEqual(agent.discard({"seat":3}),"m1")
        self.assertEqual(agent.safe_tie_opportunities,0)
        self.assertEqual(agent.applied_overrides,0)

    def test_no_extra_rng_consumption_without_policy_candidate(self):
        agent=SafeTiePolicyAgent("risk_first",seed=91900,seat=0)
        baseline=MahjongAgent("challenge",seed=91900,seat=0)
        def old_discard(self,view):
            self._last_discard_scores=None
            return "m1"
        with patch.object(MahjongAgent,"discard",old_discard):
            self.assertEqual(agent.discard({"seat":0}),baseline.discard({"seat":0}))
        self.assertEqual(agent._rng.getstate(),baseline._rng.getstate())


if __name__=="__main__":
    unittest.main()
