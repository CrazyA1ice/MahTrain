"""Auditable win-only zero-sum ledger for M3.2.

The ledger does NOT pretend that kong payments, voided kong settlements,
exhaustive-draw transfers, account currencies or finalized house parameters
are already defined. Amounts here represent verified HU payments in
*room-coefficient units*, not cash or a production-room economy.
"""
from __future__ import annotations

from typing import Any, Mapping


SELF_DRAW_MODES = frozenset(("legacy", "add_base", "add_fan"))


def payer_multiplier(kind: str, multiplier: int, mode: str) -> int:
    """For a self draw, add one base unit or double the capped fan multiple."""
    if mode not in SELF_DRAW_MODES:
        raise ValueError("unknown self-draw settlement mode")
    if kind == "self_draw":
        if mode == "add_base":
            return multiplier + 1
        if mode == "add_fan":
            return multiplier * 2
    return multiplier


class WinLedger:
    def __init__(self, room_coefficient: int = 100, fan_cap: int = 3,
                 self_draw_mode: str = "legacy") -> None:
        if type(room_coefficient) is not int or room_coefficient <= 0:
            raise ValueError("room_coefficient must be a positive integer")
        if type(fan_cap) is not int or not 0 <= fan_cap <= 12:
            raise ValueError("fan_cap must be an integer 0..12")
        if type(self_draw_mode) is not str or self_draw_mode not in SELF_DRAW_MODES:
            raise ValueError("self_draw_mode must be legacy, add_base or add_fan")
        self.room_coefficient = room_coefficient
        self.fan_cap = fan_cap
        self.self_draw_mode = self_draw_mode
        self._balances = [0, 0, 0, 0]
        self._entries: list[dict[str, Any]] = []
        self._settlements: list[dict[str, Any]] = []

    def pay_win(
        self,
        *, winner: int, payers: list[int], score: Mapping[str, Any],
        kind: str, source: int, tile: str,
    ) -> dict[str, Any]:
        """Write verified win payments atomically after game-level adjudication."""
        if not score.get("legal"):
            raise ValueError("cannot settle an illegal win")
        if kind not in ("self_draw", "ron", "rob_kong"):
            raise ValueError("unknown win kind")
        if type(winner) is not int or not 0 <= winner < 4:
            raise ValueError("invalid winner")
        if type(source) is not int or not 0 <= source < 4:
            raise ValueError("invalid source")
        if not payers or len(set(payers)) != len(payers) or any(
            type(s) is not int or not 0 <= s < 4 or s == winner for s in payers
        ):
            raise ValueError("invalid/duplicate payer seats")
        if kind != "self_draw" and (source == winner or payers != [source]):
            raise ValueError("discard/rob kong must be paid by source alone")
        if kind == "self_draw" and source != winner:
            raise ValueError("self draw must cite the winner as source")
        raw = score["raw_fan"]
        cap = score["effective_fan"]
        if type(raw) is not int or type(cap) is not int or (
            cap != min(raw, self.fan_cap)
        ) or score["multiplier"] != 2**cap:
            raise ValueError("score does not match capped scoring rules")
        unit = self.room_coefficient * payer_multiplier(
            kind, score["multiplier"], self.self_draw_mode
        )
        record = {
            "kind": kind, "winner": winner, "source": source, "tile": tile,
            "main_pattern": score["main_pattern"],
            "raw_fan": raw, "effective_fan": cap,
            "multiplier": score["multiplier"],
            "self_draw_mode": self.self_draw_mode,
            "room_coefficient": self.room_coefficient,
            "amount_per_payer": unit, "total_received": unit * len(payers),
            "payers": list(payers),
            "combinations": dict(score["combinations"]),
            "bonuses": dict(score["bonuses"]),
        }
        for payer in payers:
            self._balances[payer] -= unit
            self._balances[winner] += unit
            self._entries.append({
                "index": len(self._entries) + 1, "kind": kind,
                "winner": winner, "payer": payer, "source": source,
                "tile": tile, "amount": unit,
                "raw_fan": raw, "effective_fan": cap,
                "multiplier": score["multiplier"],
            })
        self._settlements.append(record)
        assert sum(self._balances) == 0
        return dict(record)

    def public_state(self) -> dict[str, Any]:
        return {
            "balances": list(self._balances),
            "entries": [dict(e) for e in self._entries],
            "wins": [dict(e) for e in self._settlements],
            "room_coefficient": self.room_coefficient,
            "fan_cap": self.fan_cap,
            "self_draw_mode": self.self_draw_mode,
            "zero_sum": sum(self._balances) == 0,
            "coverage": "verified_win_payments_only",
            "kong_payments_posted": False,
            "exhaustive_draw_payments_posted": False,
        }
