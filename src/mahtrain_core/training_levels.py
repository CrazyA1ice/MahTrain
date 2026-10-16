"""Verified input-shape families for progressively harder single questions.

The family describes how the INITIAL 13-tile shape was constructed, not its
answer. Candidates are validated again by the full shanten/win kernel; no
constructed hand is declared correct merely because it looks plausible.
"""
from __future__ import annotations

import random
from collections import Counter

from .rules import SUITS

DIFFICULTIES = ("basic", "intermediate", "challenge")
LEVEL_LABELS = {"basic": "基础", "intermediate": "进阶", "challenge": "挑战"}


def _meld(rng: random.Random, suit: str, prefer_sequence: bool) -> list[str]:
    if prefer_sequence or rng.random() < .65:
        start = rng.randint(1, 7)
        return [f"{suit}{rank}" for rank in (start, start + 1, start + 2)]
    tile = f"{suit}{rng.randint(1, 9)}"
    return [tile] * 3


def _valid(cards: list[str]) -> bool:
    return len(cards) == 13 and all(0 <= n <= 4 for n in Counter(cards).values())


def make_ready(
    rng: random.Random, *, pure: bool, difficulty: str
) -> tuple[list[str], str, str]:
    """Return (13 tiles, missing suit, family) for an intended tenpai."""
    if difficulty not in DIFFICULTIES:
        raise ValueError("unsupported difficulty")
    if pure:
        suit, missing = rng.sample(SUITS, 2)
        allowed = (suit,)
    else:
        suits = rng.sample(SUITS, 3)
        missing = suits[-1]
        allowed = tuple(suits[:2])
    for _ in range(120):
        if difficulty == "challenge" and rng.random() < .6:
            ranks = rng.sample(range(1, 10), 7)
            suit = rng.choice(allowed)
            hand = [f"{suit}{r}" for r in ranks[:6] for _ in range(2)]
            hand.append(f"{suit}{ranks[6]}")
            family = "seven_pairs"
        else:
            sequence_first = difficulty in ("intermediate", "challenge")
            hand = []
            for i in range(4):
                hand.extend(_meld(rng, rng.choice(allowed), sequence_first))
            hand.append(f"{rng.choice(allowed)}{rng.randint(1,9)}")
            family = "sequence_melds" if sequence_first else "mixed_melds"
        if _valid(hand) and (not pure or len({c[0] for c in hand}) == 1):
            rng.shuffle(hand)
            return hand, missing, family
    raise RuntimeError("unable to construct physical tenpai skeleton")


def make_one_shanten(
    rng: random.Random, *, difficulty: str
) -> tuple[list[str], str, str]:
    """Create three melds + pair + two lone tiles, or seven-pairs rival."""
    if difficulty not in DIFFICULTIES:
        raise ValueError("unsupported difficulty")
    available = rng.sample(SUITS, 3)
    missing = available[-1]
    for _ in range(120):
        if difficulty == "challenge" and rng.random() < .65:
            suits = tuple(available[:2])
            tiles = [f"{s}{rank}" for s in suits for rank in range(1,10)]
            chosen = rng.sample(tiles, 8)
            hand = [t for t in chosen[:5] for _ in range(2)] + chosen[5:]
            family = "seven_pairs_race"
        else:
            hand = []
            suits = available[:2]
            sequence = difficulty != "basic"
            for _ in range(3):
                hand.extend(_meld(rng, rng.choice(suits), sequence))
            if sequence:
                # 3 complete melds + 2 incomplete adjacent groups, NO fixed
                # head. A hand with a completed head AND adjacent group here
                # would actually be tenpai (0 shanten), not one-shanten.
                for suit in suits:
                    a = rng.randint(1, 8)
                    hand.extend((f"{suit}{a}", f"{suit}{a+1}"))
                family = "two_taatsu"
            else:
                paired = f"{rng.choice(suits)}{rng.randint(1,9)}"
                hand += [paired, paired]
                hand += [
                    f"{rng.choice(suits)}{rng.randint(1,9)}" for _ in range(2)
                ]
                family = "meld_and_isolates"
        if _valid(hand):
            rng.shuffle(hand)
            return hand, missing, family
    raise RuntimeError("unable to construct physical 1-shanten skeleton")
