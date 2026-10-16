"""M3.10 five-policy discard-component ablation under the draft game rules.

Every independent shuffle seed has five *dependent* games. A cyclic incomplete
block of five policies occupying four seats ensures each policy appears once
in EACH seat per seed; one policy rests in each rotation. Do not treat the five
matches as five independent experiments or the win events as official wins.
"""
from __future__ import annotations

from random import Random
from typing import Any

from .ai_tournament import simulate_match

LEVELS = ("baseline", "advanced", "challenge_no_ukeire",
          "challenge_no_pressure", "challenge")
METRICS = ("win_event_fraction", "min_shanten_fraction",
           "local_optimal_fraction")
# First policy minus second policy, per whole-shuffle-seed paired cluster.
CONTRASTS = (
    ("challenge", "challenge_no_pressure"),
    ("challenge", "challenge_no_ukeire"),
    ("challenge_no_pressure", "advanced"),
    ("challenge_no_ukeire", "advanced"),
    ("challenge", "baseline"),
)
MIN_SEEDS_FOR_INTERVAL = 5


def ablation_lineup(rotation: int) -> list[str]:
    if type(rotation) is not int or rotation not in range(5):
        raise ValueError("ablation rotation must be 0..4")
    return [LEVELS[(seat + rotation) % 5] for seat in range(4)]


def _empty() -> dict[str, int]:
    return {"exposures": 0, "wins": 0, "deal_ins": 0,
            "discards": 0, "minimum_shanten": 0, "local_optimal": 0}


