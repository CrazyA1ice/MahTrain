"""M3.54 bounded counterfactual discard-loss simulation.

Uses own concealed tiles + public inventory and hand lengths only. The drawn
worlds are synthetic opponent hands, NEVER the match's actual private hands or
wall. Proposal weights combine public river and meld-suit patterns with a small
explicit ready-hand hypothesis mixture. Hit rates are NOT calibrated odds.
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
                # Unknown an-gang consumes four matching physical copies.
                # Without its kind, even OTHER seats' disjoint allocations
                # cannot be certified; decline sampling altogether.
                return None
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



def _public_styles(view: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    """Extract only river and exposed-meld evidence, never inferred secrets."""
    styles: dict[int, dict[str, Any]] = {}
    for seat in range(4):
        river = [
            e["tile"] for e in view["discards"]
            if e.get("seat") == seat and e.get("tile") in TILE_INDEX
        ]
        open_suits = [
            m["tile"][0] for m in view["melds"][seat]
            if m.get("tile") in TILE_INDEX
        ]
        styles[seat] = {
            "river": tuple(river),
            "meld_suits": tuple(open_suits),
        }
    return styles


def _tile_weight(tile: str, missing: str, style: Mapping[str, Any],
                 chosen: Sequence[str], late: bool) -> float:
    """Public behavioral proposal score, explicitly NOT a posterior density."""
    river = style.get("river", ())
    revealed = style.get("meld_suits", ())
    score = (0.19 if late else 0.42) if tile[0] == missing else 1.0
    if tile in river:
        score *= 0.80  # Mahjong blood battle has no furiten.
    if len(river) >= 6:
        count = sum(t[0] == tile[0] for t in river)
        score *= 1.27 if count == 0 else max(0.7, 1 - 0.045 * count)
    if len(revealed) >= 2 and len(set(revealed)) == 1:
        score *= 1.75 if tile[0] == revealed[0] else 0.90
    if chosen and tile[0] != missing:
        own = Counter(chosen)
        if own[tile]:
            score *= 1.85 if own[tile] == 1 else 1.45
        rank = int(tile[1])
        neighbors = (
            sum(own.get(tile[0] + str(n), 0) for n in (rank - 1, rank + 1)
                if 1 <= n <= 9)
        )
        gaps = (
            sum(own.get(tile[0] + str(n), 0) for n in (rank - 2, rank + 2)
                if 1 <= n <= 9)
        )
        score *= 1 + min(1.1, 0.38 * neighbors + 0.13 * gaps)
    return score


def _weighted_index(weights: Sequence[float], rng: random.Random) -> int:
    cutoff = rng.random() * sum(weights)
    for index, weight in enumerate(weights):
        cutoff -= weight
        if cutoff < 0:
            return index
    return len(weights) - 1


def _ready_hypothesis(
    remaining: list[str], size: int, missing: str,
    melds: Sequence[Mapping[str, str]], style: Mapping[str, Any],
    rng: random.Random, late: bool,
) -> tuple[list[str], list[str]] | None:
    """Construct a PHYSICALLY VALID, ready-shaped 13-effective hand.

    Complete concealed melds + one singleton form one legal pair wait.
    This is an over-sampled hypothesis for sensitivity testing, not an
    inference that an actual opponent is ready. Never see actual hidden cards.
    """
    sets_needed = 4 - len(melds)
    if not 0 <= sets_needed <= 4 or size != 3 * sets_needed + 1:
        return None
    available = Counter(remaining)
    singletons = [tile for tile in TILES
                  if tile[0] != missing and available[tile] >= 1]
    if not singletons:
        return None
    single = singletons[_weighted_index([
        available[t] * _tile_weight(t, missing, style, (), late)
        for t in singletons], rng)]
    available[single] -= 1
    shaped = [single]
    for _ in range(sets_needed):
        candidates: list[tuple[str, ...]] = []
        for tile in TILES:
            if tile[0] == missing:
                continue
            if available[tile] >= 3:
                candidates.append((tile, tile, tile))
            if int(tile[1]) <= 7:
                seq = (tile, tile[0] + str(int(tile[1]) + 1),
                       tile[0] + str(int(tile[1]) + 2))
                if all(available[t] for t in seq):
                    candidates.append(seq)
        if not candidates:
            return None
        chosen = candidates[_weighted_index([
            sum(_tile_weight(t, missing, style, shaped, late) for t in group) / 3
            for group in candidates
        ], rng)]
        for tile in chosen:
            available[tile] -= 1
            shaped.append(tile)
    # Keep the original pool's order for deterministic physical removal.
    leftover = remaining[:]
    for tile in shaped:
        leftover.remove(tile)
    return shaped, leftover

def _deal(pool: list[str], targets: list[tuple[int, int, str, list[dict[str, str]]]],
          rng: random.Random, late: bool, *,
          evidence: Mapping[int, Mapping[str, Any]] | None = None,
          world_index: int = 0,
          diagnostics: dict[str, int] | None = None
          ) -> list[tuple[int, list[str], str, list[dict[str, str]]]]:
    """Sample all opponents jointly, without replacement.

    Alternate ordinary style-weighted hands with a bounded fraction of
    *explicitly hypothetical* ready-shaped hands for opponents with >=2
    exposed melds. The mixture is NOT P(tenpai).
    """
    remaining = pool[:]
    sampled: list[tuple[int, list[str], str, list[dict[str, str]]]] = []
    seats = targets[:]
    rng.shuffle(seats)
    for seat, size, missing, melds in seats:
        style = (evidence or {}).get(seat, {})
        hypothesis = (
            len(melds) >= 2 and
            world_index % (3 if len(melds) >= 3 else 4) == 0
        )
        shaped = (_ready_hypothesis(remaining, size, missing, melds,
                                   style, rng, late) if hypothesis else None)
        if shaped is not None:
            hand, remaining = shaped
            if diagnostics is not None:
                diagnostics["ready_hypotheses"] += 1
        else:
            hand = []
            for _ in range(size):
                if not remaining:
                    raise ValueError("insufficient physical unknown tiles")
                selected = _weighted_index([
                    _tile_weight(tile, missing, style, hand, late)
                    for tile in remaining
                ], rng)
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
    if not tiles or any(type(tile) is not str or tile not in TILE_INDEX
                        for tile in tiles):
        raise ValueError("invalid candidate tiles")
    candidates = sorted(set(tiles), key=TILE_INDEX.__getitem__)
    inputs = _private_world_inputs(view)
    blank = {tile: {"hits": 0, "mean_loss_multiplier": 0.0}
             for tile in candidates}
    if inputs is None or not inputs[1]:
        return {"available": False, "worlds": 0, "by_tile": blank,
                "model": "river_conditioned_proposal_v2"}
    pool, targets = inputs
    cap = view.get("win_ledger", {}).get("fan_cap", 3) if isinstance(view.get("win_ledger"), dict) else 3
    if type(cap) is not int or not 0 <= cap <= 12:
        cap = 3
    late = type(view.get("wall_count")) is int and view["wall_count"] <= 24
    rng = random.Random(_seed(view, candidates))
    totals = dict.fromkeys(candidates, 0.0)
    hits = dict.fromkeys(candidates, 0)
    diagnostics = {"ready_hypotheses": 0}
    evidence = _public_styles(view)
    for index in range(worlds):
        for seat, hand, missing, melds in _deal(
            pool, targets, rng, late, evidence=evidence,
            world_index=index, diagnostics=diagnostics
        ):
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
        "ready_hypotheses": diagnostics["ready_hypotheses"],
        "by_tile": {
            tile: {
                "hits": hits[tile],
                "mean_loss_multiplier": round(totals[tile] / worlds, 6),
            } for tile in candidates
        },
        "model": "river_conditioned_proposal_v2",
    }
