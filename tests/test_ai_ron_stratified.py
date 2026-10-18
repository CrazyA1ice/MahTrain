"""M3.58 offline-only public strata and shuffle-seed-cluster uncertainty."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.ai_ron_calibration import (
    NAMES, SAFE_INDEX, run_candidate_ron_pilot,
)
from mahtrain_core.ai_ron_stratified import (
    PROTOCOL, public_risk_strata, _seed_bootstrap, analyze_ron_validation,
)


def row(seed, *, progress=0.1, melds=0., safe=False, hit=False):
    features=[0.]*len(NAMES)
    features[0]=1.
    features[1]=progress
    features[2]=melds
    features[SAFE_INDEX]=float(safe)
    if safe and hit:
        raise ValueError("dingque-safe cannot score ron")
    return {
        "seed":seed,
        "features":tuple(features),
        "ron":int(hit),
        "payout_multiplier":2 if hit else 0,
    }


class PublicRonStratificationTests(unittest.TestCase):
    def test_public_strata_cutoffs_and_meld_groups(self):
        self.assertEqual(public_risk_strata(row(1)["features"]),{
            "wall_stage":"early",
            "target_public_melds":"zero",
            "candidate_rule":"ron_eligible",
        })
        self.assertEqual(public_risk_strata(
            row(1,progress=31/55, melds=.25)["features"])["wall_stage"],"late")
        self.assertEqual(public_risk_strata(
            row(1,progress=43/55, melds=.5)["features"])["wall_stage"],"critical")
        self.assertEqual(public_risk_strata(
            row(1,progress=43/55, melds=.5,safe=True)["features"])[
                "candidate_rule"],"dingque_safe")
        self.assertEqual(public_risk_strata(
            row(1,progress=0.8, melds=.25)["features"])[
                "target_public_melds"],"one")
        self.assertEqual(public_risk_strata(
            row(1,progress=0.8, melds=.5)["features"])[
                "target_public_melds"],"two_plus")
        with self.assertRaises(ValueError):
            public_risk_strata([float("nan")]*len(NAMES))

    def test_stratified_report_preserves_denominators_and_no_raw_rows(self):
        rows=[
            row(11,progress=.10,melds=0.,hit=True),
            row(11,progress=.10,melds=0.,safe=True),
            row(12,progress=31/55,melds=.25,hit=False),
            row(12,progress=31/55,melds=.25,hit=True),
            row(13,progress=43/55,melds=.5,hit=False),
            row(13,progress=43/55,melds=.5,safe=True),
        ]
        params=(-2.,)+(0.,)*(len(NAMES)-1)
        result=analyze_ron_validation(
            rows,params,actionable_prior=.25,conditional_multiplier=2,trials=256)
        self.assertEqual(result["protocol"],PROTOCOL)
        self.assertFalse(result["has_hidden_hands"])
        self.assertFalse(result["row_level_predictions_exported"])
        self.assertEqual(result["overall"]["n"],6)
        self.assertEqual(result["overall"]["true_ron_events"],2)
        self.assertEqual(result["strata"]["candidate_rule"]["ron_eligible"]["n"],4)
        self.assertEqual(result["strata"]["candidate_rule"]["dingque_safe"]["n"],2)
        self.assertEqual(result["strata"]["candidate_rule"]["dingque_safe"]["true_ron_events"],0)
        for grouping in ("wall_stage","target_public_melds","candidate_rule"):
            self.assertEqual(sum(x["n"] for x in result["strata"][grouping].values()),6)
        self.assertEqual(result["strata"]["wall_stage"]["early"]["n"],2)
        self.assertEqual(result["strata"]["wall_stage"]["late"]["n"],2)
        self.assertEqual(result["strata"]["wall_stage"]["critical"]["n"],2)
        self.assertEqual(result["strata"]["target_public_melds"]["zero"]["n"],2)
        self.assertEqual(result["strata"]["target_public_melds"]["one"]["n"],2)
        self.assertEqual(result["strata"]["target_public_melds"]["two_plus"]["n"],2)
        self.assertEqual(len(result["by_seed"]),3)
        self.assertEqual(result["cluster_bootstrap_brier"]["seed_clusters"],3)
        self.assertEqual(result["cluster_bootstrap_brier"]["repetitions"],256)
        self.assertEqual(result,analyze_ron_validation(
            rows,params,actionable_prior=.25,conditional_multiplier=2,trials=256))
        blob=json.dumps(result)
        for forbidden in ('"features":','"payout_multiplier":',
                          '"ron":','"opponent_hands":',
                          '"future_wall":','"candidate_tile":'):
            self.assertNotIn(forbidden,blob)

    def test_absent_subgroup_is_null_not_pseudo_zero(self):
        rows=[row(1,progress=.1,melds=0.),row(2,progress=.1,melds=0.,hit=True)]
        params=(-3.,)+(0.,)*(len(NAMES)-1)
        result=analyze_ron_validation(
            rows,params,actionable_prior=.1,conditional_multiplier=2,
            trials=128)
        absent=result["strata"]["wall_stage"]["critical"]
        self.assertEqual(absent["n"],0)
        self.assertIsNone(absent["brier_delta"])
        self.assertIsNone(absent["candidate_brier"])

    def test_bootstrap_samples_whole_seeds_and_reports_direction(self):
        d=[-.04,.03,-.01,.02]
        actual=_seed_bootstrap(d,trials=256)
        self.assertEqual(actual,_seed_bootstrap(d,trials=256))
        self.assertEqual(actual["seeds_better"],2)
        self.assertEqual(actual["seeds_worse"],2)
        self.assertAlmostEqual(actual["seed_macro_mean_delta"],0)
        self.assertLessEqual(actual["bootstrap_95pct_range"][0],
                             actual["bootstrap_95pct_range"][1])
        with self.assertRaises(ValueError):
            _seed_bootstrap([],trials=128)
        with self.assertRaises(ValueError):
            _seed_bootstrap([0.],trials=0)

    def test_pilot_integration_retains_disjoint_seed_and_privacy_constraints(self):
        def fake(seed, *, stride=3):
            self.assertEqual(stride,2)
            return [
                row(seed,progress=.3,melds=.25,hit=(seed%2==0)),
                row(seed,progress=.8,melds=.5,hit=False),
                row(seed,progress=.8,melds=.5,safe=True),
            ]
        with patch("mahtrain_core.ai_ron_calibration.collect_ron_labels",
                   side_effect=fake):
            report=run_candidate_ron_pilot([20,21,22],[30,31,32],stride=2)
        segment=report["stratified_validation"]
        self.assertEqual(segment["overall"]["n"],report["test_n"])
        self.assertEqual(segment["cluster_bootstrap_brier"]["seed_clusters"],3)
        self.assertFalse(segment["has_hidden_hands"])
        self.assertFalse(report["can_claim_generalization"])
        self.assertEqual(len(segment["by_seed"]),len(report["test_seeds"]))


if __name__=="__main__":
    unittest.main()
