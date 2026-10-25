"""M4.26 deterministic *constructed* legal delayed-bu-gang decision checkpoints.

Only synthetic game states; NOT representative natural-game frequencies or
estimates of win probability / EV. Physical copies, public/private boundaries,
real turns, rob windows, tail replacements and ledger postings are authoritative.
"""
from __future__ import annotations

from collections import Counter
from random import Random
from typing import Any, Mapping

from .ai import MahjongAgent
from .four_player import FourPlayerOpening
from .rules import TILES

PROTOCOL = "m426_constructed_legal_bugang_decision_coverage_v1"
FAMILIES = ("mixed", "concentrated")
RANKS = (1, 2, 3, 5, 7, 9)
SPECS = tuple((suit + str(rank), family)
              for suit in ("m", "s")
              for rank in RANKS
              for family in FAMILIES)
SHARDS = {
    "set_a": tuple(range(0, 6)),
    "set_b": tuple(range(6, 12)),
    "set_c": tuple(range(12, 18)),
    "set_d": tuple(range(18, 24)),
}


def _spec(case_id: int) -> tuple[str, str]:
    if type(case_id) is not int or not 0 <= case_id < len(SPECS):
        raise ValueError("unknown preregistered constructed checkpoint")
    return SPECS[case_id]


def construct_checkpoint(case_id: int, *, delayed: bool) -> FourPlayerOpening:
    """Build 108 physical tiles with a PENG and fourth tile on front wall.

    The synthetic initial checkpoint contains a genuine 3-tile exposed peng
    and 10 concealed tiles (13 effective), three 13-tile other hands, and a
    real 56-tile wall. All concealed hands start with NO p suit; missing=p.
    The fourth target copy is physically on front of wall. No opponent
    concealed tiles/wall contents are ever supplied to AI.
    """
    if type(delayed) is not bool:
        raise ValueError("delayed must be bool")
    target, family = _spec(case_id)
    rng = Random(74000 + case_id)
    pool = [tile for tile in TILES
            if tile[0] != "p" and tile != target
            for _ in range(4)]
    rng.shuffle(pool)
    if family == "mixed":
        own = pool[:10]
    else:
        # Deliberately build a concentrated, sequence/pair-heavy profile
        # without altering tile counts or looking at any future wall draws.
        ordered = sorted(
            pool,
            key=lambda t: (
                t[0] != target[0],
                abs(int(t[1]) - int(target[1])),
                rng.random(),
            ),
        )
        own = ordered[:10]
    for tile in own:
        pool.remove(tile)
    rng.shuffle(pool)
    opponents = [pool[i * 13:(i + 1) * 13] for i in range(3)]
    leftover = pool[39:]
    if len(own) != 10 or any(len(h) != 13 for h in opponents):
        raise RuntimeError("bad constructed hand sizes")
    if len(leftover) != 19:
        raise RuntimeError("bad constructed wall prefix")
    # Reserve the next four real draws as non-missing, non-target: 1-3
    # other players may discard their actual draw, then seat 0 comes back.
    next_four = leftover[:4]
    other_wall = leftover[4:] + [
        tile for tile in TILES if tile[0] == "p" for _ in range(4)
    ]
    rng.shuffle(other_wall)
    g = FourPlayerOpening(
        74000 + case_id, dealer_override=0, kong_base=20,
        legacy_bugang_cash=False,
    )
    g._hands = [list(own), *(list(h) for h in opponents)]
    g._melds = [[{"type": "peng", "tile": target}], [], [], []]
    g._wall = [target, *next_four, *other_wall]
    g.missing_suits = ["p", "p", "p", "p"]
    g.phase = "await_draw"
    g.turn = 0
    g._assert_physical_tiles()
    if g.draw(0) != target:
        raise RuntimeError("fourth copy was not actually drawn")
    if {"type": "bu_gang", "tile": target} not in g.kong_options(0):
        raise RuntimeError("newly drawn fourth copy is not a legal kong")
    if delayed:
        cut = next(t for t in g._hands[0] if t != target)
        g.discard(0, cut, from_draw=False)
        for s in (1, 2, 3):
            g.respond_discard(s, "pass")
        for s in (1, 2, 3):
            drawn = g.draw(s)
            g.discard(s, drawn, from_draw=True)
            for other in range(4):
                if other != s:
                    g.respond_discard(other, "pass")
        if g.phase != "await_draw" or g.turn != 0:
            raise RuntimeError("constructed passage through real turns failed")
        next_draw = g.draw(0)
        if next_draw == target:
            raise RuntimeError("delayed case illegally got fourth again")
        if g.private_view(0)["drawn_tile"] == target:
            raise RuntimeError("no-cash checkpoint was not delayed")
        if {"type": "bu_gang", "tile": target} not in g.kong_options(0):
            raise RuntimeError("legal delayed kong vanished")
    if g.debug_tile_counts()["total"] != 108:
        raise RuntimeError("physical tile count changed")
    return g


