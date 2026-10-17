"""M3.30 paired initial-shuffle official-score experiment; fast synthetic tests."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core.ai_controlled_scores import controlled_official_scores
from mahtrain_core.ai_tournament import seat_assignment


def sample(seed_count=5, seed_start=11):
    scores={"basic":-2,"advanced":0,"challenge":2}
    records=[]
    for seed in range(seed_start,seed_start+seed_count):
        for rotation in range(3):
            lineup=seat_assignment(rotation)
            values=[scores[level] for level in lineup]
            # Integer, zero-sum, seat-dependent payoffs without pretending to
            # run real matches in fast protocol tests.
            scale=seed-seed_start+1
            balances=[(4*v-sum(values))*scale for v in values]
            records.append({
                "seed":seed, "rotation":rotation,
                "assignment":lineup, "terminal_phase":"finished",
                "partial_win_balances":list(balances),
                "official_settled_balances":list(balances),
                "official_exhaustive_posted":False,
                "scoring_rules":{"room_coefficient":100,
                                 "fan_cap":3,"kong_base":None},
            })
    return records


class ControlledOfficialAITests(unittest.TestCase):
    def test_complete_clusters_and_exact_seat_exposure(self):
        games=sample(2)
        report=controlled_official_scores(games)
        self.assertEqual(report["protocol"],
                         "paired_initial_shuffle_3_rotation_official_a_v1")
        self.assertEqual(report["requested_seeds"],2)
        self.assertEqual(report["valid_seeds"],2)
        self.assertEqual(report["complete_games"],6)
        self.assertEqual(report["excluded_seed_count"],0)
        self.assertEqual(report["room_coefficient"],100)
        self.assertEqual(report["fan_cap"],3)
        self.assertTrue(report["zero_sum"])
        self.assertFalse(report["kong_included"])
        self.assertIsNone(report["intervals"])
        self.assertEqual(report["levels"]["basic"]["seat_exposures"],8)
        self.assertEqual(report["levels"]["basic"]["official_total"],-90)
        self.assertEqual(report["levels"]["advanced"]["official_total"],0)
        self.assertEqual(report["levels"]["challenge"]["official_total"],90)
        self.assertEqual(report["paired_differences"]["challenge_minus_basic"],22.5)
        self.assertEqual(report["paired_differences"]["challenge_minus_advanced"],11.25)
        self.assertEqual([item["levels"]["challenge"]["official_total"]
                          for item in report["per_seed"]],[30,60])
        self.assertNotIn("opponent_hands",json.dumps(report))
        self.assertNotIn("future_wall",json.dumps(report))
        self.assertNotIn("hidden_tiles",json.dumps(report))
        self.assertEqual(controlled_official_scores(list(reversed(games))),report)

    def test_unresolved_wall_excludes_entire_seed_not_one_rotation(self):
        records=sample(2)
        uncertain=records[0]
        uncertain["terminal_phase"]="wall_exhausted"
        uncertain["official_exhaustive_posted"]=False
        result=controlled_official_scores(records)
        self.assertEqual(result["requested_seeds"],2)
        self.assertEqual(result["valid_seeds"],1)
        self.assertEqual(result["excluded_seed_ids"],[11])
        self.assertEqual(result["complete_games"],3)
        self.assertEqual(result["levels"]["challenge"]["official_total"],60)
        self.assertEqual(result["levels"]["basic"]["seat_exposures"],4)

    def test_nonwall_and_unresolved_ledger_not_falsified(self):
        records=sample(2)
        records[0]["official_settled_balances"]=[-1,1,0,0]
        with self.assertRaises(ValueError):
            controlled_official_scores(records)
        records=sample(2)
        records[0]["terminal_phase"]="wall_exhausted"
        records[0]["official_exhaustive_posted"]=False
        records[0]["official_settled_balances"]=[-1,1,0,0]
        with self.assertRaises(ValueError):
            controlled_official_scores(records)

    def test_deterministic_cluster_bootstrap_only_after_five_seeds(self):
        records=sample(5)
        report=controlled_official_scores(records,bootstrap_replicates=120)
        self.assertEqual(report["valid_seeds"],5)
        self.assertEqual(report["interval_status"],"exploratory_only")
        self.assertEqual(report["intervals"]["replications"],120)
        self.assertEqual(len(report["intervals"]["levels"]["challenge"]),2)
        self.assertEqual(
            report["intervals"]["differences"]["challenge_minus_basic"],
            controlled_official_scores(
                records,bootstrap_replicates=120)["intervals"]["differences"][
                    "challenge_minus_basic"]
        )
        self.assertEqual(sum(v["official_total"]
                             for v in report["levels"].values()),0)
        for num in (99,2001,True,3.0):
            with self.subTest(num=num), self.assertRaises(ValueError):
                controlled_official_scores(records,bootstrap_replicates=num)

    def test_rejects_improper_rotation_rules_corruption_and_seed_gaps(self):
        original=sample(2)
        scenarios=[]
        missing=copy.deepcopy(original)
        missing.pop()
        scenarios.append(missing)
        duplicate=copy.deepcopy(original)
        duplicate.append(copy.deepcopy(duplicate[0]))
        scenarios.append(duplicate)
        wronglineup=copy.deepcopy(original)
        wronglineup[0]["assignment"][1]="basic"
        scenarios.append(wronglineup)
        nonszero=copy.deepcopy(original)
        nonszero[0]["official_settled_balances"][0]+=2
        scenarios.append(nonszero)
        mixed=copy.deepcopy(original)
        mixed[1]["scoring_rules"]["fan_cap"]=4
        scenarios.append(mixed)
        paidkong=copy.deepcopy(original)
        paidkong[1]["scoring_rules"]["kong_base"]=100
        scenarios.append(paidkong)
        badseed=copy.deepcopy(original)
        badseed[3]["seed"]=True
        scenarios.append(badseed)
        gap=sample(1,11)+sample(1,13)
        scenarios.append(gap)
        dishonest=copy.deepcopy(original)
        dishonest[0]["official_exhaustive_posted"]=True
        scenarios.append(dishonest)
        for index,scenario in enumerate(scenarios):
            with self.subTest(index=index),self.assertRaises(ValueError):
                controlled_official_scores(scenario)


if __name__ == "__main__":
    unittest.main()
