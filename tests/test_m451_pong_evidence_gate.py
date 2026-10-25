"""M4.51 exact SAFE-study protocol, settlement, phase contrast and stop gate."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]
from mahtrain_core.ai_pong_evidence_gate import (
    PROTOCOL,SOURCES,audit_safe_reports,load_safe_json,
)


def fixture()->dict:
    # Aggregate-only real published M4.47..M4.50 summary shapes.
    # No private games, wall, seeds or hands are stored here.
    return {
        "m447":{
            "protocol":SOURCES["m447"],
            "independent_original_shuffle_clusters":8,
            "actual_natural_original_challenge_games":8,
            "genuine_full_terminal_branch_games":32,
            "real_completed_full_games_baseline_plus_branches":40,
            "paired_future_wall_worlds":16,
            "branch_pairs_where_peng_was_actually_claimed":16,
            "original_shuffles_with_legal_peng_after_challenge_pass":8,
            "original_shuffles_without_such_a_checkpoint":0,
            "seed_level_positive_delta":3,
            "seed_level_negative_delta":3,
            "seed_level_zero_delta":2,
            "mean_forced_peng_minus_pass_all_seed_clusters":20,
            "mean_official_component_delta_all_seed_clusters":{
                "win":18.75,"kong":1.25,"exhaustive":0
            },
            "new_candidate_policy_not_fitted_or_promoted":True,
            "same_original_shuffle_future_worlds_not_independent":True,
        },
        "m448":{
            "protocol":SOURCES["m448"],
            "new_independent_original_shuffle_clusters":24,
            "real_natural_challenge_baseline_games":24,
            "real_terminal_branch_games":72,
            "total_true_complete_paid_games":96,
            "two_world_matched_branch_pairs":36,
            "branch_pairs_with_actual_peng":36,
            "original_shuffles_with_first_pass_peng_checkpoint":18,
            "original_shuffles_without_checkpoint":6,
            "original_shuffles_positive":8,
            "original_shuffles_negative":9,
            "original_shuffles_equal":7,
            "mean_forced_peng_minus_pass_official_net_points":-30.83333,
            "mean_official_component_delta_points":{
                "win":-35.41667,"kong":2.5,"exhaustive":2.08333
            },
            "previous_m447_original_shuffles_audited_but_not_pooled":True,
            "online_challenge_ai_unchanged":True,
            "same_shuffle_two_future_worlds_not_independent":True,
        },
        "m449":{
            "protocol":SOURCES["m449"],
            "independent_original_shuffle_clusters":24,
            "natural_complete_games":24,
            "true_full_terminal_branch_games":68,
            "matched_two_world_action_pairs":34,
            "actual_peng_accepted_pairs":34,
            "eligible_first_peng_after_original_challenge_pass_clusters":17,
            "original_shuffles_without_eligible_checkpoint":7,
            "original_shuffle_positive":9,
            "original_shuffle_negative":8,
            "original_shuffle_equal":7,
            "all_shuffle_mean_peng_minus_pass_points":21.25,
            "all_shuffle_mean_real_component_deltas":{
                "win":27.08333,"kong":4.58333,"exhaustive":-10.41667
            },
            "pre_action_actor_only_strata":{
                "public_wall_segment":{
                    "early":{"independent_original_shuffles":10,
                             "mean_peng_minus_pass_points_exploratory":-59},
                    "middle":{"independent_original_shuffles":7,
                              "mean_peng_minus_pass_points_exploratory":157.14286},
                    "late":{"independent_original_shuffles":0,
                            "small_group_outcomes_suppressed":True},
                },
            },
            "old_m447_m448_outcomes_not_fitted_or_pooled":True,
            "original_challenge_agent_unchanged":True,
            "two_worlds_not_independent_original_shuffles":True,
        },
        "m450":{
            "protocol":SOURCES["m450"],
            "independent_new_original_shuffle_clusters":48,
            "actual_natural_challenge_games":48,
            "actual_true_full_terminal_branch_games":132,
            "actual_total_complete_paid_games":180,
            "matched_real_two_world_action_pairs":66,
            "true_peng_accepted_pairs":66,
            "first_natural_legal_peng_after_challenge_pass_clusters":33,
            "original_shuffles_without_eligible_checkpoint":15,
            "original_shuffles_positive":12,
            "original_shuffles_negative":19,
            "original_shuffles_equal":17,
            "overall_all_seed_mean_forced_peng_minus_pass_points":-35,
            "official_net_component_means":{
                "win":-33.33333,"kong":-.625,"exhaustive":-1.04167
            },
            "comparison_status":"exploratory_independent_replication_complete",
            "precommitted_public_wall_phase_groups":{
                "early":{"independent_original_shuffle_clusters":16,
                         "positive":6,"negative":10,"equal":0,
                         "mean_net_peng_minus_pass_points":-44.375},
                "middle":{"independent_original_shuffle_clusters":15,
                          "positive":6,"negative":9,"equal":0,
                          "mean_net_peng_minus_pass_points":-64.66667},
                "late":{"independent_original_shuffle_clusters":2,
                        "direction_counts_suppressed_insufficient_support":True},
            },
            "middle_minus_early_mean_net_points":-20.29167,
            "cluster_bootstrap_middle_minus_early_95_percentile_interval":[
                -163.49479,119.30208,
            ],
            "direction_supported_in_new_independent_shuffles":False,
            "previous_m449_twenty_four_shuffles_verified_but_not_pooled":True,
            "no_training_no_threshold_selection_no_online_challenge_change":True,
            "future_wall_worlds_are_correlated_within_original_shuffle":True,
        },
    }


class M451SafeEvidenceGateTests(unittest.TestCase):
    def test_four_distinct_real_report_shapes_not_pooled(self):
        result=audit_safe_reports(fixture())
        self.assertEqual(result["protocol"],PROTOCOL)
        self.assertEqual(result["mean_effect_sign_reversals_between_consecutive_studies"],3)
        self.assertEqual([
            x["conditional_peng_minus_pass_mean_points"]
            for x in result["studies_in_natural_chronological_order"].values()
        ],[20,-30.83333,21.25,-35])
        self.assertEqual([
            x["total_paid_games"]
            for x in result["studies_in_natural_chronological_order"].values()
        ],[40,96,92,180])
        self.assertEqual(result["m450_predeclared_middle_minus_early_points"],-20.29167)
        self.assertIs(result["m450_predeclared_direction_supported"],False)
        self.assertTrue(result["m449_midwall_claim_not_independently_supported"])
        self.assertEqual(result["recommendation"],
                         "HOLD_CURRENT_CHALLENGE_POLICY_NO_PROMOTION")
        text=json.dumps(result)
        self.assertNotIn("model_sha256",text)
        self.assertNotIn("private_original_shuffle_seed",text)
        self.assertNotIn("PRIVATE_",text)

    def test_reject_missing_wrong_or_unverified_protocol(self):
        data=fixture()
        del data["m447"]
        with self.assertRaisesRegex(ValueError,"all four"):
            audit_safe_reports(data)
        data=fixture()
        data["m450"]["protocol"]="invented"
        with self.assertRaisesRegex(ValueError,"protocol"):
            audit_safe_reports(data)

    def test_reject_nonconservation_of_paid_balances(self):
        data=fixture()
        data["m450"]["official_net_component_means"]["kong"]=20
        with self.assertRaisesRegex(ValueError,"reconcile"):
            audit_safe_reports(data)

    def test_reject_fake_completion_or_nonindependent_world_count(self):
        for field in ("matched_real_two_world_action_pairs",
                      "actual_true_full_terminal_branch_games",
                      "actual_total_complete_paid_games"):
            data=fixture()
            data["m450"][field]+=1
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,"inconsistent"):
                audit_safe_reports(data)

    def test_reject_misleading_pooled_or_online_promoted_claims(self):
        for label,key in (
            ("m449","old_m447_m448_outcomes_not_fitted_or_pooled"),
            ("m448","online_challenge_ai_unchanged"),
            ("m450","future_wall_worlds_are_correlated_within_original_shuffle"),
        ):
            data=fixture()
            data[label][key]=False
            with self.subTest(key=key),self.assertRaises(ValueError):
                audit_safe_reports(data)

    def test_reject_inaccurate_prespecified_mid_minus_early(self):
        data=fixture()
        data["m450"]["middle_minus_early_mean_net_points"]=200
        with self.assertRaisesRegex(ValueError,"contrast"):
            audit_safe_reports(data)

    def test_reject_incorrect_bootstrap_claim(self):
        data=fixture()
        data["m450"]["direction_supported_in_new_independent_shuffles"]=True
        with self.assertRaisesRegex(ValueError,"bootstrap"):
            audit_safe_reports(data)

    def test_reject_phase_histogram_missing_original_eligible_case(self):
        data=fixture()
        data["m449"]["pre_action_actor_only_strata"]["public_wall_segment"][
            "middle"]["independent_original_shuffles"]=8
        with self.assertRaisesRegex(ValueError,"cover eligible"):
            audit_safe_reports(data)

    def test_no_new_policy_even_if_a_future_conditional_study_is_positive(self):
        data=fixture()
        # Change M4.50 no score: it is still not a policy-vs-policy trial.
        # Test only the strategy promotion invariant, not a fake study profit.
        result=audit_safe_reports(data)
        self.assertFalse(result["formal_candidate_full_game_ab_evaluation_provided"])
        self.assertTrue(result["no_causal_population_ev_or_pong_always_bad_claim"])

    def test_safe_loader_duplicate_nan_secret_and_valid_public_safety_flags(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"safe.json"
            p.write_text('{"x":1,"x":2}',encoding="utf8")
            with self.assertRaisesRegex(ValueError,"duplicate"):
                load_safe_json(p)
            p.write_text('{"x":NaN}',encoding="utf8")
            with self.assertRaisesRegex(ValueError,"nonfinite"):
                load_safe_json(p)
            p.write_text('{"hand":["W1"]}',encoding="utf8")
            with self.assertRaisesRegex(ValueError,"unsafe"):
                load_safe_json(p)
            p.write_text(json.dumps({
                "future_wall_worlds_are_correlated_within_original_shuffle":True,
                "no_specific_hand_tiles_future_wall_shuffle_seed_or_weights_exported":True,
            }),encoding="utf8")
            self.assertTrue(load_safe_json(p)[
                "future_wall_worlds_are_correlated_within_original_shuffle"])


if __name__=="__main__":
    unittest.main()
