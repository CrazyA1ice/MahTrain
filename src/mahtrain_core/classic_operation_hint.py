"""Authorized, public-information action advice for Sichuan call / kong / Hu.

Read ONLY private_view(seat) and public tiles. Never assume a future draw,
opponent hidden hand or guaranteed net score for a kong/peng. This explains
the existing challenge-tier bounded outlook rather than claiming perfect EV.
The caller chooses whether to follow the reference; this module never acts.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .ai import (
    _call_outlook, _call_settings, _challenge_claim, _challenge_kong,
    _cut_shanten, _outlook_better_than_baseline, _own_view,
)
from .rules import TILE_INDEX

_TURNS = ("dealer_discard", "await_discard")
_CLAIMS = ("claim_window", "rob_kong_window")


def _summary(action: str, label: str, outlook: Mapping[str, Any] | None,
             *, tile: str | None = None, reason: str = "") -> dict[str, Any]:
    return {
        "action": action, "tile": tile, "label": label,
        "shanten": (outlook["shanten"] if outlook else None),
        "effective_copies": (outlook["ukeire"] if outlook else None),
        "fan_weighted": (outlook["value"] if outlook else None),
        "reason": reason, "reference_best": False,
    }


def _best_post_peng(hand: list[str], melds: list[dict],
                    missing: str, target: str, public: list[str],
                    cap: int, tian: Mapping[str, Any]) -> dict[str, Any]:
    remainder = list(hand)
    for _ in range(2):
        remainder.remove(target)
    exposed = [*melds, {"type": "peng", "tile": target}]
    allowed = sorted(set(remainder), key=TILE_INDEX.__getitem__)
    forced = [t for t in allowed if t[0] == missing]
    if forced:
        allowed = forced
    if not allowed:
        raise ValueError("peng has no legal follow-up cut")
    outlooks = []
    for discard in allowed:
        after = list(remainder)
        after.remove(discard)
        outcome = _call_outlook(
            after, exposed, missing, [*public, discard], cap, tian)
        outlooks.append((outcome, discard))
    outcome, cut = min(outlooks, key=lambda x: (
        x[0]["shanten"], -x[0]["value"], -x[0]["ukeire"],
        TILE_INDEX[x[1]],
    ))
    return {**outcome, "next_discard": cut}


def _best_post_discard(hand: list[str], melds: list[dict],
                       missing: str, public: list[str], cap: int,
                       tian: Mapping[str, Any]) -> dict[str, Any]:
    allowed = sorted(set(hand), key=TILE_INDEX.__getitem__)
    forced = [t for t in allowed if t[0] == missing]
    if forced:
        allowed = forced
    if not allowed:
        raise ValueError("no legal cut after declining kong")
    results = []
    for discard in allowed:
        after = list(hand)
        after.remove(discard)
        info = _call_outlook(after, melds, missing,
                             [*public, discard], cap, tian)
        results.append((info, discard))
    return min(results, key=lambda x: (
        x[0]["shanten"], -x[0]["value"], -x[0]["ukeire"],
        TILE_INDEX[x[1]],
    ))[0]


def classic_operation_hint(view: Mapping[str, Any], seat: int) -> dict[str, Any]:
    """Explain each legal action at this seat's CURRENT decision window.

    A Hu recommendation is a server-confirmed immediate score opportunity,
    not a claim that declining it can never improve eventual match payoff.
    Other action preferences mirror current challenge bounded-call heuristics.
    """
    if (type(seat) is not int or seat not in range(4) or
            view.get("seat") != seat):
        raise ValueError("operation hint requires the acting seat's private view")
    phase = view.get("phase")
    if phase not in (*_CLAIMS, *_TURNS):
        raise ValueError("no current operation window")
    hand, melds, missing = _own_view(view)
    public, cap, tian = _call_settings(view)
    rows: list[dict[str, Any]] = []

    if phase in _CLAIMS:
        if seat in (view.get("claim_submitted") or []):
            raise ValueError("operation response was already submitted")
        rob = phase == "rob_kong_window"
        options = view.get("rob_options" if rob else "claim_options") or []
        target_obj = view.get("pending_rob_kong" if rob else "pending_discard")
        if not isinstance(target_obj, dict) or target_obj.get("seat") == seat:
            raise ValueError("no actionable opponent tile")
        if not isinstance(options, list) or len(options) < 2 or "pass" not in options:
            raise ValueError("there are no optional legal responses")
        target = target_obj["tile"]
        before = _call_outlook(hand, melds, missing, public, cap, tian)
        rows.append(_summary(
            "pass", "过", before,
            reason="保留现有手牌结构；没有立即取得碰杠得分"))
        if "hu" in options:
            rows.append(_summary(
                "hu", "抢杠胡" if rob else "胡", None,
                reason="规则引擎已确认合法胡牌，可立即进入正式结算"))
        if not rob and any(x in options for x in ("peng", "ming_gang")):
            exposed_public = list(public)
            # The pending discard already belongs to the PUBLIC river; after
            # taking it into an exposed meld, it must no longer be counted as
            # a separate visible tile in the hypothetical outcome.
            exposed_public.remove(target)
            if "peng" in options:
                # Real peng irrevocably cancels Tian Ting. Do not score
                # a hypothetical after-peng wait as still earning its bonus.
                after = _best_post_peng(
                    hand, melds, missing, target, exposed_public, cap,
                    {"eligible": False} if tian.get("eligible") else tian)
                rows.append(_summary(
                    "peng", "碰", after,
                    reason=("预计碰后优先切" + after["next_discard"] +
                            "；需比较向听及有效进张，碰会取消已验证天听")))
            if "ming_gang" in options:
                rem = list(hand)
                for _ in range(3):
                    rem.remove(target)
                after = _call_outlook(
                    rem, [*melds, {"type": "ming_gang", "tile": target}],
                    missing, exposed_public, cap, tian)
                rows.append(_summary(
                    "ming_gang", "明杠", after,
                    reason="若实际生效将尾部补牌并按规则结杠钱；补牌未知"))
        recommended = (
            "hu" if "hu" in options else _challenge_claim(view)
        )
        selected = (recommended, None)
    else:
        if view.get("turn") != seat or view.get("won", [False]*4)[seat]:
            raise ValueError("not this seat's active turn")
        options = view.get("kong_options") or []
        winning = view.get("can_self_draw_win") is True
        if not options and not winning:
            raise ValueError("no optional self-turn operation")
        before = _best_post_discard(hand, melds, missing, public, cap, tian)
        rows.append(_summary(
            "pass", "暂不杠，继续出牌", before,
            reason="假设优先选择当前最优合法切牌，保留公开信息下的有效进张"))
        if winning:
            rows.append(_summary(
                "hu", "自摸胡", None,
                reason="规则引擎已确认合法自摸，可以立即结算当前所得"))
        for choice in options:
            after = list(hand)
            extra = [dict(m) for m in melds]
            tile, kind = choice["tile"], choice["type"]
            if kind == "an_gang":
                for _ in range(4):
                    after.remove(tile)
                extra.append({"type": "an_gang", "tile": tile})
            elif kind == "bu_gang":
                after.remove(tile)
                extra = [
                    {"type": ("bu_gang" if m["type"] == "peng"
                              and m["tile"] == tile else m["type"]),
                     "tile": m["tile"]} for m in extra
                ]
            else:
                raise ValueError("invalid legal own-kong offer")
            outcome = _call_outlook(after, extra, missing, public, cap, tian)
            rows.append(_summary(
                kind, ("暗杠" if kind == "an_gang" else "补杠") + " " + tile,
                outcome, tile=tile,
                reason=("杠后尚未摸尾牌；补杠可能被抢杠。"
                        if kind == "bu_gang" else "杠后从尾部补摸未知牌。")))
        chosen = None if winning else _challenge_kong(view)
        selected = (
            ("hu", None) if winning else
            (chosen["type"], chosen["tile"]) if chosen else ("pass", None)
        )

    if not any((r["action"], r["tile"]) == selected for r in rows):
        raise RuntimeError("reference operation is absent from legal server options")
    for row in rows:
        row["reference_best"] = (row["action"], row["tile"]) == selected
    rows.sort(key=lambda r: (
        not r["reference_best"],
        r["shanten"] if r["shanten"] is not None else -1,
        -(r["fan_weighted"] if r["fan_weighted"] is not None else 0),
        -(r["effective_copies"] if r["effective_copies"] is not None else 0),
        r["action"], r["tile"] or "",
    ))
    return {
        "status": "choose_operation", "seat": seat, "phase": phase,
        "recommended": {"action": selected[0], "tile": selected[1]},
        "candidates": rows,
        "interpretation": "challenge_bounded_public_call_outlook",
        "limitations": (
            "碰杠比较是公开信息下的单步向听、有效张及听牌基础番值参考；"
            "没有已知墙内剩余牌，不计算真实吃碰成功率、点炮概率、"
            "抢杠概率或完整终局净积分。胡牌是即时合法得分建议，"
            "不宣称放弃后永远不可能获得更高分。"),
    }


def classic_live_operation_hint(view: Mapping[str, Any]) -> dict[str, Any]:
    if view.get("seat") != 0:
        raise ValueError("live operation advice is restricted to seat zero")
    return classic_operation_hint(view, 0)