def _choice(action: Mapping[str, str] | None) -> str:
    return action["type"] if action is not None else "pass"


def _resolve_rob(g: FourPlayerOpening) -> None:
    for seat in (1, 2, 3):
        g.respond_rob_kong(seat, "pass")
    if g.phase != "await_discard":
        raise RuntimeError("rob-kong window failed to resolve")


def _exercise_real_ledger(case_id: int, *, delayed: bool) -> dict[str, Any]:
    target, _ = _spec(case_id)
    game = construct_checkpoint(case_id, delayed=delayed)
    before = game.public_state()["wall_count"]
    game.declare_kong(0, "bu_gang", target)
    pending = game.public_state()["pending_rob_kong"]
    if pending["cash_eligible"] is delayed:
        raise RuntimeError("cash eligibility inverted in authoritative engine")
    _resolve_rob(game)
    board = game.public_state()
    event = board["kong_ledger"]["events"][-1]
    expected_status = "not_payable" if delayed else "posted"
    expected_cash = [0, 0, 0, 0] if delayed else [60, -20, -20, -20]
    if (event["status"] != expected_status or
            event["cash_eligible"] is delayed or
            board["kong_ledger"]["balances"] != expected_cash or
            not board["kong_ledger"]["zero_sum"] or
            board["wall_count"] != before - 1 or
            board["melds"][0][0]["type"] != "bu_gang" or
            game.debug_tile_counts()["total"] != 108):
        raise RuntimeError("official kong money, tail draw or physical invariant failed")
    return {
        "status": event["status"],
        "money_to_actor": board["kong_ledger"]["balances"][0],
        "physical_count": game.debug_tile_counts()["total"],
        "wall_supplement_used": True,
    }


def evaluate_case(case_id: int) -> dict[str, Any]:
    """All policy choices are made ONLY from seat-zero authorized private views."""
    target, family = _spec(case_id)
    paid = construct_checkpoint(case_id, delayed=False)
    late = construct_checkpoint(case_id, delayed=True)
    paid_view, late_view = paid.private_view(0), late.private_view(0)
    if (paid_view["legacy_bugang_cash_rule"] is not False or
        late_view["legacy_bugang_cash_rule"] is not False or
        paid_view["drawn_tile"] != target or
        late_view["drawn_tile"] == target or
        late_view["hand"].count(target) != 1):
        raise RuntimeError("invalid current-rule authorized fixture")
    original = MahjongAgent("challenge", seed=74000 + case_id, seat=0)
    paid_action = original.kong(paid_view)
    guarded_action = original.kong(late_view)
    # This flag is a temporary, POLICY-ONLY offline ablation passed to the
    # AI; it never changes the game engine, whose cash rule remains current.
    ablated_action = original.kong({
        **late_view, "legacy_bugang_cash_rule": True,
    })
    for action, view in (
        (paid_action, paid_view), (guarded_action, late_view),
        (ablated_action, late_view)
    ):
        if action is not None and action not in view["kong_options"]:
            raise RuntimeError("AI returned an illegal candidate")
    timely_settlement = _exercise_real_ledger(case_id, delayed=False)
    delayed_settlement = _exercise_real_ledger(case_id, delayed=True)
    if "hand" in paid.public_state() or "drawn_tile" in late.public_state():
        raise RuntimeError("public state disclosed private tiles")
    return {
        "case_id": case_id,
        "declared_peng_tile": target,  # exposed tile, already public
        "shape_family": family,
        "paid_action": _choice(paid_action),
        "delayed_guarded_action": _choice(guarded_action),
        "delayed_unguarded_action": _choice(ablated_action),
        "guard_disagreement": guarded_action != ablated_action,
        # Not a causal cash-only contrast: the subsequent real turn also
        # changes own drawn tile and others' public discards.
        "paid_vs_delayed_action_changed": paid_action != guarded_action,
        "other_kong_options": sum(
            x["type"] != "bu_gang" for x in late_view["kong_options"]
        ),
        "paid_event_status": timely_settlement["status"],
        "paid_kong_money": timely_settlement["money_to_actor"],
        "delayed_event_status": delayed_settlement["status"],
        "delayed_kong_money": delayed_settlement["money_to_actor"],
        "physical_count": delayed_settlement["physical_count"],
    }


