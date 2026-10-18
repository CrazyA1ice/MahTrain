"""M3.54 bounded counterfactual discard-loss simulation.

Uses own concealed tiles + public inventory and hand lengths only. The drawn
worlds are synthetic opponent hands, NEVER the match's actual private hands or
wall. Proposal weights encode a weak post-dingque preference, so the reported
frequencies are *not* calibrated probabilities of tenpai or dealing in.
"""
from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from typing import Any, Mapping, Sequence

from .rules import TILES, TILE_INDEX, SUITS, is_legal_win, score_win

DEFAULT_WORLDS = 24
MAX_WORLDS = 64
MELD_SIZES = {"peng": 3, "ming_gang": 4, "an_gang": 4, "bu_gang": 4}


def _private_world_inputs(view: Mapping[str, Any]) -> tuple[list[str], list[tuple[int, int, str, list[dict[str, str]]]]] | None:
    """Rebuild physical unknown pool without touching undocumented fields.

    Refuse malformed/redacted known melds rather than invent a hidden kong's
    identity; the existing public heuristic remains the safe fallback.
    """
    own = view.get("seat")
    hand = view.get("hand")
    lengths = view.get("hand_counts")
    missing = view.get("missing_suits")
    melds = view.get("melds")
    won = view.get("won")
    discards = view.get("discards")
    if (type(own) is not int or own not in range(4)
        or not isinstance(hand, list)
        or any(t not in TILE_INDEX for t in hand)
        or not isinstance(lengths, (list, tuple)) or len(lengths) != 4
        or not isinstance(missing, (list, tuple)) or len(missing) != 4
        or any(s not in SUITS for s in missing)
        or not isinstance(melds, (list, tuple)) or len(melds) != 4
        or not isinstance(won, (list, tuple)) or len(won) != 4
        or not isinstance(discards, (list, tuple))):
        return None
    own_melds = view.get("own_melds")
    if not isinstance(own_melds, list):
        return None
    if type(lengths[own]) is not int or lengths[own] != len(hand):
        return None
    known = Counter(hand)
    for d in discards:
        if not isinstance(d, dict) or d.get("tile") not in TILE_INDEX:
            return None
        if "claimed_by" not in d:
            known[d["tile"]] += 1
    targets: list[tuple[int, int, str, list[dict[str, str]]]] = []
    for seat in range(4):
        groups = own_melds if seat == own else melds[seat]
        if not isinstance(groups, list) or len(groups) > 4:
            return None
        redacted = False
        for m in groups:
            if not isinstance(m, dict) or m.get("type") not in MELD_SIZES:
                return None
            tile = m.get("tile")
            if tile is None:
                redacted = True
                continue
            if tile not in TILE_INDEX:
                return None
            known[tile] += MELD_SIZES[m["type"]]
        if seat != own and not won[seat]:
            size = lengths[seat]
            if (type(size) is not int or size < 0 or size > 14
                or size != 13 - 3 * len(groups)):
                # A transient pending claim is not a valid 13-tile wait state.
                redacted = True
            if not redacted:
                targets.append((seat, size, missing[seat], groups))
    if any(known[t] > 4 for t in TILES) or sum(known.values()) > 108:
        return None
    pool = [tile for tile in TILES for _ in range(4 - known[tile])]
    if sum(size for _, size, _, _ in targets) > len(pool):
        return None
    return pool, targets


def _seed(view: Mapping[str, Any], tiles: Sequence[str]) -> int:
    """Stable, seat-authorized projection: injected hidden keys have no effect."""
    own = view["seat"]
    allowed = {
        "seat": own, "hand": sorted(view["hand"]),
        "own_melds": view["own_melds"],
        "hand_counts": view["hand_counts"],
        "missing_suits": view["missing_suits"],
        "melds": view["melds"], "won": view["won"],
        "discards": view["discards"],
        "wall_count": view.get("wall_count"),
        "candidate_tiles": sorted(set(tiles)),
    }
    payload = json.dumps(allowed, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return int.from_bytes(hashlib.blake2b(payload.encode(), digest_size=8).digest(), "big")


def _deal(pool: list[str], targets: list[tuple[int, int, str, list[dict[str, str]]]],
          rng: random.Random, late: bool) -> list[tuple[int, list[str], str, list[dict[str, str]]]]:
    """Physical sampling without replacement across all active opponent seats.

    Opponent dingque is a *soft* late-game proposal bias, never a hard
    assertion that their actual concealed hand has completed clearing.
    """
    remaining = pool[:]
    sampled: list[tuple[int, list[str], str, list[dict[str, str]]]] = []
    seats = targets[:]
    rng.shuffle(seats)
    for seat, size, missing, melds in seats:
        hand = []
        for _ in range(size):
            if not remaining:
                raise ValueError("insufficient physical unknown tiles")
            weights = [(0.25 if late else 0.5) if t[0] == missing else 1.0
                       for t in remaining]
            pick = rng.random() * sum(weights)
            selected = len(remaining) - 1
            for i, weight in enumerate(weights):
                pick -= weight
                if pick < 0:
                    selected = i
                    break
            hand.append(remaining.pop(selected))
        sampled.append((seat, hand, missing, melds))
    return sampled


def sample_discard_losses(tiles: Sequence[str], view: Mapping[str, Any], *,
                          worlds: int = DEFAULT_WORLDS) -> dict[str, Any]:
    """Estimate one-immediate-discard counterfactual loss across shared worlds.

    The only output is aggregate counts and per-tile average *base payout
    multiplier*, not any sampled hand. Direct next-discard ron only: no
    self-draw future, post-kong, exhaustive-settlement or full-game rollout.
    """
    if type(worlds) is not int or not 1 <= worlds <= MAX_WORLDS:
        raise ValueError("world budget must be 1..64")
    candidates = sorted(set(tiles), key=TILE_INDEX.__getitem__)
    if not candidates or any(tile not in TILE_INDEX for tile in candidates):
        raise ValueError("invalid candidate tiles")
    inputs = _private_world_inputs(view)
    blank = {tile: {"hits": 0, "mean_loss_multiplier": 0.0}
             for tile in candidates}
    if inputs is None or not inputs[1]:
        return {"available": False, "worlds": 0, "by_tile": blank,
                "model": "proposal_mc_v1"}
    pool, targets = inputs
    cap = view.get("win_ledger", {}).get("fan_cap", 3) if isinstance(view.get("win_ledger"), dict) else 3
    if type(cap) is not int or not 0 <= cap <= 12:
        cap = 3
    late = type(view.get("wall_count")) is int and view["wall_count"] <= 24
    rng = random.Random(_seed(view, candidates))
    totals = dict.fromkeys(candidates, 0.0)
    hits = dict.fromkeys(candidates, 0)
    for _ in range(worlds):
        for seat, hand, missing, melds in _deal(pool, targets, rng, late):
            # A seat cannot win a discard in its *declared* missing suit.
            if any(t[0] == missing for t in hand):
                continue
            for tile in candidates:
                if tile[0] == missing:
                    continue
                # The synthetic concealed tiles and public melds together
                # respect the 108 physical copies by construction.
                if is_legal_win([*hand, tile], melds, missing):
                    scored = score_win([*hand, tile], melds, missing, cap=cap)
                    hits[tile] += 1
                    totals[tile] += scored["multiplier"]
    return {
        "available": True, "worlds": worlds,
        "by_tile": {
            tile: {
                "hits": hits[tile],
                "mean_loss_multiplier": round(totals[tile] / worlds, 6),
            } for tile in candidates
        },
        "model": "proposal_mc_v1",
    }
