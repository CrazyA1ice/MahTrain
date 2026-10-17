"""Sichuan exhaustive draw inspection and authoritative active-only settlement.

Only players who have NOT won participate in flower-pig / da-jiao charges.
Historical two-scope comparison remains informational. Exposed missing-suit
melds or invalid hand shape block settlement rather than invent a payment.
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

def finalize_active_only(preview: Mapping[str, Any], *, won: Sequence[bool],
                         coefficient: int, fan_cap: int) -> dict[str, Any]:
    """Validate a server-calculated exhaustive preview and post a ONE-SHOT result.

    The caller (the trusted game state machine) must invoke this only on
    transition into wall_exhausted, and store the result. It never posts an
    unverified missing-suit meld or an unconfirmed 14-tile terminal hand.
    """
    if (len(won) != 4 or any(type(x) is not bool for x in won)
            or type(coefficient) is not int or coefficient <= 0
            or type(fan_cap) is not int or not 0 <= fan_cap <= 12):
        raise ValueError("invalid official exhaustive settlement parameters")
    if preview.get("triggered") is not True or preview.get("posted") is not False:
        raise ValueError("requires an unposted, triggered exhaustive review")
    active = [i for i in range(4) if not won[i]]
    if preview.get("participating_active_seats") != active or len(active) < 2:
        raise ValueError("exhaustive settlement participants mismatch")
    base = {
        "policy": "active_only_final", "posted": False,
        "balances": [0, 0, 0, 0], "entries": [],
        "zero_sum": True, "room_coefficient": coefficient,
        "fan_cap": fan_cap,
    }
    classifications = preview.get("seats")
    if not isinstance(classifications, list) or len(classifications) != len(active):
        raise ValueError("invalid terminal seat classifications")
    by_seat = {}
    for item in classifications:
        if not isinstance(item, dict) or type(item.get("seat")) is not int:
            raise ValueError("invalid classified seat")
        seat = item["seat"]
        if seat not in active or seat in by_seat:
            raise ValueError("invalid/duplicate terminal seat")
        by_seat[seat] = item
    if len(by_seat) != len(active):
        raise ValueError("incomplete terminal seat classifications")
    if any(item.get("classification") in (
            "unresolved_exposed_missing", "unresolved_nonstable_hand")
           for item in classifications):
        return {**base, "reason": "unresolved_terminal_hand"}
    labels = {"flower_pig", "listening", "unready"}
    if any(item.get("classification") not in labels for item in classifications):
        raise ValueError("unknown terminal hand classification")
    expected = []
    for payer in active:
        if by_seat[payer]["classification"] == "flower_pig":
            for recipient in active:
                if recipient != payer and by_seat[recipient]["classification"] != "flower_pig":
                    expected.append({"stage": "flower_pig", "payer": payer,
                                     "recipient": recipient, "amount": 8*coefficient})
    for payer in active:
        if by_seat[payer]["classification"] != "unready":
            continue
        for recipient in active:
            ready = by_seat[recipient]
            if ready["classification"] != "listening":
                continue
            fan = ready.get("max_effective_fan")
            if type(fan) is not int or not 0 <= fan <= fan_cap:
                raise ValueError("invalid ready-hand maximum effective fan")
            expected.append({"stage": "da_jiao", "payer": payer,
                             "recipient": recipient,
                             "amount": coefficient * 2**fan, "effective_fan": fan})
    if preview.get("proposed_transfers") != expected:
        raise ValueError("preview and authoritative payment rows disagree")
    balances = [0, 0, 0, 0]
    for transfer in expected:
        balances[transfer["payer"]] -= transfer["amount"]
        balances[transfer["recipient"]] += transfer["amount"]
    if sum(balances) or preview.get("preview_balances") != balances:
        raise ValueError("exhaustive payments are not zero-sum / preview mismatch")
    return {**base, "posted": True, "reason": "settled",
            "balances": balances,
            "entries": [{**entry, "index": i+1} for i, entry in enumerate(expected)]}


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
