"""M3.4 transparent, reproducible and information-limited Sichuan AI policies.

First-generation heuristic opponents, NOT trained or search-based agents.
They receive only their own server-authorized private_view dictionary and
public board facts; no wall, opponents' concealed hands or opponent W0.

basic:     seeded varied legal cuts / conservative calls.
advanced:  minimum-shanten cuts, only useful peng/ming-gang.
challenge: minimum-shanten, public ukeire, then weak open-meld pressure ties.
All difficulty levels accept verified HU, not speculative or illegal claims.
"""
from __future__ import annotations

import random
from collections import Counter
from typing import Any, Mapping, Sequence

from .efficiency import shanten_13, analyze_discards
from .rules import TILE_INDEX, TILES, SUITS

AI_LEVELS = ("basic", "advanced", "challenge")
# Experimental variants are excluded from normal game difficulty selection.
ABLATION_LEVELS = ("challenge_no_ukeire", "challenge_no_risk")
LABELS = {"basic": "入门", "advanced": "进阶", "challenge": "挑战"}


def _validate_level(level: str) -> None:
    if type(level) is not str or level not in (*AI_LEVELS, *ABLATION_LEVELS):
        raise ValueError("AI difficulty must be basic, advanced or challenge")


def _own_view(view: Mapping[str, Any]) -> tuple[list[str], list[dict[str, str]], str]:
    """No game object dependency: callers can audit everything AI is given."""
    hand = view["hand"]
    melds = view["own_melds"]
    missing = view["missing_suits"][view["seat"]]
    if type(hand) is not list or missing not in SUITS:
        raise ValueError("AI requires its own valid post-dingque hand view")
    return hand, melds, missing


def visible_tiles(view: Mapping[str, Any]) -> list[str]:
    """Only known PUBLIC physical tiles, with no claimed-discard double count.

    An-gang is publicly redacted. Own melds are already validated separately
    by shanten/effective-draws, hence must not be counted twice here.
    """
    own = view["seat"]
    visible = [
        e["tile"] for e in view["discards"]
        if "claimed_by" not in e
    ]
    for seat, groups in enumerate(view["melds"]):
        if seat == own:
            continue
        for meld in groups:
            tile = meld["tile"]
            if tile is not None:
                visible.extend([tile] * (3 if meld["type"] == "peng" else 4))
    return visible


def public_suit_pressure(tile: str, view: Mapping[str, Any]) -> int:
    """Weak OPEN-MELD exposure heuristic, never an absolute safe-tile claim.

    When another active seat openly holds >=2 melds all in one suit, it
    *might* be building a suit-focused hand. Only break exact shanten/ukeire
    ties with this signal. No hidden hand or future draw is consulted.
    """
    if tile not in TILE_INDEX:
        raise ValueError("unknown tile")
    pressure=0
    own=view["seat"]
    for seat, groups in enumerate(view["melds"]):
        if seat==own or view["won"][seat]:
            continue
        if view["missing_suits"][seat]==tile[0]:
            continue
        public_suits=[
            m["tile"][0] for m in groups
            if m.get("tile") in TILE_INDEX
        ]
        if len(public_suits)>=2 and set(public_suits)=={tile[0]}:
            pressure+=len(public_suits)-1
    return pressure


def _cut_shanten(hand: Sequence[str], melds: Sequence[Mapping[str, str]],
                 missing: str, discard: str) -> int:
    after = list(hand)
    after.remove(discard)
    return shanten_13(after, melds, missing)


