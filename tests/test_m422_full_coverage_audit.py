"""M4.22: frozen top-six reproduction, full coverage and private-state guards."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tests")]

from mahtrain_core.ai_bounded_first_split_tenpai_audit import FirstSplitBoundedAuditAgent
from mahtrain_core.ai_bounded_full_coverage_audit import (
    PROTOCOL, HISTORICAL_CHANGED, FullCoverageAuditAgent,
    complete_branch_profile, historical_changed_position, study,
)
from mahtrain_core.rules import TILE_INDEX

MODULE = "mahtrain_core.ai_bounded_full_coverage_audit"


class M422FullCoverageAuditTests(unittest.TestCase):
    def test_all_public_draw_types_include_omitted_tail(self):
        tiles = list(TILE_INDEX)[:7]
        info = {"shanten": 1, "effective_tile_count": 7,
                "effective_details": [{"tile": tile, "remaining": 1} for tile in tiles]}
        frozen = {"proxy": 6.0, "draw_copy_mass": 6,
                  "draw_types": 6, "all_effective_copies": 7,
                  "coverage_fraction": round(6 / 7, 5)}
        with (patch(f"{MODULE}._own_view", return_value=(["m1", "m2"], [], "p")),
              patch(f"{MODULE}.visible_tiles", return_value=[]),
              patch(f"{MODULE}.effective_draws", return_value=info),
              patch(f"{MODULE}.next_discard_wait_value",
                    side_effect=lambda after, draw, *args: (100.0 if draw == tiles[6] else 1.0, 2)),
              patch(f"{MODULE}.projected_branch_score", return_value=frozen)):
            profile = complete_branch_profile({"win_ledger": {"fan_cap": 3}}, "m1")
        self.assertEqual(profile["truncated_proxy"], 6)
        self.assertEqual(profile["complete_proxy"], 106)
        self.assertEqual(profile["omitted_proxy"], 100)
        self.assertEqual(profile["omitted_draw_types"], 1)
        self.assertEqual(profile["all_effective_copies"], 7)
        self.assertEqual(profile["additional_second_cuts_checked"], 2)
        self.assertEqual(profile["coverage_fraction"], round(6 / 7, 5))

    def test_frozen_top_six_mismatch_fails_closed(self):
        tiles = list(TILE_INDEX)[:2]
        info = {"shanten": 1, "effective_tile_count": 2,
                "effective_details": [{"tile": tile, "remaining": 1} for tile in tiles]}
        with (patch(f"{MODULE}._own_view", return_value=(["m1"], [], "p")),
              patch(f"{MODULE}.visible_tiles", return_value=[]),
              patch(f"{MODULE}.effective_draws", return_value=info),
              patch(f"{MODULE}.next_discard_wait_value", return_value=(1.0, 1)),
              patch(f"{MODULE}.projected_branch_score", return_value={
                  "proxy": 999.0, "draw_copy_mass": 2, "draw_types": 2,
                  "all_effective_copies": 2, "coverage_fraction": 1.0,
              })):
            with self.assertRaisesRegex(RuntimeError, "failed to reproduce"):
                complete_branch_profile({}, "m1")

    def test_bad_private_or_nonnumeric_inputs_are_rejected(self):
        with patch(f"{MODULE}._own_view", return_value=(["m1"], [], "p")):
            with self.assertRaises(ValueError):
                complete_branch_profile({}, "m2")
            with self.assertRaises(ValueError):
                complete_branch_profile({"win_ledger": {"fan_cap": True}}, "m1")

    def test_actual_action_unchanged_even_if_complete_score_reverses(self):
        agent = FullCoverageAuditAgent(seed=42, seat=0, arm="bounded_two_transition")
        def frozen_cut(self, view):
            self._last_discard_scores = [{"discard": "m1"}, {"discard": "m2"}]
            self.anonymous_changes.append({"own_discard_ordinal": 1, "projected_ratio": 1.25})
            return "m2"
        def profile(view, tile):
            return {"complete_proxy": 200.0 if tile == "m1" else 100.0}
        with (patch.object(FirstSplitBoundedAuditAgent, "discard", frozen_cut),
              patch(f"{MODULE}.complete_branch_profile", side_effect=profile)):
            cut = agent.discard({})
        self.assertEqual(cut, "m2")
        self.assertTrue(agent.coverage_records[0]["reverses_original_proxy_order"])
        self.assertFalse(agent.coverage_records[0]["full_branch_retains_gain_gate"])
        self.assertEqual(agent.coverage_records[0]["full_branch_ratio"], 0.5)
        raw = json.dumps(agent.coverage_records)
        for secret in ('"hand"', '"tile"', '"m1"', '"m2"', '"future_wall"'):
            self.assertNotIn(secret, raw)

    def test_baseline_cannot_run_expanded_audit(self):
        agent = FullCoverageAuditAgent(seed=42, seat=0, arm="baseline")
        with patch.object(FirstSplitBoundedAuditAgent, "discard", return_value="m1"):
            self.assertEqual(agent.discard({}), "m1")
        self.assertEqual(agent.coverage_records, [])

    def test_historical_position_reconciles_authoritative_ledger(self):
        money = {"official_net": 4, "win_points": 2,
                 "kong_points": 2, "exhaustive_points": 0}
        prior = {
            "challenge_seat": 3, "actual_changes": 1,
            "first_split": {"event_ordinal": 77, "own_discard_ordinal": 3,
                            "first_policy_change": {"projected_ratio": 1.2}},
            "authoritative_deltas": {k: 0 for k in money},
            "arms": {"bounded_two_transition": {
                "official": money, "terminal_phase": "finished",
            }},
        }
        def pretend_match(*args, **kwargs):
            agent = kwargs["offline_agent_overrides"][3]
            agent.coverage_records = [{"own_discard_ordinal": 3, "original_truncated_ratio": 1.2}]
            agent.anonymous_changes = [{"own_discard_ordinal": 3}]
            return {"physical_count": 108, "terminal_phase": "finished"}
        with (patch(f"{MODULE}.paired_audit_position", return_value=prior),
              patch(f"{MODULE}._fixed_lineup", return_value=(["challenge"] * 4, 3)),
              patch(f"{MODULE}.simulate_match", side_effect=pretend_match),
              patch(f"{MODULE}._official_outcome", return_value=money)):
            row = historical_changed_position(60001, 1)
        self.assertEqual(row["actual_changes"], 1)
        self.assertEqual(row["official_component_deltas"]["official_net"], 0)
        self.assertEqual(row["original_first_split_event_ordinal"], 77)
        self.assertTrue(row["retrospective_not_independent_validation"])
        self.assertFalse(row["online_ai_modified"])
        for secret in ('"hand"', '"tile"', '"future_wall"', '"_trace"'):
            self.assertNotIn(secret, json.dumps(row))

    def test_historical_wrong_position_and_input_fail_closed(self):
        for seed, rotation in ((True, 1), (60001, True), (-1, 1),
                               (60001, 4), (2**32, 1)):
            with self.subTest(seed=seed, rotation=rotation), self.assertRaises(ValueError):
                historical_changed_position(seed, rotation)
        with patch(f"{MODULE}.paired_audit_position",
                   return_value={"actual_changes": 0, "first_split": None}):
            with self.assertRaisesRegex(RuntimeError, "not truly changed"):
                historical_changed_position(60000, 0)

    def test_historical_not_new_holdout_or_live_rollout(self):
        self.assertEqual(HISTORICAL_CHANGED, (("development", 60001, 1),
                                               ("holdout", 61000, 1)))
        with patch(f"{MODULE}.historical_changed_position",
                   side_effect=lambda s, r: {"seed": s, "rotation": r}):
            report = study()
        self.assertEqual(report["protocol"], PROTOCOL)
        self.assertEqual(len(report["positions"]), 2)
        self.assertTrue(report["retrospective_not_independent_validation"])
        self.assertFalse(report["online_ai_modified"])
        self.assertIsNotNone(report["limitations"])


if __name__ == "__main__":
    unittest.main()
