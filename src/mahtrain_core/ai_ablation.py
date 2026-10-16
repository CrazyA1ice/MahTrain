"""M3.10 controlled challenge-policy ablation in real four-player games.

Two separately analyzed four-seat cohorts compare the full challenge agent
with each one-signal removal. A cohort has four seat rotations per independent
shuffle seed. Win events are not official fully settled Sichuan match wins.
"""
from __future__ import annotations

from random import Random
from typing import Any, Callable

from .ai_tournament import simulate_match

VARIANTS = ("challenge_no_ukeire", "challenge_no_risk")
COHORTS = {
    "baseline": ("baseline", "challenge", *VARIANTS),
    "advanced": ("advanced", "challenge", *VARIANTS),
}
METRICS = {
    "win_event_fraction": ("wins", "exposures"),
    "min_shanten_fraction": ("minimum_shanten", "discards"),
    "local_optimal_fraction": ("local_optimal", "discards"),
}


def ablation_lineup(cohort: str, rotation: int) -> list[str]:
    if cohort not in COHORTS:
        raise ValueError("unknown ablation cohort")
    if type(rotation) is not int or rotation not in range(4):
        raise ValueError("rotation must be 0..3")
    levels = COHORTS[cohort]
    return [levels[(seat + rotation) % 4] for seat in range(4)]


def _empty() -> dict[str, int]:
    return {
        "exposures": 0, "wins": 0, "deal_ins": 0,
        "discards": 0, "minimum_shanten": 0, "local_optimal": 0,
    }


def _counts(games: list[dict[str, Any]], cohort: str) -> dict[str, dict[str, int]]:
    result = {level: _empty() for level in COHORTS[cohort]}
    for game in games:
        seats = game["assignment"]
        if len(seats) != 4 or set(seats) != set(result):
            raise ValueError("unexpected ablation lineup")
        for level in seats:
            result[level]["exposures"] += 1
        for win in game["winners"]:
            seat, source = win["seat"], win["source"]
            if type(seat) is not int or seat not in range(4):
                raise ValueError("invalid winner seat")
            result[seats[seat]]["wins"] += 1
            if source != seat:
                if type(source) is not int or source not in range(4):
                    raise ValueError("invalid deal-in seat")
                result[seats[source]]["deal_ins"] += 1
        for action in game["trace"]:
            if action["action"] != "discard":
                continue
            seat = action["seat"]
            if type(seat) is not int or seat not in range(4):
                raise ValueError("invalid discard seat")
            row = result[seats[seat]]
            row["discards"] += 1
            row["minimum_shanten"] += int(action["shanten_regret"] == 0)
            row["local_optimal"] += int(bool(action["locally_optimal"]))
    return result


def _ratio(row: dict[str, int], metric: str) -> float | None:
    numerator, denominator = METRICS[metric]
    if row[denominator] == 0:
        return None
    return row[numerator] / row[denominator]


def _totals(groups: list[dict[str, dict[str, int]]],
            cohort: str) -> dict[str, dict[str, int]]:
    combined = {level: _empty() for level in COHORTS[cohort]}
    for group in groups:
        for level, row in combined.items():
            for key in row:
                row[key] += group[level][key]
    return combined


def _diff(totals: dict[str, dict[str, int]]) -> dict[str, dict[str, float | None]]:
    # Positive means the *complete challenge* has the higher rate.
    result = {}
    for level in totals:
        if level == "challenge":
            continue
        differences = {}
        for metric in METRICS:
            full = _ratio(totals["challenge"], metric)
            other = _ratio(totals[level], metric)
            differences[metric] = (
                round(full - other, 4)
                if full is not None and other is not None else None
            )
        result[level] = differences
    return result


def _interval(values: list[float]) -> list[float] | None:
    if not values:
        return None
    sorted_values = sorted(values)
    return [
        round(sorted_values[int((len(values) - 1) * 0.025)], 4),
        round(sorted_values[int((len(values) - 1) * 0.975)], 4),
    ]


def ablation_benchmark(
    seed_start: int = 11,
    seeds: int = 1,
    *,
    bootstrap_replicates: int = 400,
    on_match: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    if (type(seed_start) is not int or not 0 <= seed_start < 2**32
            or type(seeds) is not int or not 1 <= seeds <= 50
            or seed_start + seeds > 2**32):
        raise ValueError("seed_start must be uint32 and seeds 1..50")
    if (type(bootstrap_replicates) is not int
            or not 100 <= bootstrap_replicates <= 2000):
        raise ValueError("bootstrap_replicates must be 100..2000")
    groups = {cohort: [] for cohort in COHORTS}
    completed = 0
    for seed in range(seed_start, seed_start + seeds):
        for cohort in COHORTS:
            games = []
            for rotation in range(4):
                games.append(simulate_match(
                    seed, rotation, lineup=ablation_lineup(cohort, rotation)
                ))
                completed += 1
                if on_match is not None:
                    on_match(completed, 8 * seeds)
            totals = _counts(games, cohort)
            if any(row["exposures"] != 4 for row in totals.values()):
                raise RuntimeError("unbalanced ablation seat exposures")
            groups[cohort].append({"seed": seed, "levels": totals})
    output = {}
    for cohort, by_seed in groups.items():
        totals = _totals([item["levels"] for item in by_seed], cohort)
        summary = {
            level: {
                **row,
                **{metric: (
                    round(value, 4) if (value := _ratio(row, metric)) is not None
                    else None
                ) for metric in METRICS},
            }
            for level, row in totals.items()
        }
        intervals = None
        if seeds >= 5:
            rng = Random(20261016)
            samples = {
                level: {metric: [] for metric in METRICS}
                for level in COHORTS[cohort] if level != "challenge"
            }
            for _ in range(bootstrap_replicates):
                sample = [
                    by_seed[rng.randrange(seeds)]["levels"]
                    for _ in range(seeds)
                ]
                differences = _diff(_totals(sample, cohort))
                for level, metrics in differences.items():
                    for metric, difference in metrics.items():
                        if difference is not None:
                            samples[level][metric].append(difference)
            intervals = {
                "method": "whole_shuffle_seed_paired_bootstrap_exploratory",
                "replications": bootstrap_replicates,
                "challenge_minus_other": {
                    level: {
                        metric: _interval(values)
                        for metric, values in metrics.items()
                    }
                    for level, metrics in samples.items()
                },
            }
        output[cohort] = {
            "levels": summary,
            "challenge_minus_other": _diff(totals),
            "per_seed": by_seed,
            "intervals": intervals,
        }
    return {
        "protocol": "challenge_two_cohort_ablation_v1",
        "seed_start": seed_start,
        "independent_shuffle_seeds": seeds,
        "rotations_per_seed_per_cohort": 4,
        "games": completed,
        "cohorts": output,
        "interval_status": (
            "exploratory_only" if seeds >= 5
            else "insufficient_independent_seeds_need_5"
        ),
        "limitations": [
            "cohorts have different fourth opponents; never compare their raw rates directly",
            "four seat rotations within a shuffle seed are correlated",
            "full challenge retains the same internal evaluator used by diagnostic metrics",
            "win events are not formal fully settled match win rates",
            "kong and exhaustive wall payouts remain incomplete",
        ],
    }
