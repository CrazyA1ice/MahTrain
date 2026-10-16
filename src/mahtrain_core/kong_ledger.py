"""M3.3 reversible kong ledger, separate from verified win payments.

Kong base is deliberately independent of the room coefficient.  Without an
explicit base, a kong remains UNPRICED.  If a base is supplied, transactions
are *simulated points*, not a declaration that base == room coefficient.
A void appends exact reversing entries so the audit trail stays intact.
"""
from __future__ import annotations

from typing import Any


class KongLedger:
    def __init__(self, base: int | None = None) -> None:
        if base is not None and (type(base) is not int or not 1 <= base <= 10**6):
            raise ValueError("kong base must be an integer 1..1000000 or null")
        self.base = base
        self._balances = [0] * 4
        self._events: list[dict[str, Any]] = []
        self._entries: list[dict[str, Any]] = []

    @staticmethod
    def _seat(seat: int) -> None:
        if type(seat) is not int or seat not in range(4):
            raise ValueError("invalid seat")

    def declare(self, *, kind: str, winner: int,
                payers: list[int], source: int | None = None) -> int:
        if kind not in ("ming_gang", "an_gang", "bu_gang"):
            raise ValueError("unknown kong type")
        self._seat(winner)
        if source is not None:
            self._seat(source)
        if (kind == "ming_gang" and
            (source is None or payers != [source])) or (
            kind != "ming_gang" and source is not None
        ):
            raise ValueError("invalid kong source/payers")
        if not payers or len(payers) != len(set(payers)) or any(
            type(s) is not int or s not in range(4) or s == winner
            for s in payers
        ):
            raise ValueError("invalid kong payer set")
        factor = 1 if kind == "bu_gang" else 2
        amount = factor * self.base if self.base is not None else None
        event_id = len(self._events) + 1
        self._events.append({
            "id": event_id, "type": kind, "seat": winner, "source": source,
            "payers": list(payers), "amount_per_payer": amount,
            "status": "posted" if amount is not None else "unpriced",
            "reason": ("simulation_using_explicit_kong_base"
                       if amount is not None else "kong_base_not_confirmed"),
        })
        if amount is not None:
            for payer in payers:
                self._post(event_id, payer, winner, amount, "charge")
        return event_id

    def _post(self, event_id: int, payer: int, winner: int,
              amount: int, entry_kind: str) -> None:
        self._balances[payer] -= amount
        self._balances[winner] += amount
        self._entries.append({
            "index": len(self._entries) + 1,
            "kong_id": event_id, "kind": entry_kind,
            "payer": payer, "recipient": winner, "amount": amount,
        })
        assert sum(self._balances) == 0

    def void(self, event_id: int, *, reason: str) -> None:
        if type(event_id) is not int or event_id not in range(1, len(self._events)+1):
            raise ValueError("unknown kong event")
        if reason not in ("kong_discard_ron", "rob_kong"):
            raise ValueError("unverified void reason")
        record = self._events[event_id-1]
        if record["status"] == "voided":
            raise ValueError("kong already voided")
        if record["status"] == "posted":
            amount = record["amount_per_payer"]
            for payer in record["payers"]:
                self._post(event_id, record["seat"], payer, amount, "reversal")
        record["status"] = "voided"
        record["reason"] = reason

    def public_state(self) -> dict[str, Any]:
        return {
            "base": self.base,
            "balances": list(self._balances),
            "events": [{**v, "payers": list(v["payers"])} for v in self._events],
            "entries": [dict(e) for e in self._entries],
            "zero_sum": sum(self._balances) == 0,
            "mode": ("simulated_explicit_base" if self.base is not None
                     else "unpriced"),
        }