def evaluate_shard(name: str) -> dict[str, Any]:
    if type(name) is not str or name not in SHARDS:
        raise ValueError("invalid constructed checkpoint shard")
    rows = [evaluate_case(i) for i in SHARDS[name]]
    return {
        "protocol": PROTOCOL, "shard": name,
        "case_ids": list(SHARDS[name]), "cases": rows,
        "not_natural_games": True, "no_ev_claim": True,
    }


def audit_and_combine(payloads: Mapping[str, Any]) -> dict[str, Any]:
    if type(payloads) is not dict or set(payloads) != set(SHARDS):
        raise ValueError("missing or extra registered constructed shard")
    all_cases: list[dict[str, Any]] = []
    for name in SHARDS:
        obj = payloads[name]
        if (type(obj) is not dict or obj.get("protocol") != PROTOCOL or
                obj.get("shard") != name or
                obj.get("not_natural_games") is not True or
                obj.get("no_ev_claim") is not True or
                obj.get("case_ids") != list(SHARDS[name]) or
                type(obj.get("cases")) is not list or
                len(obj["cases"]) != len(SHARDS[name])):
            raise ValueError("invalid nonrepresentative shard metadata")
        for row, case_id in zip(obj["cases"], SHARDS[name]):
            if (type(row) is not dict or type(row.get("case_id")) is not int or
                    row["case_id"] != case_id or
                    row.get("declared_peng_tile") != SPECS[case_id][0] or
                    row.get("shape_family") != SPECS[case_id][1] or
                    row.get("physical_count") != 108 or
                    row.get("paid_event_status") != "posted" or
                    row.get("paid_kong_money") != 60 or
                    row.get("delayed_event_status") != "not_payable" or
                    row.get("delayed_kong_money") != 0 or
                    type(row.get("guard_disagreement")) is not bool or
                    type(row.get("paid_vs_delayed_action_changed")) is not bool or
                    type(row.get("other_kong_options")) is not int or
                    row["other_kong_options"] < 0 or
                    any(row.get(key) not in ("pass", "bu_gang", "an_gang")
                        for key in ("paid_action", "delayed_guarded_action",
                                    "delayed_unguarded_action")) or
                    row["guard_disagreement"] != (
                        row["delayed_guarded_action"] !=
                        row["delayed_unguarded_action"])):
                raise ValueError("non-authoritative or mislabelled case")
            all_cases.append(row)
    if len(all_cases) != len(SPECS):
        raise ValueError("incomplete fixed constructed case grid")
    counts = Counter()
    for row in all_cases:
        counts["paid_bugang_choices"] += (
            row["paid_action"] == "bu_gang")
        counts["delayed_guarded_bugang_choices"] += (
            row["delayed_guarded_action"] == "bu_gang")
        counts["delayed_unguarded_bugang_choices"] += (
            row["delayed_unguarded_action"] == "bu_gang")
        counts["guard_disagreements"] += row["guard_disagreement"]
        counts["paid_vs_delayed_action_differences"] += (
            row["paid_vs_delayed_action_changed"])
        counts["competing_other_kong_choices"] += (
            row["other_kong_options"] > 0)
    return {
        "protocol": PROTOCOL,
        "total_constructed_checkpoints": len(all_cases),
        "independent_natural_shuffle_seeds": 0,
        "complete_natural_games": 0,
        "current_rule": "current_m423",
        "money_per_payer": 20,
        "measured_counts": dict(counts),
        "cases": all_cases,
        "interpretation": (
            "Coverage of constructed lawful states only. These are NOT "
            "representative game frequency, win rate or realized score EV."
        ),
    }
