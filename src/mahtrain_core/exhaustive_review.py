"""Read-only exhaustive-draw check and transparent provisional payment preview.

The *trigger* and flower-pig definition are verified by v0.4. Whether players
who already won participate in payments remains unconfirmed; this preview
deliberately considers ACTIVE seats only and NEVER posts a transaction.
Missing-suit exposed melds remain an explicit unresolved policy edge.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .rules import score_win, winning_tiles



def compare_exhaustive_scopes(
    preview: Mapping[str, Any],
    *, won: Sequence[bool], coefficient: int,
) -> dict[str, Any]:
    """Compare two *unposted* scopes for flower-pig payments.

    Variant A: existing active-only preview.
    Variant B: a flower pig also pays to seats that have already legally won,
    treating them as non-flower-pigs. The da-jiao stage is unchanged because
    already-won players are no longer in the ready/unready comparison.
    Neither variant is an official rule or a mutation of any score ledger.
    """
    if len(won) != 4 or any(type(flag) is not bool for flag in won):
        raise ValueError("scope comparison needs four verified winner flags")
    if type(coefficient) is not int or coefficient <= 0:
        raise ValueError("scope comparison requires a positive room coefficient")
    if not preview.get("triggered") or preview.get("posted") is not False:
        return {"available": False, "posted": False, "scenarios": [],
                "reason": "not_an_unposted_exhaustive_draw"}
    if preview.get("reason") == "unresolved_missing_meld_or_nonstable_hand":
        return {"available": False, "posted": False, "scenarios": [],
                "reason": "unresolved_hand_classification"}
    entries = preview.get("proposed_transfers")
    seats = preview.get("seats")
    active = preview.get("participating_active_seats")
    if not (isinstance(entries, list) and isinstance(seats, list) and
            isinstance(active, list)):
        raise ValueError("malformed exhaustive preview")
    # Only validated, already-known flower pigs may pay in this scenario.
    pigs = [x["seat"] for x in seats
            if x.get("classification") == "flower_pig"]
    winners = [seat for seat in range(4) if won[seat]]
    baseline = [dict(item) for item in entries]
    inclusive = [*baseline]
    for pig in pigs:
        for recipient in winners:
            inclusive.append({
                "stage": "flower_pig", "payer": pig,
                "recipient": recipient, "amount": 8 * coefficient,
            })
    def variant(policy: str, transfers: list[dict]) -> dict:
        balances = [0, 0, 0, 0]
        for payment in transfers:
            amount = payment["amount"]
            balances[payment["payer"]] -= amount
            balances[payment["recipient"]] += amount
        if sum(balances) != 0:
            raise ValueError("exhaustive scope settlement is not zero-sum")
        return {"policy": policy, "transfers": transfers,
                "balances": balances, "zero_sum": True, "posted": False}
    return {
        "available": True, "posted": False,
        "difference": "whether already-won seats also receive flower-pig compensation",
        "scenarios": [
            variant("active_only_preview", baseline),
            variant("won_players_collect_flower_pig_preview", inclusive),
        ],
    }

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
    result = {
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
    result["scope_comparison"] = compare_exhaustive_scopes(
        result, won=won, coefficient=coefficient,
    )
    return result
