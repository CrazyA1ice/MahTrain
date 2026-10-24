"""M4.25 fresh-seed M4.23 cash-rule guard audit with 4 frozen CI shards.

OFFLINE ONLY. Never changes the live challenge agent, actual rules, or
historical M4.24 seed cohorts. Each initial shuffle is ONE independent
cluster even though it produces four seat-rotated paired positions.
"""
from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Mapping

from .ai_action_extended_study import _fixed_lineup
from .ai_delayed_bugang_paired import (
    ARMS, COMPONENTS, PROTOCOL as M424_PROTOCOL, cohort,
)

PROTOCOL = "m425_fresh_independent_seed_cluster_extension_v1"
SEEDS_PER_SHARD = 4
SHARDS = {
    "development_a": ("development", 66000),
    "development_b": ("development", 66004),
    "holdout_a": ("holdout", 67000),
    "holdout_b": ("holdout", 67004),
}
PRIMARY_METRIC = "official_net"
LEDGER_COMPONENTS = ("win_points", "kong_points", "exhaustive_points")


def run_shard(name: str) -> dict[str, Any]:
    """Prespecified, non-selected complete games under current rules only."""
    if type(name) is not str or name not in SHARDS:
        raise ValueError("unknown or non-preregistered M4.25 shard")
    group, start = SHARDS[name]
    result = cohort(start, SEEDS_PER_SHARD)
    if (result["independent_shuffle_seeds"] != SEEDS_PER_SHARD
            or result["paired_positions"] != 4 * SEEDS_PER_SHARD
            or result["complete_games"] != 8 * SEEDS_PER_SHARD):
        raise RuntimeError("missing complete paired game positions")
    return {
        "protocol": PROTOCOL,
        "parent_protocol": M424_PROTOCOL,
        "official_ruleset": "current_m423",
        "shard": name,
        "cohort": group,
        "seed_start": start,
        "seed_end_exclusive": start + SEEDS_PER_SHARD,
        "result": result,
    }


