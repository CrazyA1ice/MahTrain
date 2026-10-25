"""M4.47 true state-branch contract, private resume and real engine fidelity."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]
from mahtrain_core.ai_pong_pass_branch_rollouts import (
    PROTOCOL, SUMMARY, SEED_COUNT, _aggregate, _private_shard,
    _validate_case, one_natural_shuffle, run_matched_pong_branch_trial,
)
from mahtrain_core.ai_shadow_headtohead import (
    _finish_real_full_game, _paired_digest,
)
from mahtrain_core.ai_selfplay_local_batch import _get_json


def fake_case(seed:int,*,found:bool=True)->dict:
    branches=[]
    if found:
        for world in (0,1):
            n=10 if world==0 else -10
            branches.append({
                "world":world,
                "forced_pass_terminal_actor_net":0,
                "forced_peng_terminal_actor_net":n,
                "peng_claim_actually_accepted":True,
                "official_actor_net_delta":n,
                "win_actor_delta":n,
                "kong_actor_delta":0,
                "exhaustive_actor_delta":0,
                "both_arms_genuine_terminal_ledgers":True,
                "no_opponent_hidden_hand_given_to_actors":True,
            })
    natural={
        "phase":"finished",
        "official_net":[0]*4,
        "win_points":[0]*4,
        "kong_points":[0]*4,
        "exhaustive_points":[0]*4,
    }
    return {
        "private_original_shuffle_seed":seed,
        "natural_complete_challenge_games":1,
        "natural_terminal_baseline":natural,
        "first_natural_challenge_pass_with_peng_found":found,
        "private_first_actor_seat":1 if found else None,
        "private_matched_branches":branches,
        "checkpoints_selected_by_first_opportunity_only":True,
        "no_hidden_actor_input_or_online_policy_change":True,
    }


class M447NewSourceContractTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.out=self.root/"m447"
        self.train=self.root/"m434"
        self.old=self.root/"m446"
        self.old.mkdir()
        self.model={
            "model_sha256":"a"*64,
            "source_m434_train_seed_start":89800,
            "source_m434_seed_end_exclusive":89804,
            "trained_original_shuffle_clusters":2,
        }

    def _run(self,*,start=92800,resume=False,effect=fake_case):
        with patch("mahtrain_core.ai_pong_pass_branch_rollouts.load_frozen_local_model",
                   return_value=((0,0,0),self.model)), \
             patch("mahtrain_core.ai_pong_pass_branch_rollouts._source_plan_and_exclusion",
                   return_value={
                       "private_m446_source":str(self.old.resolve()),
                       "private_m445_source":"audit-provenance",
                       "private_m444_source":"audit-provenance",
                   }), \
             patch("mahtrain_core.ai_pong_pass_branch_rollouts.one_natural_shuffle",
                   side_effect=effect) as play:
            safe=run_matched_pong_branch_trial(
                training_dir=self.train,prior_m446_dir=self.old,
                seed_start=start,seeds=SEED_COUNT,out_dir=self.out,resume=resume,
            )
        return safe,play.call_count

    def test_eight_new_natural_games_true_branch_accounting(self):
        safe,calls=self._run()
        self.assertEqual(calls,8)
        self.assertEqual(safe["protocol"],PROTOCOL)
        self.assertEqual(safe["independent_original_shuffle_clusters"],8)
        self.assertEqual(safe["real_completed_full_games_baseline_plus_branches"],40)
        self.assertEqual(safe["paired_future_wall_worlds"],16)
        self.assertEqual(safe["branch_pairs_where_peng_was_actually_claimed"],16)
        self.assertEqual(safe["mean_forced_peng_minus_pass_all_seed_clusters"],0)
        self.assertEqual(safe["seed_level_zero_delta"],8)
        self.assertTrue(safe["no_new_candidate_policy_or_refit"] if
                        "no_new_candidate_policy_or_refit" in safe else
                        safe["new_candidate_policy_not_fitted_or_promoted"])
        self.assertEqual(safe,_get_json(self.out/SUMMARY))
        published=json.dumps(safe)
        for secret in ("92800","PRIVATE_","a"*64,str(self.train),
                       '"hand":','"private_first_actor_seat"'):
            self.assertNotIn(secret,published)

    def test_no_available_call_is_neutral_and_has_no_branch_games(self):
        c=fake_case(92800,found=False)
        _validate_case(c,92800)
        safe=_aggregate([c])
        self.assertEqual(safe["real_completed_full_games_baseline_plus_branches"],1)
        self.assertEqual(safe["mean_forced_peng_minus_pass_all_seed_clusters"],0)
        self.assertIsNone(safe[
            "mean_forced_peng_minus_pass_only_covered_seed_clusters_descriptive"])

    def test_resume_skips_immutable_original_seed_shards(self):
        self._run()
        safe,replayed=self._run(resume=True,effect=AssertionError("replayed!"))
        self.assertEqual(replayed,0)
        self.assertEqual(safe["verified_original_seed_shards_reused_on_resume"],8)

    def test_crash_then_resume_only_new_unfinished_seed(self):
        def interrupt(seed):
            if seed==92801:
                raise RuntimeError("simulated after first complete shuffle")
            return fake_case(seed)
        with self.assertRaisesRegex(RuntimeError,"simulated"):
            self._run(effect=interrupt)
        self.assertTrue(_private_shard(self.out,0).is_file())
        self.assertFalse(_private_shard(self.out,1).exists())
        safe,played=self._run(resume=True)
        self.assertEqual(played,7)
        self.assertEqual(safe["verified_original_seed_shards_reused_on_resume"],1)

    def test_wrong_original_seed_and_modified_plan_are_rejected(self):
        with self.assertRaisesRegex(ValueError,"overlaps original training"):
            self._run(start=89800)
        with self.assertRaisesRegex(ValueError,"requires the frozen eight"):
            run_matched_pong_branch_trial(
                training_dir=self.train,prior_m446_dir=self.old,
                seed_start=92800,seeds=7,out_dir=self.out,
            )
        self._run()
        with self.assertRaisesRegex(ValueError,"newly empty"):
            self._run()
        with self.assertRaisesRegex(ValueError,"resume parameters"):
            self._run(start=92801,resume=True)

    def test_tampered_sha_and_recomputed_inconsistent_delta_rejected(self):
        self._run()
        f=_private_shard(self.out,0)
        envelope=_get_json(f)
        envelope["case_sha256"]="0"*64
        f.write_text(json.dumps(envelope),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            self._run(resume=True,effect=AssertionError("no replay"))
        envelope["private_case"]["private_matched_branches"][0][
            "official_actor_net_delta"]=999
        envelope["case_sha256"]=_paired_digest(envelope["private_case"])
        f.write_text(json.dumps(envelope),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"not a reconciled"):
            self._run(resume=True,effect=AssertionError("no replay"))

    def test_preempted_peng_cannot_create_synthetic_net_profit(self):
        c=fake_case(92800)
        c["private_matched_branches"][0]["peng_claim_actually_accepted"]=False
        with self.assertRaisesRegex(ValueError,"unaccepted peng"):
            _validate_case(c,92800)

    def test_real_natural_challenge_with_branch_matches_original_baseline(self):
        # True FourPlayerOpening, not a fake fixture; at the first naturally
        # eligible Challenge PASS, both actions settle against identical state
        # and RNG. If no checkpoint occurs, report accurately without one.
        seed=90411
        real=one_natural_shuffle(seed)
        _validate_case(real,seed)
        original=_finish_real_full_game(seed,None,None)
        self.assertEqual(real["natural_terminal_baseline"]["official_net"],
                         original["official_net_by_seat"])
        self.assertEqual(real["natural_terminal_baseline"]["phase"],
                         original["phase"])
        self.assertEqual(len(real["private_matched_branches"]),
                         2 if real["first_natural_challenge_pass_with_peng_found"] else 0)
        self.assertTrue(_aggregate([real])[
            "no_specific_hand_tiles_future_wall_shuffle_seed_or_weights_exported"])


if __name__=="__main__":
    unittest.main()
