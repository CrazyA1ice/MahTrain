"""M3.10 challenge ablation legality, controlled signals and clustered samples."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core.ai import AI_LEVELS, ABLATION_LEVELS, MahjongAgent
from mahtrain_core.ai_ablation import (
    COHORTS, ablation_lineup, ablation_benchmark,
)
from mahtrain_core.ai_tournament import simulate_match


def fake_match(seed, rotation, lineup):
    challenge = lineup.index("challenge")
    return {
        "assignment": list(lineup),
        "winners": [
            {"seat": challenge, "source": (challenge + 1) % 4, "kind": "ron"}
        ],
        "trace": [
            {"action": "discard", "seat": seat,
             "shanten_regret": int(level == "challenge_no_ukeire"),
             "locally_optimal": level != "challenge_no_ukeire"}
            for seat, level in enumerate(lineup)
        ],
    }


class ChallengeAblationTests(unittest.TestCase):
    def test_variants_are_not_normal_difficulty_choices(self):
        self.assertEqual(AI_LEVELS, ("basic", "advanced", "challenge"))
        self.assertEqual(len(ABLATION_LEVELS), 2)
        for variant in ABLATION_LEVELS:
            agent = MahjongAgent(variant, seed=11, seat=0)
            self.assertEqual(agent.level, variant)
            self.assertIn("消融", agent.policy_description())
        with self.assertRaises(ValueError):
            MahjongAgent("challenge_no_shape", seed=1, seat=0)

    def test_removed_signals_are_not_consulted(self):
        hand = ["m1","m1","m2","m3","m4","s1","s2","s3","s4",
                "p1","p2","p3","p4","p5"]
        view = {
            "hand": hand, "own_melds": [], "seat": 0,
            "missing_suits": ["s", "m", "p", "m"],
            "phase": "dealer_discard",
            "discards": [], "melds": [[], [], [], []],
            "won": [False]*4,
        }
        choices = ["s1","s2","s3","s4"]
        with patch("mahtrain_core.ai._cut_shanten", return_value=1):
            with patch("mahtrain_core.ai.analyze_discards",
                       side_effect=AssertionError("ukeire was consulted")):
                with patch("mahtrain_core.ai.public_suit_pressure",
                           side_effect=lambda tile, _: 9-int(tile[1])):
                    self.assertEqual(
                        MahjongAgent("challenge_no_ukeire",seed=1,seat=0)
                        .discard(view), "s4"
                    )
            def fake_oracle(*args, **kwargs):
                return {"candidates": [
                    {"discard": tile, "effective_tile_count": (
                        10 if tile == "s2" else 2)}
                    for tile in choices
                ]}
            with patch("mahtrain_core.ai.analyze_discards",
                       side_effect=fake_oracle):
                with patch("mahtrain_core.ai.public_suit_pressure",
                           side_effect=AssertionError("risk was consulted")):
                    self.assertEqual(
                        MahjongAgent("challenge_no_risk",seed=1,seat=0)
                        .discard(view), "s2"
                    )

    def test_each_cohort_balances_four_seats(self):
        for cohort, names in COHORTS.items():
            self.assertEqual(len(set(names)), 4)
            for seat in range(4):
                self.assertEqual(
                    set(ablation_lineup(cohort, r)[seat] for r in range(4)),
                    set(names)
                )
        for rotation in (-1,4,True,"1"):
            with self.assertRaises(ValueError):
                ablation_lineup("baseline", rotation)
        with self.assertRaises(ValueError):
            ablation_lineup("unknown", 0)

    def test_aggregate_only_pairing_and_bootstrap(self):
        seen = []
        def stub(seed, rotation=0, *, lineup=None):
            seen.append((seed, rotation, tuple(lineup)))
            return fake_match(seed, rotation, lineup)
        with patch("mahtrain_core.ai_ablation.simulate_match",
                   side_effect=stub):
            result = ablation_benchmark(20, 5, bootstrap_replicates=100)
        self.assertEqual(result["games"], 40)
        self.assertEqual(len(seen), 40)
        self.assertEqual(result["independent_shuffle_seeds"], 5)
        self.assertEqual(result["interval_status"], "exploratory_only")
        for cohort, stats in result["cohorts"].items():
            self.assertEqual(len(stats["per_seed"]), 5)
            self.assertNotIn("trace", str(stats))
            self.assertEqual(stats["levels"]["challenge"]["exposures"], 20)
            self.assertEqual(stats["levels"]["challenge"]["wins"], 20)
            self.assertEqual(
                stats["challenge_minus_other"]["challenge_no_ukeire"]
                ["local_optimal_fraction"], 1.0
            )
            self.assertEqual(stats["intervals"]["replications"], 100)
            self.assertEqual(
                stats["intervals"]["challenge_minus_other"]
                ["challenge_no_ukeire"]["local_optimal_fraction"], [1.0, 1.0]
            )

    def test_small_sample_and_inputs(self):
        with patch("mahtrain_core.ai_ablation.simulate_match",
                   side_effect=lambda seed,rotation=0,*,lineup=None:
                   fake_match(seed,rotation,lineup)):
            result = ablation_benchmark(11, 1)
        self.assertEqual(result["games"], 8)
        self.assertTrue(all(v["intervals"] is None
                            for v in result["cohorts"].values()))
        for bad in (0,-1,51,True,1.2):
            with self.assertRaises(ValueError):
                ablation_benchmark(11,bad)
        for bad in (-1,2**32,True,"11"):
            with self.assertRaises(ValueError):
                ablation_benchmark(bad,1)
        with self.assertRaises(ValueError):
            ablation_benchmark(1,1,bootstrap_replicates=99)

    def test_real_game_with_ablation(self):
        match = simulate_match(
            11, 0, lineup=ablation_lineup("advanced",0)
        )
        self.assertEqual(match["physical_count"],108)
        self.assertEqual(sum(match["partial_win_balances"]),0)
        self.assertIn(match["terminal_phase"],("finished","wall_exhausted"))
        for frame in match["public_replay"]:
            self.assertNotIn("opponent_hands", frame)
            self.assertNotIn("future_wall", frame)


if __name__ == "__main__":
    unittest.main()