def _audit_shard(name: str, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if type(payload) is not dict:
        raise ValueError("shard must be a JSON object")
    group, start = SHARDS[name]
    if any((
        payload.get("protocol") != PROTOCOL,
        payload.get("parent_protocol") != M424_PROTOCOL,
        payload.get("official_ruleset") != "current_m423",
        payload.get("shard") != name,
        payload.get("cohort") != group,
        type(payload.get("seed_start")) is not int,
        payload.get("seed_start") != start,
        type(payload.get("seed_end_exclusive")) is not int,
        payload.get("seed_end_exclusive") != start + SEEDS_PER_SHARD,
    )):
        raise ValueError("shard does not match registered fresh-seed rules")
    result = payload.get("result")
    if type(result) is not dict:
        raise ValueError("missing actual paired cohort")
    if (result.get("independent_shuffle_seeds") != SEEDS_PER_SHARD
            or result.get("four_seat_rotations") != 4
            or result.get("paired_positions") != SEEDS_PER_SHARD * 4
            or result.get("complete_games") != SEEDS_PER_SHARD * 8):
        raise ValueError("incomplete paired cohort or incorrect trial count")
    positions = result.get("positions")
    if type(positions) is not list or len(positions) != SEEDS_PER_SHARD * 4:
        raise ValueError("incomplete paired result rows")
    seen = set()
    for row in positions:
        if type(row) is not dict:
            raise ValueError("invalid paired position")
        seed, rotation = row.get("seed"), row.get("rotation")
        if (type(seed) is not int or type(rotation) is not int
                or seed not in range(start, start + SEEDS_PER_SHARD)
                or rotation not in range(4) or (seed, rotation) in seen):
            raise ValueError("duplicate, absent or unregistered seed/seat")
        seen.add((seed, rotation))
        lineup, seat = _fixed_lineup(rotation)
        if row.get("challenge_seat") != seat:
            raise ValueError("mismatched challenge seat")
        arms = row.get("arms")
        if type(arms) is not dict or set(arms) != set(ARMS):
            raise ValueError("paired arm mismatch")
        scores = []
        for arm_name in ARMS:
            arm = arms[arm_name]
            if type(arm) is not dict or arm.get("terminal_phase") not in (
                    "finished", "wall_exhausted"):
                raise ValueError("incomplete real game")
            score = arm.get("score")
            if (type(score) is not dict or
                any(type(score.get(k)) is not int for k in COMPONENTS) or
                score[PRIMARY_METRIC] !=
                    sum(score[k] for k in LEDGER_COMPONENTS)):
                raise ValueError("invalid official zero-sum ledger components")
            counts = arm.get("counts")
            if (type(counts) is not dict or
                any(type(v) is not int or v < 0 for v in counts.values())):
                raise ValueError("invalid measured legal opportunity counts")
            scores.append(score)
        diffs = row.get("component_deltas")
        if (type(diffs) is not dict or any(
            type(diffs.get(metric)) is not int or
            diffs[metric] != scores[0][metric] - scores[1][metric]
            for metric in COMPONENTS
        )):
            raise ValueError("paired differences mismatch actual official scores")
    if seen != {(seed, rotation)
                for seed in range(start, start + SEEDS_PER_SHARD)
                for rotation in range(4)}:
        raise ValueError("not every preregistered seat observed")
    return positions


def combine_shards(shards: Mapping[str, Any]) -> dict[str, Any]:
    """Merge CI artifacts, but fail closed on missing/mismatched data."""
    if type(shards) is not dict or set(shards) != set(SHARDS):
        raise ValueError("expected exactly four preregistered shard results")
    grouped = {"development": [], "holdout": []}
    for name in SHARDS:
        positions = _audit_shard(name, shards[name])
        grouped[SHARDS[name][0]].extend(positions)

    summaries = {}
    for group, positions in grouped.items():
        cluster_rows = []
        opportunity_counts: Counter[str] = Counter()
        for row in positions:
            for arm in ARMS:
                opportunity_counts.update({
                    arm + "_" + name: count
                    for name, count in row["arms"][arm]["counts"].items()
                })
        starts = sorted(SHARDS[name][1] for name in SHARDS
                        if SHARDS[name][0] == group)
        seeds = [seed for start in starts
                 for seed in range(start, start + SEEDS_PER_SHARD)]
        for seed in seeds:
            four_seats = [row for row in positions if row["seed"] == seed]
            if (len(four_seats) != 4 or
                    sorted(x["challenge_seat"] for x in four_seats) !=
                        [0, 1, 2, 3]):
                raise RuntimeError("seat rotation is not balanced")
            cluster_rows.append({
                "seed": seed,
                "mean_four_seat_delta": {
                    metric: mean(row["component_deltas"][metric]
                                 for row in four_seats)
                    for metric in COMPONENTS
                },
                "old_guard_interventions": sum(
                    row["arms"]["old_guard_ablation"]["counts"].get(
                        "policy_interventions", 0)
                    for row in four_seats
                ),
            })
        pooled = {
            metric: mean(row["mean_four_seat_delta"][metric]
                         for row in cluster_rows)
            for metric in COMPONENTS
        }
        if abs(pooled[PRIMARY_METRIC] -
               sum(pooled[m] for m in LEDGER_COMPONENTS)) > 1e-8:
            raise RuntimeError("official group delta decomposition mismatch")
        net = [row["mean_four_seat_delta"][PRIMARY_METRIC]
               for row in cluster_rows]
        summaries[group] = {
            "independent_shuffle_seeds": len(cluster_rows),
            "seat_rotations_per_seed": 4,
            "complete_games": len(positions) * len(ARMS),
            "primary_metric": PRIMARY_METRIC,
            "current_guard_minus_old_guard": {
                key: round(value, 5) for key, value in pooled.items()
            },
            "positive_clusters": sum(x > 0 for x in net),
            "negative_clusters": sum(x < 0 for x in net),
            "zero_clusters": sum(x == 0 for x in net),
            "observed_old_guard_interventions": sum(
                row["old_guard_interventions"] for row in cluster_rows
            ),
            "opportunity_counts": dict(opportunity_counts),
            "seed_cluster_rows": cluster_rows,
            "confidence_interval_95pct": None,
            "exploratory_only": True,
        }
    return {
        "protocol": PROTOCOL,
        "source_protocol": M424_PROTOCOL,
        "official_ruleset": "current_m423",
        "frozen_groups": {
            group: [
                [SHARDS[n][1], SHARDS[n][1] + SEEDS_PER_SHARD]
                for n in SHARDS if SHARDS[n][0] == group
            ] for group in ("development", "holdout")
        },
        "total_independent_shuffle_seeds": 2 * 2 * SEEDS_PER_SHARD,
        "total_complete_games": sum(
            x["complete_games"] for x in summaries.values()
        ),
        "development": summaries["development"],
        "holdout": summaries["holdout"],
        "recommendation": (
            "No new live threshold is justified without substantial, "
            "consistent cluster-level evidence and a separate future holdout."
        ),
        "limitations": [
            "The unit of independence is the initial shuffle, not 128 games.",
            "All seat rotations share the same initial shuffle.",
            "Paired future game paths diverge after an altered decision.",
            "Observing zero interventions supplies no evidence of superiority.",
            "Eight independent shuffle seeds per group are still exploratory.",
            "Original historical M4.24 seeds were not reused in this study.",
            "No winner hidden tiles or wall information enter the agent policy.",
        ],
    }
