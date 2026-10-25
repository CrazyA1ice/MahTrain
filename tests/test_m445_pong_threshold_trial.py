"""M4.45: four-seat real score contract, original seed separation and peng veto."""
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
    PROTOCOL as P437, SHARD_PROTOCOL as P437_SHARD, _paired_digest,
)
from mahtrain_core.ai_shadow_action_diagnostics import PROTOCOL as P439
from mahtrain_core.ai_shadow_guarded_trial import PROTOCOL as P441
from mahtrain_core.ai_challenge_tie_opportunities import PROTOCOL as P442
from mahtrain_core.ai_safe_tie_policy_trial import PROTOCOL as P443
from mahtrain_core.ai_challenge_call_frontier import PROTOCOL as P444
from mahtrain_core.ai_pong_threshold_trial import (
    FrozenPengThresholdAgent, METRICS, PROTOCOL, SUMMARY, _path,
    run_pong_threshold_trial,
)
from mahtrain_core.ai_selfplay_local_batch import _get_json


def fake_full_game(seed,seat):
    net=[0]*4
    if seat is not None:
        net[seat]=20
        net[(seat+1)%4]=-20
    stats=None
    if seat is not None:
        stats={k:0 for k in METRICS}
        stats.update({
            "response_windows":3,
            "legal_peng_windows":1,
            "baseline_challenge_pass_with_peng":1,
            "eligible_equal_shanten_plus1or2_peng":1,
            "actual_peng_overrides":1,
        })
    return {
        "phase":"finished",
        "official_net_by_seat":net,
        "win_points_by_seat":net[:],
        "kong_points_by_seat":[0]*4,
        "exhaustive_points_by_seat":[0]*4,
        "actor_counts":stats,
    }


class PongThresholdTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.train=self.root/"m434"
        self.old437=self.root/"m437"
        self.old439=self.root/"m439"
        self.old441=self.root/"m441"
        self.old442=self.root/"m442"
        self.old443=self.root/"m443"
        self.old444=self.root/"m444"
        self.out=self.root/"m445"
        for d in (self.old437,self.old439,self.old441,
                  self.old442,self.old443,self.old444):
            d.mkdir()
        self.meta={
            "model_sha256":"b"*64,
            "source_m434_train_seed_start":89800,
            "source_m434_seed_end_exclusive":89804,
            "trained_original_shuffle_clusters":2,
        }
        def write(folder,name,data):
            (folder/name).write_text(json.dumps(data),encoding="utf8")
        write(self.old437,"PRIVATE_frozen_benchmark_plan.json",{
            "protocol":P437,
            "resumable_shards_protocol":P437_SHARD,
            "private_source_training_directory":str(self.train.resolve()),
            "private_frozen_model_sha256":"b"*64,
            "private_evaluation_seed_start":91100,
            "private_eval_original_shuffle_count":2,
        })
        write(self.old439,"PRIVATE_actor_diagnostic_plan.json",{
            "protocol":P439,
            "private_source_training_directory":str(self.train.resolve()),
            "private_frozen_model_sha256":"b"*64,
            "private_eval_seed_start":91300,
            "private_eval_seed_count":2,
        })
        write(self.old441,"PRIVATE_guard_trial_plan.json",{
            "protocol":P441,
            "private_training_dir":str(self.train.resolve()),
            "frozen_model_sha256":"b"*64,
            "private_seed_start":91500,
            "original_shuffle_clusters":2,
        })
        write(self.old442,"PRIVATE_challenge_tie_probe_plan.json",{
            "protocol":P442,
            "private_train_dir":str(self.train.resolve()),
            "model_sha256":"b"*64,
            "private_prior_m437_dir":str(self.old437.resolve()),
            "private_prior_m439_dir":str(self.old439.resolve()),
            "private_prior_m441_dir":str(self.old441.resolve()),
            "private_original_seed_start":91700,
            "independent_seed_clusters":2,
        })
        write(self.old443,"PRIVATE_safe_tie_policy_plan.json",{
            "protocol":P443,
            "private_training_dir":str(self.train.resolve()),
            "private_prior_m442_dir":str(self.old442.resolve()),
            "model_sha256_provenance_only":"b"*64,
            "private_new_shuffle_start":91900,
            "private_independent_shuffle_count":2,
        })
        write(self.old444,"PRIVATE_call_frontier_plan.json",{
            "protocol":P444,
            "private_model_source":str(self.train.resolve()),
            "private_m442_source":str(self.old442.resolve()),
            "private_m443_source":str(self.old443.resolve()),
            "model_sha256_provenance_only":"b"*64,
            "private_original_shuffle_start":92100,
            "private_original_shuffle_count":2,
            "challenge_unmodified":True,
            "no_candidate_policy_test":True,
        })

    def _run(self,*,seed_start=92300,seeds=2,resume=False,game=fake_full_game):
        with patch("mahtrain_core.ai_pong_threshold_trial.load_frozen_local_model",
                   return_value=((-.1,-.02,-.01),self.meta)), \
             patch("mahtrain_core.ai_pong_threshold_trial._one_game",
                   side_effect=game) as played:
            data=run_pong_threshold_trial(
                training_dir=self.train,prior_m444_dir=self.old444,
                seed_start=seed_start,seeds=seeds,
                out_dir=self.out,resume=resume,
            )
        return data,played.call_count

    def test_two_new_seeds_ten_paid_games_and_safe_aggregation(self):
        report,played=self._run()
        self.assertEqual(played,10)
        self.assertEqual(report["protocol"],PROTOCOL)
        self.assertEqual(report["complete_authoritative_games"],10)
        self.assertEqual(report["candidate_four_seat_games"],8)
        self.assertEqual(report["independent_original_shuffle_clusters"],2)
        self.assertEqual(report["actor_only_response_counts"]["actual_peng_overrides"],8)
        self.assertEqual(report["mean_official_net_delta_points"],20)
        self.assertEqual(report["mean_official_component_delta_points"],
                         {"win":20,"kong":0,"exhaustive":0})
        self.assertEqual(report["precommitted_equal_shanten_peng_extra_ukeire_copy_range"],[1,2])
        self.assertEqual(_get_json(self.out/SUMMARY),report)
        serialized=json.dumps(report,ensure_ascii=False)
        for forbidden in ('"hand":',"92300","92100","PRIVATE_",
                          "b"*64,str(self.train)):
            self.assertNotIn(forbidden,serialized)

    def test_complete_original_seed_resume_never_replays_finished_games(self):
        report,_=self._run()
        again,played=self._run(resume=True,game=AssertionError("no replay"))
        self.assertEqual(played,0)
        self.assertEqual(again["reused_completed_original_shuffle_clusters"],2)

    def test_interruption_replays_only_incomplete_five_game_cluster(self):
        def interrupt(seed,seat):
            if seed==92301:
                raise RuntimeError("interrupted seed")
            return fake_full_game(seed,seat)
        with self.assertRaisesRegex(RuntimeError,"interrupted seed"):
            self._run(game=interrupt)
        self.assertTrue(_path(self.out,0).is_file())
        self.assertFalse(_path(self.out,1).exists())
        result,played=self._run(resume=True)
        self.assertEqual(played,5)
        self.assertEqual(result["reused_completed_original_shuffle_clusters"],1)

    def test_strict_old_seed_intervals_and_immutable_resume_plan(self):
        for seed in (89801,91100,91300,91501,91700,91901,92100):
            with self.subTest(seed=seed):
                with self.assertRaisesRegex(ValueError,"overlap"):
                    self._run(seed_start=seed,seeds=1)
        self.assertFalse(self.out.exists())
        self._run()
        with self.assertRaisesRegex(ValueError,"new empty"):
            self._run()
        with self.assertRaisesRegex(ValueError,"plan"):
            self._run(resume=True,seeds=1)

    def test_changed_checksum_and_recalculated_illegal_action_counts_rejected(self):
        self._run()
        file=_path(self.out,0)
        envelope=_get_json(file)
        envelope["sha256_case"]="0"*64
        file.write_text(json.dumps(envelope),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            self._run(resume=True,game=AssertionError("must not replay"))
        envelope["private_case"]["seat_rotation_results"][0][
            "actor_counts"]["actual_peng_overrides"]=8
        envelope["sha256_case"]=_paired_digest(envelope["private_case"])
        file.write_text(json.dumps(envelope),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"invalid rejected/accepted"):
            self._run(resume=True,game=AssertionError("must not replay"))

    def test_only_precommitted_one_or_two_additional_ukeire_can_peng(self):
        def exercise(additional):
            agent=FrozenPengThresholdAgent(seed=92300,seat=0)
            view={
                "claim_options":["pass","peng"],
                "tian_ting":{},
                "pending_discard":{"tile":"m1"},
            }
            hand=["m1","m1","m2","m3","m4","m5","m6",
                  "p1","p2","p3","p4","p5","p6"]
            def outlook(tiles,melds,missing,public,cap,tian):
                return {"shanten":1,"ukeire":8+(additional if melds else 0),
                        "value":8+(additional if melds else 0),"tian_kept":False}
            with patch.object(MahjongAgent,"response",return_value="pass"), \
                 patch("mahtrain_core.ai_pong_threshold_trial._own_view",
                       return_value=(hand,[],"s")), \
                 patch("mahtrain_core.ai_pong_threshold_trial._call_settings",
                       return_value=(["m1"],3,{})), \
                 patch("mahtrain_core.ai_pong_threshold_trial._cut_shanten",
                       return_value=1), \
                 patch("mahtrain_core.ai_pong_threshold_trial._call_outlook",
                       side_effect=outlook):
                choice=agent.response(view)
            return choice,agent.counts
        for copies in (1,2):
            choice,counts=exercise(copies)
            self.assertEqual(choice,"peng")
            self.assertEqual(counts["actual_peng_overrides"],1)
        for copies in (-1,0,3):
            choice,counts=exercise(copies)
            self.assertEqual(choice,"pass")
            self.assertEqual(counts["actual_peng_overrides"],0)

    def test_preserve_tian_ting_and_hu_and_non_claim_windows(self):
        a=FrozenPengThresholdAgent(seed=92300,seat=0)
        views=[
            ({"claim_options":["pass","peng"],
              "tian_ting":{"eligible":True}},False,"pass"),
            ({"claim_options":["pass","hu","peng"],
              "tian_ting":{}},False,"hu"),
            ({"rob_options":["pass","hu"],"claim_options":[]},
             True,"hu"),
        ]
        def baseline(self,view,*,rob=False):
            return "hu" if "hu" in (
                view["rob_options"] if rob else view["claim_options"]) else "pass"
        with patch.object(MahjongAgent,"response",baseline):
            for view,rob,expected in views:
                self.assertEqual(a.response(view,rob=rob),expected)
        self.assertEqual(a.counts["actual_peng_overrides"],0)
        self.assertEqual(a.counts["pass_with_tian_ting_excluded"],1)
        self.assertEqual(a.counts["baseline_challenge_pass_with_peng"],1)


if __name__=="__main__":
    unittest.main()
