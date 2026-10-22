"""Public-knowledge-only cut ranking: live seat-zero and terminal seat-specific review.

No opponent hands, hidden wall contents, RNG, or perfect-information EV.
Counts reflect unknown physical copies from own hand/melds + published
discards/exposed melds. They are NOT known wall contents or draw odds.
"""
from __future__ import annotations

from collections.abc import Mapping
from .ai import visible_tiles
from .efficiency import analyze_discards, effective_draws
from .rules import TILE_INDEX, score_win, winning_tiles

_TURNS = frozenset(("dealer_discard", "await_discard"))


def classic_hand_hint(view: Mapping) -> dict:
    """Seat-zero-only live advice. The web endpoint MUST use this wrapper."""
    if view.get("seat") != 0:
        raise ValueError("牌效分析仅支持当前玩家的授权视图")
    return classic_archive_seat_hint(view, 0)


def classic_archive_seat_hint(view: Mapping, seat: int) -> dict:
    """Trusted server-side historic cut scoring, never exposed as live HTTP.

    Caller must pass the AUTHORIZED private_view(seat) captured *before*
    that seat's physical discard. Does not inspect any opponent private hand.
    """
    if type(seat) is not int or seat not in (0, 1, 2, 3) or view.get("seat") != seat:
        raise ValueError("出牌评分只能读取该座位的授权视图")
    if view.get("phase") not in _TURNS or view.get("turn") != seat:
        raise ValueError("仅在轮到该座位出牌时可分析牌效")
    missing_suits = view.get("missing_suits")
    if not isinstance(missing_suits, list) or len(missing_suits) != 4:
        raise ValueError("必须先完成定缺")
    missing = missing_suits[seat]
    if missing not in ("m", "p", "s"):
        raise ValueError("尚未完成定缺")
    hand = view["hand"]
    melds = view["own_melds"]
    if len(hand) + 3 * len(melds) != 14:
        raise ValueError("当前不是完整的待出牌手牌")
    public = visible_tiles(view)
    # As in MahjongAgent, all of the declared-missing suit must be
    # discarded first. Thus hypothetical non-missing cuts are not offered.
    forced = sorted({x for x in hand if x[0] == missing},
                    key=TILE_INDEX.__getitem__)
    if forced:
        analyses = []
        for discard in forced:
            remainder = list(hand)
            remainder.remove(discard)
            info = effective_draws(
                remainder, melds, missing,
                visible_tiles=[*public, discard],
            )
            analyses.append({"discard": discard, **info})
    else:
        report = analyze_discards(hand, melds, missing, public)
        if report["status"] == "already_winning":
            return {
                "status": "already_winning",
                "phase": view["phase"],
                "interpretation": "structural_only",
                "candidates": [],
                "forced_missing": False,
            }
        analyses = report["candidates"]
    # Only an actually tenpai post-cut hand has a direct winning-tile
    # multiplier. Use the exact room fan cap and preserve authenticated
    # Tian Ting ONLY when this hypothetical discard keeps the initial waits.
    # Sum (unexcluded unknown physical copies * official base multiplier).
    # This is a comparative upper-bound WEIGHT, NOT draw probability, wall
    # composition, danger model or a guaranteed future payoff.
    cap = view.get("win_ledger", {}).get("fan_cap", 3)
    if type(cap) is not int or cap < 0:
        cap = 3
    tian = view.get("tian_ting") or {}
    enriched = []
    for row in analyses:
        item = dict(row)
        item["fan_weighted_unknown_copies"] = None
        item["winning_details"] = []
        if row["shanten"] == 0:
            after = list(hand)
            after.remove(row["discard"])
            waits = set(winning_tiles(after, melds, missing))
            preserve_tian = (
                tian.get("eligible") is True
                and waits == set(tian.get("initial_waits", []))
            )
            total = 0
            for draw in row["effective_details"]:
                tile = draw["tile"]
                score = score_win(
                    [*after, tile], melds, missing, cap=cap,
                    context={"tian_ting_verified": preserve_tian},
                )
                # effective_draws already checked each structural winning
                # tile; fail closed if a future rule revision disagrees.
                if not score["legal"]:
                    raise ValueError("结构听口与真实计分规则不一致")
                total += draw["remaining"] * score["multiplier"]
                item["winning_details"].append({
                    "tile": tile,
                    "unknown_copies_upper_bound": draw["remaining"],
                    "main_pattern": score["main_pattern"],
                    "effective_fan": score["effective_fan"],
                    "multiplier": score["multiplier"],
                    "tian_ting_applied": preserve_tian,
                })
            item["fan_weighted_unknown_copies"] = total
        enriched.append(item)

    def key(row):
        weighted = (row["fan_weighted_unknown_copies"]
                    if row["shanten"] == 0
                    else row["effective_tile_count"])
        return (
            row["shanten"],
            -weighted,
            -row["effective_tile_count"],
        )

    best_key = min(key(row) for row in enriched)
    ranked = sorted(enriched, key=lambda row: (*key(row), TILE_INDEX[row["discard"]]))
    return {
        "status": "choose_discard",
        "phase": view["phase"],
        "forced_missing": bool(forced),
        "missing_suit": missing,
        "interpretation": "public_information_fan_weighted_upper_bound",
        "fan_cap": cap,
        "ranking_rule": "min_shanten_then_tenpai_fan_weighted_upper_bound_else_ukeire",
        "candidates": [{
            "discard": row["discard"],
            "shanten": row["shanten"],
            "effective_details": [{
                "tile": d["tile"],
                "unknown_copies_upper_bound": d["remaining"],
            } for d in row["effective_details"]],
            "effective_tile_count_upper_bound": row["effective_tile_count"],
            "effective_type_count": len(row["effective_types"]),
            "fan_weighted_unknown_copies": row["fan_weighted_unknown_copies"],
            "winning_details": row["winning_details"],
            "reference_best": key(row) == best_key,
        } for row in ranked],
        "limitations": (
            "听牌时仅把公开未知张数上限乘以当前规则计算的基础胡牌倍率。"
            "它不代表真实墙内张数、下一摸胡牌概率或完整收益期望，"
            "且不考虑尚未发生的杠上花、海底等事件或放铳风险。"
        ),
    }
