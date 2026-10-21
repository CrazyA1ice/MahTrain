"""House rules for the next dealer in a continuing Sichuan match.

Public settled win events only: never inspect private hands, actual wall,
opponent strategy or frontend claims. The dealer for a *fresh* series is
random; for an explicitly continued completed round, use this priority:
1. One-discard-multiple-HU (one cannon hits two or more): discard source.
2. One seat paid the other three distinct winners, including self-draw
   payouts as well as point-discard and robbing-added-kong payouts.
3. The first verified HU winner, in official adjudication order.
4. Wall exhaustion with zero winners: previous dealer holds.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping


def next_dealer(public: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic, explainable dealer selection from a finished board.

    This function is read-only, accepts *public* authoritative outcomes, and
    intentionally never counts kong transfers or exhaustive dajiao as HU
    losses. One payout by self-draw must count only once per actual winner,
    even when a win has multiple payment entries.
    """
    if public.get("phase") not in ("finished", "wall_exhausted"):
        raise ValueError("cannot assign next dealer before round completes")
    current = public.get("dealer")
    if type(current) is not int or not 0 <= current <= 3:
        raise ValueError("invalid previous dealer")
    events = public.get("events") or []
    for event in events:
        if event.get("type") == "multi_ron":
            source, seats = event.get("source"), event.get("seats")
            if (type(source) is int and 0 <= source <= 3
                    and isinstance(seats, list) and len(set(seats)) >= 2
                    and all(type(s) is int and 0 <= s <= 3 and s != source
                            for s in seats)):
                return {"dealer":source, "reason":"multi_ron",
                        "label":"一炮双响，点炮者坐庄"}
    wins = (public.get("win_ledger") or {}).get("wins") or []
    paid_winners: dict[int, set[int]] = defaultdict(set)
    for record in wins:
        winner = record.get("winner")
        if type(winner) is not int or not 0 <= winner <= 3:
            continue
        payers = record.get("payers") or []
        for payer in payers:
            if type(payer) is int and 0 <= payer <= 3 and payer != winner:
                paid_winners[payer].add(winner)
    # In a 4-seat blood battle it is impossible for more than one distinct
    # seat to pay ALL three other winning seats. Explicit seat order gives
    # a stable fallback if supplied a synthetic abnormal result.
    for payer in range(4):
        if len(paid_winners[payer]) == 3:
            return {"dealer":payer, "reason":"lost_to_three",
                    "label":"输三家，下局坐庄"}
    winners = public.get("winners") or []
    for win in winners:
        seat = win.get("seat")
        if type(seat) is int and 0 <= seat <= 3:
            return {"dealer":seat, "reason":"first_hu",
                    "label":"首位胡牌玩家坐庄"}
    return {"dealer":current, "reason":"draw_keep",
            "label":"流局无人胡牌，原庄续庄"}
