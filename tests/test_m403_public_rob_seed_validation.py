"""M4.03: seed-cluster-only public-risk signal coverage and no probability."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_public_rob_seed_validation import (
    PROTOCOL,compare,summarize,study,WARNING_BANDS,
)
from mahtrain_core.ai_all_seat_bugang_audit import observe_game


def cohort(start=30000,n=8,kind="positive_and_negative"):
    rows=[]
    for i in range(n):
        seed=start+i
        for rotation in range(4):
            first=[]
            actual=[]
            if rotation==0 and kind!="empty":
                positive=i%2==0 and kind!="negative_only"
                band="same_suit_focus" if i<4 else "unresolved"
                label=int(positive)
                first=[{
                    "seat":0,"level":"challenge",
                    "features":{
                        "band":band,"wall_band":"early",
                        "dingque_eligible_opponents":2,
                    },
                    "rob_possible":label,
                    "potential_robbers":label,
                }]
                if i==1:
                    actual=[{
                        **first[0],
                        "actual_robbed":0,
                        "actual_rob_winners":0,
                        "legal_rob_possible_but_not_realized":0,
                    }]
            rows.append({
                "seed":seed,"rotation":rotation,
                "challenge_seat":(4-rotation)%4,
                "seat_level":["challenge","advanced","basic","baseline"],
                "counts":{
                    "eligible_candidate_windows":len(first),
                    "first_distinct":len(first),
                    "repeated_candidate_windows":0,
                },
                "first_candidates":first,
                "actual_bugang_decisions":actual,
                "official_net_by_seat":[0,0,0,0],
                "terminal_phase":"wall_exhausted",
            })
    return {"independent_initial_shuffle_seeds":n,"positions":rows}


class M403PublicRobSeedValidationTests(unittest.TestCase):
    def test_empty_and_zero_positive_cohorts_cannot_estimate_probability(self):
        for condition,expected in [
            ("empty","no_natural_bugang_candidates"),
            ("negative_only","no_natural_legal_rob_positives"),
        ]:
            with self.subTest(condition=condition):
                summary=summarize(cohort(kind=condition))
                self.assertEqual(summary["validation_status"],expected)
                self.assertIsNone(summary["calibrated_rob_probability"])
                self.assertEqual(summary["independent_initial_shuffle_seeds"],8)
                self.assertEqual(summary["complete_games"],32)
                self.assertEqual(summary["correlated_seat_positions"],128)

    def test_by_public_band_truth_matrix_and_seed_support(self):
        s=summarize(cohort())
        self.assertEqual(s["counts"]["distinct_first"],8)
        self.assertEqual(s["counts"]["first_positive"],4)
        self.assertEqual(s["counts"]["first_negative"],4)
        self.assertEqual(s["counts"]["attempted"],1)
        self.assertEqual(s["seed_support"]["positive_label_seeds"],4)
        self.assertEqual(s["seed_support"]["negative_label_seeds"],4)
        self.assertEqual(s["seed_support"]["public_warning_seeds"],4)
        self.assertEqual(s["seed_support"]["unresolved_nonwarning_seeds"],4)
        self.assertEqual(s["public_band_counts"]["same_suit_focus"]["first_distinct"],4)
        self.assertEqual(s["public_band_counts"]["same_suit_focus"]["label_positive"],2)
        self.assertEqual(s["frozen_warning_cross_counts"]["warning"]["label_positive"],2)
        self.assertEqual(s["frozen_warning_cross_counts"]["not_warned_unresolved"]["label_positive"],2)
        self.assertEqual(s["validation_status"],"descriptive_association_check_only_not_calibrated")
        self.assertIsNone(s["calibrated_rob_probability"])
        self.assertEqual(len(s["per_seed"]),8)
        self.assertNotIn("tile",json.dumps(s))

    def test_positive_labels_in_one_seed_do_not_count_as_multiple_seeds(self):
        c=cohort()
        for row in c["positions"]:
            if row["seed"]!=30000:
                row["first_candidates"]=[]
                row["counts"]["eligible_candidate_windows"]=0
                row["counts"]["first_distinct"]=0
            elif row["rotation"] in (1,2,3):
                row["first_candidates"]=[copy.deepcopy(c["positions"][0]["first_candidates"][0])]
                row["counts"]["eligible_candidate_windows"]=1
                row["counts"]["first_distinct"]=1
                row["first_candidates"][0]["level"]="advanced"
        s=summarize(c)
        self.assertEqual(s["counts"]["first_positive"],4)
        self.assertEqual(s["seed_support"]["positive_label_seeds"],1)
        self.assertEqual(s["validation_status"],"fewer_than_three_positive_seed_clusters")

    def test_no_dingque_mask_violation_even_when_fake_positive_is_label(self):
        c=cohort()
        x=c["positions"][0]["first_candidates"][0]
        x["features"]["band"]="dingque_excluded"
        with self.assertRaisesRegex(RuntimeError,"structural"):
            summarize(c)

    def test_latest_real_rob_hu_cannot_exceed_authorized_legal_responders(self):
        c=cohort()
        decision=c["positions"][4]["actual_bugang_decisions"][0]
        decision["actual_robbed"]=1
        decision["actual_rob_winners"]=1
        with self.assertRaisesRegex(RuntimeError,"latest legal"):
            summarize(c)

    def test_reject_missing_seed_rotation_or_corrupt_de_duplication(self):
        for corrupt in ("missing","duplicate","repeat","balance"):
            c=cohort()
            if corrupt=="missing":
                c["positions"].pop()
            if corrupt=="duplicate":
                c["positions"][1]["rotation"]=0
            if corrupt=="repeat":
                c["positions"][0]["counts"]["repeated_candidate_windows"]=1
            if corrupt=="balance":
                c["positions"][0]["official_net_by_seat"]=[1,0,0,0]
            with self.subTest(corrupt=corrupt),self.assertRaises(
                (ValueError,RuntimeError)):
                summarize(c)

    def test_dev_and_holdout_must_have_nonoverlapping_initial_seeds(self):
        with self.assertRaisesRegex(ValueError,"reused"):
            compare(cohort(),cohort())
        report=compare(cohort(30000),cohort(31000,kind="negative_only"))
        self.assertEqual(report["cross_cohort_decision"],
                         "cannot_validate_public_risk_warning_on_this_holdout")
        self.assertTrue(report["seed_sets_disjoint"])
        self.assertFalse(report["live_policy_modified"])
        self.assertIsNone(report["calibrated_rob_probability"])
        self.assertEqual(report["feature_source"],"public_state_only")
        self.assertEqual(report["protocol"],PROTOCOL)

    def test_new_12_by_12_seed_ranges_and_no_retrospective_selection(self):
        for kw in (
            {"holdout":30005},{"holdout":30000},
            {"development":31000},
            {"seeds":13},{"seeds":0},{"seeds":True},
            {"development":True},{"holdout":2**32-3},
        ):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                study(**kw)
        with patch("mahtrain_core.ai_public_rob_seed_validation.aggregate",
                   side_effect=[cohort(30000,12),cohort(31000,12)]) as fn:
            r=study()
        self.assertEqual(fn.call_args_list[0].args,(30000,12))
        self.assertEqual(fn.call_args_list[1].args,(31000,12))
        self.assertEqual(r["development_seed_range"],[30000,30012])
        self.assertEqual(r["holdout_seed_range"],[31000,31012])

    def test_one_genuine_full_match_preserves_all_seat_outcome_and_sealed_privacy(self):
        row=observe_game(30000,0)
        self.assertEqual(len(row["seat_level"]),4)
        self.assertEqual(sum(row["official_net_by_seat"]),0)
        self.assertEqual(
            row["counts"].get("eligible_candidate_windows",0),
            row["counts"].get("first_distinct",0)+
            row["counts"].get("repeated_candidate_windows",0))
        for event in row["actual_bugang_decisions"]:
            self.assertLessEqual(event["actual_rob_winners"],
                                 event["potential_robbers"])
        raw=json.dumps(row,ensure_ascii=False)
        for private in ("opponent_hands","future_wall","_hands",
                        "offer_signature"):
            self.assertNotIn(private,raw)


if __name__=="__main__":
    unittest.main()
