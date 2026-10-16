"""M3.13 physical-count checked open-pung scenarios and real oracle decisions."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core.ai_pressure_scenarios import (  # noqa: E402
    SCENARIOS, pressure_scenario_matrix, pressure_scenario_view,
    validate_snapshot,
)
from mahtrain_core.ai import (  # noqa: E402
    MahjongAgent, AblationMahjongAgent, public_suit_pressure,
)


class ConstructedPublicPressureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Genuine project shanten/effective-copy evaluator, no mocked oracle.
        cls.report = pressure_scenario_matrix()
        cls.rows = {r["scenario"]: r for r in cls.report["scenarios"]}

    def test_each_snapshot_is_legal_14_effective_and_physically_feasible(self):
        self.assertEqual(len(SCENARIOS), 5)
        self.assertEqual(self.report["summary"]["scenarios"], 5)
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                v = pressure_scenario_view(scenario)
                physical = validate_snapshot(v)
                self.assertEqual(len(v["hand"]), 14)
                self.assertEqual(physical["known_physical_tiles"],
                                 self.rows[scenario]["known_physical_tiles"])
                self.assertGreater(physical["unknown_physical_tiles"], 0)
                self.assertLessEqual(physical["maximum_tile_multiplicity"], 4)
                self.assertTrue(self.rows[scenario]["physically_feasible"])
                self.assertNotIn("shadow_tile", self.rows[scenario])
                self.assertNotIn("alternative_tile", self.rows[scenario])
        with self.assertRaises(ValueError):
            pressure_scenario_view("not_a_fixture")

    def test_true_tie_rule_must_change_when_two_visible_m_pungs(self):
        row = self.rows["two_same_suit_pungs"]
        self.assertTrue(row["effective_tie"])
        self.assertTrue(row["public_pressure_present"])
        self.assertTrue(row["public_pressure_discriminates"])
        self.assertTrue(row["choice_would_change"])
        self.assertTrue(row["actual_choice_changed"])
        self.assertFalse(row["no_pressure_policy_actual_changed"])
        self.assertTrue(row["same_state_ai_choices_differ"])
        view = pressure_scenario_view("two_same_suit_pungs")
        self.assertGreater(public_suit_pressure("m9",view),
                           public_suit_pressure("s9",view))
        # Verify *real* decisions, not a mocked hand-scoring function.
        self.assertEqual(
            MahjongAgent("challenge",seed=17,seat=0).discard(view),"s9")
        self.assertEqual(
            AblationMahjongAgent("challenge_no_pressure",
                                 seed=17,seat=0).discard(view),"m9")

    def test_negative_controls_refuse_false_activation(self):
        for name in ("one_pung_only", "pungs_across_opponents",
                     "two_pungs_owner_already_won",
                     "two_pungs_in_lower_priority_suit"):
            with self.subTest(name=name):
                row = self.rows[name]
                self.assertTrue(row["effective_tie"])
                self.assertFalse(row["choice_would_change"])
                self.assertFalse(row["actual_choice_changed"])
                self.assertFalse(row["same_state_ai_choices_differ"])
        self.assertTrue(self.rows[
            "two_pungs_in_lower_priority_suit"]["public_pressure_discriminates"])
        self.assertFalse(self.rows[
            "two_pungs_owner_already_won"]["public_pressure_present"])

    def test_unphysical_and_illegal_visible_claims_are_rejected(self):
        view = pressure_scenario_view("two_same_suit_pungs")
        invalid = copy.deepcopy(view)
        invalid["hand"].remove("m4")
        invalid["hand"].remove("s9")
        invalid["hand"].extend(["m1","m1"])
        with self.assertRaises(ValueError):
            validate_snapshot(invalid)
        invalid = copy.deepcopy(view)
        invalid["missing_suits"][1] = "m"
        with self.assertRaises(ValueError):
            validate_snapshot(invalid)
        invalid = copy.deepcopy(view)
        invalid["melds"][1][0]["type"] = "an_gang"
        with self.assertRaises(ValueError):
            validate_snapshot(invalid)
        invalid = copy.deepcopy(view)
        invalid["phase"] = "missing_select"
        with self.assertRaises(ValueError):
            validate_snapshot(invalid)

    def test_report_is_deterministic_aggregate_only(self):
        report = self.report
        self.assertEqual(report["summary"]["choice_would_change"], 1)
        data = json.dumps(report,ensure_ascii=False,sort_keys=True)
        for forbidden in ("opponent_hands","future_wall","private_view",
                          "alternative_tile","shadow_tile","hand"):
            self.assertNotIn('"' + forbidden + '"',data)
        for scenario in report["scenarios"]:
            self.assertEqual(scenario["choice_would_change"],
                             scenario["same_state_ai_choices_differ"])
        self.assertIn("constructed",report["source"])
        self.assertIn("not full replay reachability",
                      " ".join(report["limitations"]))


if __name__ == "__main__":
    unittest.main()
