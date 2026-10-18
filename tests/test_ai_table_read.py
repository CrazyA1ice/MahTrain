"""M3.53 read-only opponent danger: dingque, river, melds, phase, privacy."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core.ai import challenge_discard_scores
from mahtrain_core.ai_table_read import (
    read_discard_threat, discard_survival_factor,
)


def board():
    return {
        "seat": 0, "phase": "dealer_discard",
        "hand": ["m1","m2","m3","m4","m5","m6","m7","m8","m9",
                 "s1","s2","s3","s4","s5"],
        "own_melds": [],
        "missing_suits": ["p", "m", "m", "s"],
        "melds": [[], [], [], []], "won": [False] * 4,
        "discards": [], "wall_count": 52,
    }


class PublicTableReaderTests(unittest.TestCase):
    def test_dingque_and_won_exclude_claimants(self):
        view = board()
        m = read_discard_threat("m4", view)
        s = read_discard_threat("s4", view)
        self.assertEqual(m["dingque_safe_seats"], 2)
        self.assertEqual(m["active_threats"], 1)
        self.assertEqual(s["active_threats"], 2)
        self.assertGreater(s["risk_index"], m["risk_index"])
        view["won"][3] = True
        self.assertEqual(read_discard_threat("m4", view)["risk_index"], 0)
        view["missing_suits"][3] = "m"
        self.assertEqual(discard_survival_factor("m4", view), 1.0)

    def test_real_history_shift_and_no_japanese_furiten(self):
        view = board()
        early = read_discard_threat("s4", view)["risk_index"]
        view["wall_count"] = 20
        late = read_discard_threat("s4", view)
        self.assertGreater(late["risk_index"], early)
        self.assertEqual(late["stage"], "late")
        view["wall_count"] = 8
        self.assertGreater(read_discard_threat("s4", view)["risk_index"],
                           late["risk_index"])
        view["discards"] = [{"seat": 1, "tile": "s4", "discard_kind": "tedashi"},
                            {"seat": 1, "tile": "p2", "discard_kind": "tsumogiri"}]
        previously_discarded = read_discard_threat("s4", view)
        self.assertGreater(previously_discarded["risk_index"], 0,
                           "own earlier discard is NOT furiten in Sichuan rules")
        self.assertLess(previously_discarded["risk_index"],
                        read_discard_threat("s3", view)["risk_index"])

    def test_open_pung_pressure_and_concealed_kong_privacy(self):
        view = board()
        view["missing_suits"][1] = "p"
        base = read_discard_threat("m5", view)["risk_index"]
        view["melds"][1] = [
            {"type": "peng", "tile": "m2"},
            {"type": "peng", "tile": "m8"},
        ]
        with_melds = read_discard_threat("m5", view)["risk_index"]
        self.assertGreater(with_melds, base)
        view["melds"][1] = [{"type": "an_gang", "tile": None}]
        with_hidden_kong = read_discard_threat("m5", view)["risk_index"]
        self.assertGreater(with_hidden_kong, base)
        self.assertLess(with_hidden_kong, with_melds)

    def test_no_hidden_peek_even_when_metadata_is_injected(self):
        view = board()
        old = read_discard_threat("s4", view)
        injected = copy.deepcopy(view)
        injected["future_wall"] = ["s4"] * 108
        injected["opponent_hands"] = [["s4"] * 13] * 3
        injected["private_draw"] = "s4"
        self.assertEqual(read_discard_threat("s4", injected), old)
        self.assertEqual(discard_survival_factor("s4", injected),
                         discard_survival_factor("s4", view))
        with self.assertRaises(ValueError):
            read_discard_threat("flower", view)
        with self.assertRaises(ValueError):
            discard_survival_factor("s4", view, -1)

    def test_equal_expected_reward_prefers_dingque_safer_cut(self):
        view = board()
        fake = {
            "shanten": 0, "effective_tile_count": 6,
            "effective_types": ["p1"],
            "effective_details": [{"tile": "p1", "remaining": 6}],
        }
        with patch("mahtrain_core.ai.effective_draws", return_value=fake), \
             patch("mahtrain_core.ai.score_win", return_value={"multiplier": 2}):
            ranked = challenge_discard_scores(view, cuts=["m4", "s4"])
            no_defense = challenge_discard_scores(
                view, cuts=["m4", "s4"], use_pressure=False)
        self.assertEqual(ranked[0]["discard"], "m4")
        self.assertGreater(ranked[0]["score"], ranked[1]["score"])
        self.assertTrue(all(x["expected_fan_weighted_copies"] == 12 for x in ranked))
        self.assertEqual([x["score"] for x in no_defense], [12, 12])
        self.assertGreater(ranked[0]["dingque_safe_seats"],
                           ranked[1]["dingque_safe_seats"])


if __name__ == "__main__":
    unittest.main()
