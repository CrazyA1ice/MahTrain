"""Public-knowledge-only, ON-DEMAND efficiency notes for seat-zero Mahjong UI.

No opponent hands, hidden wall contents, RNG, or perfect-information EV.
Counts reflect unknown physical copies from own hand/melds + published
discards/exposed melds. They are NOT known wall contents or draw odds.
"""
from __future__ import annotations

from collections.abc import Mapping
from .ai import visible_tiles
from .efficiency import analyze_discards, effective_draws
from .rules import TILE_INDEX

_TURNS = frozenset(("dealer_discard", "await_discard"))


def classic_hand_hint(view: Mapping) -> dict:
    if view.get("seat") != 0:
        raise ValueError("牌效分析仅支持当前玩家的授权视图")
    if view.get("phase") not in _TURNS or view.get("turn") != 0:
        raise ValueError("仅在轮到自己出牌时可查看牌效")
    missing_suits = view.get("missing_suits")
    if not isinstance(missing_suits, list) or len(missing_suits) != 4:
        raise ValueError("必须先完成定缺")
    missing = missing_suits[0]
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
    lowest = min(row["shanten"] for row in analyses)
    largest = max(row["effective_tile_count"]
                  for row in analyses if row["shanten"] == lowest)
    ranked = sorted(analyses, key=lambda row: (
        row["shanten"], -row["effective_tile_count"],
        TILE_INDEX[row["discard"]],
    ))
    return {
        "status": "choose_discard",
        "phase": view["phase"],
        "forced_missing": bool(forced),
        "missing_suit": missing,
        "interpretation": "structural_only",
        "ranking_rule": "minimum_shanten_then_unknown_copy_upper_bound",
        "candidates": [{
            "discard": row["discard"],
            "shanten": row["shanten"],
            "effective_details": [{
                "tile": item["tile"],
                "unknown_copies_upper_bound": item["remaining"],
            } for item in row["effective_details"]],
            "effective_tile_count_upper_bound": row["effective_tile_count"],
            "effective_type_count": len(row["effective_types"]),
            "reference_best": row["shanten"] == lowest
                and row["effective_tile_count"] == largest,
        } for row in ranked],
        "limitations": (
            "以自己的手牌和公开弃牌／公开副露扣除已知牌。"
            "未排除张数是未知位置中的物理牌张上限，不是牌墙真实剩余数，"
            "也不是下一摸概率或综合番型收益。"
        ),
    }
