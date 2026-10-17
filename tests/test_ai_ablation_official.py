"""M3.33 official A-only settlement in five-policy incomplete blocks."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_ablation_official import (
    POLICIES, analyze_official_ablation, CONTRASTS, _lineup)


def fake(seeds=5,start=11):
    weight={"baseline":-8,"advanced":-4,"challenge_no_ukeire":0,
            "challenge_no_pressure":4,"challenge":8}
    games=[]
    for seed in range(start,start+seeds):
        for rotation in range(5):
            lineup=_lineup(rotation)
            missing=next(level for level in POLICIES if level not in lineup)
            scale=seed-start+1
            balances=[(weight[level] + weight[missing]//4)*scale for level in lineup]
            assert sum(balances)==0
            games.append({
                "seed":seed,"rotation":rotation,"assignment":lineup,
                "terminal_phase":"finished",
                "partial_win_balances":balances,
                "official_settled_balances":list(balances),
                "official_exhaustive_posted":False,
                "scoring_rules":{"room_coefficient":100,"fan_cap":3,
                                 "kong_base":None},
                "winners":[{"seat":0,"source":1,"kind":"ron"}],
                "trace":[{
                    "seat":seat,"level":level,"action":"discard",
                    "shanten_regret":1 if level=="baseline" else 0,
                    "locally_optimal":level!="baseline",
                    "effective_copies":1 if level=="baseline" else 5,
                    "private_tile":"DO_NOT_EXPORT",
                } for seat,level in enumerate(lineup)],
            })
    return games


class OfficialFivePolicyTests(unittest.TestCase):
    def test_complete_five_rotations_every_policy_every_seat_once(self):
        self.assertEqual(len(POLICIES),5)
        for seat in range(4):
            self.assertEqual(sorted(_lineup(r)[seat] for r in range(5)),
                             sorted(POLICIES))
        result=analyze_official_ablation(fake(2))
        self.assertEqual(result["protocol"],
                         "five_policy_incomplete_block_official_a_v1")
        self.assertEqual(result["requested_seeds"],2)
        self.assertEqual(result["valid_seeds"],2)
        self.assertEqual(result["complete_games"],10)
        self.assertTrue(result["zero_sum"])
        self.assertFalse(result["kong_included"])
        self.assertIsNone(result["intervals"])
        for level in POLICIES:
            self.assertEqual(result["levels"][level]["seat_exposures"],8)
            self.assertEqual(result["levels"][level]["discards"],8)
            self.assertEqual(result["per_seed"][0]["levels"][level]
                             ["seat_exposures"],4)
        self.assertEqual(result["levels"]["baseline"]["official_total"],-90)
        self.assertEqual(result["levels"]["challenge"]["official_total"],90)
        self.assertEqual(result["levels"]["baseline"]["mean_effective_copies"],1)
        self.assertEqual(result["levels"]["challenge"]["mean_effective_copies"],5)
        self.assertEqual(result["levels"]["baseline"]["min_shanten_fraction"],0)
        self.assertEqual(result["levels"]["challenge"]["min_shanten_fraction"],1)
        self.assertEqual(
            result["contrasts"]["challenge_vs_challenge_no_pressure"]
            ["official_mean_delta"],5.625)
        self.assertEqual(result["contrasts"]["challenge_vs_baseline"]
                         ["score_sign_counts"]["positive"],2)
        self.assertEqual(result,analyze_official_ablation(list(reversed(fake(2)))))
        for marker in ("DO_NOT_EXPORT","private_tile","trace","opponent_hands"):
            self.assertNotIn(marker,json.dumps(result))

    def test_one_unverified_wall_excludes_entire_five_game_seed(self):
        games=fake(2)
        games[3]["terminal_phase"]="wall_exhausted"
        result=analyze_official_ablation(games)
        self.assertEqual(result["excluded_seed_ids"],[11])
        self.assertEqual(result["valid_seeds"],1)
        self.assertEqual(result["complete_games"],5)
        self.assertEqual(result["levels"]["challenge"]["seat_exposures"],4)
        self.assertEqual(result["per_seed"][0]["seed"],12)

    def test_no_valid_seeds_has_none_not_fake_performance_rates(self):
        games=fake(1)
        games[0]["terminal_phase"]="wall_exhausted"
        result=analyze_official_ablation(games)
        self.assertEqual(result["valid_seeds"],0)
        self.assertEqual(result["excluded_seed_count"],1)
        self.assertIsNone(result["levels"]["challenge"]["official_mean_per_exposure"])
        self.assertIsNone(result["levels"]["challenge"]["mean_effective_copies"])
        self.assertIsNone(result["contrasts"]["challenge_vs_baseline"]
                          ["official_mean_delta"])
        self.assertIsNone(result["intervals"])

    def test_fixed_cluster_bootstrap_exploratory_after_five_valid_seeds(self):
        games=fake(5)
        a=analyze_official_ablation(games,bootstrap_replicates=100)
        b=analyze_official_ablation(games,bootstrap_replicates=100)
        self.assertEqual(a,b)
        self.assertEqual(a["interval_status"],"exploratory_only")
        self.assertEqual(a["intervals"]["replications"],100)
        self.assertEqual(set(a["intervals"]["official_mean_delta"]),
                         {x+"_vs_"+y for x,y in CONTRASTS})
        self.assertEqual(len(a["intervals"]["official_mean_delta"]
                             ["challenge_vs_challenge_no_ukeire"]),2)
        games[0]["terminal_phase"]="wall_exhausted"
        self.assertIsNone(analyze_official_ablation(games)["intervals"])

    def test_rejects_corruption_mixed_rules_invalid_diagnostics(self):
        original=fake(2)
        cases=[]
        g=copy.deepcopy(original);g.pop();cases.append(g)
        g=copy.deepcopy(original);g.append(copy.deepcopy(g[0]));cases.append(g)
        g=copy.deepcopy(original);g[0]["assignment"][0]="baseline";cases.append(g)
        g=copy.deepcopy(original);g[0]["scoring_rules"]["fan_cap"]=4;cases.append(g)
        g=copy.deepcopy(original);g[0]["scoring_rules"]["kong_base"]=100;cases.append(g)
        g=copy.deepcopy(original);g[0]["official_settled_balances"][0]+=1;cases.append(g)
        g=copy.deepcopy(original);g[0]["official_settled_balances"]=[-1,1,0,0];cases.append(g)
        g=copy.deepcopy(original);g[0]["official_exhaustive_posted"]=True;cases.append(g)
        g=copy.deepcopy(original);g[0]["trace"][0]["effective_copies"]=False;cases.append(g)
        g=copy.deepcopy(original);g[0]["trace"][0]["locally_optimal"]=1;cases.append(g)
        g=copy.deepcopy(original);g[0]["trace"][0]["level"]="wrong";cases.append(g)
        g=copy.deepcopy(original);g[0]["winners"][0]["source"]=True;cases.append(g)
        g=copy.deepcopy(original);g[0]["seed"]=True;cases.append(g)
        cases.append(fake(1,11)+fake(1,13))
        for index,invalid in enumerate(cases):
            with self.subTest(index=index),self.assertRaises(ValueError):
                analyze_official_ablation(invalid)
        for n in (99,2001,True,1.5):
            with self.subTest(n=n),self.assertRaises(ValueError):
                analyze_official_ablation(original,bootstrap_replicates=n)

if __name__=="__main__":
    unittest.main()
