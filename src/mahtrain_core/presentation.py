"""MahTrain shared hand arrangement / 理牌 rules.

Suits always form contiguous groups in display order 万 → 条 → 筒, and within
each suit ranks run 1 → 9 with identical tiles next to each other. Sorting is
presentation-only; it does NOT consume, draw, or otherwise mutate any tile.
"""
from __future__ import annotations

from collections import Counter
from typing import Sequence

from .rules import SUITS, TILES

SUIT_NAMES = {"m": "万", "s": "条", "p": "筒"}
_SUIT_INDEX = {s: i for i, s in enumerate(SUITS)}
_TILE_SET = frozenset(TILES)


def sort_hand(tiles: Sequence[str]) -> list[str]:
    """Return a NEW arranged list; preserve every tile and multiplicity."""
    if any(tile not in _TILE_SET for tile in tiles):
        raise ValueError("invalid tile in hand")
    return sorted(tiles, key=lambda tile: (_SUIT_INDEX[tile[0]], int(tile[1:])))


def grouped_hand(tiles: Sequence[str]) -> list[dict[str, object]]:
    """Display groups in suit order, omitting suits not present."""
    arranged = sort_hand(tiles)
    return [
        {"suit": suit, "name": SUIT_NAMES[suit],
         "tiles": [tile for tile in arranged if tile.startswith(suit)]}
        for suit in SUITS
        if any(tile.startswith(suit) for tile in arranged)
    ]


def format_hand(tiles: Sequence[str]) -> str:
    """Human-readable, ascending groups: 万[1 8 8 9] | 条[2 7]."""
    groups = grouped_hand(tiles)
    return " | ".join(
        f"{group['name']}[" +
        " ".join(tile[1:] for tile in group["tiles"]) + "]"
        for group in groups
    )


def assert_unchanged(before: Sequence[str], arranged: Sequence[str]) -> bool:
    """Used by tests/clients to ensure formatting did not modify tile counts."""
    return Counter(before) == Counter(arranged)