class MahjongAgent:
    """Per-seat stateful seeded RNG; no access to any hidden game object."""

    def __init__(self, level: str, *, seed: int, seat: int) -> None:
        _validate_level(level)
        if type(seed) is not int or type(seat) is not int or seat not in range(4):
            raise ValueError("invalid reproducible AI seed / seat")
        self.level = level
        self.seat = seat
        self._rng = random.Random((seed << 5) ^ (seat * 987_653 + 41))

    def exchange(self, view: Mapping[str, Any]) -> list[str]:
        if view["phase"] != "exchange_select":
            raise ValueError("AI exchange requires opening phase")
        hand = list(view["hand"])
        suits = {s: [t for t in hand if t.startswith(s)] for s in SUITS}
        eligible = [s for s in SUITS if len(suits[s]) >= 3]
        if not eligible:
            raise ValueError("no legal three-suit exchange")
        if self.level == "basic":
            suit = self._rng.choice(eligible)
            candidates = suits[suit][:]
            self._rng.shuffle(candidates)
            return candidates[:3]
        # Minimize same-suit cards left behind. A rare suit is a sensible
        # early dingque target when the incoming three tiles remain unseen.
        count = min(len(suits[s]) for s in eligible)
        suit = min((s for s in eligible if len(suits[s]) == count),
                   key=SUITS.index)
        # Avoid handing over obvious triplet strength unless forced; pick
        # singletons first, then pairs / triplets as needed.
        counts = Counter(suits[suit])
        return sorted(suits[suit],
                      key=lambda t: (counts[t], -TILE_INDEX[t]))[:3]

    def missing(self, view: Mapping[str, Any]) -> str:
        if view["phase"] != "missing_select":
            raise ValueError("AI dingque requires post-exchange hand")
        counts = Counter(t[0] for t in view["hand"])
        minimum = min(counts[s] for s in SUITS)
        choices = [s for s in SUITS if counts[s] == minimum]
        if self.level == "basic":
            return self._rng.choice(choices)
        return choices[0]

    def response(self, view: Mapping[str, Any], *, rob: bool = False) -> str:
        if view["phase"] != ("rob_kong_window" if rob else "claim_window"):
            raise ValueError("AI response phase mismatch")
        options = view["rob_options"] if rob else view["claim_options"]
        if not options:
            raise ValueError("AI has no eligible claim decision")
        if "hu" in options:
            return "hu"
        if rob:
            return "pass"
        if self.level == "basic":
            return "peng" if "peng" in options and self._rng.random() < .35 else "pass"
        hand, melds, missing = _own_view(view)
        target = view["pending_discard"]["tile"]
        before = shanten_13(hand, melds, missing)
        if "ming_gang" in options:
            remainder = list(hand)
            for _ in range(3):
                remainder.remove(target)
            after = shanten_13(
                remainder,[*melds,{"type":"ming_gang","tile":target}],missing
            )
            if after <= before:
                return "ming_gang"
        if "peng" in options:
            if view.get("tian_ting", {}).get("eligible"):
                return "pass"  # Do not throw away a verified 2-fan bonus.
            remainder = list(hand)
            for _ in range(2):
                remainder.remove(target)
            next_melds = [*melds,{"type":"peng","tile":target}]
            best = min(
                _cut_shanten(remainder,next_melds,missing,cut)
                for cut in set(remainder)
            )
            if best < before:
                return "peng"
        return "pass"

    def kong(self, view: Mapping[str, Any]) -> dict[str, str] | None:
        choices = view["kong_options"]
        if not choices:
            return None
        if self.level == "basic":
            return self._rng.choice(choices) if self._rng.random() < .60 else None
        hand, melds, missing = _own_view(view)
        # Evaluate post-kong 13-effective tiles, before unknown tail draw.
        baseline = min(_cut_shanten(hand, melds, missing, t)
                       for t in set(hand))
        for option in choices:
            tile, kind = option["tile"], option["type"]
            after = list(hand)
            additional = [dict(m) for m in melds]
            if kind == "an_gang":
                for _ in range(4):
                    after.remove(tile)
                additional.append({"type":"an_gang","tile":tile})
            else:
                after.remove(tile)
                additional = [
                    {"type":("bu_gang" if m["type"]=="peng" and m["tile"]==tile
                             else m["type"]), "tile":m["tile"]}
                    for m in additional
                ]
            if shanten_13(after, additional, missing) <= baseline:
                return dict(option)
        return None

    def discard(self, view: Mapping[str, Any]) -> str:
        hand, melds, missing = _own_view(view)
        if view["phase"] not in ("await_discard","dealer_discard"):
            raise ValueError("AI discard requires own discard phase")
        if len(hand) + 3 * len(melds) != 14:
            raise ValueError("not a legal 14-effective-tile discard hand")
        cuts = sorted(set(hand),key=TILE_INDEX.__getitem__)
        forced = [t for t in cuts if t.startswith(missing)]
        if forced:
            # Missing-suit-priority is a deliberate POLICY heuristic, not
            # assertion of an as-yet-unconfirmed mandatory discard rule.
            cuts = forced
        if self.level == "basic":
            return self._rng.choice(cuts)
        scored = [(t, _cut_shanten(hand,melds,missing,t)) for t in cuts]
        minimum = min(score for _,score in scored)
        best = [t for t,s in scored if s == minimum]
        if self.level == "advanced" or len(best) == 1:
            return best[0]
        if self.level == "challenge_no_ukeire":
            # Remove public effective-draw ranking, retain open-meld pressure.
            # No analyze_discards oracle is called in this ablated policy.
            return min(best, key=lambda t:(
                public_suit_pressure(t, view), TILE_INDEX[t]
            ))
        # Challenge / no-risk ablation: public effective copies.
        # analyze_discards validates known physical counts and uses NO wall.
        ranked = analyze_discards(
            hand, melds, missing_suit=missing,
            visible_tiles=visible_tiles(view),
        )
        candidates = {
            entry["discard"]: entry for entry in ranked["candidates"]
        }
        return min(best,key=lambda t:(
            -candidates[t]["effective_tile_count"],
            (0 if self.level == "challenge_no_risk" else
             public_suit_pressure(t,view)),
            TILE_INDEX[t],
        ))

    def policy_description(self) -> str:
        return {
            "basic":"种子随机的合法切牌，适度尝试碰/暗杠；能胡必胡",
            "advanced":"优先不退向听，仅在牌效提升时主动碰杠",
            "challenge":"向听及公开有效进张优先；完全相同时以公开副露花色压力做弱风险判别",
            "challenge_no_ukeire":"消融公开进张排序：向听优先、公开副露压力作平局排序",
            "challenge_no_risk":"消融弱风险项：向听和公开进张优先，完全并列按牌序",
        }[self.level]
