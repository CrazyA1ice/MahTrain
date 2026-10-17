"""M3.32 cross-check decision diagnostics against M3.31 authoritative payoffs.

Diagnostic measures come ONLY from already-finished games and use the project's
existing own-hand oracle. Return aggregate counts, never private action traces,
opponent hands, effective tile arrays, future wall tiles or hand identities.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Sequence

from .ai_independent_scores import LEVELS, independent_lineup


def _blank() -> dict[str, int]:
    return {
        "discards": 0, "min_shanten_cuts": 0, "local_optimal_cuts": 0,
        "effective_copies_total": 0, "shanten_regret_total": 0,
        "win_events": 0, "deal_in_events": 0,
        "seat_exposures": 0,
    }


def _ratio(a: int, b: int, *, digits: int = 4) -> float | None:
    return round(a / b, digits) if b else None


def _score_counts(seeded: list[dict]) -> dict[str, dict[str, int]]:
    rows = {level: _blank() for level in LEVELS}
    for game in seeded:
        assignment = game.get("assignment")
        if (type(assignment) is not list or
                assignment != independent_lineup(game.get("rotation"))):
            raise ValueError("invalid four-policy action attribution")
        for level in assignment:
            rows[level]["seat_exposures"] += 1
        trace = game.get("trace")
        winners = game.get("winners")
        if type(trace) is not list or type(winners) is not list:
            raise ValueError("post-game decision diagnostics missing")
        for win in winners:
            if (type(win) is not dict or
                    type(win.get("seat")) is not int or
                    type(win.get("source")) is not int or
                    win["seat"] not in range(4) or
                    win["source"] not in range(4)):
                raise ValueError("invalid published win responsibility")
            rows[assignment[win["seat"]]]["win_events"] += 1
            if win["source"] != win["seat"]:
                rows[assignment[win["source"]]]["deal_in_events"] += 1
        for event in trace:
            if type(event) is not dict:
                raise ValueError("invalid decision event")
            if event.get("action") != "discard":
                continue
            seat = event.get("seat")
            if type(seat) is not int or seat not in range(4):
                raise ValueError("invalid discard seat")
            if event.get("level") != assignment[seat]:
                raise ValueError("decision attribution mismatches assigned strategy")
            regret = event.get("shanten_regret")
            copies = event.get("effective_copies")
            optimal = event.get("locally_optimal")
            if (type(regret) is not int or not 0 <= regret <= 20
                    or type(copies) is not int or not 0 <= copies <= 108
                    or type(optimal) is not bool):
                raise ValueError("invalid private-oracle diagnostic")
            row = rows[assignment[seat]]
            row["discards"] += 1
            row["min_shanten_cuts"] += int(regret == 0)
            row["local_optimal_cuts"] += int(optimal)
            row["effective_copies_total"] += copies
            row["shanten_regret_total"] += regret
    return rows


def _summary(row: dict[str, int]) -> dict[str, Any]:
    return {
        **row,
        "min_shanten_fraction": _ratio(row["min_shanten_cuts"], row["discards"]),
        "local_optimal_fraction": _ratio(row["local_optimal_cuts"], row["discards"]),
        "mean_effective_copies": _ratio(
            row["effective_copies_total"], row["discards"], digits=3),
        "mean_shanten_regret": _ratio(
            row["shanten_regret_total"], row["discards"], digits=3),
        "deal_in_events_per_100_discards": (
            _ratio(row["deal_in_events"] * 100, row["discards"], digits=3)
        ),
    }


def analyze_decision_score_diagnostics(
    matches: Sequence[dict[str, Any]], score_analysis: dict[str, Any],
) -> dict[str, Any]:
    """Compute decision quality on EXACTLY the valid official-score seed cohort."""
    if (type(score_analysis) is not dict or
            score_analysis.get("protocol") !=
            "paired_initial_shuffle_4_rotation_official_a_v1"
            or score_analysis.get("zero_sum") is not True):
        raise ValueError("requires M3.31 trusted official score analysis")
    per_seed = score_analysis.get("per_seed")
    if type(per_seed) is not list or type(matches) is not list:
        raise ValueError("invalid decision/official experiment inputs")
    if (type(score_analysis.get("requested_seeds")) is not int or
            type(score_analysis.get("valid_seeds")) is not int or
            len(per_seed) != score_analysis["valid_seeds"] or
            type(score_analysis.get("excluded_seed_ids")) is not list):
        raise ValueError("inconsistent official score cohort")

    grouped: dict[int, dict[int, dict]] = defaultdict(dict)
    for game in matches:
        if type(game) is not dict:
            raise ValueError("invalid experiment game")
        seed, rotation = game.get("seed"), game.get("rotation")
        if (type(seed) is not int or not 0 <= seed < 2**32 or
                type(rotation) is not int or rotation not in range(4)
                or rotation in grouped[seed]):
            raise ValueError("invalid/duplicate seed rotation")
        grouped[seed][rotation] = game
    if len(grouped) != score_analysis["requested_seeds"]:
        raise ValueError("decision games do not cover requested seeds")

    valid_ids = [entry.get("seed") for entry in per_seed]
    if (any(type(seed) is not int for seed in valid_ids)
            or len(valid_ids) != len(set(valid_ids))
            or set(valid_ids) & set(score_analysis["excluded_seed_ids"])
            or set(grouped) != set(valid_ids) |
            set(score_analysis["excluded_seed_ids"])):
        raise ValueError("official and diagnostic seed sets disagree")
    totals = {level: _blank() for level in LEVELS}
    disagreement = {
        level: {
            "comparable_seeds": 0,
            "higher_min_shanten_but_lower_score_seeds": 0,
            "lower_min_shanten_but_higher_score_seeds": 0,
        } for level in LEVELS if level != "baseline"
    }
    observed = 0
    for official in per_seed:
        seed = official["seed"]
        rotations = grouped[seed]
        if sorted(rotations) != [0, 1, 2, 3]:
            raise ValueError("valid seed lacks a complete four-seat rotation")
        games = [rotations[r] for r in range(4)]
        counts = _score_counts(games)
        official_rows = official.get("levels")
        if type(official_rows) is not dict:
            raise ValueError("official cluster lacks seat scores")
        for level in LEVELS:
            if counts[level]["seat_exposures"] != 4:
                raise ValueError("unbalanced diagnostic seat exposure")
            row = official_rows.get(level)
            if (type(row) is not dict or row.get("seat_exposures") != 4
                    or type(row.get("official_total")) is not int):
                raise ValueError("official seed score and diagnostics mismatch")
            real_score = sum(
                game["official_settled_balances"][seat]
                for game in games
                for seat, selected in enumerate(game["assignment"])
                if selected == level
            )
            if real_score != row["official_total"]:
                raise ValueError("official payoffs differ from scored games")
            for field in totals[level]:
                totals[level][field] += counts[level][field]
        baseline = counts["baseline"]
        baseline_score = official_rows["baseline"]["official_total"]
        for level in disagreement:
            opponent = counts[level]
            if baseline["discards"] == 0 or opponent["discards"] == 0:
                continue
            a = opponent["min_shanten_cuts"] * baseline["discards"]
            b = baseline["min_shanten_cuts"] * opponent["discards"]
            delta_score = official_rows[level]["official_total"] - baseline_score
            disagreement[level]["comparable_seeds"] += 1
            if a > b and delta_score < 0:
                disagreement[level]["higher_min_shanten_but_lower_score_seeds"] += 1
            if a < b and delta_score > 0:
                disagreement[level]["lower_min_shanten_but_higher_score_seeds"] += 1
        observed += len(games)
    if observed != score_analysis.get("complete_games"):
        raise ValueError("diagnostic games do not match official accepted cohort")
    return {
        "protocol": "decision_quality_vs_rule_a_official_points_v1",
        "cohort": "only_complete_verified_m331_seed_clusters",
        "valid_seeds": len(per_seed),
        "excluded_seed_count": score_analysis["excluded_seed_count"],
        "complete_games": observed,
        "levels": {level: _summary(totals[level]) for level in LEVELS},
        "direction_disagreements_vs_baseline": disagreement,
        "warnings": [
            "minimum-shanten and effective-copies use the same internal own-hand evaluator across policies",
            "effective copies are the chosen discard's nominal visible-adjusted tile count, not realized future draws",
            "observed deal-in events per 100 discards are descriptive, not calibrated risk probabilities",
            "four rotated matches with one initial shuffle remain a single correlated seed sample",
            "min-shanten quality and official settled points are not causally linked by this analysis",
            "do not treat absent discard samples or excluded unsettled wall draws as zero performance",
            "all private decision records remain on server; only aggregates are returned",
        ],
    }
