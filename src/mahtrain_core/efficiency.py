"""Shanten, effective draws and no-regression discard analysis for Sichuan tiles.

A 13-effective-tile hand has exactly 13 - 3*len(exposed_melds) concealed
tiles (a declared kong counts as a single group, despite four physical tiles).
This module considers standard four-melds-and-pair and concealed seven pairs;
only the two non-missing suits may be used in the finished hand.

Tile visibility is an *information model*: visible_tiles must contain only
additional publicly visible physical tiles, not cards already represented by
this player's concealed hand or exposed melds. Discards from a 14-tile hand
remain known after being cut and therefore stay in the denominator.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import Any, Mapping, Sequence

from .rules import SUITS, TILES, TILE_INDEX, _validate, is_legal_win, winning_tiles


@lru_cache(maxsize=200_000)
def _standard_shanten(suit_counts: tuple[int, ...], exposed_count: int) -> int:
    """Exhaustive decomposition into complete melds, pairs and incomplete melds.

    The classic 8 - 2*melds - taatsu - head formula applies at a stable
    13-effective-tile stage. Suits excluded by dingque are zeroed *before*
    this function is invoked. Exposed melds are already complete.
    """
    if exposed_count < 0 or exposed_count > 4:
        raise ValueError("invalid exposed meld count")

    @lru_cache(maxsize=None)
    def walk(
        remaining: tuple[int, ...], made_melds: int, incomplete: int, head: int
    ) -> int:
        total_melds = exposed_count + made_melds
        slots = max(0, 4 - total_melds)
        # Keeping excess incomplete groups provides no benefit.
        best = 8 - 2 * total_melds - min(incomplete, slots) - head
        first = next((i for i, n in enumerate(remaining) if n), None)
        if first is None:
            return best

        current = list(remaining)

        def try_remove(items: tuple[int, ...], dm=0, dt=0, dh=0) -> None:
            nonlocal best
            for idx in items:
                current[idx] -= 1
            best = min(
                best,
                walk(tuple(current), made_melds + dm, incomplete + dt, head + dh),
            )
            for idx in items:
                current[idx] += 1

        # Discard/ignore this tile; it may be unhelpful even when legal-suit.
        try_remove((first,))
        if total_melds < 4:
            if current[first] >= 3:
                try_remove((first, first, first), dm=1)
            if (
                first % 9 <= 6
                and current[first + 1] > 0
                and current[first + 2] > 0
            ):
                try_remove((first, first + 1, first + 2), dm=1)

        if current[first] >= 2:
            if head == 0:
                try_remove((first, first), dh=1)
            if incomplete < 4:
                try_remove((first, first), dt=1)

        if incomplete < 4:
            if first % 9 <= 7 and current[first + 1] > 0:
                try_remove((first, first + 1), dt=1)
            if first % 9 <= 6 and current[first + 2] > 0:
                try_remove((first, first + 2), dt=1)
        return best

    return walk(suit_counts, 0, 0, 0)


@lru_cache(maxsize=200_000)
def _cached_shanten(
    tile_counts: tuple[int, ...], exposed_count: int, missing_suit: str
) -> int:
    absent_count = sum(
        tile_counts[i] for i, tile in enumerate(TILES) if tile[0] == missing_suit
    )
    allowed = tuple(
        0 if tile[0] == missing_suit else tile_counts[i]
        for i, tile in enumerate(TILES)
    )
    standard = _standard_shanten(allowed, exposed_count)
    # The missing suit must be completely cut by tenpai, even when
    # decomposition alone would report fewer necessary changes.
    standard = max(standard, absent_count)
    if exposed_count:
        return standard
    # Four identical tiles count as two pairs in the user's dragon-seven-pairs
    # rule. No exposed meld is permitted in a seven-pairs hand.
    pairs = sum(n // 2 for n in allowed)
    seven_pairs = max(6 - pairs, absent_count)
    return min(standard, seven_pairs)


def shanten_13(
    concealed: Sequence[str],
    melds: Sequence[Mapping[str, str]] = (),
    missing_suit: str = "p",
) -> int:
    """Exact current-stage shanten for supported hand structures.

    0 = tenpai; 1 = one away from tenpai; returns >=0 at 13 effective tiles.
    For already completed 14-effective-tile hands use is_legal_win instead.
    """
    _validate(concealed, melds, missing_suit)
    if len(concealed) != 13 - 3 * len(melds):
        raise ValueError("shanten requires 13 effective tiles")
    counts = Counter(concealed)
    return _cached_shanten(
        tuple(counts[tile] for tile in TILES), len(melds), missing_suit
    )


def _remaining_counts(
    concealed: Sequence[str],
    melds: Sequence[Mapping[str, str]],
    visible_tiles: Sequence[str],
    missing_suit: str,
) -> tuple[dict[str, int], int]:
    physical = _validate([*concealed, *visible_tiles], melds, missing_suit)
    # _validate includes meld tiles; visible_tiles must not duplicate them.
    known = sum(physical.values())
    if known > 108:
        raise ValueError("known tile count exceeds deck")
    return ({tile: 4 - physical[tile] for tile in TILES}, 108 - known)


@lru_cache(maxsize=16_384)
def _cached_effective_types_non_tenpai(
    concealed_counts: tuple[int, ...], exposed_count: int,
    missing_suit: str, available_mask: int, current: int,
) -> tuple[str, ...]:
    """Exact one-draw improvements without rebuilding Python tile hands.

    The mask excludes tiles whose four physical copies are ALL represented
    by this player's own hand/melds. PUBLIC river tiles deliberately do NOT
    enter this cache: public availability is applied later, per observation,
    by _remaining_counts. A bounded cache limits long-lived server memory.
    """
    counts = list(concealed_counts)
    improving: list[str] = []
    for draw_index, drawn_tile in enumerate(TILES):
        if not (available_mask & (1 << draw_index)):
            continue
        counts[draw_index] += 1
        for cut_index in range(len(TILES)):
            # Cutting the newly drawn tile returns the original 13 tiles,
            # whose shanten is 'current': it cannot be an improvement.
            if cut_index == draw_index or not counts[cut_index]:
                continue
            counts[cut_index] -= 1
            reduces = (
                _cached_shanten(tuple(counts), exposed_count, missing_suit)
                < current
            )
            counts[cut_index] += 1
            if reduces:
                improving.append(drawn_tile)
                break
        counts[draw_index] -= 1
    return tuple(improving)


def _effective_types_13(
    concealed: Sequence[str],
    melds: Sequence[Mapping[str, str]],
    missing_suit: str,
) -> list[str]:
    current = shanten_13(concealed, melds, missing_suit)
    if current == 0:
        # Tenpai uses the authoritative legal-win enumeration, including
        # four-copy exclusions, rather than the non-tenpai cache.
        return winning_tiles(concealed, melds, missing_suit)

    # _validate counts physical concealed + exposed meld tiles (four for
    # an_gang, three for peng). Never allow a hypothetical fifth tile.
    physical = _validate(concealed, melds, missing_suit)
    owned = Counter(concealed)
    concealed_counts = tuple(owned[tile] for tile in TILES)
    available_mask = sum(
        1 << index for index, tile in enumerate(TILES)
        if physical[tile] < 4
    )
    return list(_cached_effective_types_non_tenpai(
        concealed_counts, len(melds), missing_suit,
        available_mask, current,
    ))


def effective_draws(
    concealed: Sequence[str],
    melds: Sequence[Mapping[str, str]] = (),
    missing_suit: str = "p",
    visible_tiles: Sequence[str] = (),
) -> dict[str, Any]:
    """Analyze 13 effective tiles using own tiles + public visible tiles only.

    A tile is effective if its draw lowers shanten after the best legal cut,
    or if it directly wins from tenpai. Result counts physically unknown
    copies, not merely distinct tile types. This is *not* a future-k-turn
    winning probability or AI hidden-information peek.
    """
    current = shanten_13(concealed, melds, missing_suit)
    remaining, unknown_count = _remaining_counts(
        concealed, melds, visible_tiles, missing_suit
    )
    types = _effective_types_13(concealed, melds, missing_suit)
    details = [
        {"tile": t, "remaining": remaining[t]}
        for t in types if remaining[t] > 0
    ]
    count = sum(item["remaining"] for item in details)
    return {
        "shanten": current,
        "effective_types": [item["tile"] for item in details],
        "effective_details": details,
        "effective_tile_count": count,
        "unknown_tile_count": unknown_count,
        "next_draw_probability": (
            count / unknown_count if unknown_count else 0.0
        ),
    }


def analyze_discards(
    concealed: Sequence[str],
    melds: Sequence[Mapping[str, str]] = (),
    missing_suit: str = "p",
    visible_tiles: Sequence[str] = (),
) -> dict[str, Any]:
    """Analyze all 14-effective-tile legal cuts and report tied local optima.

    Ranking is lexicographic: minimum resulting shanten, then maximum
    remaining effective tile copies. All tied discards are equally optimal;
    never voluntarily regress shanten for additional eventual scoring.
    """
    _validate([*concealed, *visible_tiles], melds, missing_suit)
    if len(concealed) != 14 - 3 * len(melds):
        raise ValueError("discard analysis needs 14 effective tiles")

    if is_legal_win(concealed, melds, missing_suit):
        return {"status": "already_winning", "candidates": [], "best_discards": []}

    candidates: list[dict[str, Any]] = []
    for discard in sorted(set(concealed), key=TILE_INDEX.__getitem__):
        remain = list(concealed)
        remain.remove(discard)
        # The discarded tile was in the player's 14-tile hand and remains
        # visibly known; otherwise the denominator would grow by one.
        info = effective_draws(
            remain, melds, missing_suit,
            visible_tiles=[*visible_tiles, discard],
        )
        candidates.append({"discard": discard, **info})

    min_shanten = min(item["shanten"] for item in candidates)
    max_ukeire = max(
        item["effective_tile_count"]
        for item in candidates if item["shanten"] == min_shanten
    )
    for item in candidates:
        item["local_optimal"] = (
            item["shanten"] == min_shanten
            and item["effective_tile_count"] == max_ukeire
        )
        item["non_regressing"] = item["shanten"] == min_shanten
    candidates.sort(key=lambda row: (
        row["shanten"], -row["effective_tile_count"], TILE_INDEX[row["discard"]]
    ))
    return {
        "status": "choose_discard",
        "minimum_shanten": min_shanten,
        "best_discards": [
            item["discard"] for item in candidates if item["local_optimal"]
        ],
        "candidates": candidates,
    }
