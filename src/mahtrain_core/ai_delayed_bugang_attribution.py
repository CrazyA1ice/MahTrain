"""M4.27: exact, OFFLINE explanation of the current challenge bu-gang guard.

Uses only the acting seat's authorized view and existing shanten/copy/fan-proxy
calculations. Does not use other hands, the actual future wall or game outcomes.
Reports proxy comparisons, NOT calibrated probabilities / expected-score EV.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from .ai import (
    MahjongAgent, _own_view, _cut_shanten, _call_outlook, _call_settings,
    _outlook_better_than_baseline,
)
from .ai_delayed_bugang_targeted import (
    SPECS, SHARDS, construct_checkpoint,
)
from .efficiency import shanten_13
from .rules import TILE_INDEX

PROTOCOL = "m427_same_view_delayed_bugang_exact_guard_attribution_v1"
REASONS = (
    "worse_shanten",
    "tian_ting_not_retained",
    "zero_remaining_effective_copies",
    "below_75pct_ukeire_floor",
    "below_75pct_fan_proxy_floor",
    "guard_ukeire_down",
    "guard_fan_proxy_down",
    "guard_both_unchanged",
    "structural_improvement",
    "equal_stage_guard_admissible",
)
STRICT_REASONS = frozenset((
    "guard_ukeire_down", "guard_fan_proxy_down", "guard_both_unchanged",
))
OPTIONS = ("pass", "an_gang", "bu_gang")


def _action_name(action: Mapping[str, str] | None) -> str:
    if action is None:
        return "pass"
    return action["type"]


def diagnose_view(view: Mapping[str, Any],
                  *, target: str) -> dict[str, Any]:
    """Explain a REAL legal *delayed* supplement kong on this exact view."""
    if view.get("legacy_bugang_cash_rule") is not False:
        raise ValueError("current M4.23 rules must govern the real state")
    if (view.get("phase") not in ("await_discard", "dealer_discard")
            or view.get("seat") != view.get("turn")
            or type(target) is not str
            or {"type": "bu_gang", "tile": target} not in view["kong_options"]
            or view.get("drawn_tile") == target):
        raise ValueError("the same-view diagnosis requires a legal cashless bu-gang")

    hand, melds, missing = _own_view(view)
    public, cap, tian = _call_settings(view)
    allowed = sorted(set(hand), key=TILE_INDEX.__getitem__)
    forced = [tile for tile in allowed if tile[0] == missing]
    if forced:
        allowed = forced
    baseline_stages = [
        (tile, _cut_shanten(hand, melds, missing, tile))
        for tile in allowed
    ]
    least = min(stage for _, stage in baseline_stages)
    baselines = []
    for tile, stage in baseline_stages:
        if stage != least:
            continue
        remaining = list(hand)
        remaining.remove(tile)
        baselines.append(_call_outlook(
            remaining, melds, missing, [*public, tile], cap, tian,
        ))
    baseline = max(baselines, key=lambda x:(x["value"], x["ukeire"]))
    if baseline["shanten"] != least:
        raise RuntimeError("the best ordinary cut stage did not reconcile")

    after = list(hand)
    after.remove(target)
    new_melds = [
        {"type": "bu_gang" if group["type"] == "peng"
         and group["tile"] == target else group["type"],
         "tile": group["tile"]}
        for group in melds
    ]
    stage = shanten_13(after, new_melds, missing)
    outlook = _call_outlook(after, new_melds, missing, public, cap, tian)
    if outlook["shanten"] != stage:
        raise RuntimeError("candidate stage did not reconcile")

    b_ukeire, c_ukeire = baseline["ukeire"], outlook["ukeire"]
    b_value, c_value = baseline["value"], outlook["value"]
    passes_75 = _outlook_better_than_baseline(
        outlook, baseline, fraction=0.75)
    if stage > least:
        reason = "worse_shanten"
    elif tian.get("eligible") and not outlook["tian_kept"]:
        reason = "tian_ting_not_retained"
    elif stage < least:
        reason = "structural_improvement"
    elif b_ukeire and c_ukeire == 0:
        reason = "zero_remaining_effective_copies"
    elif c_ukeire < b_ukeire * 0.75:
        reason = "below_75pct_ukeire_floor"
    elif c_value < b_value * 0.75:
        reason = "below_75pct_fan_proxy_floor"
    elif c_ukeire < b_ukeire:
        reason = "guard_ukeire_down"
    elif c_value < b_value:
        reason = "guard_fan_proxy_down"
    elif c_ukeire == b_ukeire and c_value == b_value:
        reason = "guard_both_unchanged"
    else:
        reason = "equal_stage_guard_admissible"

    # A strictly attributed guard-only rejection MUST have passed the old
    # structural/75%-proxy policy first. Other reasons are not guard effects.
    if (reason in STRICT_REASONS and not passes_75):
        raise RuntimeError("incorrect ordering of old floor and strict guard")

    agent = MahjongAgent("challenge", seed=74000, seat=view["seat"])
    guarded = agent.kong(view)
    unguarded = agent.kong({
        **view, "legacy_bugang_cash_rule": True
    })
    for action in (guarded, unguarded):
        if action is not None and action not in view["kong_options"]:
            raise RuntimeError("agent returned a kong outside its legal options")
    choice_differs = guarded != unguarded
    if choice_differs and reason not in STRICT_REASONS:
        raise RuntimeError("policy changed despite no strict delayed guard rejection")
    if (reason in STRICT_REASONS and
            unguarded == {"type": "bu_gang", "tile": target} and
            guarded == unguarded):
        raise RuntimeError("the strict guard failed to reject its own target")

    return {
        "baseline_shanten": least,
        "candidate_shanten": stage,
        "baseline_effective_copies": b_ukeire,
        "candidate_effective_copies": c_ukeire,
        "baseline_fan_proxy": b_value,
        "candidate_fan_proxy": c_value,
        "passed_original_75pct_policy": passes_75,
        "strict_guard_reason": reason,
        "guard_only_rejection_of_target": reason in STRICT_REASONS,
        "same_view_action_changed": choice_differs,
        "guarded_action": _action_name(guarded),
        "unguarded_action": _action_name(unguarded),
        "competing_other_kongs": sum(
            option["type"] != "bu_gang" or option["tile"] != target
            for option in view["kong_options"]
        ),
    }


def diagnose_case(case_id: int) -> dict[str, Any]:
    if type(case_id) is not int or not 0 <= case_id < len(SPECS):
        raise ValueError("invalid frozen constructed case")
    target, family = SPECS[case_id]
    game = construct_checkpoint(case_id, delayed=True)
    view = game.private_view(0)
    before = game.debug_tile_counts()
    row = diagnose_view(view, target=target)
    if before != game.debug_tile_counts() or game.phase != "await_discard":
        raise RuntimeError("diagnosis mutated authoritative physical game state")
    if (row["candidate_shanten"] > row["baseline_shanten"] and
            row["strict_guard_reason"] != "worse_shanten"):
        raise RuntimeError("incorrect structural exclusion")
    return {
        "case_id":case_id, "exposed_peng": target, "shape_family":family,
        **row,
        "physical_count": before["total"],
    }


def diagnose_shard(name: str) -> dict[str, Any]:
    if type(name) is not str or name not in SHARDS:
        raise ValueError("only four frozen M4.27 shards allowed")
    cases = [diagnose_case(i) for i in SHARDS[name]]
    return {
        "protocol":PROTOCOL,
        "shard":name,
        "case_ids":list(SHARDS[name]),
        "constructs_only":True,
        "no_expected_score_claim":True,
        "cases":cases,
    }


def combine(shards: Mapping[str, Any]) -> dict[str, Any]:
    if type(shards) is not dict or set(shards) != set(SHARDS):
        raise ValueError("all four frozen shards required")
    rows = []
    for name in SHARDS:
        data = shards[name]
        if (type(data) is not dict or data.get("protocol") != PROTOCOL
                or data.get("shard") != name
                or data.get("case_ids") != list(SHARDS[name])
                or data.get("constructs_only") is not True
                or data.get("no_expected_score_claim") is not True
                or type(data.get("cases")) is not list
                or len(data["cases"]) != len(SHARDS[name])):
            raise ValueError("unregistered case group or illegal causal claim")
        for case_id, row in zip(SHARDS[name], data["cases"]):
            target, family = SPECS[case_id]
            if (type(row) is not dict or
                    type(row.get("case_id")) is not int or
                    row["case_id"] != case_id or
                    row.get("exposed_peng") != target or
                    row.get("shape_family") != family or
                    row.get("physical_count") != 108 or
                    row.get("strict_guard_reason") not in REASONS or
                    type(row.get("same_view_action_changed")) is not bool or
                    type(row.get("guard_only_rejection_of_target")) is not bool or
                    type(row.get("passed_original_75pct_policy")) is not bool or
                    type(row.get("competing_other_kongs")) is not int or
                    row["competing_other_kongs"] < 0 or
                    any(type(row.get(k)) is not int or row[k] < 0
                        for k in (
                            "baseline_effective_copies",
                            "candidate_effective_copies",
                            "baseline_fan_proxy", "candidate_fan_proxy",
                        )) or
                    any(type(row.get(k)) is not int or row[k] < -1
                        for k in ("baseline_shanten", "candidate_shanten")) or
                    any(row.get(k) not in OPTIONS for k in
                        ("guarded_action", "unguarded_action")) or
                    row["same_view_action_changed"] != (
                        row["guarded_action"] != row["unguarded_action"]) or
                    row["guard_only_rejection_of_target"] != (
                        row["strict_guard_reason"] in STRICT_REASONS) or
                    (row["same_view_action_changed"] and
                     row["strict_guard_reason"] not in STRICT_REASONS)):
                raise ValueError("failed exact policy diagnosis invariant")
            rows.append(row)
    if len(rows) != len(SPECS):
        raise RuntimeError("unbalanced targeted grid")
    counts = Counter(row["strict_guard_reason"] for row in rows)
    disagreed = [row for row in rows if row["same_view_action_changed"]]
    return {
        "protocol":PROTOCOL,
        "total_constructed_checkpoints":len(rows),
        "independent_natural_shuffle_seeds":0,
        "completed_natural_games":0,
        "guard_reason_counts":{reason:counts[reason] for reason in REASONS},
        "strict_guard_rejected_target_count":sum(
            row["guard_only_rejection_of_target"] for row in rows
        ),
        "same_view_policy_disagreement_count":len(disagreed),
        "disagreement_cases":[{
            "case_id":row["case_id"],
            "exposed_peng":row["exposed_peng"],
            "shape_family":row["shape_family"],
            "baseline_shanten":row["baseline_shanten"],
            "candidate_shanten":row["candidate_shanten"],
            "baseline_effective_copies":row["baseline_effective_copies"],
            "candidate_effective_copies":row["candidate_effective_copies"],
            "baseline_fan_proxy":row["baseline_fan_proxy"],
            "candidate_fan_proxy":row["candidate_fan_proxy"],
            "reason":row["strict_guard_reason"],
        } for row in disagreed],
        "cases":rows,
        "policy_changed":False,
        "no_ev_conclusion":True,
        "limitations":[
            "Guard admission is decided using publicly visible effective copies and a fan proxy, not expected net score.",
            "Only existing constructed states were used; no natural population frequency or win rate can be estimated.",
            "A same-view flag ablation isolates the guard decision, not its ultimate game outcome.",
            "Disagreement classifications do not expose other players' concealed tiles or actual wall draws.",
        ],
    }
