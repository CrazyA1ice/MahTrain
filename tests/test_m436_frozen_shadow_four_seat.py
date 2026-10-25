"""M4.36 tests: real official five-game rotated comparison, actor-only model."""
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

from mahtrain_core.ai_selfplay_local_batch import (
    BatchPlan, _get_json, run_local_batch
)
from mahtrain_core.ai_selfplay_uncertainty import analyze_saved_local_batch
from mahtrain_core.ai_shadow_headtohead import (
    PROTOCOL, FrozenShadowAgent, _bounded_weights,
    _finish_real_full_game, evaluate_frozen_shadow,
    evaluate_one_seed, load_frozen_local_model,
)


class M436FrozenFourSeatBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private=tempfile.TemporaryDirectory()
        cls.root=Path(cls.private.name)
        cls.training=cls.root/"PRIVATE_completed_batch"
        cls.plan=BatchPlan(89823,1,1,1)
        cls.local=run_local_batch(
            cls.plan,cls.training,workers=1,
        )
        analyze_saved_local_batch(cls.training)
        cls.weights,cls.provenance=load_frozen_local_model(cls.training)
        cls.output=cls.root/"PRIVATE_real_shadow_eval"
        cls.result=evaluate_frozen_shadow(
            training_dir=cls.training,seed_start=90023,
            seeds=1,out_dir=cls.output,
        )

    @classmethod
    def tearDownClass(cls):
        cls.private.cleanup()

    def test_real_authoritative_payouts_all_four_seat_rotations(self):
        r=self.result
        self.assertEqual(r["protocol"],PROTOCOL)
        self.assertEqual(r["independent_initial_shuffle_seed_clusters"],1)
        self.assertEqual(r["actual_real_complete_games"],5)
        self.assertEqual(r["baseline_games"],1)
        self.assertEqual(r["experimental_shadow_games"],4)
        self.assertEqual(len(r["per_seat_conditional_net_delta_means"]),4)
        self.assertTrue(r["official_score_ledger_reconciled"])
        self.assertFalse(r["no_change_to_online_ai"] is False)
        self.assertFalse(r["no_generalization_or_strength_proven"] is False)
        self.assertFalse(
            r["enough_independent_seeds_for_exploratory_comparison"])
        self.assertFalse(r["candidate_no_change_to_live_challenge_agent"] is False)
        self.assertEqual(
            r["trained_original_shuffle_clusters"],
            self.provenance["trained_original_shuffle_clusters"],
        )
        self.assertTrue(
            r["evaluation_shuffles_disjoint_from_train_and_original_holdout"],
        )
        self.assertEqual(r,_get_json(
            self.output/"safe_four_seat_shadow_summary.json"
        ))
        for secret in ("90023","89823","89824","private_evaluation_shuffle_seed",
                       "hand","private_original"):
            self.assertNotIn(secret,json.dumps(r))

    def test_true_private_four_rotations_balanced_one_seed_one_cluster(self):
        import gzip
        with gzip.open(
            self.output/"PRIVATE_four_seat_paired_matches.jsonl.gz",
            "rt",encoding="utf8"
        ) as f:
            rows=[json.loads(x) for x in f]
        self.assertEqual(len(rows),1)
        case=rows[0]
        self.assertEqual(case["private_evaluation_shuffle_seed"],90023)
        self.assertEqual(case["complete_authoritative_games"],5)
        self.assertTrue(
            case["original_natural_shuffle_seed_is_one_statistical_cluster"]
        )
        self.assertEqual(
            [s["seat"] for s in case["seat_rotation_results"]],[0,1,2,3]
        )
        for entry in case["seat_rotation_results"]:
            self.assertEqual(
                entry["shadow_official_net"]-
                entry["challenge_baseline_official_net"],
                entry["delta_shadow_minus_challenge"],
            )
            self.assertEqual(
                entry["real_win_delta"]+entry["real_kong_delta"]+
                entry["real_exhaustive_delta"],
                entry["delta_shadow_minus_challenge"],
            )
            self.assertLessEqual(
                entry["shadow_override_count"],
                entry["shadow_discard_decisions"],
            )
        self.assertEqual(
            sum(s["shadow_override_count"] for s in case["seat_rotation_results"]),
            self.result["candidate_legal_minimum_shanten_overrides"],
        )

    def test_resume_reuses_genuine_paid_five_game_cluster_without_replay(self):
        # The setUpClass fixture above created and audited five REAL
        # authoritative paid games; a restart must not invoke any new game.
        with patch("mahtrain_core.ai_shadow_headtohead.evaluate_one_seed",
                   side_effect=AssertionError("must not replay genuine games")):
            resumed=evaluate_frozen_shadow(
                training_dir=self.training,seed_start=90023,
                seeds=1,out_dir=self.output,resume=True,
            )
        self.assertEqual(resumed["reused_prior_completed_seed_shards"],1)
        self.assertEqual(resumed["interruption_safe_completed_seed_shards"],1)
        self.assertEqual(resumed["actual_real_complete_games"],5)
        self.assertEqual(
            resumed["seat_rotated_seed_cluster_mean_delta_points"],
            self.result["seat_rotated_seed_cluster_mean_delta_points"],
        )

    def test_m438_read_only_accounting_over_actual_paid_games(self):
        # M4.36 setUpClass executed FIVE real four-seat complete games,
        # not mocked accounting rows; audit them without rerunning the engine.
        from mahtrain_core.ai_shadow_loss_audit import audit_saved_shadow_results
        destination=self.root/"M438_genuine_ledger_accounting"
        with patch("mahtrain_core.ai_shadow_headtohead.evaluate_one_seed",
                   side_effect=AssertionError("analysis must never replay")):
            safe=audit_saved_shadow_results(
                evaluation_dir=self.output,report_dir=destination,
            )
        self.assertEqual(safe["original_shuffle_seed_clusters"],1)
        self.assertEqual(safe["total_complete_authoritative_games"],5)
        self.assertEqual(safe["correlated_rotated_seat_comparisons"],4)
        self.assertEqual(
            safe["paired_mean_official_net_delta_points"],
            self.result["seat_rotated_seed_cluster_mean_delta_points"],
        )
        self.assertAlmostEqual(
            sum(safe["paid_net_delta_accounting_by_component_points"].values()),
            safe["paired_mean_official_net_delta_points"],
            places=4,
        )
        self.assertTrue(safe["no_action_level_causal_attribution"])

    def test_m439_real_new_seed_five_paid_games_and_actor_trace(self):
        # One truly unseen initial shuffle; baseline and four seat rotations
        # are real authoritative finished games with private actor-only cuts.
        from mahtrain_core.ai_shadow_action_diagnostics import run_actor_diagnostics
        output=self.root/"M439_authentic_actor_trace"
        report=run_actor_diagnostics(
            training_dir=self.training,prior_evaluation_dir=self.output,
            seed_start=90034,seeds=1,out_dir=output,
        )
        self.assertEqual(report["actual_real_complete_games"],5)
        self.assertEqual(report["original_shuffle_seed_clusters"],1)
        self.assertEqual(
            report["actor_discard_opportunities"],
            report["actual_model_override_count"]+
            report["baseline_kept_discard_count"],
        )
        self.assertEqual(
            report["actor_visible_effective_tile_count_lower_on_override"]+
            report["actor_visible_effective_tile_count_higher_on_override"]+
            report["actor_visible_effective_tile_count_tied_on_override"],
            report["actual_model_override_count"],
        )
        self.assertTrue(report["online_challenge_unchanged"])
        self.assertTrue(report[
            "diagnosed_cuts_are_not_single_action_counterfactual_effects"])
        self.assertNotIn("90034",json.dumps(report))
        from mahtrain_core.ai_shadow_action_diagnostics import _case_path
        shard=_get_json(_case_path(output,0))
        self.assertEqual(sum(
            len(r["private_actor_discard_trace"])
            for r in shard["private_case"]["seat_rotation_results"]
        ),report["actor_discard_opportunities"])
        with patch("mahtrain_core.ai_shadow_action_diagnostics.evaluate_one_seed",
                   side_effect=AssertionError("never replay completed games")):
            second=run_actor_diagnostics(
                training_dir=self.training,prior_evaluation_dir=self.output,
                seed_start=90034,seeds=1,out_dir=output,resume=True,
            )
        self.assertEqual(second["reused_completed_original_shuffle_clusters"],1)
        from mahtrain_core.ai_shadow_score_geometry import audit_frozen_score_geometry
        with patch("mahtrain_core.ai_shadow_action_diagnostics.evaluate_one_seed",
                   side_effect=AssertionError("M4.40 must never replay matches")):
            geometry=audit_frozen_score_geometry(
                training_dir=self.training,
                actor_evaluation_dir=output,
                report_dir=self.root/"M440_authentic_frozen_geometry",
            )
        self.assertEqual(geometry["real_finished_games_already_reused"],5)
        self.assertEqual(
            geometry["overrides_verified_against_exact_frozen_weights"],
            report["actual_model_override_count"],
        )
        self.assertTrue(geometry["no_new_matches"])
        self.assertTrue(geometry["raw_frozen_weights_hidden"])

    def test_m441_real_nine_paid_games_guarded_and_unguarded(self):
        # This plays NINE truly complete rule-engine Mahjong matches with
        # one original shuffle and all seat rotations, not a fake ledger.
        from mahtrain_core.ai_shadow_guarded_trial import (
            _path as trial_path, run_guarded_trial,
        )
        from mahtrain_core.ai_shadow_action_diagnostics import (
            PROTOCOL as M439_PROTOCOL,
        )
        prior=self.root/"M439_prior_plan_for_M441"
        prior.mkdir()
        prior.joinpath("PRIVATE_actor_diagnostic_plan.json").write_text(
            json.dumps({
                "protocol":M439_PROTOCOL,
                "private_source_training_directory":str(self.training),
                "private_source_m437_directory":str(self.output),
                "private_frozen_model_sha256":self.provenance["model_sha256"],
                "online_policy_changed":False,
                "private_eval_seed_start":90034,
                "private_eval_seed_count":1,
            }),encoding="utf8")
        target=self.root/"M441_genuine_nine_game_trial"
        result=run_guarded_trial(
            training_dir=self.training,
            prior_m437_dir=self.output,
            prior_m439_dir=prior,
            seed_start=90047,seeds=1,out_dir=target,
        )
        self.assertEqual(result["actual_complete_paid_games"],9)
        self.assertEqual(result["challenge_baseline_games"],1)
        self.assertEqual(result["unguarded_four_seat_games"],4)
        self.assertEqual(result["guarded_four_seat_games"],4)
        self.assertTrue(result["online_challenge_ai_unchanged"])
        private=_get_json(trial_path(target,0))["private_case"]
        self.assertEqual(private["complete_authoritative_games"],9)
        for seat in private["seat_rotation_results"]:
            for policy in ("unguarded","guarded"):
                entry=seat["policies"][policy]
                self.assertEqual(entry["official_net_delta"],
                                 sum(entry["paid_component_delta"].values()))
        with patch("mahtrain_core.ai_shadow_guarded_trial._one_original_shuffle",
                   side_effect=AssertionError("genuine paid games cannot replay")):
            repeat=run_guarded_trial(
                training_dir=self.training,prior_m437_dir=self.output,
                prior_m439_dir=prior,seed_start=90047,seeds=1,
                out_dir=target,resume=True,
            )
        self.assertEqual(repeat["completed_seed_shards_reused_on_resume"],1)

    def test_m442_real_challenge_baseline_tie_probe_is_strategy_identical(self):
        # Genuine terminal game, all four Challenge seats, immutable seed.
        # The probe uses original Challenge ranking and never chooses a cut.
        from mahtrain_core.ai_challenge_tie_opportunities import (
            _aggregate as safe_aggregate, play_one_challenge_baseline,
            _verify_case,
        )
        seed=90244
        probed=play_one_challenge_baseline(seed)
        vanilla=_finish_real_full_game(seed,None,None)
        self.assertEqual(probed["official_net_by_seat"],
                         vanilla["official_net_by_seat"])
        self.assertEqual(probed["terminal_phase"],vanilla["phase"])
        _verify_case(probed,seed)
        public=safe_aggregate(
            [probed],self.provenance["trained_original_shuffle_clusters"]
        )
        self.assertEqual(public["actual_complete_four_challenge_games"],1)
        self.assertEqual(public["independent_original_shuffle_clusters"],1)
        self.assertTrue(public["original_challenge_policy_unmodified"])
        self.assertEqual(public["counts"]["discard_decisions"],
                         public["sampled_actor_discard_opportunities"])
        self.assertEqual(public["counts"][
            "single_policy_choice_decisions"]+
            public["counts"]["multichoice_minimum_shanten_decisions"],
            public["sampled_actor_discard_opportunities"])
        self.assertNotIn(str(seed),json.dumps(public))

    def test_m443_authentic_nine_game_same_ukeire_two_policy_trial(self):
        from mahtrain_core.ai_safe_tie_policy_trial import _one_seed, _audit_case
        # Nine authoritative games, one genuine natural shuffle: Challenge
        # + four risk-first + four fan-first rotations.
        seed=90319
        game=_one_seed(seed)
        _audit_case(game,seed)
        self.assertEqual(game["real_completed_games"],9)
        vanilla=_finish_real_full_game(seed,None,None)
        self.assertEqual(game["official_baseline_by_seat"],
                         vanilla["official_net_by_seat"])
        for seat in game["seat_rotation_results"]:
            for mode in ("risk_first","fan_first"):
                sample=seat["policies"][mode]
                self.assertEqual(sample["official_net_delta"],
                                 sum(sample["real_paid_component_delta"].values()))
                self.assertLessEqual(sample["accepted_overrides"],
                                     sample["safe_tie_opportunities"])
                if sample["accepted_overrides"]==0:
                    self.assertEqual(sample["official_net_delta"],0)

    def test_no_weights_never_change_true_baseline_all_four_seats(self):
        one=evaluate_one_seed(90025,None)
        self.assertEqual(one["complete_authoritative_games"],5)
        for seat in one["seat_rotation_results"]:
            self.assertEqual(seat["delta_shadow_minus_challenge"],0)
            self.assertEqual(seat["shadow_override_count"],0)

    def test_frozen_model_fit_from_train_only_and_tampered_weights_rejected(self):
        model=_get_json(self.training/"PRIVATE_uncertainty_offline_model.json")
        self.assertEqual(
            _bounded_weights(model),self.weights,
        )
        self.assertFalse(model["online_policy_promotion_allowed"])
        bad=deepcopy(model)
        bad["online_policy_promotion_allowed"]=True
        with self.assertRaises(ValueError):
            _bounded_weights(bad)
        bad=deepcopy(model)
        bad["weights"]=[float("nan"),.1,.1]
        with self.assertRaises(ValueError):
            _bounded_weights(bad)
        bad=deepcopy(model)
        bad["weights"]=[.8,.1,.1]
        with self.assertRaises(ValueError):
            _bounded_weights(bad)
        file=self.training/"PRIVATE_uncertainty_offline_model.json"
        saved=file.read_text(encoding="utf8")
        try:
            compromised=deepcopy(model)
            compromised["train_seed_clusters"]+=1
            file.write_text(json.dumps(compromised),encoding="utf8")
            with self.assertRaises(ValueError):
                load_frozen_local_model(self.training)
        finally:
            file.write_text(saved,encoding="utf8")

    def test_reject_same_seed_or_existing_result_dir(self):
        with self.assertRaises(ValueError):
            evaluate_frozen_shadow(
                training_dir=self.training,seed_start=89823,
                seeds=1,out_dir=self.root/"reject_train",
            )
        with self.assertRaises(ValueError):
            evaluate_frozen_shadow(
                training_dir=self.training,seed_start=89824,
                seeds=1,out_dir=self.root/"reject_old_holdout",
            )
        with self.assertRaises(ValueError):
            evaluate_frozen_shadow(
                training_dir=self.training,seed_start=90024,
                seeds=1,out_dir=self.output,
            )
        with self.assertRaises(ValueError):
            evaluate_frozen_shadow(
                training_dir=self.training,seed_start=90024,
                seeds=1,out_dir=self.training,
            )

    def test_invalid_seeds_and_online_agent_state_blocked(self):
        for bad in (0,-1,101,True,1.4):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                evaluate_frozen_shadow(
                    training_dir=self.training,seed_start=90025,
                    seeds=bad,out_dir=self.root/"invalid",
                )
        with self.assertRaises(ValueError):
            FrozenShadowAgent(seed=89823,seat=4,weights=None)
        with self.assertRaises(ValueError):
            FrozenShadowAgent(seed=89823,seat=0,
                              weights=(.3,0.,0.))

    def test_own_view_only_override_respects_minimum_shanten(self):
        # Controlled legal snapshot features; no hidden wall/opponent hands.
        original="m1"
        other="m2"
        view={
            "seat":0,"phase":"await_discard","hand":["m1","m2"],
            "own_melds":[],"missing_suits":["s","s","s","s"],
        }
        o={
            "status":"choose_discard","minimum_shanten":1,
            "candidates":[
                {"discard":original,"shanten":1,
                 "effective_tile_count":1,
                 "next_draw_probability":0.,
                 "effective_types":[]},
                {"discard":other,"shanten":1,
                 "effective_tile_count":39,
                 "next_draw_probability":1.,
                 "effective_types":["m3"]},
                {"discard":"m4","shanten":2,
                 "effective_tile_count":40,
                 "next_draw_probability":1.,
                 "effective_types":["m3"]},
            ],
        }
        shadow=FrozenShadowAgent(
            seed=90026,seat=0,weights=(.2,.2,.2)
        )
        with patch.object(
            shadow._delegate,"discard",return_value=original
        ), patch(
            "mahtrain_core.ai_shadow_headtohead.analyze_discards",
            return_value=o
        ), patch(
            "mahtrain_core.ai_shadow_headtohead.visible_tiles",
            return_value=[]
        ):
            result=shadow.discard(view)
        self.assertEqual(result,other)
        self.assertEqual(shadow.override_count,1)
        self.assertTrue(shadow.last_choice["kept_minimum_shanten"])

if __name__=="__main__":
    unittest.main()
