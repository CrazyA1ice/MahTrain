"""M3.4 transparent, reproducible and information-limited Sichuan AI policies.

First-generation heuristic opponents, NOT trained or search-based agents.
They receive only their own server-authorized private_view dictionary and
public board facts; no wall, opponents' concealed hands or opponent W0.

basic:     seeded varied legal cuts / conservative calls.
advanced:  minimum-shanten cuts, only useful peng/ming-gang.
challenge: minimum-shanten, remaining-copy weighted winning score / shape value,
           then calibrated weak public-meld danger. A one-ply EV heuristic,
           not perfect-information or provably optimal full-game search.
All difficulty levels accept verified HU, not speculative or illegal claims.
"""
from __future__ import annotations

import random
from collections import Counter
from typing import Any, Mapping, Sequence

from .efficiency import shanten_13, effective_draws
from .rules import TILE_INDEX, TILES, SUITS, score_win, winning_tiles

AI_LEVELS = ("basic", "advanced", "challenge")
# Evaluation-only controlled variants; not advertised as player difficulty tiers.
ABLATION_VARIANTS = ("challenge_no_ukeire", "challenge_no_pressure")
LABELS = {"basic": "入门", "advanced": "进阶", "challenge": "挑战"}


def _validate_level(level: str) -> None:
    if type(level) is not str or level not in AI_LEVELS:
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


def challenge_discard_scores(view: Mapping[str, Any],
                             cuts: Sequence[str] | None = None,
                             *, use_pressure: bool = True) -> list[dict[str, Any]]:
    """Rank own 14-tile cuts by *public-information* next-draw value.

    This is a bounded one-step heuristic, not a perfect-information oracle:
    unknown physical copies are estimated as uniformly accessible (opponents
    and wall are not inspected). Never regress the minimum post-cut shanten.
    In tenpai, compute the EXACT supported fan for EACH viable winning tile,
    then weight 2**fan by publicly remaining copies. Before tenpai, retain
    ukeire but reward potential seven-pairs, all-pungs and pure-suit structures.
    Conservative public-meld risk adjusts close decisions only.
    """
    hand, melds, missing = _own_view(view)
    if len(hand) + 3 * len(melds) != 14:
        raise ValueError("challenge evaluation requires 14 effective tiles")
    allowed = sorted(set(hand), key=TILE_INDEX.__getitem__)
    forced = [tile for tile in allowed if tile[0] == missing]
    if forced:
        allowed = forced
    if cuts is not None:
        allowed = [tile for tile in allowed if tile in cuts]
    if not allowed:
        raise ValueError("no legal discard to evaluate")
    public = visible_tiles(view)
    cap = view.get("win_ledger", {}).get("fan_cap", 3) if view.get("win_ledger") else 3
    if type(cap) is not int or not 0 <= cap <= 12:
        cap = 3
    tian = view.get("tian_ting") or {}
    verified_tian = tian.get("eligible") is True
    wall_count = view.get("wall_count")
    wall_late = type(wall_count) is int and wall_count <= 24
    result: list[dict[str, Any]] = []
    for tile in allowed:
        after = list(hand)
        after.remove(tile)
        # This tile is now visible. Missing this known fourth copy otherwise
        # biases the effective-copy denominator and expected winning value.
        info = effective_draws(after, melds, missing, [*public, tile])
        ukeire = info["effective_tile_count"]
        expected = float(ukeire)
        value = 1.0
        if info["shanten"] == 0:
            # Tian-ting +2 is valid only if this hypothetical cut preserves
            # exactly the originally verified waiting set (not just tenpai).
            candidate_tian = (verified_tian and
                set(winning_tiles(after, melds, missing)) ==
                set(tian.get("initial_waits", [])))
            expected = 0.0
            for item in info["effective_details"]:
                scoring = score_win(
                    [*after, item["tile"]], melds, missing, cap=cap,
                    context={"tian_ting_verified": candidate_tian},
                )
                expected += item["remaining"] * scoring["multiplier"]
            value = expected / ukeire if ukeire else 0.0
        else:
            own_counts = Counter(after)
            pairs = sum(n // 2 for n in own_counts.values())
            triples = sum(n >= 3 for n in own_counts.values())
            physical = [*after, *(m["tile"] for m in melds for _ in range(3))]
            suit_counts = Counter(t[0] for t in physical)
            dominant = max(suit_counts.values()) / len(physical)
            # These are small calibrated priors, NOT invented fan or
            # a guarantee of eventual completion.
            pure_possible = all(m["tile"][0] == max(suit_counts,
                key=suit_counts.get) for m in melds)
            value += min(0.25, max(0.0, (dominant - 0.70) * .70)) if pure_possible else 0
            value += 0.06 * triples
            if not melds:
                value += 0.08 * max(0, pairs - 3)
            expected *= value
        pressure = public_suit_pressure(tile, view) if use_pressure else 0
        # Opponent open suits are evidence of risk, not proof of tenpai.
        risk_multiplier = max(0.72, 1 - (0.055 if wall_late else 0.025) * pressure)
        result.append({
            "discard": tile,
            "shanten": info["shanten"],
            "effective_tile_count": ukeire,
            "effective_types": len(info["effective_types"]),
            "expected_fan_weighted_copies": round(expected, 5),
            "value_multiplier": round(value, 4),
            "public_pressure": pressure,
            "score": round(expected * risk_multiplier, 5),
        })
    minimum = min(item["shanten"] for item in result)
    return sorted(
        (item for item in result if item["shanten"] == minimum),
        key=lambda item: (-item["score"], -item["effective_tile_count"],
                          TILE_INDEX[item["discard"]]),
    )


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
            # Controlled ablation: remove effective-copy ranking, leaving
            # only the weak PUBLIC exposure tie-break among min-shanten cuts.
            return min(best, key=lambda t: (
                public_suit_pressure(t, view), TILE_INDEX[t],
            ))
        # Challenge keeps all legal minimum-shanten cuts, then trades
        # effective-copy count against expected winning fan or shape potential.
        # The old ablation remains unchanged for comparable prior experiments.
        ranked = challenge_discard_scores(
            view, best, use_pressure=self.level != "challenge_no_pressure"
        )
        # Share this authorized observation with offline instrumentation;
        # never enumerate all candidate draws a second time for telemetry.
        self._last_discard_scores = ranked
        return ranked[0]["discard"]

    def policy_description(self) -> str:
        return {
            "basic":"种子随机的合法切牌，适度尝试碰/暗杠；能胡必胡",
            "advanced":"优先不退向听，仅在牌效提升时主动碰杠",
            "challenge":"保持最少向听，按真实听口剩余张数×封顶番倍率估算收益；非听牌时结合进张、牌型潜力和公开副露风险",
        }[self.level]


class AblationMahjongAgent(MahjongAgent):
    """M3.10 controlled variants: all non-discard behaviors match challenge.

    Not a new public difficulty tier. Keeps identical seed/RNG and opening,
    claim and kong policies so only the designated discard tie-break differs.
    """

    def __init__(self, variant: str, *, seed: int, seat: int) -> None:
        if type(variant) is not str or variant not in ABLATION_VARIANTS:
            raise ValueError("unknown AI ablation variant")
        super().__init__("challenge", seed=seed, seat=seat)
        self.level = variant

    def policy_description(self) -> str:
        return {
            "challenge_no_ukeire": "历史对照：向听优先，移除有效进张排序，仅保留公开副露压力",
            "challenge_no_pressure": "期望收益评分但移除公开副露压力，用于隔离风险项作用",
        }[self.level]
