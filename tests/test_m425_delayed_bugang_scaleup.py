"""M4.25 isolated checks for prospective shard audit and privacy boundaries."""
from __future__ import annotations

from copy import deepcopy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mahtrain_core.ai_delayed_bugang_scaleup import (
    PROTOCOL, SHARDS, SEEDS_PER_SHARD, combine_shards, run_shard,
)
from mahtrain_core.ai_delayed_bugang_paired import ARMS, COMPONENTS, PROTOCOL as PARENT


def _fake_shard(name, *, net=0):
    """Synthetic authority-consistent records, never made-up study results."""
    group, start = SHARDS[name]
    positions = []
    seed_rows = []
    for seed in range(start, start + SEEDS_PER_SHARD):
        for rotation in range(4):
            seat = ([0, 3, 2, 1][rotation])
            a = {
                "official_net": net,
                "win_points": net,
                "kong_points": 0,
                "exhaustive_points": 0,
                "win_events": 1,
                "deal_in_events": 0,
                "realized_kongs": 1,
            }
            b = {
                "official_net": 0,
                "win_points": 0,
                "kong_points": 0,
                "exhaustive_points": 0,
                "win_events": 1,
                "deal_in_events": 0,
                "realized_kongs": 1,
            }
            positions.append({
                "seed": seed, "rotation": rotation, "challenge_seat": seat,
                "arms": {
                    ARMS[0]: {"score": a, "counts": {}, "terminal_phase": "finished"},
                    ARMS[1]: {"score": b, "counts": {}, "terminal_phase": "finished"},
                },
                "component_deltas": {
                    m: a[m] - b[m] for m in COMPONENTS
                },
            })
        seed_rows.append({"seed": seed, "mean_four_seat_deltas": {},
                          "unguarded_interventions": 0})
    return {
        "protocol": PROTOCOL, "parent_protocol": PARENT,
        "official_ruleset": "current_m423",
        "shard": name, "cohort": group,
        "seed_start": start, "seed_end_exclusive": start + SEEDS_PER_SHARD,
        "result": {
            "independent_shuffle_seeds": SEEDS_PER_SHARD,
            "four_seat_rotations": 4,
            "paired_positions": 4 * SEEDS_PER_SHARD,
            "complete_games": 8 * SEEDS_PER_SHARD,
            "per_seed": seed_rows, "positions": positions,
        },
    }


class M425IndependentScaleUpTests(unittest.TestCase):
    def _all(self, *, net=0):
        return {key: _fake_shard(key, net=net) for key in SHARDS}

    def test_exact_fresh_seed_plan_and_no_reused_study_seeds(self):
        self.assertEqual(SHARDS, {
            "development_a": ("development", 66000),
            "development_b": ("development", 66004),
            "holdout_a": ("holdout", 67000),
            "holdout_b": ("holdout", 67004),
        })
        all_seeds = {n for _, start in SHARDS.values()
                     for n in range(start, start + SEEDS_PER_SHARD)}
        self.assertEqual(len(all_seeds), 16)
        self.assertFalse(all_seeds.intersection(
            {64000, 64001, 65000, 65001}))

    def test_strict_full_actual_score_and_four_seat_aggregation(self):
        merged = combine_shards(self._all(net=8))
        self.assertEqual(merged["total_independent_shuffle_seeds"], 16)
        self.assertEqual(merged["total_complete_games"], 128)
        for group in ("development", "holdout"):
            result = merged[group]
            self.assertEqual(result["independent_shuffle_seeds"], 8)
            self.assertEqual(result["seat_rotations_per_seed"], 4)
            self.assertEqual(result["complete_games"], 64)
            self.assertEqual(result["current_guard_minus_old_guard"]["official_net"],8)
            self.assertEqual(result["current_guard_minus_old_guard"]["win_points"],8)
            self.assertEqual(result["current_guard_minus_old_guard"]["kong_points"],0)
            self.assertEqual(result["positive_clusters"],8)
            self.assertEqual(result["negative_clusters"],0)
            self.assertEqual(result["confidence_interval_95pct"],None)
            self.assertTrue(result["exploratory_only"])

    def test_do_not_treat_repeated_rotations_as_independent(self):
        result = combine_shards(self._all(net=-12))
        self.assertEqual(result["development"]["negative_clusters"],8)
        self.assertEqual(len(result["development"]["seed_cluster_rows"]),8)
        self.assertEqual(result["development"]["current_guard_minus_old_guard"]
                         ["official_net"], -12)

    def test_reject_missing_duplicate_or_wrong_cluster(self):
        good = self._all()
        for example in (
            {k: v for k, v in good.items() if k != "holdout_b"},
            {**good, "unknown_shard": _fake_shard("holdout_b")},
        ):
            with self.assertRaises(ValueError):
                combine_shards(example)
        changed = deepcopy(good)
        changed["holdout_b"]["result"]["positions"][0]["rotation"] = 1
        with self.assertRaises(ValueError):
            combine_shards(changed)
        changed = deepcopy(good)
        changed["holdout_b"]["result"]["positions"][0]["seed"] = 65000
        with self.assertRaises(ValueError):
            combine_shards(changed)

    def test_reject_historical_cash_rules_and_reconstructed_scores(self):
        good = self._all()
        for key, value in (
            ("official_ruleset", "frozen_pre_m423"),
            ("seed_start", 64000),
            ("parent_protocol", "tampered"),
            ("shard", "holdout_b"),
        ):
            bad = deepcopy(good)
            bad["development_a"][key] = value
            with self.subTest(field=key),self.assertRaises(ValueError):
                combine_shards(bad)
        changed = deepcopy(good)
        changed["development_a"]["result"]["positions"][0]["arms"][
            ARMS[0]]["score"]["official_net"] = 200
        with self.assertRaises(ValueError):
            combine_shards(changed)
        changed = deepcopy(good)
        changed["development_a"]["result"]["positions"][0][
            "component_deltas"]["official_net"] = 5
        with self.assertRaises(ValueError):
            combine_shards(changed)

    def test_verify_all_four_positions_and_nonnegative_action_counts(self):
        good = self._all()
        bad = deepcopy(good)
        bad["holdout_a"]["result"]["positions"].pop()
        with self.assertRaises(ValueError):
            combine_shards(bad)
        bad = deepcopy(good)
        bad["development_a"]["result"]["positions"][0]["arms"][
            ARMS[0]]["counts"]["policy_interventions"] = -1
        with self.assertRaises(ValueError):
            combine_shards(bad)

    def test_unsupported_shards_never_trigger_expensive_games(self):
        with patch("mahtrain_core.ai_delayed_bugang_scaleup.cohort") as fake:
            for name in ("unknown", "", "development", True, 66000):
                with self.subTest(name=name),self.assertRaises(ValueError):
                    run_shard(name)
            fake.assert_not_called()

    def test_run_shard_explicit_counts_passed_to_frozen_parent(self):
        fake = _fake_shard("development_a")
        with patch("mahtrain_core.ai_delayed_bugang_scaleup.cohort",
                   return_value=fake["result"]) as cohort:
            result=run_shard("development_a")
        cohort.assert_called_once_with(66000, 4)
        self.assertEqual(result["protocol"], PROTOCOL)
        self.assertEqual(result["official_ruleset"], "current_m423")


if __name__=="__main__":
    unittest.main()
