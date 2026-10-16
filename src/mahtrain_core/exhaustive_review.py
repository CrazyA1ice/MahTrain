"""Read-only exhaustive-draw check and transparent provisional payment preview.

The *trigger* and flower-pig definition are verified by v0.4. Whether players
who already won participate in payments remains unconfirmed; this preview
deliberately considers ACTIVE seats only and NEVER posts a transaction.
Missing-suit exposed melds remain an explicit unresolved policy edge.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .rules import score_win, winning_tiles


def review_exhaustive_draw(
    *, hands: Sequence[Sequence[str]],
    melds: Sequence[Sequence[Mapping[str, str]]],
    missing_suits: Sequence[str],
    won: Sequence[bool],
    tian_ting: Sequence[Mapping[str, Any]],
    coefficient: int,
    fan_cap: int,
) -> dict[str, Any]:
    if not (len(hands) == len(melds) == len(missing_suits)
            == len(won) == len(tian_ting) == 4):
        raise ValueError("review requires exactly four seats")
    active = [s for s in range(4) if not won[s]]
    if len(active) < 2:
        return {"triggered": False, "reason": "fewer_than_two_active",
                "posted": False, "policy": "active_only_preview"}
    seats: list[dict[str, Any]] = []
    for s in active:
        missing = missing_suits[s]
        concealed_missing = any(t[0] == missing for t in hands[s])
        meld_missing = any(m["tile"][0] == missing for m in melds[s])
        entry: dict[str, Any] = {
            "seat": s,
            "missing_suit": missing,
            "concealed_missing": concealed_missing,
            "exposed_missing": meld_missing,
            "classification": "flower_pig" if concealed_missing else
                "unresolved_exposed_missing" if meld_missing else "unready",
            "wait_count": 0, "max_raw_fan": None, "max_effective_fan": None,
        }
        if not concealed_missing and not meld_missing:
            if len(hands[s]) + 3*len(melds[s]) != 13:
                entry["classification"] = "unresolved_nonstable_hand"
            else:
                waits = winning_tiles(hands[s],melds[s],missing)
                if waits:
                    values = [score_win(
                        [*hands[s],t],melds[s],missing,cap=fan_cap,
                        context={"tian_ting_verified":bool(
                            tian_ting[s]["eligible"]
                        )},
                    ) for t in waits]
                    valid = [x for x in values if x["legal"]]
                    if valid:
                        entry.update({
                            "classification":"listening",
                            "wait_count":len(waits),
                            "max_raw_fan":max(x["raw_fan"] for x in valid),
                            "max_effective_fan":max(
                                x["effective_fan"] for x in valid),
                        })
        seats.append(entry)

    # The "active seats only" model is shown as a preview, not an official
    # interpretation. No transfer goes into WinLedger or KongLedger.
    states = {x["seat"]:x for x in seats}
    uncertain = any(x["classification"].startswith("unresolved")
                    for x in seats)
    transfers: list[dict[str, Any]] = []
    if not uncertain:
        for pig in seats:
            if pig["classification"] == "flower_pig":
                for s in active:
                    if s != pig["seat"] and states[s]["classification"] != "flower_pig":
                        transfers.append({
                            "stage":"flower_pig", "payer":pig["seat"],
                            "recipient":s, "amount":8*coefficient,
                        })
        # Flower pigs cannot participate in the subsequent ready-hand check.
        for unready in seats:
            if unready["classification"] != "unready":
                continue
            for listener in seats:
                if listener["classification"] == "listening":
                    transfers.append({
                        "stage":"da_jiao", "payer":unready["seat"],
                        "recipient":listener["seat"],
                        "amount":coefficient * 2**listener["max_effective_fan"],
                        "effective_fan":listener["max_effective_fan"],
                    })
    return {
        "triggered":True,"posted":False,
        "policy":"active_only_preview",
        "participating_active_seats":active,
        "seats":seats,
        "proposed_transfers":transfers,
        "preview_balances":[
            sum(t["amount"] for t in transfers if t["recipient"]==s) -
            sum(t["amount"] for t in transfers if t["payer"]==s)
            for s in range(4)
        ],
        "reason":("unresolved_missing_meld_or_nonstable_hand" if uncertain
                  else "requires_confirmation_of_settlement_participants"),
        "limitations":[
            "already_won_players_payer_recipient_scope_unconfirmed",
            "exposed_missing_melds_definition_unconfirmed",
            "maximum_fan_ignores_unverified_win_events",
            "no_money_posted",
        ],
    }
