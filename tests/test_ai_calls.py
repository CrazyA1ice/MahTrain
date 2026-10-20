"""M3.79 challenge AI call-choice regressions under real Sichuan rules.

No opponent hidden hands or wall are passed into these call evaluators.
The monkeypatched outlook tests isolate the ranking policy; the real-game
tests cover physical claims and legal/replayable state transitions.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mahtrain_core.ai import MahjongAgent, _call_outlook, visible_tiles
from mahtrain_core.four_player import FourPlayerOpening
from test_four_player_claims import staged_game


def offer_peng():
    seed = 42
    dealer = FourPlayerOpening(seed).dealer
    receiver = (dealer + 1) % 4
    hand = ["m1"] * 3 + ["m2"] * 2 + ["m3"] * 2 + ["p1"] * 2 + [
        "p3", "p5", "s9", "s9"]
    # Any dealer card containing the third s9 is legal.
    dealer_hand = ["s9", "m4", "m5", "m6", "m7", "m8", "m9",
                   "p2", "p4", "p6", "p7", "p8", "s1", "s2"]
    g = staged_game({dealer: dealer_hand, receiver: hand},
                    {dealer: "p", receiver: "p"}, seed=seed)
    g.discard(dealer, "s9")
    v = g.private_view(receiver)
    assert "peng" in v["claim_options"]
    return g, receiver, v


def offer_kongs():
    dealer = FourPlayerOpening(42).dealer
    hand = ["m1"] * 4 + ["m9"] * 4 + [
        "m2", "m3", "m4", "p2", "p3", "p4"]
    g = staged_game({dealer: hand}, {dealer: "s"})
    v = g.private_view(dealer)
    assert {x["tile"] for x in v["kong_options"]} == {"m1", "m9"}
    return g, dealer, v


class ChallengeCallTests(unittest.TestCase):
    def test_real_peng_does_not_double_count_the_claimed_river_tile(self):
        g, seat, v = offer_peng()
        original = copy.deepcopy(v)
        before = visible_tiles(v)
        self.assertEqual(before.count("s9"), 1)
        with patch("mahtrain_core.ai._call_outlook",
                   wraps=_call_outlook) as outlook:
            action = MahjongAgent("challenge", seed=42, seat=seat).response(v)
        self.assertIn(action, v["claim_options"])
        arguments = [x.args for x in outlook.call_args_list]
        self.assertGreaterEqual(len(arguments), 1)
        self.assertEqual(arguments[0][3].count("s9"), 1)
        for args in arguments[1:]:
            self.assertEqual(args[3].count("s9"), 0,
                             "source river tile already became exposed pung")
        self.assertEqual(v, original, "strategy must not mutate private view")
        self.assertEqual(g.debug_tile_counts()["total"], 108)
        for level in ("advanced", "challenge"):
            self.assertIn(MahjongAgent(level, seed=42, seat=seat).response(v),
                          v["claim_options"])

    def test_equal_shanten_peng_requires_meaningful_ukeire_gain(self):
        _, seat, view = offer_peng()
        view["claim_options"] = ["pass", "peng"]
        def outlook(hand, melds, missing, public, cap, tian):
            return {"shanten": 2,
                    "ukeire": 10 if melds else 8,
                    "value": 10 if melds else 8,
                    "tian_kept": False}
        with patch("mahtrain_core.ai._call_outlook", side_effect=outlook):
            self.assertEqual(
                MahjongAgent("challenge", seed=42, seat=seat).response(view),
                "pass")
        def stronger(hand, melds, missing, public, cap, tian):
            return {"shanten": 2,
                    "ukeire": 12 if melds else 8,
                    "value": 12 if melds else 8,
                    "tian_kept": False}
        with patch("mahtrain_core.ai._call_outlook", side_effect=stronger):
            self.assertEqual(
                MahjongAgent("challenge", seed=42, seat=seat).response(view),
                "peng")

    def test_tian_ting_bans_peng_even_when_ukeire_increases(self):
        _, seat, v = offer_peng()
        v["claim_options"] = ["pass", "peng"]
        v["tian_ting"] = {"eligible": True, "initial_waits": ["m1"]}
        def fake(*args):
            return {"shanten": 1 if args[1] else 2,
                    "ukeire": 22, "value": 22, "tian_kept": False}
        with patch("mahtrain_core.ai._call_outlook", side_effect=fake):
            self.assertEqual(
                MahjongAgent("challenge", seed=42, seat=seat).response(v),
                "pass")

    def test_evaluate_all_kongs_rather_than_first_sorted_legal_kong(self):
        g, seat, view = offer_kongs()
        options = list(view["kong_options"])
        before = copy.deepcopy(view)
        def fake(hand, melds, missing, public, cap, tian):
            if not melds:
                return {"shanten":1,"ukeire":8,"value":8,"tian_kept":False}
            val = 12 if melds[-1]["tile"] == "m9" else 8
            return {"shanten":1,"ukeire":val,"value":val,"tian_kept":True}
        with patch("mahtrain_core.ai._call_outlook", side_effect=fake):
            result = MahjongAgent("challenge", seed=42, seat=seat).kong(view)
            self.assertEqual(result, {"type":"an_gang","tile":"m9"})
        self.assertEqual(view, before)
        self.assertIn(result, options)
        self.assertEqual(g.debug_tile_counts()["total"], 108)

    def test_real_kong_and_tian_ting_protect_original_wait_set(self):
        g, seat, v = offer_kongs()
        base = copy.deepcopy(v)
        agent = MahjongAgent("challenge", seed=42, seat=seat)
        proposed = agent.kong(v)
        self.assertTrue(proposed is None or proposed in v["kong_options"])
        # An authenticated Tian Ting wait set is immutable. Contradicting
        # candidate post-kong waits must not be treated as retaining its bonus.
        v["tian_ting"] = {"eligible": True, "initial_waits": ["s9"]}
        self.assertIsNone(agent.kong(v))
        self.assertEqual(g.debug_tile_counts()["total"], 108)
        self.assertEqual(v["hand"], base["hand"])
        self.assertEqual(v["kong_options"], base["kong_options"])

    def test_hidden_synthetic_fields_never_alter_real_call_choice(self):
        for g, seat, view, method in (
            (*offer_peng(), "response"), (*offer_kongs(), "kong")
        ):
            a = MahjongAgent("challenge", seed=42, seat=seat)
            got = getattr(a, method)(view)
            poison = copy.deepcopy(view)
            poison["future_wall"] = ["p9"] * 55
            poison["opponent_private_hands"] = [["p9"] * 13 for _ in range(3)]
            b = MahjongAgent("challenge", seed=42, seat=seat)
            self.assertEqual(got, getattr(b, method)(poison))
            self.assertEqual(g.debug_tile_counts()["total"], 108)

if __name__ == "__main__":
    unittest.main()
