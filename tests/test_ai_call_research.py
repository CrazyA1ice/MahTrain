"""M3.80 fully grounded scoring, resolved-call, and cluster-bootstrap checks."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))

from compare_challenge_call_policy import (
    CLUSTER_KEYS, TimedChallenge, cluster_bootstrap_ci, public_outcome,
    summarize_cases,
)
from mahtrain_core.ai_tournament import simulate_match


class CallExperimentTests(unittest.TestCase):
    def test_authoritative_component_ledgers_and_resolved_calls(self):
        game = {
            "official_settled_balances": [10, -10, 0, 0],
            "partial_win_balances": [8, -8, 0, 0],
            "official_kong_balances": [3, -3, 0, 0],
            "official_exhaustive_balances": [-1, 1, 0, 0],
            "winners": [
                {"seat": 0, "source": 1, "kind": "ron"},
                {"seat": 2, "source": 0, "kind": "ron"},
                {"seat": 3, "source": 0, "kind": "rob_kong"},
                {"seat": 0, "source": 0, "kind": "self_draw"},
            ],
            "public_events": [
                {"type": "peng", "seat": 0},
                {"type": "an_gang", "seat": 0, "tile": "m1", "revealed": True},
                {"type": "bu_gang_declared", "seat": 0},  # Not a settled kong.
                {"type": "multi_ron", "seat": 1, "seats": [2, 3]},
            ],
            "trace": [
                {"action": "peng", "seat": 0},
                {"action": "ming_gang", "seat": 0},  # Lost competing claim.
                {"action": "an_gang", "seat": 0},
            ],
            "terminal_phase": "finished",
        }
        agent = TimedChallenge(seed=42, seat=0)
        agent._call_wall_ms = [1.0, 3.0]
        agent._real_call_decisions = 2
        row = public_outcome(game, 0, agent)
        self.assertEqual((row["net"], row["hu_points"],
                          row["kong_points"], row["exhaustive_points"]),
                         (10, 8, 3, -1))
        self.assertEqual(row["win_events"], 2)
        self.assertEqual(row["self_draws"], 1)
        self.assertEqual(row["ron_wins"], 1)
        self.assertEqual(row["deal_in_events"], 2)
        self.assertEqual(row["rob_kong_deal_ins"], 1)
        self.assertEqual(row["resolved_calls"], 2)
        self.assertEqual(row["resolved_kongs"], 1)
        self.assertEqual(row["attempted_calls"], 3)
        self.assertEqual(row["mean_legal_call_decision_wall_ms"], 2)
        self.assertEqual(row["call_decision_opportunities"], 2)

    def test_rejects_ledger_mismatch_even_when_total_is_zero_sum(self):
        g = {
            "official_settled_balances": [10, -10, 0, 0],
            "partial_win_balances": [8, -8, 0, 0],
            "official_kong_balances": [3, -3, 0, 0],
            "official_exhaustive_balances": [0, 0, 0, 0],
        }
        with self.assertRaisesRegex(RuntimeError, "reconcile"):
            public_outcome(g, 0, TimedChallenge(seed=0, seat=0))

    def test_four_seat_cluster_means_differ_from_pooled_fake_independence(self):
        cases = []
        for seed in range(900, 908):
            for seat in range(4):
                old = {key: 0 for key in CLUSTER_KEYS}
                new = dict(old)
                new["net"] = seed - 901
                new["deal_in_events"] = int(seat == 0)
                cases.append({"seed": seed, "seat": seat,
                              "legacy": old, "proposed": new})
        report = summarize_cases(cases, 8)
        self.assertEqual(len(report["per_seed"]), 8)
        self.assertEqual(report["mean_seed_cluster_delta"], 2.5)
        self.assertEqual(
            report["mean_paired_deltas"]["deal_in_events"], 0.25)
        interval = report["cluster_bootstrap_95pct_intervals"]["net"]
        self.assertIsNotNone(interval)
        self.assertLessEqual(interval[0], 2.5)
        self.assertGreaterEqual(interval[1], 2.5)
        self.assertEqual(report, summarize_cases(cases, 8))
        with self.assertRaisesRegex(ValueError, "four distinct"):
            summarize_cases(cases[:-1], 8)

    def test_small_cluster_count_does_not_create_fake_confidence_interval(self):
        self.assertIsNone(cluster_bootstrap_ci([1, 2, 3, 4]))
        self.assertEqual(
            cluster_bootstrap_ci([0] * 8), [0, 0])
        self.assertEqual(cluster_bootstrap_ci([1, 2, 3, 4, 5, 6, 7, 8]),
                         cluster_bootstrap_ci([1, 2, 3, 4, 5, 6, 7, 8]))

    def test_real_authoritative_match_exposes_reconciling_components(self):
        # One real match is enough to assert exposure and reconciliation;
        # the seeded holdout tournament itself runs in its own CI step.
        match = simulate_match(11, rotation=0, offline_kong_base=1)
        self.assertEqual(match["physical_count"], 108)
        for name in ("partial_win_balances", "official_kong_balances",
                     "official_exhaustive_balances"):
            self.assertEqual(sum(match[name]), 0)
        self.assertEqual(
            match["official_settled_balances"],
            [sum(values) for values in zip(
                match["partial_win_balances"],
                match["official_kong_balances"],
                match["official_exhaustive_balances"],
            )],
        )


if __name__ == "__main__":
    unittest.main()
