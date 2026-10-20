"""M3.81 exact optimized ukeire must agree with pre-optimization reference.

The reference intentionally reconstructs 14/13-tile hands as M3.80 did.
Tests include publicly visible tiles, concealed four-of-a-kind, kong melds,
different missing suits and cache reuse on independent observations.
"""
from __future__ import annotations

import copy
import random
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core import efficiency
from mahtrain_core.rules import TILES, TILE_INDEX, _validate, winning_tiles


def reference_effective_types(hand, melds, missing):
    """The PRE-M3.81 _effective_types_13 logic, kept independently here."""
    current = efficiency.shanten_13(hand, melds, missing)
    if current == 0:
        return winning_tiles(hand, melds, missing)
    own_counts = _validate(hand, melds, missing)
    improving = []
    for drawn_tile in TILES:
        if own_counts[drawn_tile] >= 4:
            continue
        fourteen = [*hand, drawn_tile]
        candidates = set(fourteen)
        if min(
            efficiency.shanten_13(
                [tile for idx, tile in enumerate(fourteen) if idx != cut_index],
                melds, missing,
            )
            for cut_tile in candidates
            for cut_index in (fourteen.index(cut_tile),)
        ) < current:
            improving.append(drawn_tile)
    return improving


def reference_effective_draws(hand, melds, missing, public):
    current = efficiency.shanten_13(hand, melds, missing)
    remaining, unknown_count = efficiency._remaining_counts(
        hand, melds, public, missing)
    types = reference_effective_types(hand, melds, missing)
    details = [{"tile": tile, "remaining": remaining[tile]}
               for tile in types if remaining[tile] > 0]
    count = sum(item["remaining"] for item in details)
    return {
        "shanten": current,
        "effective_types": [item["tile"] for item in details],
        "effective_details": details,
        "effective_tile_count": count,
        "unknown_tile_count": unknown_count,
        "next_draw_probability": count / unknown_count if unknown_count else 0.0,
    }


def legal_position(seed, exposed_count, missing):
    """Draw legal tile-count fixtures with both peng and concealed kongs."""
    rng = random.Random(seed)
    physical = Counter({tile: 4 for tile in TILES})
    groups = []
    for i in range(exposed_count):
        kind = "an_gang" if i % 2 == 0 else "peng"
        tile = rng.choice([t for t in TILES if physical[t] >=
                           (4 if kind == "an_gang" else 3)])
        count = 4 if kind == "an_gang" else 3
        physical[tile] -= count
        groups.append({"type": kind, "tile": tile})
    deck = [tile for tile in TILES for _ in range(physical[tile])]
    rng.shuffle(deck)
    hand = deck[:13 - 3*exposed_count]
    known = hand + [t for group in groups for t in
                    [group["tile"]]*(4 if group["type"]=="an_gang" else 3)]
    seen = Counter(known)
    public = []
    for tile in TILES:
        public.extend([tile] * min(2, 4-seen[tile]))
    return hand, groups, missing, public


