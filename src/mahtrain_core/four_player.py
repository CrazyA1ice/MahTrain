"""M3 pre-release four-player Sichuan Mahjong opening and turn skeleton.

This is NOT the full blood-battle game.  Claims, wins, melds, payments,
exhaustive draw checks and AI are deliberately absent. In this prototype a
discard creates an explicit unresolved claim window; callers can advance
only by explicitly choosing the *demo-only* all-pass transition. This is not
permitted to represent real claim adjudication.

Tile grammar: m=万, s=条, p=筒; each numbered 1..9 with exactly four copies.
All hands and sealed choices are private to the trusted Python process.
"""
from __future__ import annotations

import random
from collections import Counter
from typing import Any, Sequence

from .presentation import sort_hand
from .rules import SUITS, TILES, is_legal_win

EXCHANGE_OFFSETS = {"clockwise": 1, "counterclockwise": 3, "opposite": 2}
SEAT_COUNT = 4


class FourPlayerOpening:
    """Strict, seeded four-player opening and demo-only turns.

    Phases: exchange_select -> missing_select -> dealer_discard ->
    claim_window -> await_draw -> await_discard -> claim_window ...
    -> wall_exhausted.  The phase after each discard intentionally requires
    an explicit no-claims assertion rather than silently skipping responses.

    No Internet-facing route should grant private_view(seat) access using only
    an unverified, client-provided seat number.
    """

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
        self._exchange_offers: dict[int, tuple[str, ...]] = {}
        self._missing_offers: dict[int, str] = {}
        self.missing_suits: list[str | None] = [None] * SEAT_COUNT
        self._tianque: list[bool] = [False] * SEAT_COUNT
        self.phase = "exchange_select"
        self.turn: int | None = None
        self._pending_discard: dict[str, Any] | None = None
        self._events: list[dict[str, Any]] = []
        self._assert_physical_tiles()

    @staticmethod
    def _seat(seat: int) -> None:
        if type(seat) is not int or not 0 <= seat < SEAT_COUNT:
            raise ValueError("seat must be 0, 1, 2 or 3")

    def _phase(self, required: str) -> None:
        if self.phase != required:
            raise ValueError(f"expected phase {required}; actual {self.phase}")

    def _assert_physical_tiles(self) -> None:
        physical = Counter(self._wall)
        for hand in self._hands:
            physical.update(hand)
        physical.update(item["tile"] for item in self._discards)
        expected = Counter({tile: 4 for tile in TILES})
        if physical != expected:
            raise RuntimeError("physical 108-tile conservation violated")

    def select_exchange(self, seat: int, tiles: Sequence[str]) -> None:
        """Seal exactly three same-suit tiles, transferring only once all 4 seal."""
        self._phase("exchange_select")
        self._seat(seat)
        if seat in self._exchange_offers:
            raise ValueError("exchange selection is already sealed for this seat")
        if type(tiles) not in (list, tuple) or len(tiles) != 3:
            raise ValueError("exchange requires exactly three tile symbols")
        if any(type(tile) is not str or tile not in TILES for tile in tiles):
            raise ValueError("invalid tile for exchange")
        if len({tile[0] for tile in tiles}) != 1:
            raise ValueError("all three exchanged tiles must have one suit")
        if Counter(tiles) - Counter(self._hands[seat]):
            raise ValueError("cannot exchange tiles not owned by seat")
        self._exchange_offers[seat] = tuple(tiles)
        if len(self._exchange_offers) == SEAT_COUNT:
            self._complete_exchange()
        self._assert_physical_tiles()

    def _complete_exchange(self) -> None:
        """Atomic four-way simultaneous transfer, original dealer stays 14."""
        outgoing = {s: list(self._exchange_offers[s]) for s in range(SEAT_COUNT)}
        for seat in range(SEAT_COUNT):
            for tile in outgoing[seat]:
                self._hands[seat].remove(tile)
        offset = EXCHANGE_OFFSETS[self.exchange_direction]
        for seat in range(SEAT_COUNT):
            receiver = (seat + offset) % SEAT_COUNT
            self._hands[receiver].extend(outgoing[seat])
        self._exchange_offers.clear()
        self.phase = "missing_select"
        self._tianque = [
            len({tile[0] for tile in self._hands[seat]}) == 2
            for seat in range(SEAT_COUNT)
        ]
        self._events.append({
            "type": "exchange_complete", "direction": self.exchange_direction
        })
        self._assert_physical_tiles()

    def select_missing(self, seat: int, suit: str) -> None:
        """Seal missing suit only AFTER all 4 transfers; reveal simultaneously."""
        self._phase("missing_select")
        self._seat(seat)
        if seat in self._missing_offers:
            raise ValueError("missing-suit declaration already sealed")
        if type(suit) is not str or suit not in SUITS:
            raise ValueError("missing suit must be m, s or p")
        self._missing_offers[seat] = suit
        if len(self._missing_offers) == SEAT_COUNT:
            self.missing_suits = [
                self._missing_offers[i] for i in range(SEAT_COUNT)
            ]
            self._missing_offers.clear()
            self.phase = "dealer_discard"
            self.turn = self.dealer
            self._events.append({
                "type": "missing_suits_revealed",
                "missing_suits": list(self.missing_suits),
            })
        self._assert_physical_tiles()

    def discard(self, seat: int, tile: str) -> None:
        """Accept only dealer's initial first cut or current player's cut."""
        self._seat(seat)
        if self.phase not in ("dealer_discard", "await_discard"):
            raise ValueError("must be the current player's discard phase")
        if seat != self.turn:
            raise ValueError("only the active turn may discard")
        if type(tile) is not str or tile not in self._hands[seat]:
            raise ValueError("cannot discard a tile absent from own hand")
        if len(self._hands[seat]) != 14:
            raise RuntimeError("current hand must have 14 effective tiles")
        self._hands[seat].remove(tile)
        entry = {"seat": seat, "tile": tile, "index": len(self._discards) + 1}
        self._discards.append(entry)
        self._pending_discard = dict(entry)
        self.phase = "claim_window"
        self._events.append({"type": "discard", **entry})
        self._assert_physical_tiles()

    def pass_all_claims_demo(self) -> None:
        """UNSCORED DEMO ONLY. No win, kong or peng adjudication is performed."""
        self._phase("claim_window")
        if self._pending_discard is None or self.turn is None:
            raise RuntimeError("missing pending discard")
        self._pending_discard = None
        if not self._wall:
            self.phase = "wall_exhausted"
            self.turn = None
        else:
            self.turn = (self.turn + 1) % SEAT_COUNT
            self.phase = "await_draw"
        self._events.append({
            "type": "demo_no_claims",
            "next_turn": self.turn,
        })
        self._assert_physical_tiles()

    def draw(self, seat: int) -> str:
        """Draw from FRONT; dealer must not draw prior to opening discard."""
        self._phase("await_draw")
        self._seat(seat)
        if seat != self.turn:
            raise ValueError("only the current seat may draw")
        if not self._wall:
            raise RuntimeError("empty wall")
        if len(self._hands[seat]) != 13:
            raise RuntimeError("drawer must have 13 effective tiles")
        tile = self._wall.pop(0)
        self._hands[seat].append(tile)
        self.phase = "await_discard"
        # Event log intentionally never reveals the hidden drawn tile.
        self._events.append({"type": "draw", "seat": seat})
        self._assert_physical_tiles()
        return tile  # TRUSTED caller only; do not serve publicly.

    def public_state(self) -> dict[str, Any]:
        """State visible to all seats; no hidden tiles or sealed declarations."""
        return {
            "phase": self.phase,
            "dealer": self.dealer,
            "exchange_direction": self.exchange_direction,
            "exchange_submitted": sorted(self._exchange_offers),
            "missing_submitted": sorted(self._missing_offers),
            "missing_suits": (
                list(self.missing_suits) if self.phase not in
                ("exchange_select", "missing_select") else None
            ),
            "hand_counts": [len(hand) for hand in self._hands],
            "wall_count": len(self._wall),
            "turn": self.turn,
            "pending_discard": (
                dict(self._pending_discard) if self._pending_discard else None
            ),
            "discards": [dict(event) for event in self._discards],
            "events": [dict(event) for event in self._events],
            "prototype_limitations": {
                "claim_resolution": "explicit demo all-pass only",
                "winning_and_scoring": False,
                "ai": False,
            },
        }

    def private_view(self, seat: int) -> dict[str, Any]:
        """TRUSTED in-process use only; a public API needs seat authorization."""
        self._seat(seat)
        view = self.public_state()
        view["seat"] = seat
        view["hand"] = sort_hand(self._hands[seat])
        view["sealed_exchange"] = (
            list(self._exchange_offers[seat])
            if seat in self._exchange_offers else None
        )
        view["sealed_missing"] = self._missing_offers.get(seat)
        view["tianque"] = (
            self._tianque[seat] if self.phase not in
            ("exchange_select",) else None
        )
        view["can_self_draw_win"] = (
            is_legal_win(
                self._hands[seat],
                missing_suit=self.missing_suits[seat],
            ) if self.phase in ("await_discard", "dealer_discard")
            and self.turn == seat else False
        )
        return view

    def debug_tile_counts(self) -> dict[str, Any]:
        """Trusted unit-testing helper; do not expose over HTTP."""
        self._assert_physical_tiles()
        return {"wall": len(self._wall),
                "hands": [len(h) for h in self._hands],
                "discards": len(self._discards), "total": 108}
