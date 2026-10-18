"""M3.53 public-information-only table reading for Sichuan blood battle.

No wall sampling, opponent private hands, or fabricated opponent tenpai odds.
The returned threat index is an interpretable ranking heuristic, NOT P(ron).
Sichuan blood-battle has no Japanese-mahjong furiten restriction: a previously
discarded copy does NOT make a tile absolutely safe against that opponent.
"""
from __future__ import annotations

from typing import Any, Mapping

from .rules import TILE_INDEX, SUITS


def _is_seat(value: object) -> bool:
    return type(value) is int and 0 <= value < 4


def read_discard_threat(tile: str, view: Mapping[str, Any]) -> dict[str, Any]:
    """Explain weak per-seat danger using just legally public board history.

    A seat whose declared missing suit equals the tile's suit cannot win on
    this tile under the current dingque rule (but may still peng when legal).
    Won seats cannot claim again. For other seats a prior same-kind discard is
    only a SMALL negative signal, never Japanese genbutsu or a guaranteed safe
    tile. Late-wall and concentration of revealed melds increase caution.
    """
    if tile not in TILE_INDEX:
        raise ValueError("invalid discard tile")
    own = view.get("seat")
    missing = view.get("missing_suits")
    melds = view.get("melds")
    won = view.get("won")
    if not _is_seat(own) or not isinstance(missing, (list, tuple)) or len(missing) != 4:
        raise ValueError("invalid table reading seat/dingque")
    if not isinstance(melds, (list, tuple)) or len(melds) != 4:
        raise ValueError("invalid public meld seats")
    if not isinstance(won, (list, tuple)) or len(won) != 4:
        raise ValueError("invalid public completion flags")
    if any(s not in SUITS for s in missing):
        raise ValueError("missing suit must be m/s/p")
    discards = view.get("discards", ())
    if not isinstance(discards, (list, tuple)):
        raise ValueError("invalid public discard history")
    wall = view.get("wall_count")
    remaining = wall if type(wall) is int and 0 <= wall <= 108 else 54
    late = remaining <= 24
    critical = remaining <= 12

    by_seat: list[dict[str, Any]] = []
    for seat in range(4):
        if seat == own or bool(won[seat]):
            continue
        if missing[seat] == tile[0]:
            by_seat.append({"seat": seat, "danger": 0.0, "dingque_safe": True})
            continue
        exposed = [
            m.get("tile") for m in melds[seat]
            if isinstance(m, dict) and m.get("tile") in TILE_INDEX
        ]
        # Covered an-gang has no authorized tile kind: count its existence,
        # but NEVER infer which suit or exact tile it hides.
        declared_melds = min(4, len(melds[seat]))
        same_suit_melds = sum(t[0] == tile[0] for t in exposed)
        related = same_suit_melds >= 2 and same_suit_melds == len(exposed)
        own_discards = [
            d["tile"] for d in discards
            if isinstance(d, dict) and d.get("seat") == seat
            and d.get("tile") in TILE_INDEX
        ]
        same_kind_discarded = tile in own_discards
        recent_still_clearing = bool(
            own_discards and own_discards[-1][0] == missing[seat]
            and len(own_discards) >= 2
        )
        # Tiny bounded priors, not calibrated conditional probabilities.
        danger = 0.11 + 0.115 * declared_melds
        if late:
            danger += 0.11
        if critical:
            danger += 0.10
        if related:
            danger += 0.19
        # Public river suit selection: absence of this suit after many cuts
        # weakly suggests retention, not certainty of a flush.
        if len(own_discards) >= 7 and not any(t[0] == tile[0] for t in own_discards):
            danger += 0.045
        if same_kind_discarded:
            danger -= 0.055
        if recent_still_clearing:
            danger -= 0.045
        danger = round(max(0.06, min(0.82, danger)), 5)
        by_seat.append({
            "seat": seat, "danger": danger, "dingque_safe": False,
        })
    total = round(sum(d["danger"] for d in by_seat), 5)
    return {
        "tile": tile, "risk_index": total,
        "active_threats": sum(d["danger"] > 0 for d in by_seat),
        "dingque_safe_seats": sum(d["dingque_safe"] for d in by_seat),
        "by_seat": by_seat,
        "stage": "critical" if critical else "late" if late else "early",
        "model": "public_heuristic_v1",
    }


def discard_survival_factor(tile: str, view: Mapping[str, Any],
                            open_meld_pressure: int = 0) -> float:
    """Bound defensive adjustment to [0.72, 1]; not an estimated win rate."""
    if type(open_meld_pressure) is not int or open_meld_pressure < 0:
        raise ValueError("invalid visible meld pressure")
    report = read_discard_threat(tile, view)
    wall = view.get("wall_count")
    late = type(wall) is int and wall <= 24
    penalty = 0.105 * report["risk_index"] + (
        (0.055 if late else 0.025) * open_meld_pressure
    )
    return round(max(0.72, 1.0 - penalty), 6)
