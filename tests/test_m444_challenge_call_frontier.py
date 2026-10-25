"""M4.44 actor-only call/kong coverage, private source isolation, safe crash resume.

Synthetic matches in fast tests are contract-shaped paid-game substitutes;
the M4.36 suite executes genuine terminal game with the unchanged challenge.
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
    PROTOCOL as M437_PROTOCOL, SHARD_PROTOCOL as M437_SHARD,
    _paired_digest,
)
from mahtrain_core.ai_shadow_action_diagnostics import PROTOCOL as M439_PROTOCOL
from mahtrain_core.ai_shadow_guarded_trial import PROTOCOL as M441_PROTOCOL
from mahtrain_core.ai_challenge_tie_opportunities import PROTOCOL as M442_PROTOCOL
from mahtrain_core.ai_safe_tie_policy_trial import PROTOCOL as M443_PROTOCOL
from mahtrain_core.ai_challenge_call_frontier import (
    KEYS, PROTOCOL, SUMMARY, ChallengeCallFrontierProbe, _shard,
    run_new_seed_claim_frontier,
)
from mahtrain_core.ai_selfplay_local_batch import _get_json


def _completed(seed):
    row={k:0 for k in KEYS}
    row.update({
        "response_windows_seen":5,
        "response_pass_only_windows":2,
        "claim_windows_with_peng":2,
        "claim_windows_with_ming_gang":1,
        "claim_windows_with_both_peng_and_ming_gang":1,
        "claim_legal_hu_windows":1,
        "rob_kong_response_windows":1,
        "rob_kong_legal_hu_windows":1,
        "claim_chose_peng":1,
        "claim_chose_hu":1,
        "rob_chose_hu":1,
        "claim_action_choice_windows":2,
        "own_discard_stage_visits":3,
        "own_self_win_opportunities":1,
        "own_kong_checks":2,
        "own_kong_checks_with_options":1,
        "own_kong_options_an_gang":1,
        "own_kong_chose_an_gang":1,
    })
    return {
        "private_original_shuffle_seed":seed,
        "actual_completed_challenge_games":1,
        "terminal_phase":"finished",
        "official_net_by_seat":[-20,-10,30,0],
        "per_seat_actor_action_counts":[dict(row) for _ in range(4)],
        "live_challenge_action_identity_preserved":True,
        "no_hidden_wall_or_opponent_hands_recorded":True,
    }


class CallFrontierTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.train=self.root/"m434"
        self.m437=self.root/"m437"
        self.m439=self.root/"m439"
        self.m441=self.root/"m441"
        self.m442=self.root/"m442"
        self.m443=self.root/"m443"
        self.out=self.root/"m444"
        for p in (self.m437,self.m439,self.m441,self.m442,self.m443):
            p.mkdir()
        self.model={
            "model_sha256":"a"*64,
            "source_m434_train_seed_start":89800,
            "source_m434_seed_end_exclusive":89804,
        }
        def save(folder,name,val):
            (folder/name).write_text(json.dumps(val),encoding="utf8")
        save(self.m437,"PRIVATE_frozen_benchmark_plan.json",{
            "protocol":M437_PROTOCOL,
            "resumable_shards_protocol":M437_SHARD,
            "private_source_training_directory":str(self.train.resolve()),
            "private_frozen_model_sha256":"a"*64,
            "private_evaluation_seed_start":91100,
            "private_eval_original_shuffle_count":2,
        })
        save(self.m439,"PRIVATE_actor_diagnostic_plan.json",{
            "protocol":M439_PROTOCOL,
            "private_source_training_directory":str(self.train.resolve()),
            "private_frozen_model_sha256":"a"*64,
            "private_eval_seed_start":91300,
            "private_eval_seed_count":2,
        })
        save(self.m441,"PRIVATE_guard_trial_plan.json",{
            "protocol":M441_PROTOCOL,
            "private_training_dir":str(self.train.resolve()),
            "frozen_model_sha256":"a"*64,
            "private_seed_start":91500,
            "original_shuffle_clusters":2,
        })
        save(self.m442,"PRIVATE_challenge_tie_probe_plan.json",{
            "protocol":M442_PROTOCOL,
            "private_train_dir":str(self.train.resolve()),
            "model_sha256":"a"*64,
            "private_prior_m437_dir":str(self.m437.resolve()),
            "private_prior_m439_dir":str(self.m439.resolve()),
            "private_prior_m441_dir":str(self.m441.resolve()),
            "private_original_seed_start":91700,
            "independent_seed_clusters":2,
            "challenge_behavior_unchanged":True,
        })
        save(self.m443,"PRIVATE_safe_tie_policy_plan.json",{
            "protocol":M443_PROTOCOL,
            "private_training_dir":str(self.train.resolve()),
            "model_sha256_provenance_only":"a"*64,
            "private_prior_m437_dir":str(self.m437.resolve()),
            "private_prior_m439_dir":str(self.m439.resolve()),
            "private_prior_m441_dir":str(self.m441.resolve()),
            "private_prior_m442_dir":str(self.m442.resolve()),
            "private_new_shuffle_start":91900,
            "private_independent_shuffle_count":2,
            "live_policy_untouched":True,
        })

    def _run(self,*,seeds=2,start=92100,resume=False,game=_completed,model=None):
        with patch("mahtrain_core.ai_challenge_call_frontier.load_frozen_local_model",
                   return_value=((-.1,-.02,-.01),model or self.model)), \
             patch("mahtrain_core.ai_challenge_call_frontier.play_challenge_call_frontier_seed",
                   side_effect=game) as played:
            report=run_new_seed_claim_frontier(
                training_dir=self.train,prior_m442_dir=self.m442,
                prior_m443_dir=self.m443,seed_start=start,seeds=seeds,
                out_dir=self.out,resume=resume)
        return report,played.call_count

    def test_new_two_seed_real_contract_counts_and_private_redaction(self):
        report,played=self._run()
        self.assertEqual(played,2)
        self.assertEqual(report["protocol"],PROTOCOL)
        self.assertEqual(report["independent_original_shuffle_clusters"],2)
        self.assertEqual(report["real_finished_four_player_challenge_games"],2)
        self.assertEqual(report["counts"]["response_windows_seen"],40)
        self.assertEqual(report["counts"]["claim_action_choice_windows"],16)
        self.assertEqual(report["counts"]["own_kong_checks_with_options"],8)
        self.assertEqual(report["counts"]["claim_chose_peng"],8)
        self.assertEqual(report["counts"]["own_self_win_opportunities"],8)
        self.assertEqual(report["original_shuffles_with_at_least_one_peng_or_kong_alternative"],2)
        self.assertTrue(report["unchanged_challenge_policy"])
        self.assertEqual(report,_get_json(self.out/SUMMARY))
        public=json.dumps(report,ensure_ascii=False)
        for token in ('"hand":',"92100","92101","91900",
                      "PRIVATE_","a"*64,str(self.train)):
            self.assertNotIn(token,public)

    def test_reuse_completed_and_recover_only_second_seed(self):
        calls=[]
        def interrupt(seed):
            calls.append(seed)
            if len(calls)==2:
                raise RuntimeError("simulated Windows interruption")
            return _completed(seed)
        with self.assertRaisesRegex(RuntimeError,"interruption"):
            self._run(game=interrupt)
        self.assertTrue(_shard(self.out,0).is_file())
        result,count=self._run(resume=True)
        self.assertEqual(count,1)
        self.assertEqual(result["reused_verified_original_shuffles"],1)
        report,again=self._run(resume=True,game=AssertionError("no replay"))
        self.assertEqual(again,0)
        self.assertEqual(report["reused_verified_original_shuffles"],2)

    def test_no_overlap_with_any_known_real_evaluation_seed(self):
        for original in (89800,91101,91301,91500,91701,91900):
            with self.subTest(seed=original):
                with self.assertRaisesRegex(ValueError,"overlap"):
                    self._run(start=original,seeds=1)
        self.assertFalse(self.out.exists())
        self._run()
        with self.assertRaisesRegex(ValueError,"new empty"):
            self._run()
        with self.assertRaisesRegex(ValueError,"resume parameters"):
            self._run(resume=True,seeds=1)

    def test_checksum_tamper_and_private_observation_corruption(self):
        self._run()
        p=_shard(self.out,0)
        raw=_get_json(p)
        raw["checksum"]="0"*64
        p.write_text(json.dumps(raw),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"checksum"):
            self._run(resume=True,game=AssertionError("no replay"))
        raw["private_case"]["per_seat_actor_action_counts"][0][
            "own_kong_checks_with_options"]=100
        raw["checksum"]=_paired_digest(raw["private_case"])
        p.write_text(json.dumps(raw),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"impossible"):
            self._run(resume=True,game=AssertionError("no replay"))

    def test_response_observer_keeps_challenge_actions_and_randomness(self):
        agent=ChallengeCallFrontierProbe(seed=92100,seat=2)
        original=MahjongAgent("challenge",seed=92100,seat=2)
        def act_response(self,view,*,rob=False):
            opts=view["rob_options"] if rob else view["claim_options"]
            return "hu" if "hu" in opts else "pass"
        with patch.object(MahjongAgent,"response",act_response):
            for view,rob in (
                ({"claim_options":["pass","peng"],"rob_options":[]},False),
                ({"claim_options":["pass","hu"],"rob_options":[]},False),
                ({"rob_options":["pass","hu"],"claim_options":[]},True),
            ):
                self.assertEqual(agent.response(view,rob=rob),
                                 original.response(view,rob=rob))
        self.assertEqual(agent.counts["claim_action_choice_windows"],1)
        self.assertEqual(agent.counts["claim_chose_pass_with_claim_available"],1)
        self.assertEqual(agent.counts["claim_chose_hu"],1)
        self.assertEqual(agent.counts["rob_chose_hu"],1)
        self.assertEqual(agent._rng.getstate(),original._rng.getstate())

    def test_kong_observer_keeps_challenge_actions_and_randomness(self):
        agent=ChallengeCallFrontierProbe(seed=92101,seat=3)
        original=MahjongAgent("challenge",seed=92101,seat=3)
        option={"type":"an_gang","tile":"m5"}
        def act_kong(self,view):
            return dict(view["kong_options"][0]) if view["kong_options"] else None
        with patch.object(MahjongAgent,"kong",act_kong):
            v={"kong_options":[option]}
            self.assertEqual(agent.kong(v),original.kong(v))
            self.assertEqual(agent.kong({"kong_options":[]}),
                             original.kong({"kong_options":[]}))
        self.assertEqual(agent.counts["own_kong_checks"],2)
        self.assertEqual(agent.counts["own_kong_chose_an_gang"],1)
        self.assertEqual(agent._rng.getstate(),original._rng.getstate())

    def test_reject_invalid_private_claim_option_or_duplicate_kongs(self):
        agent=ChallengeCallFrontierProbe(seed=92100,seat=0)
        with self.assertRaisesRegex(ValueError,"option schema"):
            agent.response({"claim_options":["pass","pass"]})
        with self.assertRaisesRegex(ValueError,"duplicate"):
            agent.kong({"kong_options":[
                {"type":"an_gang","tile":"p1"},
                {"type":"an_gang","tile":"p1"},
            ]})


if __name__=="__main__":
    unittest.main()