class FastUkeireExactParity(unittest.TestCase):
    def test_reference_match_non_tenpai_and_tenpai_with_all_meld_counts(self):
        positions = [
            legal_position(seed, exposed, missing)
            for seed in (2, 19, 47)
            for exposed in (0, 1, 2, 3, 4)
            for missing in ("m", "p", "s")
        ]
        # Don't need the expensive reference for every visibility version:
        # effective-type enumeration never depends on PUBLIC observations.
        for hand, melds, missing, public in positions:
            with self.subTest(melds=len(melds), missing=missing,
                              tiles=tuple(sorted(hand))):
                expected = reference_effective_draws(hand, melds, missing, [])
                actual = efficiency.effective_draws(hand, melds, missing, [])
                self.assertEqual(actual, expected)
                # Drawing from the same hand with more public exposure MUST
                # recompute physical remaining copies rather than reusing
                # stale per-view weights.
                p0 = public[:max(1, len(public)//3)]
                p1 = public[:max(1, len(public)//2)]
                for exposure in (p0, p1):
                    got = efficiency.effective_draws(hand, melds, missing, exposure)
                    remain, unknown = efficiency._remaining_counts(
                        hand, melds, exposure, missing)
                    details = [{"tile":t, "remaining":remain[t]}
                               for t in expected["effective_types"]
                               if remain[t] > 0]
                    self.assertEqual(got["effective_details"], details)
                    self.assertEqual(got["unknown_tile_count"], unknown)

    def test_mutating_input_lists_and_view_does_not_touch_cached_results(self):
        hand, melds, missing, public = legal_position(30, 1, "p")
        first = efficiency.effective_draws(hand, melds, missing, public)
        again = efficiency.effective_draws(hand, melds, missing, public)
        self.assertEqual(first, again)
        again["effective_details"].clear()
        again["effective_types"].clear()
        self.assertEqual(
            efficiency.effective_draws(hand, melds, missing, public), first)
        self.assertLessEqual(
            efficiency._cached_effective_types_non_tenpai.cache_info().maxsize,
            16_384,
        )

    def test_non_tenpai_no_hand_rebuilds_or_repeated_validation(self):
        hand, melds, missing, public = legal_position(42, 0, "s")
        # This test explicitly exercises non-tenpai; tenpai deliberately
        # delegates to authoritative 'winning_tiles' instead.
        if efficiency.shanten_13(hand, melds, missing) == 0:
            self.skipTest("fixture unexpectedly tenpai")
        efficiency._cached_effective_types_non_tenpai.cache_clear()
        original = efficiency.shanten_13
        with patch("mahtrain_core.efficiency.shanten_13", wraps=original) as counter:
            fast = efficiency.effective_draws(hand, melds, missing, public)
        self.assertEqual(fast, reference_effective_draws(
            hand, melds, missing, public))
        self.assertLessEqual(counter.call_count, 4,
                             "slow path recreated hundreds of 13-tile arrays")

    def test_meld_tile_with_four_owned_copies_is_never_drawable(self):
        concealed = ["m2"]*3 + ["m3"]*3 + ["p1"]*3 + ["s2"]
        groups = [{"type": "an_gang", "tile": "m1"}]
        for public in ([], ["p4", "p4", "m5"]):
            ref = reference_effective_draws(concealed, groups, "s", public)
            got = efficiency.effective_draws(concealed, groups, "s", public)
            self.assertEqual(got, ref)
            self.assertNotIn("m1", got["effective_types"])

    def test_same_multiset_key_is_order_invariant(self):
        hand, melds, missing, public = legal_position(30, 0, "p")
        got = efficiency.effective_draws(hand, melds, missing, public)
        reversed_got = efficiency.effective_draws(
            list(reversed(hand)), list(reversed(melds)), missing, public)
        self.assertEqual(got, reversed_got)

    def test_real_ai_tournament_trace_matches_legacy_ukeire(self):
        # Verify complete rule-engine outputs and agent calls, not merely
        # isolated helper functions. The benchmark's clock samples naturally
        # differ and must NEVER affect game decisions.
        from mahtrain_core.ai_tournament import simulate_match
        for seed in (11, 29):
            with self.subTest(seed=seed):
                with patch("mahtrain_core.efficiency._effective_types_13",
                           side_effect=reference_effective_types):
                    original = simulate_match(
                        seed, rotation=0, offline_kong_base=1)
                optimized = simulate_match(
                    seed, rotation=0, offline_kong_base=1)
                for key in ("terminal_phase", "winners", "trace",
                            "public_events", "public_replay",
                            "official_settled_balances",
                            "official_kong_balances",
                            "official_exhaustive_balances"):
                    self.assertEqual(original[key], optimized[key], key)
                self.assertEqual(optimized["physical_count"], 108)


if __name__ == "__main__":
    unittest.main()
