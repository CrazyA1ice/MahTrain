"""M3.32 decision diagnosis against matched M3.31 official rule-A seed cohorts."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core.ai_independent_scores import (
    controlled_four_policy_scores, independent_lineup, LEVELS)
from mahtrain_core.ai_decision_score_diagnostics import (
    analyze_decision_score_diagnostics)


def case(seed_count=2, first=11):
    games=[]
    for seed in range(first,first+seed_count):
        for rotation in range(4):
            lineup=independent_lineup(rotation)
            payoffs={"baseline":2,"basic":-2,"advanced":4,"challenge":-4}
            if seed>first:
                payoffs={"baseline":-6,"basic":-2,"advanced":2,"challenge":6}
            scores=[payoffs[level] for level in lineup]
            trace=[{
                "action":"discard","level":level,"seat":seat,
                "shanten_regret":0 if level!="baseline" else 1,
                "locally_optimal":level!="baseline",
                "effective_copies":6 if level!="baseline" else 3,
                "private_tile":"NEVER_EXPORT_THIS",
            } for seat,level in enumerate(lineup)]
            games.append({
                "seed":seed,"rotation":rotation,"assignment":lineup,
                "terminal_phase":"finished","official_exhaustive_posted":False,
                "partial_win_balances":scores,
                "official_settled_balances":list(scores),
                "scoring_rules":{"room_coefficient":100,
                                 "fan_cap":3,"kong_base":None},
                "winners":[{
                    "seat":lineup.index("advanced"),"source":lineup.index("baseline"),
                    "kind":"ron","secret":"NO_PUBLIC_HAND",
                }],
                "trace":trace,
            })
    return games


class DecisionOfficialCohortTests(unittest.TestCase):
    def test_matched_cohort_quality_against_real_official_score_keys(self):
        games=case()
        official=controlled_four_policy_scores(games)
        report=analyze_decision_score_diagnostics(games,official)
        self.assertEqual(report["valid_seeds"],2)
        self.assertEqual(report["excluded_seed_count"],0)
        self.assertEqual(report["complete_games"],8)
        self.assertEqual(set(report["levels"]),set(LEVELS))
        base=report["levels"]["baseline"]
        hard=report["levels"]["challenge"]
        self.assertEqual(base["seat_exposures"],8)
        self.assertEqual(base["discards"],8)
        self.assertEqual(hard["discards"],8)
        self.assertEqual(base["min_shanten_fraction"],0)
        self.assertEqual(hard["min_shanten_fraction"],1)
        self.assertEqual(base["mean_effective_copies"],3)
        self.assertEqual(hard["mean_effective_copies"],6)
        self.assertEqual(base["local_optimal_fraction"],0)
        self.assertEqual(hard["local_optimal_fraction"],1)
        self.assertEqual(base["deal_in_events"],8)
        self.assertEqual(base["deal_in_events_per_100_discards"],100)
        self.assertEqual(hard["deal_in_events"],0)
        discordance=report["direction_disagreements_vs_baseline"]["challenge"]
        self.assertEqual(discordance["comparable_seeds"],2)
        self.assertEqual(discordance["higher_min_shanten_but_lower_score_seeds"],1)
        self.assertEqual(discordance["lower_min_shanten_but_higher_score_seeds"],0)
        for term in ("NEVER_EXPORT_THIS","NO_PUBLIC_HAND","private_tile","trace"):
            self.assertNotIn(term,json.dumps(report))
        self.assertEqual(report,analyze_decision_score_diagnostics(
            list(reversed(games)),official))

    def test_unresolved_wall_excludes_same_four_games_as_official(self):
        games=case()
        games[1]["terminal_phase"]="wall_exhausted"
        official=controlled_four_policy_scores(games)
        report=analyze_decision_score_diagnostics(games,official)
        self.assertEqual(official["excluded_seed_ids"],[11])
        self.assertEqual(report["valid_seeds"],1)
        self.assertEqual(report["excluded_seed_count"],1)
        self.assertEqual(report["complete_games"],4)
        self.assertEqual(report["levels"]["baseline"]["seat_exposures"],4)
        self.assertEqual(report["levels"]["challenge"]["discards"],4)

    def test_no_valid_seeds_never_reports_fabricated_zero_rates(self):
        games=case(1)
        games[0]["terminal_phase"]="wall_exhausted"
        official=controlled_four_policy_scores(games)
        report=analyze_decision_score_diagnostics(games,official)
        self.assertEqual(report["valid_seeds"],0)
        self.assertEqual(report["levels"]["challenge"]["discards"],0)
        for field in ("mean_effective_copies","min_shanten_fraction",
                      "local_optimal_fraction","deal_in_events_per_100_discards"):
            self.assertIsNone(report["levels"]["challenge"][field])
        self.assertEqual(
            report["direction_disagreements_vs_baseline"]["challenge"]["comparable_seeds"],0)

    def test_rejects_unreliable_or_inconsistent_privately_measured_counts(self):
        games=case(1)
        official=controlled_four_policy_scores(games)
        cases=[]
        a=copy.deepcopy(games)
        a[0]["trace"][0]["effective_copies"]=False
        cases.append(a)
        a=copy.deepcopy(games)
        a[0]["trace"][0]["shanten_regret"]=-1
        cases.append(a)
        a=copy.deepcopy(games)
        a[0]["trace"][0]["locally_optimal"]=2
        cases.append(a)
        a=copy.deepcopy(games)
        a[0]["trace"][0]["level"]="challenge"
        cases.append(a)
        a=copy.deepcopy(games)
        a[0]["trace"][0]["seat"]=4
        cases.append(a)
        a=copy.deepcopy(games)
        a[0]["winners"][0]["source"]=True
        cases.append(a)
        a=copy.deepcopy(games)
        a[0]["official_settled_balances"][0]+=100
        cases.append(a)
        a=copy.deepcopy(games)
        a.pop()
        cases.append(a)
        a=copy.deepcopy(games)
        a[0]["seed"]=17
        cases.append(a)
        a=copy.deepcopy(games)
        a[0]["trace"]=None
        cases.append(a)
        for i,corruption in enumerate(cases):
            with self.subTest(i=i), self.assertRaises(ValueError):
                analyze_decision_score_diagnostics(corruption,official)
        with self.assertRaises(ValueError):
            analyze_decision_score_diagnostics(games,{"protocol":"wrong"})

    def test_no_discard_sample_means_missing_not_perfect_rates(self):
        games=case(1)
        for game in games:game["trace"]=[]
        official=controlled_four_policy_scores(games)
        report=analyze_decision_score_diagnostics(games,official)
        self.assertEqual(report["levels"]["challenge"]["discards"],0)
        self.assertIsNone(report["levels"]["challenge"]["mean_shanten_regret"])
        self.assertIsNone(report["levels"]["baseline"]["min_shanten_fraction"])
        self.assertEqual(report["levels"]["advanced"]["win_events"],4)
        self.assertEqual(report["levels"]["challenge"]["win_events"],0)


if __name__=="__main__":
    unittest.main()
