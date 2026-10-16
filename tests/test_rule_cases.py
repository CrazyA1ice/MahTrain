"""Run: python -m unittest discover -s tests -v (no third-party deps)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mahtrain_core.rules import (  # noqa: E402
    is_legal_win,
    score_win,
    tian_ting_qualifies,
    winning_tiles,
)


class RuleCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / "tests" / "fixtures" / "win_fan_cases_v0.4.json"
        cls.cases = json.loads(source.read_text(encoding="utf-8"))["cases"]

    def test_fixed_cases(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                kind = case["kind"]
                if kind == "score":
                    got = score_win(
                        case["concealed"],
                        case.get("melds", []),
                        case["missing_suit"],
                        cap=case.get("cap", 3),
                        context=case.get("context"),
                    )
                    for key, expected in case["expect"].items():
                        self.assertEqual(got.get(key), expected, (case["id"], key, got))
                elif kind == "waits":
                    got = winning_tiles(
                        case["concealed"],
                        case.get("melds", []),
                        case["missing_suit"],
                    )
                    self.assertEqual(got, case["expect"])
                elif kind == "tian_ting":
                    got = tian_ting_qualifies(
                        case["starting_13"],
                        case["missing_suit"],
                        case["checkpoints"],
                        is_dealer=case["is_dealer"],
                    )
                    self.assertEqual(got, case["expect"])
                else:
                    self.fail(f"unknown case kind: {kind}")

    def test_case_inventory(self):
        self.assertEqual(len(self.cases), 29)
        self.assertEqual(len({c["id"] for c in self.cases}), 29)

    def test_missing_suit_applies_to_win_and_waits(self):
        ready = [
            "m1", "m1", "m1", "m4", "m4", "m4",
            "p1", "p1", "p1", "p4", "p4", "p4", "m9",
        ]
        self.assertIn("m9", winning_tiles(ready, [], "s"))
        self.assertNotIn("m9", winning_tiles(ready, [], "m"))

    def test_four_copies_guard(self):
        with self.assertRaises(ValueError):
            is_legal_win(["m1"] * 5 + ["m2"] * 9, [], "p")

    def test_tian_ting_not_inferred_from_final_hand(self):
        hand = [
            "m1", "m2", "m3", "m4", "m5", "m6",
            "m7", "m8", "m9", "p2", "p3", "p4", "p5", "p5",
        ]
        self.assertNotIn(
            "tian_ting", score_win(hand, missing_suit="s", cap=6)["combinations"]
        )

    def test_invalid_heaven_earth_event_combo(self):
        hand = [
            "m1", "m2", "m3", "m4", "m5", "m6",
            "m7", "m8", "m9", "p2", "p3", "p4", "p5", "p5",
        ]
        with self.assertRaises(ValueError):
            score_win(
                hand, missing_suit="s",
                context={"heaven_win_verified": True, "earth_win_verified": True},
            )


if __name__ == "__main__":
    unittest.main()
