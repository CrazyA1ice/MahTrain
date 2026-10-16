"""M3.9 independent shape-only benchmark opponent (not a fourth difficulty).

Uses own-hand counts, suit adjacency and basic public game phases ONLY.
Explicitly does NOT import or call mahtrain_core.efficiency, any shanten
oracle, optimal-discard oracle, hidden wall or opponent concealed cards.
It is an independently specified *rule baseline*, not an external trained AI.
"""
from __future__ import annotations

from collections import Counter
from random import Random
from typing import Any, Mapping

from .rules import SUITS, TILE_INDEX


class ShapeBaselineAgent:
    level = "baseline"

    def __init__(self, *, seed: int, seat: int) -> None:
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError("invalid seed")
        if type(seat) is not int or seat not in range(4):
            raise ValueError("invalid seat")
        self.seat = seat
        self._rng = Random((seed << 7) ^ (seat*237_497 + 599))

    @staticmethod
    def _self(view: Mapping[str, Any]) -> list[str]:
        hand=view["hand"]
        if type(hand) is not list or any(t not in TILE_INDEX for t in hand):
            raise ValueError("baseline requires own concealed hand")
        return hand

    @staticmethod
    def _isolation(tile: str, counts: Counter) -> int:
        """Higher means more useful to keep; completely no shanten logic."""
        suit, number=tile[0],int(tile[1])
        same=counts[tile]
        links=sum(
            counts.get(suit+str(n),0)*(2 if abs(n-number)==1 else 1)
            for n in range(max(1,number-2),min(9,number+2)+1)
            if n!=number
        )
        return (same-1)*5 + links

    def exchange(self, view: Mapping[str, Any]) -> list[str]:
        if view["phase"]!="exchange_select":
            raise ValueError("baseline exchange phase mismatch")
        hand=self._self(view)
        counts=Counter(hand)
        suits={s:[t for t in hand if t[0]==s] for s in SUITS}
        legal=[s for s in SUITS if len(suits[s])>=3]
        if not legal:
            raise ValueError("no legal same-suit triple")
        choice=min(legal,key=lambda s:(len(suits[s]),SUITS.index(s)))
        offered=sorted(suits[choice],key=lambda t:(
            self._isolation(t,counts),TILE_INDEX[t]
        ))
        return offered[:3]

    def missing(self, view: Mapping[str, Any]) -> str:
        if view["phase"]!="missing_select":
            raise ValueError("baseline missing-suit phase mismatch")
        counts=Counter(t[0] for t in self._self(view))
        return min(SUITS,key=lambda s:(counts[s],SUITS.index(s)))

    def response(self, view: Mapping[str, Any], *, rob: bool = False) -> str:
        expected="rob_kong_window" if rob else "claim_window"
        if view["phase"]!=expected:
            raise ValueError("baseline claim phase mismatch")
        options=view["rob_options"] if rob else view["claim_options"]
        if not options:
            raise ValueError("no legal response options")
        # An intentionally simple, transparent control policy: always
        # accept a verified win, otherwise pass on all claims.
        return "hu" if "hu" in options else "pass"

    def kong(self, view: Mapping[str, Any]) -> dict[str,str] | None:
        # Baseline declines all kongs: no optimistic tail-draw reasoning.
        if view["phase"] not in ("dealer_discard","await_discard"):
            raise ValueError("baseline kong phase mismatch")
        return None

    def discard(self, view: Mapping[str, Any]) -> str:
        if view["phase"] not in ("dealer_discard","await_discard"):
            raise ValueError("baseline discard phase mismatch")
        hand=self._self(view)
        if len(hand)+3*len(view["own_melds"])!=14:
            raise ValueError("not 14 effective tiles")
        missing=view["missing_suits"][view["seat"]]
        if missing not in SUITS:
            raise ValueError("missing suit not declared")
        choices=sorted(set(t for t in hand if t[0]==missing),key=TILE_INDEX.get)
        if not choices:
            choices=sorted(set(hand),key=TILE_INDEX.get)
        counts=Counter(hand)
        lowest=min(self._isolation(t,counts) for t in choices)
        tied=[t for t in choices if self._isolation(t,counts)==lowest]
        return self._rng.choice(tied)

    def policy_description(self) -> str:
        return ("独立牌形基线：优先打缺门；其余按自己同牌/邻牌数量"
                "丢最孤立牌，胡必胡、其他碰杠均过；不调用向听或有效进张评估器")