def _totals(games: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result = {level: _empty() for level in LEVELS}
    for game in games:
        assignment = game["assignment"]
        if (len(assignment) != 4 or len(set(assignment)) != 4 or
                any(level not in result for level in assignment)):
            raise ValueError("invalid four-player ablation lineup")
        for level in assignment:
            result[level]["exposures"] += 1
        for winner in game["winners"]:
            seat, source = winner["seat"], winner["source"]
            result[assignment[seat]]["wins"] += 1
            if source != seat:
                result[assignment[source]]["deal_ins"] += 1
        for event in game["trace"]:
            if event["action"] != "discard":
                continue
            row = result[assignment[event["seat"]]]
            row["discards"] += 1
            row["minimum_shanten"] += int(event["shanten_regret"] == 0)
            row["local_optimal"] += int(event["locally_optimal"])
    return result


def _ratio(row: dict[str, int], metric: str) -> float | None:
    numerator, denominator = {
        "win_event_fraction": ("wins", "exposures"),
        "min_shanten_fraction": ("minimum_shanten", "discards"),
        "local_optimal_fraction": ("local_optimal", "discards"),
    }[metric]
    return (row[numerator] / row[denominator]
            if row[denominator] else None)


def _difference(totals: dict[str, dict[str, int]], a: str,
                b: str, metric: str) -> float | None:
    x, y = _ratio(totals[a], metric), _ratio(totals[b], metric)
    return None if x is None or y is None else x - y


def _quantiles(values: list[float]) -> list[float] | None:
    if not values:
        return None
    values.sort()
    n = len(values)
    return [round(values[int((n-1)*.025)], 4),
            round(values[int((n-1)*.975)], 4)]


def ablation_benchmark(seed_start: int = 11, seeds: int = 1, *,
                       on_match: Any = None, include_traces: bool = False,
                       bootstrap_replicates: int = 400) -> dict[str, Any]:
    if (type(seed_start) is not int or not 0 <= seed_start < 2**32
            or type(seeds) is not int or not 1 <= seeds <= 50
            or seed_start + seeds > 2**32):
        raise ValueError("seed_start must be uint32 and seeds 1..50")
    if (type(bootstrap_replicates) is not int
            or not 100 <= bootstrap_replicates <= 2000):
        raise ValueError("bootstrap_replicates must be 100..2000")

    by_seed = []
    matches = []
    for seed in range(seed_start, seed_start + seeds):
        batch = []
        for rotation in range(5):
            game = simulate_match(seed, rotation=rotation,
                                  lineup=ablation_lineup(rotation))
            batch.append(game)
            matches.append(game)
            if on_match is not None:
                on_match(len(matches), seeds*5)
        subtotal = _totals(batch)
        if any(row["exposures"] != 4 for row in subtotal.values()):
            raise RuntimeError("unbalanced ablation seat exposure")
        by_seed.append({"seed": seed, "rotations": 5, "levels": subtotal})

    totals = _totals(matches)
    if any(row["exposures"] != 4*seeds for row in totals.values()):
        raise RuntimeError("unbalanced total ablation seat exposure")
    summary = {
        level: {**totals[level], **{
            metric: (round(ratio, 4)
                     if (ratio := _ratio(totals[level], metric)) is not None
                     else None)
            for metric in METRICS
        }}
        for level in LEVELS
    }
    differences = {
        a+"_vs_"+b: {
            metric: (round(value, 4)
                     if (value := _difference(totals, a, b, metric))
                     is not None else None)
            for metric in METRICS
        }
        for a, b in CONTRASTS
    }
    intervals = None
    if seeds >= MIN_SEEDS_FOR_INTERVAL:
        rng = Random(20261016)
        bootstrap = {
            a+"_vs_"+b: {metric: [] for metric in METRICS}
            for a, b in CONTRASTS
        }
        for _ in range(bootstrap_replicates):
            sampled = {level: _empty() for level in LEVELS}
            for _ in range(seeds):
                group = by_seed[rng.randrange(seeds)]["levels"]
                for level in LEVELS:
                    for metric, value in group[level].items():
                        sampled[level][metric] += value
            for a, b in CONTRASTS:
                for metric in METRICS:
                    diff = _difference(sampled, a, b, metric)
                    if diff is not None:
                        bootstrap[a+"_vs_"+b][metric].append(diff)
        intervals = {
            "method": "whole_shuffle_seed_paired_bootstrap_exploratory",
            "replications": bootstrap_replicates,
            "paired_differences": {
                contrast: {
                    metric: _quantiles(values)
                    for metric, values in measures.items()
                }
                for contrast, measures in bootstrap.items()
            },
        }

    return {
        "protocol": "five_policy_four_seat_incomplete_block_ablation_v1",
        "independent_shuffle_seeds": seeds,
        "seed_start": seed_start,
        "games": len(matches),
        "rotations_per_seed": 5,
        "opponents": list(LEVELS),
        "seat_balance": "each policy appears in every seat once per shuffle seed",
        "ablation_controls": {
            "advanced": "min shanten; stable tile order on tie",
            "challenge_no_ukeire": "min shanten then public meld pressure; no effective-copy ranking",
            "challenge_no_pressure": "min shanten then public effective copies; no pressure tie-break",
            "challenge": "min shanten then public effective copies then pressure",
            "baseline": "separate shape-only policy, no shanten oracle",
        },
        "levels": summary,
        "paired_differences": differences,
        "per_seed": by_seed,
        "terminal_phase_counts": {
            phase: sum(game["terminal_phase"] == phase for game in matches)
            for phase in ("finished", "wall_exhausted")
        },
        "interval_status": ("exploratory_only" if intervals is not None
                            else "insufficient_independent_seeds_need_5"),
        "intervals": intervals,
        "matches": matches if include_traces else [
            {key: value for key, value in game.items()
             if key not in ("trace", "public_events", "public_replay")}
            for game in matches
        ],
        "limitations": [
            "five rotations of one shuffle seed are dependent, not five samples",
            "the 5-policy comparisons are shared-shuffle but different-seat games",
            "the same internal oracle evaluates shanten and local optimality",
            "prototype win events do not establish official settled win rates",
            "unconfirmed kong and exhaustive-draw payments are not posted",
            "a weak public meld pressure heuristic is not validated danger prediction",
        ],
    }
