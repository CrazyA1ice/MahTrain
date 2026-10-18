"""Deterministic Sichuan Mahjong win/wait/fan kernel (v0.4 subset).

Only the fixed-case evaluator is implemented: no shanten solver, turn engine,
exchange phase, full scoring ledger, VRF, or AI policy yet.
Tile notation: m1..m9 (万), s1..s9 (条), p1..p9 (筒).
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import Any, Mapping, Sequence

SUITS = ("m", "s", "p")
TILES = tuple(f"{s}{n}" for s in SUITS for n in range(1, 10))
TILE_INDEX = {tile: i for i, tile in enumerate(TILES)}
KONG_KINDS = {"ming_gang", "an_gang", "bu_gang"}
MELD_KINDS = KONG_KINDS | {"peng"}


def _check_missing(missing_suit: str) -> None:
    if missing_suit not in SUITS:
        raise ValueError("missing_suit must be m, s or p")


def _meld_tiles(meld: Mapping[str, str]) -> list[str]:
    kind = meld.get("type")
    tile = meld.get("tile")
    if kind not in MELD_KINDS or tile not in TILE_INDEX:
        raise ValueError(f"invalid exposed meld: {meld!r}")
    return [tile] * (4 if kind in KONG_KINDS else 3)


def _validate(
    concealed: Sequence[str],
    melds: Sequence[Mapping[str, str]],
    missing_suit: str,
) -> Counter[str]:
    _check_missing(missing_suit)
    if len(melds) > 4:
        raise ValueError("at most four melds")
    full = list(concealed)
    for meld in melds:
        full.extend(_meld_tiles(meld))
    if any(t not in TILE_INDEX for t in full):
        raise ValueError("invalid tile symbol")
    counts = Counter(full)
    if any(v > 4 for v in counts.values()):
        raise ValueError("more than four physical copies of a tile")
    return counts


@lru_cache(maxsize=200_000)
def _is_meld_partition(counts: tuple[int, ...]) -> bool:
    try:
        first = next(i for i, v in enumerate(counts) if v)
    except StopIteration:
        return True
    c = list(counts)
    if c[first] >= 3:
        c[first] -= 3
        if _is_meld_partition(tuple(c)):
            return True
        c[first] += 3
    if first % 9 <= 6 and c[first + 1] and c[first + 2]:
        c[first] -= 1
        c[first + 1] -= 1
        c[first + 2] -= 1
        if _is_meld_partition(tuple(c)):
            return True
    return False


def _standard_win(concealed: Sequence[str], meld_count: int) -> bool:
    if len(concealed) != 14 - 3 * meld_count:
        return False
    counts = [0] * 27
    for tile in concealed:
        counts[TILE_INDEX[tile]] += 1
    for index, v in enumerate(counts):
        if v >= 2:
            counts[index] -= 2
            if _is_meld_partition(tuple(counts)):
                return True
            counts[index] += 2
    return False


def _seven_pairs(concealed: Sequence[str], meld_count: int) -> bool:
    if meld_count != 0 or len(concealed) != 14:
        return False
    counts = Counter(concealed)
    return all(v in (2, 4) for v in counts.values()) and sum(
        v // 2 for v in counts.values()
    ) == 7


def is_legal_win(
    concealed: Sequence[str],
    melds: Sequence[Mapping[str, str]] = (),
    missing_suit: str = "p",
) -> bool:
    """Check physical tiles, declared missing suit, and standard/seven-pairs win."""
    all_counts = _validate(concealed, melds, missing_suit)
    if any(t[0] == missing_suit for t in all_counts):
        return False
    return _standard_win(concealed, len(melds)) or _seven_pairs(
        concealed, len(melds)
    )



def diagnose_win(
    concealed: Sequence[str],
    melds: Sequence[Mapping[str, str]] = (),
    missing_suit: str = "p",
) -> dict[str, Any]:
    """Public rule explanation without claiming a not-yet-discarded win.

    Recognizes standard meld+pair and concealed seven-pairs structures,
    separately from the mandatory declared-missing-suit constraint. For an
    incomplete 13-effective-tile hand, no win is offered.
    """
    counts = _validate(concealed, melds, missing_suit)
    missing_count = sum(
        value for tile, value in counts.items() if tile[0] == missing_suit
    )
    structural = (
        _standard_win(concealed, len(melds))
        or _seven_pairs(concealed, len(melds))
    )
    legal = structural and missing_count == 0
    if missing_count:
        reason = "missing_suit_not_cleared"
    elif structural:
        reason = "legal_win"
    else:
        reason = "incomplete_hand"
    return {
        "legal_win": legal,
        "structural_win": structural,
        "missing_suit_tile_count": missing_count,
        "reason_code": reason,
    }

def winning_tiles(
    concealed: Sequence[str],
    melds: Sequence[Mapping[str, str]] = (),
    missing_suit: str = "p",
) -> list[str]:
    """All legal waits; input has 13 effective tiles (kong counts as one meld).

    This is a structural waiting set, NOT an assertion that the tile is still
    available in the unseen wall. Opponents' concealed hands are never read.
    """
    counts = _validate(concealed, melds, missing_suit)
    if len(concealed) != 13 - 3 * len(melds):
        raise ValueError("wait state must have 13 effective tiles")
    return [
        t for t in TILES
        if counts[t] < 4 and is_legal_win([*concealed, t], melds, missing_suit)
    ]


def tian_ting_qualifies(
    starting_13: Sequence[str],
    missing_suit: str,
    checkpoints: Sequence[Mapping[str, Any]],
    is_dealer: bool = False,
) -> bool:
    """Test a post-exchange tenpai trace; no-change means identical wait SETS.

    Only compare valid post-discard/post-call 13-effective-tile checkpoints.
    The caller must provide a truthful game-action history; real matches must
    derive these snapshots from the state machine rather than user inputs.
    A PENG cancels tian ting even if the wait set remains unchanged.
    A KONG alone does not cancel it (unless the wait set changes). Upgrading
    a peng to bu_gang cannot restore a tian ting that was already lost.

    Snapshots may include 'action' or 'actions_since_previous' to record
    actions already applied. A real match must submit an authoritative full
    trace; never infer qualification from a final hand alone.
    """
    if is_dealer:
        return False
    initial_waits = set(winning_tiles(starting_13, (), missing_suit))
    if not initial_waits:
        return False
    for snapshot in checkpoints:
        actions = [
            snapshot.get("action"),
            *snapshot.get("actions_since_previous", ()),
        ]
        if any(action in ("peng", "bu_gang") for action in actions):
            return False
        # Already-peng'd melds are disqualifying even if the action was
        # omitted from this snapshot. Bu_gang presupposes an earlier peng.
        if any(
            meld.get("type") in ("peng", "bu_gang")
            for meld in snapshot.get("melds", ())
        ):
            return False
        current = set(winning_tiles(
            snapshot["concealed"], snapshot.get("melds", ()), missing_suit
        ))
        if current != initial_waits:
            return False
    return True


def score_win(
    concealed: Sequence[str],
    melds: Sequence[Mapping[str, str]] = (),
    missing_suit: str = "p",
    *,
    cap: int = 3,
    context: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    """Calculate supported base patterns, explicit stacks and bonus fan.

    context['tian_ting_verified'] must come from the match's verified tenpai
    trace; this subset cannot prove it from a final hand alone.
    context['heaven_win_verified']/['earth_win_verified'] likewise require
    authenticated opening event context, not a bare final hand.
    """
    if type(cap) is not int or cap < 0:
        raise ValueError("cap must be a nonnegative integer")
    ctx = dict(context or {})
    all_counts = _validate(concealed, melds, missing_suit)
    if not is_legal_win(concealed, melds, missing_suit):
        return {"legal": False, "reason": "not_a_legal_win"}
    seven = _seven_pairs(concealed, len(melds))
    dragon = seven and any(v == 4 for v in all_counts.values())
    pure = len({tile[0] for tile in all_counts}) == 1
    pung_partitions = _pung_partitions_for_validation(concealed, len(melds))
    all_pungs = (
        not seven
        and bool(pung_partitions)  # all([]) is True; no partition means NO all-pungs.
        and all(m["type"] in MELD_KINDS | {"peng"} for m in melds)
        and any(all(count == 3 for count in part) for part in pung_partitions)
    )
    # Four declared pungs/kongs plus a concealed pair is 'golden hook'.
    gold = (
        len(melds) == 4
        and len(concealed) == 2
        and concealed[0] == concealed[1]
    )

    if seven:
        if dragon:
            main, main_fan = ("pure_dragon_seven_pairs", 5) if pure else ("dragon_seven_pairs", 3)
        else:
            main, main_fan = ("pure_seven_pairs", 4) if pure else ("seven_pairs", 2)
    elif gold:
        # Never also add all_pungs or pure_all_pungs, per user-defined exclusion.
        main, main_fan = "golden_hook", 2
    elif all_pungs:
        main, main_fan = ("pure_all_pungs", 3) if pure else ("all_pungs", 1)
    elif pure:
        main, main_fan = "pure_suit", 2
    else:
        main, main_fan = "pinghu", 0

    verified_heaven = bool(ctx.get("heaven_win_verified"))
    verified_earth = bool(ctx.get("earth_win_verified"))
    verified_tian_ting = bool(ctx.get("tian_ting_verified"))
    if verified_heaven and verified_earth:
        raise ValueError("heaven and earth events cannot both occur")
    if verified_heaven and melds:
        raise ValueError("heaven win cannot have exposed melds")
    if verified_heaven and verified_tian_ting:
        raise ValueError("heaven win and nondealer tian ting are incompatible")
    if verified_heaven and main_fan < 4:
        main, main_fan = "heaven_win", 4
    if verified_earth and main_fan < 4:
        main, main_fan = "earth_win", 4

    combination_fans: list[tuple[str, int]] = []
    if gold and pure:
        combination_fans.append(("pure_suit", 2))
    if verified_tian_ting:
        combination_fans.append(("tian_ting", 2))

    # Root means four physical copies among concealed plus declared melds.
    roots = sum(1 for n in all_counts.values() if n == 4)
    if dragon:
        roots -= 1  # counted once inside dragon seven pairs / pure dragon
    assert roots >= 0
    bonuses: list[tuple[str, int]] = []
    for field, label in (
        ("kong_bloom", "kong_bloom"),
        ("kong_discard_ron", "kong_discard_ron"),
        ("rob_added_kong", "rob_added_kong"),
        ("sea_bottom_draw", "sea_bottom_draw"),
        ("river_bottom_ron", "river_bottom_ron"),
    ):
        if ctx.get(field):
            bonuses.append((label, 1))
    if sum(bool(ctx.get(field)) for field in (
        "kong_bloom", "kong_discard_ron", "rob_added_kong"
    )) > 1:
        raise ValueError("mutually exclusive kong win events")
    if ctx.get("sea_bottom_draw") and ctx.get("river_bottom_ron"):
        raise ValueError("last-wall draw and last-wall discard wins are exclusive")
    if roots:
        bonuses.append(("roots", roots))

    raw = main_fan + sum(n for _, n in combination_fans) + sum(
        n for _, n in bonuses
    )
    effective = min(raw, cap)
    return {
        "legal": True,
        "main_pattern": main,
        "main_fan": main_fan,
        "golden_hook": gold,
        "seven_pairs": seven,
        "pure_suit": pure,
        "combinations": dict(combination_fans),
        "bonuses": dict(bonuses),
        "raw_fan": raw,
        "effective_fan": effective,
        "multiplier": 2 ** effective,
    }


def _pung_partitions_for_validation(
    concealed: Sequence[str], meld_count: int
) -> list[list[int]]:
    """Return a partition only if concealed after chosen pair is all pungs.

    Empty list means no all-pungs partition. Each successful result is a list
    containing one vector of 3s (no chow allowed); useful for validation.
    """
    if len(concealed) != 14 - 3 * meld_count:
        return []
    counts = Counter(concealed)
    for tile, cnt in counts.items():
        if cnt < 2:
            continue
        remaining = counts.copy()
        remaining[tile] -= 2
        if all(v % 3 == 0 for v in remaining.values()) and sum(
            remaining.values()
        ) == 3 * (4 - meld_count):
            return [[v for v in remaining.values() if v]]
    return []
