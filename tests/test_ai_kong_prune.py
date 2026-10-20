"""M3.83 frozen M3.82 kong policy versus exact-shanten-pruned decisions.

The reference function is a byte-for-byte copy of the M3.82 source, with
only its function name changed. Never compare altered training-seed policies
or leak future wall/opponent private tiles to the candidate policy.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from mahtrain_core.ai import (
    MahjongAgent, _call_outlook, _call_settings, _cut_shanten,
    _own_view, _outlook_better_than_baseline, _challenge_kong,
)
from mahtrain_core.efficiency import shanten_13
from mahtrain_core.rules import TILE_INDEX
from mahtrain_core.ai_tournament import simulate_match
from test_ai_calls import offer_kongs
from test_four_player_claims import staged_game
from mahtrain_core.four_player import FourPlayerOpening


def _legacy_challenge_kong(view: Mapping[str, Any]) -> dict[str, str] | None:
    """Rank all legal own kongs, rather than accepting the first option.

    A 14-effective hand is compared to its best lawful after-discard
    13-effective reference. Kong's mandatory supplement draw is unknown.
    """
    hand, melds, missing = _own_view(view)
    public, cap, tian = _call_settings(view)
    allowed = sorted(set(hand), key=TILE_INDEX.__getitem__)
    forced = [tile for tile in allowed if tile[0] == missing]
    if forced:
        allowed = forced
    # Avoid computing expensive multi-draw effective tiles for cuts that
    # already lose on exact shanten. Kong is rare, but the visual turn should
    # never wait for avoidable full-hand enumeration.
    quick = [(tile, _cut_shanten(hand, melds, missing, tile))
             for tile in allowed]
    least = min(n for _, n in quick)
    baselines = []
    for tile, shanten in quick:
        if shanten != least:
            continue
        after = list(hand)
        after.remove(tile)
        baselines.append(_call_outlook(
            after, melds, missing, [*public, tile], cap, tian,
        ))
    before = max(
        (x for x in baselines if x["shanten"] == least),
        key=lambda x: (x["value"], x["ukeire"]),
    )
    candidates = []
    for choice in view["kong_options"]:
        tile, kind = choice["tile"], choice["type"]
        after = list(hand)
        extra = [dict(group) for group in melds]
        if kind == "an_gang":
            for _ in range(4):
                after.remove(tile)
            extra.append({"type": "an_gang", "tile": tile})
        elif kind == "bu_gang":
            after.remove(tile)
            extra = [
                {"type": "bu_gang" if group["type"] == "peng"
                 and group["tile"] == tile else group["type"],
                 "tile": group["tile"]}
                for group in extra
            ]
        else:
            continue
        outlook = _call_outlook(after, extra, missing, public, cap, tian)
        if tian.get("eligible") and not outlook["tian_kept"]:
            continue
        if not _outlook_better_than_baseline(outlook, before, fraction=0.75):
            continue
        # Prefer a better structural stage, then stronger next-draw shape;
        # when exactly equal prefer concealed kong to avoid rob-kong exposure.
        candidates.append((
            (-outlook["shanten"], outlook["value"], outlook["ukeire"],
             int(kind == "an_gang"), -TILE_INDEX[tile]),
            dict(choice),
        ))
    return max(candidates, key=lambda entry: entry[0])[1] if candidates else None



def offer_seven_pairs_disrupting_kong():
    """Server-real hand: best cut is tenpai seven-pairs, kong destroys it."""
    dealer = FourPlayerOpening(42).dealer
    hand = (["m1"] * 4 + ["m3"] * 2 + ["m5"] * 2
            + ["m7"] * 2 + ["p1"] * 2 + ["p3", "p9"])
    game = staged_game({dealer: hand}, {dealer: "s"})
    view = game.private_view(dealer)
    assert view["kong_options"] == [{"type": "an_gang", "tile": "m1"}]
    assert game.debug_tile_counts()["total"] == 108
    return game, dealer, view


class KongPruningTests(unittest.TestCase):
    def test_actual_seven_pairs_waits_block_losing_kong_without_scoring(self):
        game, seat, view = offer_seven_pairs_disrupting_kong()
        original = copy.deepcopy(view)
        hand, melds, missing = _own_view(view)
        before = min(_cut_shanten(hand, melds, missing, t) for t in set(hand))
        after = list(hand)
        for _ in range(4):
            after.remove("m1")
        kong_melds = [*melds, {"type": "an_gang", "tile": "m1"}]
        stage = shanten_13(after, kong_melds, missing)
        self.assertLess(before, stage, "fixture must really lose shanten")
        self.assertIsNone(_legacy_challenge_kong(view))
        with patch("mahtrain_core.ai._call_outlook",
                   side_effect=AssertionError("no costly eval for lost shanten")):
            self.assertIsNone(_challenge_kong(view))
        self.assertEqual(view, original)
        self.assertEqual(game.debug_tile_counts()["total"], 108)


    def test_real_multiple_kongs_identical_to_preoptimization(self):
        game, seat, view = offer_kongs()
        original = copy.deepcopy(view)
        self.assertEqual(len(view["kong_options"]), 2)
        before = _legacy_challenge_kong(view)
        after = _challenge_kong(view)
        self.assertEqual(before, after)
        self.assertTrue(after is None or after in view["kong_options"])
        self.assertEqual(view, original)
        self.assertEqual(game.debug_tile_counts()["total"], 108)

    def test_worse_than_best_cut_rejects_without_any_expensive_outlook(self):
        _, _, view = offer_kongs()
        # Isolate the logically decisive inequality shanten(kong)>shanten(cut).
        with patch("mahtrain_core.ai._cut_shanten", return_value=0), \
             patch("mahtrain_core.ai.shanten_13", return_value=1), \
             patch("mahtrain_core.ai._call_outlook",
                   side_effect=AssertionError("losing kong cannot win")):
            self.assertIsNone(_challenge_kong(view))

    def test_strictly_better_kongs_skip_reference_but_rank_all_candidates(self):
        _, _, view = offer_kongs()
        got = []
        def scored(hand, melds, missing, public, cap, tian):
            got.append(tuple(group["tile"] for group in melds))
            if not melds:
                self.fail("strictly improved shanten does not need a reference")
            value = 6 if melds[-1]["tile"] == "m1" else 15
            return {"shanten": 1, "ukeire": value,
                    "value": value, "tian_kept": False}
        with patch("mahtrain_core.ai._cut_shanten", return_value=2), \
             patch("mahtrain_core.ai.shanten_13", return_value=1), \
             patch("mahtrain_core.ai._call_outlook", side_effect=scored):
            self.assertEqual(
                _challenge_kong(view), {"type": "an_gang", "tile": "m9"})
        self.assertEqual(len(got), 2)

    def test_same_stage_compares_every_real_kong_and_keeps_tie_ranking(self):
        _, _, view = offer_kongs()
        def scored(hand, melds, missing, public, cap, tian):
            value = 8 if not melds else (
                15 if melds[-1]["tile"] == "m9" else 12)
            return {"shanten": 1, "ukeire": value,
                    "value": value, "tian_kept": True}
        with patch("mahtrain_core.ai._cut_shanten", return_value=1), \
             patch("mahtrain_core.ai.shanten_13", return_value=1), \
             patch("mahtrain_core.ai._call_outlook", side_effect=scored):
            self.assertEqual(
                _challenge_kong(view), {"type": "an_gang", "tile": "m9"})

    def test_real_tian_ting_and_hidden_poison_do_not_change_call(self):
        game, seat, view = offer_kongs()
        for tian in ({}, {"eligible": True, "initial_waits": ["s9"]}):
            changed = copy.deepcopy(view)
            changed["tian_ting"] = tian
            expected = _legacy_challenge_kong(changed)
            self.assertEqual(expected, _challenge_kong(changed))
            changed["future_wall"] = ["p9"] * 40
            changed["other_player_private_hands"] = [["m1"] * 13] * 3
            self.assertEqual(expected, _challenge_kong(changed))
        self.assertEqual(game.debug_tile_counts()["total"], 108)

    def test_full_authoritative_games_match_legacy_trace_and_balances(self):
        class BeforeAgent(MahjongAgent):
            def kong(self, view):
                if self.level == "challenge" and view["kong_options"]:
                    return _legacy_challenge_kong(view)
                return super().kong(view)

        for seed, seat in ((11, 0), (29, 2)):
            with self.subTest(seed=seed, seat=seat):
                lineup = ["advanced", "basic", "baseline", "challenge"]
                while lineup[seat] != "challenge":
                    lineup = lineup[1:] + lineup[:1]
                previous = simulate_match(
                    seed, lineup=lineup, offline_kong_base=1,
                    offline_agent_overrides={
                        seat: BeforeAgent("challenge", seed=seed, seat=seat)
                    })
                updated = simulate_match(
                    seed, lineup=lineup, offline_kong_base=1)
                for field in (
                    "trace", "public_events", "public_replay",
                    "winners", "official_settled_balances",
                    "partial_win_balances", "official_kong_balances",
                    "official_exhaustive_balances", "terminal_phase",
                    "physical_count",
                ):
                    self.assertEqual(
                        previous[field], updated[field],
                        "kong pruning must not change actual games: " + field)
                self.assertEqual(updated["physical_count"], 108)


if __name__ == "__main__":
    unittest.main()
