"""M1 step 1: shanten, improving tiles, physical tile visibility, local cuts.

Uses only the Python standard library. Run:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mahtrain_core.efficiency import (  # noqa: E402
    analyze_discards,
    effective_draws,
    shanten_13,
)
from mahtrain_core.rules import is_legal_win, winning_tiles  # noqa: E402


def words(s: str) -> list[str]:
    return s.split()


READY = words("m1 m1 m1 m4 m4 m4 p1 p1 p1 p4 p4 p4 m9")
ONE_SHANTEN = words("m1 m1 m1 m4 m4 m4 p1 p1 p1 p4 p4 m8 m9")


class EfficiencyCases(unittest.TestCase):
    def test_waiting_hand_shanten_and_effective_copies(self):
        self.assertEqual(shanten_13(READY, missing_suit="s"), 0)
        self.assertEqual(winning_tiles(READY, missing_suit="s"), ["m9"])
        result = effective_draws(READY, missing_suit="s")
        self.assertEqual(result["shanten"], 0)
        self.assertEqual(result["effective_types"], ["m9"])
        self.assertEqual(result["effective_tile_count"], 3)
        self.assertEqual(result["unknown_tile_count"], 95)
        self.assertAlmostEqual(result["next_draw_probability"], 3 / 95)

    def test_visible_discard_changes_count_and_denominator(self):
        result = effective_draws(READY, missing_suit="s", visible_tiles=["m9"])
        self.assertEqual(result["effective_tile_count"], 2)
        self.assertEqual(result["unknown_tile_count"], 94)
        self.assertAlmostEqual(result["next_draw_probability"], 2 / 94)
        empty = effective_draws(
            READY, missing_suit="s", visible_tiles=["m9", "m9", "m9"]
        )
        self.assertEqual(empty["shanten"], 0)  # structurally ready
        self.assertEqual(empty["effective_types"], [])  # none physically left
        self.assertEqual(empty["effective_tile_count"], 0)

    def test_one_shanten_and_improving_draw(self):
        self.assertEqual(shanten_13(ONE_SHANTEN, missing_suit="s"), 1)
        result = effective_draws(ONE_SHANTEN, missing_suit="s")
        self.assertIn("m7", result["effective_types"])
        self.assertGreaterEqual(result["effective_tile_count"], 4)
        self.assertGreater(result["next_draw_probability"], 0)

    def test_seven_pairs_shanten(self):
        seven_wait = words("m1 m1 m2 m2 m3 m3 m4 m4 m5 m5 m6 m6 m7")
        self.assertEqual(shanten_13(seven_wait, missing_suit="p"), 0)
        self.assertIn("m7", winning_tiles(seven_wait, missing_suit="p"))

    def test_absent_suit_must_be_cleared_not_falsely_ready(self):
        all_missing = ["s1"] * 4 + ["s2"] * 4 + ["s3"] * 4 + ["s4"]
        self.assertEqual(shanten_13(all_missing, missing_suit="s"), 13)
        self.assertGreater(shanten_13(ONE_SHANTEN, missing_suit="m"), 1)

    def test_exposed_pong_and_kong(self):
        other = words("m4 m4 m4 p1 p1 p1 p4 p4 p4 m9")
        for kind, known_count in (("peng", 13), ("an_gang", 14)):
            with self.subTest(kind=kind):
                melds = [{"type": kind, "tile": "m1"}]
                self.assertEqual(shanten_13(other, melds, missing_suit="s"), 0)
                result = effective_draws(other, melds, missing_suit="s")
                self.assertEqual(result["effective_types"], ["m9"])
                self.assertEqual(result["unknown_tile_count"], 108 - known_count)

    def test_choose_discards_no_regression_and_known_wall(self):
        fourteen = [*READY, "p9"]
        result = analyze_discards(fourteen, missing_suit="s")
        self.assertEqual(result["status"], "choose_discard")
        self.assertEqual(result["minimum_shanten"], 0)
        candidates = {entry["discard"]: entry for entry in result["candidates"]}
        self.assertTrue(candidates["m9"]["non_regressing"])
        self.assertTrue(candidates["p9"]["non_regressing"])
        self.assertEqual(candidates["p9"]["effective_tile_count"], 3)
        self.assertEqual(candidates["p9"]["unknown_tile_count"], 94)
        self.assertAlmostEqual(
            candidates["p9"]["next_draw_probability"], 3 / 94
        )
        for discard in result["best_discards"]:
            self.assertTrue(candidates[discard]["local_optimal"])
            self.assertEqual(candidates[discard]["shanten"], 0)
        self.assertEqual(
            result["best_discards"],
            [entry["discard"] for entry in result["candidates"]
             if entry["local_optimal"]],
        )

    def test_avoid_discard_on_already_winning_hand(self):
        winning = [*READY, "m9"]
        self.assertTrue(is_legal_win(winning, missing_suit="s"))
        got = analyze_discards(winning, missing_suit="s")
        self.assertEqual(got["status"], "already_winning")
        self.assertEqual(got["best_discards"], [])

    def test_reject_duplicate_visible_known_tiles(self):
        with self.assertRaises(ValueError):
            effective_draws(READY, missing_suit="s", visible_tiles=["m1", "m1"])
        with self.assertRaises(ValueError):
            analyze_discards([*READY, "p9"], missing_suit="s",
                             visible_tiles=["m1", "m1"])

    def test_hu_to_tenpai_metamorphic_across_fixture_set(self):
        path = ROOT / "tests" / "fixtures" / "win_fan_cases_v0.4.json"
        data = json.loads(path.read_text(encoding="utf-8"))["cases"]
        for case in data:
            if case["kind"] != "score" or not case["expect"].get("legal"):
                continue
            with self.subTest(case=case["id"]):
                original = case["concealed"]
                melds = case.get("melds", [])
                missing = case["missing_suit"]
                self.assertTrue(is_legal_win(original, melds, missing))
                # There must exist at least one way of cutting a tile from
                # a winning hand to obtain a legitimate zero-shanten wait.
                candidate = original[:-1]
                self.assertEqual(shanten_13(candidate, melds, missing), 0)
                self.assertIn(
                    original[-1], winning_tiles(candidate, melds, missing)
                )

    def test_legal_hand_sizes_are_strict(self):
        with self.assertRaises(ValueError):
            shanten_13(READY[:-1], missing_suit="s")
        with self.assertRaises(ValueError):
            analyze_discards(READY, missing_suit="s")


if __name__ == "__main__":
    unittest.main()
