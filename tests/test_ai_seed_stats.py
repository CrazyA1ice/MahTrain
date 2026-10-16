"""M3.8 cluster-aware paired AI statistics, without long simulated games."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.ai_seed_stats import (
    MIN_INTERVAL_SEEDS, analyze_seed_clusters,
)
from mahtrain_core.ai_tournament import seat_assignment


def sample_matches(seeds: int = 5) -> list[dict]:
    games=[]
    for seed in range(20,20+seeds):
        for rotation in range(3):
            assignment=seat_assignment(rotation)
            challenge=assignment.index("challenge")
            basic=assignment.index("basic")
            winners=([{"seat":challenge,"source":basic,"kind":"ron"}]
                     if seed%2==0 else [])
            events=[]
            for seat,level in enumerate(assignment):
                for n in range(2):
                    quality=(level!="basic" or (seed+n)%2==0)
                    events.append({
                        "action":"discard","seat":seat,"level":level,
                        "shanten_regret":0 if quality else 1,
                        "locally_optimal":quality,
                    })
            games.append({
                "seed":seed,"rotation":rotation,
                "assignment":assignment,
                "winners":winners,"trace":events,
            })
    return games


class SeedClusterStatisticsTests(unittest.TestCase):
    def test_clustered_samples_are_unique_seeds_not_rotations(self):
        report=analyze_seed_clusters(sample_matches(2))
        self.assertEqual(report["distinct_seed_count"],2)
        self.assertEqual(report["rotations_per_seed"],3)
        self.assertEqual(len(report["per_seed"]),2)
        self.assertIsNone(report["intervals"])
        self.assertIn("insufficient_distinct_seeds",report["interval_status"])
        for group in report["per_seed"]:
            self.assertEqual(group["games"],3)
            for level in ("basic","advanced","challenge"):
                self.assertEqual(group["levels"][level]["seat_exposures"],4)
                self.assertEqual(group["levels"][level]["discards"],8)
        self.assertEqual(
            report["pooled_event_rates"]["min_shanten_fraction"]["challenge"],1)
        self.assertEqual(
            report["pooled_event_rates"]["min_shanten_fraction"]["advanced"],1)
        self.assertEqual(
            report["pooled_event_rates"]["min_shanten_fraction"]["basic"],0.5)
        self.assertEqual(
            report["paired_challenge_differences"]["min_shanten_fraction"][
                "challenge_minus_basic"],0.5)
        self.assertEqual(
            report["paired_challenge_differences"]["min_shanten_fraction"][
                "challenge_minus_advanced"],0)

    def test_bootstrap_resamples_whole_seeds_and_is_reproducible(self):
        sample=sample_matches(MIN_INTERVAL_SEEDS)
        a=analyze_seed_clusters(sample,bootstrap_replicates=200)
        b=analyze_seed_clusters(sample,bootstrap_replicates=200)
        self.assertEqual(a,b)
        self.assertEqual(a["interval_status"],"exploratory_only")
        self.assertEqual(a["intervals"]["replications"],200)
        self.assertEqual(a["intervals"]["method"],
                         "paired_shuffle_seed_cluster_bootstrap_exploratory")
        self.assertEqual(
            a["intervals"]["level_intervals"]["min_shanten_fraction"][
                "challenge"],[1.0,1.0])
        self.assertEqual(
            a["intervals"]["paired_difference_intervals"][
                "min_shanten_fraction"]["challenge_minus_basic"],[0.5,0.5])
        self.assertEqual(
            a["pooled_event_rates"]["win_event_fraction"]["basic"],0)
        self.assertGreater(
            a["pooled_event_rates"]["win_event_fraction"]["challenge"],0)
        self.assertIn("NOT complete-settlement",
                      json.dumps(a,ensure_ascii=False))

    def test_seed_order_has_no_influence_on_paired_results(self):
        events=sample_matches()
        report=analyze_seed_clusters(events)
        self.assertEqual(
            analyze_seed_clusters(list(reversed(events))),report)

    def test_reject_duplicate_rotation_or_unbalanced_seats(self):
        games=sample_matches(1)
        duplicated=copy.deepcopy(games)
        duplicated[-1]["rotation"]=1
        with self.assertRaisesRegex(ValueError,"exactly three"):
            analyze_seed_clusters(duplicated)
        fake=copy.deepcopy(games)
        fake[0]["assignment"]=["basic"]*4
        with self.assertRaisesRegex(ValueError,"balanced"):
            analyze_seed_clusters(fake)
        with self.assertRaises(ValueError):
            analyze_seed_clusters([])
        for count in (0,99,2001,True,1.5):
            with self.subTest(count=count),self.assertRaises(ValueError):
                analyze_seed_clusters(games,bootstrap_replicates=count)

    def test_missing_discards_are_undefined_not_zero_success(self):
        games=sample_matches(1)
        for game in games:
            game["trace"]=[]
        result=analyze_seed_clusters(games)
        self.assertIsNone(result["pooled_event_rates"]["local_optimal_fraction"]["basic"])
        self.assertIsNone(result["paired_challenge_differences"][
            "local_optimal_fraction"]["challenge_minus_basic"])
        self.assertIsNone(result["intervals"])


if __name__=="__main__":
    unittest.main()
