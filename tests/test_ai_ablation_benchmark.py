"""M3.10 independent shuffle cluster + paired component ablation tests."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.ai import MahjongAgent, AblationMahjongAgent
from mahtrain_core.ai_ablation_benchmark import (
    LEVELS, ablation_lineup, ablation_benchmark,
)
from mahtrain_core.ai_tournament import simulate_match


def fake_game(seed, rotation, lineup):
    # Every rotation misses exactly one policy. Outcome is deterministic;
    # do not count rotations as independent bootstrap observations.
    wins = []
    if seed % 2 == 0 and "challenge" in lineup:
        seat = lineup.index("challenge")
        wins = [{"seat": seat, "source": (seat+1) % 4,
                 "kind": "ron"}]
    return {
        "seed": seed, "rotation": rotation, "assignment": lineup,
        "terminal_phase": "wall_exhausted", "winners": wins,
        "trace": [
            {"action": "discard", "seat": seat, "level": level,
             "shanten_regret": int(level == "baseline"),
             "effective_copies": 1 if level == "baseline" else 5,
             "locally_optimal": level != "baseline"}
            for seat, level in enumerate(lineup)
        ],
        "public_events": [], "public_replay": [],
        "physical_count": 108, "partial_win_balances": [0]*4,
        "official_settled_balances": [0]*4,
        "official_exhaustive_posted": True,
        "scoring_rules": {"room_coefficient": 100, "fan_cap": 3,
                          "kong_base": None},
        "actions": 50, "wall_remaining": 0,
    }


class ChallengeAblationTests(unittest.TestCase):
    def test_five_rotations_balance_each_seat_and_leave_one_policy_out(self):
        self.assertEqual(len(LEVELS), 5)
        for seat in range(4):
            self.assertEqual(
                sorted(ablation_lineup(r)[seat] for r in range(5)),
                sorted(LEVELS),
            )
        self.assertEqual(
            sorted(set(LEVELS)-set(ablation_lineup(r)) for r in []), [])
        self.assertEqual(
            {next(iter(set(LEVELS)-set(ablation_lineup(r))))
             for r in range(5)}, set(LEVELS))
        for bad in (-1, 5, True, "2"):
            with self.assertRaises(ValueError):
                ablation_lineup(bad)

    def test_controlled_cut_tie_breaks(self):
        hand = ["m"+str(i) for i in range(1,8)] + [
            "s"+str(i) for i in range(1,8)]
        view = {
            "seat": 0, "phase": "dealer_discard", "hand": hand,
            "own_melds": [], "missing_suits": ["p", "m", "s", "p"],
            "discards": [], "melds": [[],[],[],[]],
            "won": [False]*4,
        }
        agents = {
            "advanced": MahjongAgent("advanced", seed=11, seat=0),
            "challenge": MahjongAgent("challenge", seed=11, seat=0),
            "challenge_no_ukeire": AblationMahjongAgent(
                "challenge_no_ukeire", seed=11, seat=0),
            "challenge_no_pressure": AblationMahjongAgent(
                "challenge_no_pressure", seed=11, seat=0),
        }
        with patch("mahtrain_core.ai._cut_shanten", return_value=0):
            # Same effective copies: public pressure changes only full model.
            rows = {"candidates": [
                {"discard": tile,
                 "effective_tile_count": 10 if tile in ("m1","m2") else 1}
                for tile in hand
            ]}
            with patch("mahtrain_core.ai.analyze_discards", return_value=rows):
                with patch("mahtrain_core.ai.public_suit_pressure",
                           side_effect=lambda t, v: (
                               {"m1": 3, "m2": 0}.get(t, 99))):
                    self.assertEqual(agents["advanced"].discard(view), "m1")
                    self.assertEqual(agents["challenge"].discard(view), "m2")
                    self.assertEqual(agents["challenge_no_pressure"].discard(view), "m1")
                    self.assertEqual(agents["challenge_no_ukeire"].discard(view), "m2")
            # A clear effective-copy advantage beats pressure in the full model.
            rows = {"candidates": [
                {"discard": tile,
                 "effective_tile_count": 20 if tile == "m2" else 2}
                for tile in hand
            ]}
            with patch("mahtrain_core.ai.analyze_discards", return_value=rows):
                with patch("mahtrain_core.ai.public_suit_pressure",
                           side_effect=lambda t,v: 0 if t=="m1" else 9):
                    self.assertEqual(agents["challenge"].discard(view), "m2")
                    self.assertEqual(agents["challenge_no_ukeire"].discard(view), "m1")
            # Pressure-only does not run the effective-draw oracle at all.
            with patch("mahtrain_core.ai.analyze_discards",
                       side_effect=AssertionError("must not call oracle")):
                with patch("mahtrain_core.ai.public_suit_pressure",
                           return_value=0):
                    self.assertEqual(
                        agents["challenge_no_ukeire"].discard(view), "m1")
        with self.assertRaises(ValueError):
            AblationMahjongAgent("challenge", seed=11, seat=0)

    def test_whole_seed_bootstrap_is_reproducible_and_compact(self):
        callbacks = []
        with patch("mahtrain_core.ai_ablation_benchmark.simulate_match",
                   side_effect=lambda seed, rotation=0, *, lineup=None:
                   fake_game(seed, rotation, lineup)) as stub:
            report = ablation_benchmark(
                20, 5, bootstrap_replicates=200,
                on_match=lambda done,total: callbacks.append((done,total)))
            self.assertEqual(stub.call_count, 25)
            repeated = ablation_benchmark(20, 5, bootstrap_replicates=200)
        self.assertEqual(callbacks[-1], (25,25))
        self.assertEqual(report, repeated)
        self.assertEqual(report["games"], 25)
        self.assertEqual(report["independent_shuffle_seeds"], 5)
        self.assertEqual(len(report["per_seed"]), 5)
        for policy in LEVELS:
            self.assertEqual(report["levels"][policy]["exposures"], 20)
            self.assertEqual(report["levels"][policy]["discards"], 20)
        self.assertEqual(report["levels"]["baseline"]["local_optimal_fraction"],0)
        self.assertEqual(report["levels"]["challenge"]["local_optimal_fraction"],1)
        self.assertEqual(report["intervals"]["replications"], 200)
        official=report["official_score_analysis"]
        self.assertEqual(official["valid_seeds"],5)
        self.assertEqual(official["excluded_seed_count"],0)
        self.assertEqual(official["complete_games"],25)
        self.assertTrue(official["zero_sum"])
        self.assertEqual(official["levels"]["challenge"]["seat_exposures"],20)
        self.assertEqual(official["levels"]["baseline"]["mean_effective_copies"],1)
        self.assertEqual(official["levels"]["challenge"]["mean_effective_copies"],5)
        self.assertEqual(official["intervals"]["replications"],200)
        self.assertEqual(
            report["intervals"]["paired_differences"][
                "challenge_vs_baseline"]["local_optimal_fraction"], [1.0,1.0])
        self.assertNotIn("trace",report["matches"][0])
        self.assertNotIn("public_replay",report["matches"][0])
        self.assertNotIn("public_events",report["matches"][0])
        json.dumps(report, ensure_ascii=False)

    def test_small_samples_not_given_intervals_and_limits(self):
        with patch("mahtrain_core.ai_ablation_benchmark.simulate_match",
                   side_effect=lambda seed, rotation=0, *, lineup=None:
                   fake_game(seed, rotation, lineup)):
            report = ablation_benchmark(11,1)
        self.assertIsNone(report["intervals"])
        self.assertIsNone(report["official_score_analysis"]["intervals"])
        self.assertEqual(report["games"],5)
        for value in (0,-1,51,True,1.5):
            with self.subTest(seeds=value), self.assertRaises(ValueError):
                ablation_benchmark(11,value)
        for value in (-1,True,"11",2**32):
            with self.subTest(seed=value), self.assertRaises(ValueError):
                ablation_benchmark(value,1)
        for value in (99,True,"200",2001):
            with self.subTest(bootstrap=value), self.assertRaises(ValueError):
                ablation_benchmark(11,1,bootstrap_replicates=value)

    def test_actual_four_agent_game_is_legal_and_public_only(self):
        game = simulate_match(11, rotation=0, lineup=ablation_lineup(0))
        self.assertEqual(game["physical_count"], 108)
        self.assertEqual(sum(game["partial_win_balances"]),0)
        self.assertIn(game["terminal_phase"], ("finished","wall_exhausted"))
        self.assertEqual(len(game["assignment"]),4)
        for frame in game["public_replay"]:
            self.assertNotIn("opponent_hands",frame)
            self.assertNotIn("future_wall",frame)
            self.assertNotIn("effective_copies",frame["action"])
            self.assertNotIn("shanten_after",frame["action"])


if __name__ == "__main__":
    unittest.main()
