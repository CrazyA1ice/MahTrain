"""M3.1 four-seat Sichuan Mahjong claim & kong state machine (no payments/AI).

Rule subset: 108 physical tiles, dealer 14, sealed exchange/dingque, discard
HU (multi-ron) > ming-gang > peng, nearest-seat tie break, concealed/supplement
kongs, robbing supplement kongs, tail draws and winner retirement.
Unconfirmed fan/payment, discard restrictions, tian-ting life cycle and wall
exhaustion inspection are NOT silently assumed.

Only trusted callers may use private_view(seat); HTTP must authorize a seat.
"""
from __future__ import annotations

import random
from collections import Counter
from typing import Any, Sequence

from .presentation import sort_hand
from .rules import SUITS, TILES, is_legal_win

EXCHANGE_OFFSETS = {"clockwise": 1, "counterclockwise": 3, "opposite": 2}
SEAT_COUNT = 4
_KONG_TYPES = ("ming_gang", "an_gang", "bu_gang")


class FourPlayerOpening:
    def __init__(self, seed: int) -> None:
        if type(seed) is not int or not 0 <= seed <= 2**64 - 1:
            raise ValueError("seed must be an integer from 0 to 2^64 - 1")
        rng = random.Random(seed)
        deck = [tile for tile in TILES for _ in range(4)]
        rng.shuffle(deck)
        self.dealer = rng.randrange(SEAT_COUNT)
        self.exchange_direction = rng.choice(tuple(EXCHANGE_OFFSETS))
        self._hands: list[list[str]] = [[], [], [], []]
        offset = 0
        for seat in range(SEAT_COUNT):
            size = 14 if seat == self.dealer else 13
            self._hands[seat] = list(deck[offset:offset + size])
            offset += size
        self._wall = list(deck[offset:])
        self._discards: list[dict[str, Any]] = []
        self._melds: list[list[dict[str, str]]] = [[] for _ in range(4)]
        self._won: list[bool] = [False] * 4
        self._winners: list[dict[str, Any]] = []
        self._exchange_offers: dict[int, tuple[str, ...]] = {}
        self._missing_offers: dict[int, str] = {}
        self.missing_suits: list[str | None] = [None] * 4
        self._tianque = [False] * 4
        self.phase = "exchange_select"
        self.turn: int | None = None
        self._pending_discard: dict[str, Any] | None = None
        self._responses: dict[int, str] = {}
        self._pending_kong: dict[str, Any] | None = None
        self._events: list[dict[str, Any]] = []
        self._assert_physical_tiles()

    @staticmethod
    def _seat(seat: int) -> None:
        if type(seat) is not int or not 0 <= seat < 4:
            raise ValueError("seat must be 0, 1, 2 or 3")

    def _phase(self, expected: str) -> None:
        if self.phase != expected:
            raise ValueError(f"expected phase {expected}; actual {self.phase}")

    def _assert_physical_tiles(self) -> None:
        physical = Counter(self._wall)
        for seat in range(4):
            physical.update(self._hands[seat])
            for meld in self._melds[seat]:
                physical.update([meld["tile"]] * (
                    4 if meld["type"] in _KONG_TYPES else 3
                ))
        physical.update(item["tile"] for item in self._discards
                        if not item.get("claimed_by") and not item.get("robbed"))
        if physical != Counter({tile: 4 for tile in TILES}):
            raise RuntimeError("physical 108-tile conservation violated")

    def select_exchange(self, seat: int, tiles: Sequence[str]) -> None:
        self._phase("exchange_select")
        self._seat(seat)
        if seat in self._exchange_offers:
            raise ValueError("exchange selection already sealed")
        if type(tiles) not in (list, tuple) or len(tiles) != 3:
            raise ValueError("exchange requires exactly three tiles")
        if any(type(t) is not str or t not in TILES for t in tiles):
            raise ValueError("invalid exchange tile")
        if len({t[0] for t in tiles}) != 1:
            raise ValueError("three exchange tiles must have one suit")
        if Counter(tiles) - Counter(self._hands[seat]):
            raise ValueError("cannot exchange cards you do not own")
        self._exchange_offers[seat] = tuple(tiles)
        if len(self._exchange_offers) == 4:
            outgoing = {s: list(self._exchange_offers[s]) for s in range(4)}
            for s in range(4):
                for tile in outgoing[s]:
                    self._hands[s].remove(tile)
            for s in range(4):
                self._hands[(s + EXCHANGE_OFFSETS[self.exchange_direction]) % 4].extend(
                    outgoing[s]
                )
            self._exchange_offers.clear()
            self._tianque = [
                len({t[0] for t in hand}) == 2 for hand in self._hands
            ]
            self.phase = "missing_select"
            self._events.append({"type": "exchange_complete",
                                 "direction": self.exchange_direction})
        self._assert_physical_tiles()

    def select_missing(self, seat: int, suit: str) -> None:
        self._phase("missing_select")
        self._seat(seat)
        if seat in self._missing_offers:
            raise ValueError("missing-suit declaration already sealed")
        if type(suit) is not str or suit not in SUITS:
            raise ValueError("missing suit must be m, s or p")
        self._missing_offers[seat] = suit
        if len(self._missing_offers) == 4:
            self.missing_suits = [self._missing_offers[s] for s in range(4)]
            self._missing_offers.clear()
            self.phase = "dealer_discard"
            self.turn = self.dealer
            self._events.append({"type": "missing_suits_revealed",
                                 "missing_suits": list(self.missing_suits)})
        self._assert_physical_tiles()

    def _active(self, seat: int) -> bool:
        return not self._won[seat]

    def _next_active(self, after: int) -> int | None:
        for i in range(1, 4):
            candidate = (after + i) % 4
            if not self._won[candidate]:
                return candidate
        return None

    def _continue_after(self, seat: int) -> None:
        if sum(self._won) >= 3:
            self.phase = "finished"
            self.turn = None
        elif not self._wall:
            self.phase = "wall_exhausted"
            self.turn = None
        else:
            self.turn = self._next_active(seat)
            self.phase = "await_draw"

    def _check_turn(self, seat: int) -> None:
        self._seat(seat)
        if seat != self.turn or not self._active(seat):
            raise ValueError("not an active seat's turn")

    def _effective(self, seat: int) -> int:
        return len(self._hands[seat]) + 3 * len(self._melds[seat])

    def _self_win(self, seat: int) -> bool:
        return is_legal_win(self._hands[seat], self._melds[seat],
                            self.missing_suits[seat])

    def discard(self, seat: int, tile: str) -> None:
        if self.phase not in ("dealer_discard", "await_discard"):
            raise ValueError("must first reach a discard phase")
        self._check_turn(seat)
        if type(tile) is not str or tile not in self._hands[seat]:
            raise ValueError("tile not in concealed hand")
        if self._effective(seat) != 14:
            raise RuntimeError("discard requires 14 effective tiles")
        self._hands[seat].remove(tile)
        entry = {"seat": seat, "tile": tile, "index": len(self._discards) + 1}
        self._discards.append(entry)
        self._pending_discard = dict(entry)
        self._responses.clear()
        self.phase = "claim_window"
        self._events.append({"type": "discard", **entry})
        self._assert_physical_tiles()

    def claim_options(self, seat: int) -> list[str]:
        """One player's possible legal responses, no opponent hand disclosure."""
        self._phase("claim_window")
        self._seat(seat)
        entry = self._pending_discard
        if entry is None or seat == entry["seat"] or self._won[seat]:
            return []
        tile = entry["tile"]
        hand = self._hands[seat]
        actions = ["pass"]
        if is_legal_win([*hand, tile], self._melds[seat],
                        self.missing_suits[seat]):
            actions.append("hu")
        if tile[0] != self.missing_suits[seat]:
            if hand.count(tile) >= 2:
                actions.append("peng")
            if len(self._wall) and hand.count(tile) >= 3:
                actions.append("ming_gang")
        return actions

    def respond_discard(self, seat: int, action: str) -> None:
        self._phase("claim_window")
        self._seat(seat)
        if seat in self._responses:
            raise ValueError("seat has already committed a response")
        options = self.claim_options(seat)
        if type(action) is not str or action not in options:
            raise ValueError("illegal claim action")
        self._responses[seat] = action
        source = self._pending_discard["seat"]
        seats = [s for s in range(4) if s != source and not self._won[s]]
        if all(s in self._responses for s in seats):
            self._resolve_discard()
        self._assert_physical_tiles()

    def _resolve_discard(self) -> None:
        entry = self._pending_discard
        if entry is None:
            raise RuntimeError("missing discard")
        source, tile = entry["seat"], entry["tile"]
        last = self._discards[-1]
        winners = [s for s, action in self._responses.items() if action == "hu"]
        if winners:
            winners.sort(key=lambda s: (s - source) % 4)
            last["won_by"] = list(winners)
            for seat in winners:
                self._won[seat] = True
                self._winners.append({
                    "seat": seat, "source": source, "tile": tile, "kind": "ron"
                })
            self._events.append({"type": "multi_ron" if len(winners)>1 else "ron",
                                 "seats": list(winners), "source": source,
                                 "tile": tile})
            self._pending_discard = None
            self._responses.clear()
            self._continue_after(source)
            return
        claims = [(s,a) for s,a in self._responses.items()
                  if a in ("ming_gang","peng")]
        if claims:
            claims.sort(key=lambda pair: (
                0 if pair[1]=="ming_gang" else 1,
                (pair[0]-source)%4
            ))
            seat,action = claims[0]
            count = 3 if action == "ming_gang" else 2
            for _ in range(count):
                self._hands[seat].remove(tile)
            self._melds[seat].append({"type": action, "tile": tile})
            last["claimed_by"] = seat
            self.turn = seat
            self._pending_discard = None
            self._responses.clear()
            self._events.append({"type": action, "seat": seat,
                                 "source": source, "tile": tile})
            if action == "ming_gang":
                self._supplement(seat)
            else:
                self.phase = "await_discard"
            return
        self._pending_discard = None
        self._responses.clear()
        self._continue_after(source)
        self._events.append({"type": "all_pass", "next_turn": self.turn})

    def _supplement(self, seat: int) -> None:
        if not self._wall:
            raise RuntimeError("cannot supplement an empty wall")
        tile = self._wall.pop()  # TAIL, not the normal front draw.
        self._hands[seat].append(tile)
        self.turn = seat
        self.phase = "await_discard"
        self._events.append({"type": "kong_supplement", "seat": seat})
        # Tail tile remains private to the acting player.

    def kong_options(self, seat: int) -> list[dict[str, str]]:
        if self.phase not in ("dealer_discard", "await_discard"):
            return []
        if seat != self.turn or self._won[seat] or not self._wall:
            return []
        missing = self.missing_suits[seat]
        counts = Counter(self._hands[seat])
        result = [{"type":"an_gang","tile":tile}
                  for tile,count in counts.items()
                  if count==4 and tile[0] != missing]
        result.extend({"type":"bu_gang","tile":meld["tile"]}
                      for meld in self._melds[seat]
                      if meld["type"]=="peng"
                      and counts[meld["tile"]]==1
                      and meld["tile"][0]!=missing)
        return sorted(result,key=lambda m:(m["type"],m["tile"]))

    def declare_kong(self, seat: int, kind: str, tile: str) -> None:
        self._check_turn(seat)
        if self.phase not in ("dealer_discard", "await_discard"):
            raise ValueError("kong requires own discard phase")
        if {"type":kind,"tile":tile} not in self.kong_options(seat):
            raise ValueError("illegal concealed or supplement kong")
        if self._effective(seat)!=14:
            raise RuntimeError("kong requires 14 effective tiles")
        if kind=="an_gang":
            for _ in range(4):
                self._hands[seat].remove(tile)
            self._melds[seat].append({"type":"an_gang","tile":tile})
            self._events.append({"type":"an_gang","seat":seat,"tile":tile})
            self._supplement(seat)
        else:
            # Robbing the added fourth tile MUST be resolved before upgrade.
            self._pending_kong = {"seat":seat,"tile":tile}
            self._responses.clear()
            self.phase = "rob_kong_window"
            self._events.append({"type":"bu_gang_declared","seat":seat,"tile":tile})
        self._assert_physical_tiles()

    def rob_options(self, seat: int) -> list[str]:
        self._phase("rob_kong_window")
        self._seat(seat)
        pending = self._pending_kong
        if pending is None or seat==pending["seat"] or self._won[seat]:
            return []
        actions = ["pass"]
        if is_legal_win([*self._hands[seat],pending["tile"]],
                        self._melds[seat],self.missing_suits[seat]):
            actions.append("hu")
        return actions

    def respond_rob_kong(self, seat: int, action: str) -> None:
        self._phase("rob_kong_window")
        self._seat(seat)
        if seat in self._responses:
            raise ValueError("duplicate rob-kong response")
        if type(action) is not str or action not in self.rob_options(seat):
            raise ValueError("illegal rob-kong response")
        self._responses[seat] = action
        source = self._pending_kong["seat"]
        seats = [s for s in range(4) if s!=source and not self._won[s]]
        if all(s in self._responses for s in seats):
            self._resolve_rob()
        self._assert_physical_tiles()

    def _resolve_rob(self) -> None:
        source,tile = self._pending_kong["seat"],self._pending_kong["tile"]
        winners = [s for s,a in self._responses.items() if a=="hu"]
        winners.sort(key=lambda s:(s-source)%4)
        if winners:
            self._hands[source].remove(tile)
            self._discards.append({"seat":source,"tile":tile,
                                   "index":len(self._discards)+1,
                                   "robbed":True})
            # Robbed physical fourth tile MUST remain conserved:
            # the discard record is a real tile although 'robbed' denotes
            # the supplementary kong was cancelled.
            self._discards[-1].pop("robbed")
            self._discards[-1]["won_by"]=list(winners)
            for seat in winners:
                self._won[seat]=True
                self._winners.append({"seat":seat,"source":source,
                                      "tile":tile,"kind":"rob_kong"})
            self._events.append({"type":"rob_kong",
                                 "seats":list(winners),
                                 "seat":source,"tile":tile})
            self._pending_kong=None
            self._responses.clear()
            self._continue_after(source)
        else:
            self._hands[source].remove(tile)
            meld = next(m for m in self._melds[source]
                        if m["tile"]==tile and m["type"]=="peng")
            meld["type"]="bu_gang"
            self._events.append({"type":"bu_gang",
                                 "seat":source,"tile":tile})
            self._pending_kong=None
            self._responses.clear()
            self._supplement(source)

    def declare_self_win(self, seat: int) -> None:
        if self.phase not in ("dealer_discard","await_discard"):
            raise ValueError("self-draw win requires own discard phase")
        self._check_turn(seat)
        if not self._self_win(seat):
            raise ValueError("not a legal win or missing suit not cleared")
        self._won[seat] = True
        self._winners.append({"seat":seat,"source":seat,
                              "kind":"self_draw"})
        self._events.append({"type":"self_draw_win","seat":seat})
        self._continue_after(seat)
        self._assert_physical_tiles()

    def pass_all_claims_demo(self) -> None:
        """Legacy explicit DEMO skip, NEVER used by the new formal responder."""
        self._phase("claim_window")
        self._pending_discard=None
        self._responses.clear()
        self._continue_after(self.turn)
        self._events.append({"type":"demo_no_claims","next_turn":self.turn})
        self._assert_physical_tiles()

    def draw(self, seat: int) -> str:
        self._phase("await_draw")
        self._check_turn(seat)
        if not self._wall or self._effective(seat)!=13:
            raise RuntimeError("no legal front-wall draw")
        tile = self._wall.pop(0)
        self._hands[seat].append(tile)
        self.phase="await_discard"
        self._events.append({"type":"draw","seat":seat})
        self._assert_physical_tiles()
        return tile

    def public_state(self) -> dict[str, Any]:
        return {
            "phase":self.phase,
            "dealer":self.dealer,
            "exchange_direction":self.exchange_direction,
            "exchange_submitted":sorted(self._exchange_offers),
            "missing_submitted":sorted(self._missing_offers),
            "missing_suits":(None if self.phase in
                ("exchange_select","missing_select") else list(self.missing_suits)),
            "hand_counts":[len(h) for h in self._hands],
            "melds":[[dict(m) for m in groups] for groups in self._melds],
            "won":list(self._won),
            "winners":[dict(w) for w in self._winners],
            "wall_count":len(self._wall),
            "turn":self.turn,
            "pending_discard":(dict(self._pending_discard)
                               if self._pending_discard else None),
            "pending_rob_kong":(dict(self._pending_kong)
                                 if self._pending_kong else None),
            "claim_submitted":sorted(self._responses),
            "discards":[dict(e) for e in self._discards],
            "events":[dict(e) for e in self._events],
            "prototype_limitations":{
                "payments":False,"ai":False,"tian_ting_tracking":False,
                "exhaustive_draw_settlement":False,
            },
        }

    def private_view(self, seat: int) -> dict[str, Any]:
        """Trusted-in-process view ONLY: never allow unverified seat queries."""
        self._seat(seat)
        view=self.public_state()
        view.update({
            "seat":seat,
            "hand":sort_hand(self._hands[seat]),
            "sealed_exchange":list(self._exchange_offers[seat])
                if seat in self._exchange_offers else None,
            "sealed_missing":self._missing_offers.get(seat),
            "tianque":self._tianque[seat]
                if self.phase!="exchange_select" else None,
            "can_self_draw_win":bool(
                self.phase in ("dealer_discard","await_discard")
                and self.turn==seat and not self._won[seat]
                and self._self_win(seat)),
            "kong_options":self.kong_options(seat),
            "claim_options":self.claim_options(seat)
                if self.phase=="claim_window" else [],
            "rob_options":self.rob_options(seat)
                if self.phase=="rob_kong_window" else [],
        })
        return view

    def debug_tile_counts(self) -> dict[str, Any]:
        self._assert_physical_tiles()
        return {"wall":len(self._wall),
                "hands":[len(h) for h in self._hands],
                "discards":sum(not d.get("claimed_by") for d in self._discards),
                "melds":sum(len(m) for m in self._melds),
                "total":108}
