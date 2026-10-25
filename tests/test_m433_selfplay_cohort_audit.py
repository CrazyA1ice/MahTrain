"""M4.33 independent natural shuffle cohort: strict, privacy-safe auditing."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from mahtrain_core.ai_selfplay_cohort_audit import (
    PROTOCOL, audit_completed_study, run_audited_cohort,
)


class M433SeedClusterAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One real two-seed cohort; run it only once. Every physical branch
        # is a real game, so unit tests must not fabricate a performance result.
        cls.study, cls.safe = run_audited_cohort(
            89703, 1, 1, max_checkpoints=1,
        )

    def test_real_108_tile_official_complete_and_hidden_safe(self):
        s = self.safe
        self.assertEqual(s["protocol"], PROTOCOL)
        self.assertEqual(s["original_natural_full_games"], 2)
        self.assertEqual(
            s["total_genuine_complete_games"],
            s["original_natural_full_games"] +
            s["conditioned_full_terminal_action_branch_games"],
        )
        self.assertTrue(s["real_terminal_components_reconciled"])
        self.assertTrue(s["training_and_holdout_seed_ranges_disjoint"])
        self.assertFalse(s["private_state_and_shuffle_seed_exported"])
        self.assertFalse(s["model_released_to_live_ai"])
        self.assertFalse(s["real_policy_strength_proven"])
        self.assertEqual(
            s["splits"]["train"]["independent_initial_shuffle_clusters"], 1,
        )
        self.assertEqual(
            s["splits"]["holdout"]["independent_initial_shuffle_clusters"], 1,
        )
        self.assertEqual(
            s["conditioned_full_terminal_action_branch_games"] % 4, 0,
        )
        self.assertNotIn("private_shuffle_seed", json.dumps(s))
        self.assertNotIn("89703", json.dumps(s))
        self.assertNotIn("89704", json.dumps(s))
        self.assertNotIn("actor_observation", json.dumps(s))
        self.assertNotIn("public_frames", json.dumps(s))

    def test_no_fake_accuracy_from_zero_or_single_labeled_holdout(self):
        s = self.safe
        self.assertIsNone(
            s["holdout_exploratory_direction_accuracy_if_at_least_five"]
        )
        self.assertEqual(
            s["holdout_accuracy_status"],
            "insufficient_scored_consensus_decisions",
        )
        self.assertLessEqual(s["holdout_scored_consensus_decisions"], 1)

    def test_missing_or_wrong_seed_fails_closed(self):
        edits = (
            lambda s: s["private_train"][0].update(
                {"private_shuffle_seed": 89704}
            ),
            lambda s: s.update({"test_seed_start": 89703}),
            lambda s: s["private_holdout"].clear(),
            lambda s: s["private_holdout"][0].update(
                {"conditional_rollout_games": 999}
            ),
            lambda s: s["private_train"][0].update(
                {"original_natural_games": 2}
            ),
            lambda s: s.update({"no_online_ai_change": False}),
            lambda s: s["public_replays"][0].update(
                {"hand": ["m1"]}
            ),
            lambda s: s["public_replays"][0].update(
                {"game_id": "game-private-seed-89703"}
            ),
            lambda s: s["public_replays"][0]["official_final_balances"].__setitem__(
                0, 9999
            ),
            lambda s: s["model"].update({
                "online_promotion_allowed": True
            }),
            lambda s: s["heldout"].update({
                "scored_decisions": 9999
            }),
        )
        for n, edit in enumerate(edits):
            test = deepcopy(self.study)
            edit(test)
            with self.subTest(tamper=n), self.assertRaises(
                (ValueError, RuntimeError)
            ):
                audit_completed_study(test)

    def test_label_and_full_game_counts_cannot_be_inflated(self):
        for change in (
            lambda s: s.update({"counterfactual_full_games": 99999}),
            lambda s: s["model"].update({"total_action_labels": 999}),
            lambda s: s["heldout"].update({
                "total_natural_checkpoints": 99
            }),
        ):
            test = deepcopy(self.study)
            change(test)
            with self.assertRaises(ValueError):
                audit_completed_study(test)

    def test_invalid_plan_prevents_expensive_simulation(self):
        with patch(
            "mahtrain_core.ai_selfplay_cohort_audit.run_study"
        ) as runner:
            for params in (
                (-1, 2, 2), (True, 2, 2), (2**32-1, 2, 2),
                (89700, 0, 2), (89700, 2, 0),
                (89700, 5, 2), (89700, 2, 5),
            ):
                with self.subTest(params=params), self.assertRaises(ValueError):
                    run_audited_cohort(*params)
            runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
