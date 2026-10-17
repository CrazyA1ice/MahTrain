"""M3.31 synthetic protocol tests; no expensive complete AI games."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core.ai_independent_scores import controlled_four_policy_scores
from mahtrain_core.ai_independent_benchmark import independent_lineup, LEVELS


def synthetic(seeds=5, first=11):
    scores={"baseline":-3, "basic":-1, "advanced":1, "challenge":3}
    games=[]
    for seed in range(first, first+seeds):
        for rotation in range(4):
            assignment=independent_lineup(rotation)
            scale=seed-first+1
            balances=[scores[level]*scale for level in assignment]
            games.append({
                "seed":seed,"rotation":rotation,"assignment":assignment,
                "terminal_phase":"finished",
                "official_exhaustive_posted":False,
                "partial_win_balances":list(balances),
                "official_settled_balances":list(balances),
                "scoring_rules":{
                    "room_coefficient":100,"fan_cap":3,"kong_base":None},
            })
    return games


class FourPolicyScoreTests(unittest.TestCase):
    def test_four_rotations_full_balance_and_paired_difference(self):
        report=controlled_four_policy_scores(synthetic(2))
        self.assertEqual(report["protocol"],
                         "paired_initial_shuffle_4_rotation_official_a_v1")
        self.assertEqual(report["requested_seeds"],2)
        self.assertEqual(report["valid_seeds"],2)
        self.assertEqual(report["excluded_seed_count"],0)
        self.assertEqual(report["complete_games"],8)
        self.assertEqual(report["room_coefficient"],100)
        self.assertTrue(report["zero_sum"])
        self.assertFalse(report["kong_included"])
        self.assertIsNone(report["intervals"])
        self.assertEqual(set(report["levels"]),set(LEVELS))
        self.assertEqual([report["levels"][x]["seat_exposures"] for x in LEVELS],
                         [8,8,8,8])
        self.assertEqual([report["levels"][x]["official_total"] for x in LEVELS],
                         [-36,-12,12,36])
        self.assertEqual(report["paired_differences_vs_baseline"],
                         {"basic":3.0,"advanced":6.0,"challenge":9.0})
        self.assertEqual(report["per_seed"][0]["levels"]["baseline"]["official_total"],-12)
        self.assertEqual(report["per_seed"][1]["levels"]["challenge"]["official_total"],24)
        self.assertEqual(report,controlled_four_policy_scores(list(reversed(synthetic(2)))))
        encoded=json.dumps(report,ensure_ascii=False)
        for secret in ("opponent_hands","future_wall","hand_counts","private_view"):
            self.assertNotIn(secret,encoded)

    def test_unverified_exhausted_wall_excludes_all_four_rotations(self):
        games=synthetic(2)
        games[2]["terminal_phase"]="wall_exhausted"
        games[2]["official_exhaustive_posted"]=False
        result=controlled_four_policy_scores(games)
        self.assertEqual(result["requested_seeds"],2)
        self.assertEqual(result["valid_seeds"],1)
        self.assertEqual(result["excluded_seed_ids"],[11])
        self.assertEqual(result["complete_games"],4)
        self.assertEqual(result["levels"]["challenge"]["official_total"],24)
        self.assertEqual(result["levels"]["baseline"]["seat_exposures"],4)

    def test_zero_valid_clusters_are_not_falsely_reported_as_zero_payoffs(self):
        games=synthetic(1)
        games[0]["terminal_phase"]="wall_exhausted"
        outcome=controlled_four_policy_scores(games)
        self.assertEqual(outcome["valid_seeds"],0)
        self.assertEqual(outcome["excluded_seed_ids"],[11])
        self.assertEqual(outcome["levels"]["baseline"]["seat_exposures"],0)
        self.assertIsNone(outcome["levels"]["challenge"]["official_mean_per_exposure"])
        self.assertIsNone(outcome["paired_differences_vs_baseline"]["challenge"])
        self.assertIsNone(outcome["intervals"])

    def test_deterministic_whole_seed_bootstrap_only_for_five_valid_clusters(self):
        five=synthetic(5)
        once=controlled_four_policy_scores(five,bootstrap_replicates=120)
        twice=controlled_four_policy_scores(five,bootstrap_replicates=120)
        self.assertEqual(once,twice)
        self.assertEqual(once["interval_status"],"exploratory_only")
        self.assertEqual(once["intervals"]["replications"],120)
        self.assertEqual(len(once["intervals"]["levels"]["advanced"]),2)
        self.assertEqual(len(once["intervals"]["differences_vs_baseline"]["challenge"]),2)
        fewer=copy.deepcopy(five)
        fewer[1]["terminal_phase"]="wall_exhausted"
        self.assertIsNone(controlled_four_policy_scores(fewer)["intervals"])

    def test_reject_duplicate_missing_rotation_nonzero_scores_and_mixed_rules(self):
        games=synthetic(2)
        scenarios=[]
        a=copy.deepcopy(games)
        a.pop()
        scenarios.append(a)
        a=copy.deepcopy(games)
        a.append(copy.deepcopy(games[0]))
        scenarios.append(a)
        a=copy.deepcopy(games)
        a[0]["assignment"][0]="basic"
        scenarios.append(a)
        a=copy.deepcopy(games)
        a[0]["official_settled_balances"][0]+=1
        scenarios.append(a)
        a=copy.deepcopy(games)
        a[0]["official_exhaustive_posted"]=True
        scenarios.append(a)
        a=copy.deepcopy(games)
        a[0]["official_settled_balances"]=[-1,1,0,0]
        scenarios.append(a)
        a=copy.deepcopy(games)
        a[0]["scoring_rules"]["room_coefficient"]=200
        scenarios.append(a)
        a=copy.deepcopy(games)
        a[0]["scoring_rules"]["kong_base"]=100
        scenarios.append(a)
        a=copy.deepcopy(games)
        a[0]["seed"]=True
        scenarios.append(a)
        scenarios.append(synthetic(1,11)+synthetic(1,13))
        for index,case in enumerate(scenarios):
            with self.subTest(case=index), self.assertRaises(ValueError):
                controlled_four_policy_scores(case)
        for invalid in (99,2001,True,1.1):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                controlled_four_policy_scores(games,bootstrap_replicates=invalid)


if __name__ == "__main__":
    unittest.main()
