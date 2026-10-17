"""M3.30 controlled three-tier AI score analysis under confirmed rule A.

Each shuffle seed is a CLUSTER of 3 dependent seat rotations. Only a FULLY
verified seed (all rotations with complete official settlement) contributes
to official-score comparisons; an unresolved wall-draw excludes the entire
seed instead of treating incomplete points as valid or as zero. AI policy
choices alter downstream actions, so this is paired INITIAL shuffling, not
identical counterfactual game trajectories.
"""
from __future__ import annotations

from collections import defaultdict
from random import Random
from typing import Any, Sequence

from .ai import AI_LEVELS

LEVELS = tuple(AI_LEVELS)
PAIRINGS = ("basic", "advanced")
MIN_SEEDS_FOR_INTERVAL = 5
DEFAULT_BOOTSTRAP_REPLICATES = 400


def _assignment(rotation: int) -> list[str]:
    return [LEVELS[(seat + rotation) % 3] for seat in range(4)]


def _interval(values: list[float]) -> list[float]:
    values.sort()
    n = len(values)
    return [round(values[int((n - 1) * .025)], 3),
            round(values[int((n - 1) * .975)], 3)]


def controlled_official_scores(
    matches: Sequence[dict[str, Any]],
    *, bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    """Analyze independent seed clusters using ONLY verified official scores."""
    if (type(bootstrap_replicates) is not int or
            not 100 <= bootstrap_replicates <= 2000):
        raise ValueError("bootstrap replicates must be 100..2000")
    if not matches:
        raise ValueError("no simulated matches")
    groups: dict[int, dict[int, dict]] = defaultdict(dict)
    for game in matches:
        if type(game) is not dict:
            raise ValueError("malformed simulated match")
        seed, rotation = game.get("seed"), game.get("rotation")
        if (type(seed) is not int or not 0 <= seed < 2**32 or
                type(rotation) is not int or rotation not in range(3)):
            raise ValueError("invalid seed or seat rotation")
        if rotation in groups[seed]:
            raise ValueError("duplicate seed/rotation")
        if game.get("assignment") != _assignment(rotation):
            raise ValueError("unequal seat assignment per rotation")
        rules = game.get("scoring_rules")
        if (type(rules) is not dict or
                type(rules.get("room_coefficient")) is not int or
                rules["room_coefficient"] <= 0 or
                type(rules.get("fan_cap")) is not int or
                not 0 <= rules["fan_cap"] <= 12 or
                rules.get("kong_base") is not None):
            raise ValueError("controlled experiment must use fixed valid rules")
        if type(game.get("official_exhaustive_posted")) is not bool:
            raise ValueError("missing official exhaustive settlement status")
        if game.get("terminal_phase") not in ("finished", "wall_exhausted"):
            raise ValueError("experiment game is not terminal")
        hu = game.get("partial_win_balances")
        total = game.get("official_settled_balances")
        if (type(hu) is not list or len(hu) != 4 or
                type(total) is not list or len(total) != 4 or
                any(type(v) is not int for v in hu + total) or
                sum(hu) or sum(total)):
            raise ValueError("invalid zero-sum official score ledger")
        # A finished round (three winners) cannot also settle wall exhaustion.
        if game["terminal_phase"] == "finished" and game["official_exhaustive_posted"]:
            raise ValueError("non-wall game cannot post exhaustive settlement")
        if (game["terminal_phase"] == "finished" and hu != total):
            raise ValueError("non-wall game changed official HU score")
        if game["terminal_phase"] == "wall_exhausted" and not game["official_exhaustive_posted"] and hu != total:
            raise ValueError("unresolved wall game claims posted score")
        groups[seed][rotation] = game
    expected_seeds = sorted(groups)
    if (any(sorted(games) != [0, 1, 2] for games in groups.values()) or
            expected_seeds != list(range(expected_seeds[0],
                                         expected_seeds[0] + len(expected_seeds)))):
        raise ValueError("experiment requires contiguous independent seed clusters and three rotations")
    fixed = None
    verified = []
    excluded = []
    for seed in expected_seeds:
        rotations = [groups[seed][r] for r in range(3)]
        for game in rotations:
            settings = game["scoring_rules"]
            config = (settings["room_coefficient"], settings["fan_cap"])
            if fixed is None:
                fixed = config
            if config != fixed:
                raise ValueError("controlled experiment mixed scoring rules")
        if any(g["terminal_phase"] == "wall_exhausted" and
               not g["official_exhaustive_posted"] for g in rotations):
            excluded.append(seed)
            continue
        totals = {level: 0 for level in LEVELS}
        exposure = {level: [0, 0, 0, 0] for level in LEVELS}
        for game in rotations:
            for seat, level in enumerate(game["assignment"]):
                totals[level] += game["official_settled_balances"][seat]
                exposure[level][seat] += 1
        if (any(exposure[level] != [1, 1, 1, 1] for level in LEVELS) or
                sum(totals.values()) != 0):
            raise ValueError("unequal seat exposure or nonzero experiment scores")
        verified.append({
            "seed": seed, "games": 3,
            "levels": {
                level: {"seat_exposures": 4, "official_total": totals[level],
                        "official_mean_per_exposure": round(totals[level] / 4, 3)}
                for level in LEVELS
            },
        })
    n = len(verified)
    aggregates = {}
    for level in LEVELS:
        total = sum(cluster["levels"][level]["official_total"] for cluster in verified)
        aggregates[level] = {
            "seat_exposures": n * 4,
            "official_total": total,
            "official_mean_per_exposure": round(total / (n * 4), 3) if n else None,
        }
    differences = {
        "challenge_minus_" + other: (
            round(aggregates["challenge"]["official_mean_per_exposure"] -
                  aggregates[other]["official_mean_per_exposure"], 3)
            if n else None
        ) for other in PAIRINGS
    }
    intervals = None
    if n >= MIN_SEEDS_FOR_INTERVAL:
        rng = Random(20261017)
        draws = {level: [] for level in LEVELS}
        diffs = {key: [] for key in differences}
        for _ in range(bootstrap_replicates):
            chosen = [verified[rng.randrange(n)] for _ in range(n)]
            means = {
                level: sum(x["levels"][level]["official_total"]
                           for x in chosen) / (n * 4)
                for level in LEVELS
            }
            for level in LEVELS:
                draws[level].append(means[level])
            for other in PAIRINGS:
                diffs["challenge_minus_" + other].append(
                    means["challenge"] - means[other]
                )
        intervals = {
            "method": "paired_shuffle_seed_cluster_bootstrap_exploratory",
            "replications": bootstrap_replicates,
            "levels": {level: _interval(v) for level, v in draws.items()},
            "differences": {key: _interval(v) for key, v in diffs.items()},
        }
    if sum(row["official_total"] for row in aggregates.values()) != 0:
        raise ValueError("controlled scoring not zero-sum")
    return {
        "protocol": "paired_initial_shuffle_3_rotation_official_a_v1",
        "room_coefficient": fixed[0], "fan_cap": fixed[1],
        "kong_included": False, "independence_unit": "initial_shuffle_seed",
        "requested_seeds": len(groups), "valid_seeds": n,
        "excluded_seed_count": len(excluded),
        "excluded_seed_ids": excluded, "games_per_seed": 3,
        "complete_games": n * 3, "per_seed": verified,
        "levels": aggregates, "paired_differences": differences,
        "interval_status": ("exploratory_only" if intervals else
                            "insufficient_valid_independent_seeds_need_5"),
        "intervals": intervals,
        "zero_sum": True,
        "limitations": [
            "three rotations share the same seed and count as ONE correlated unit",
            "same initial shuffle does NOT imply identical later draws or choices",
            "AI agents compete with themselves under prototype rules, not humans",
            "only confirmed rule-A exhaustive draws join official settled points",
            "unresolved wall-draws exclude all three rotations of that seed",
            "kong payments are deliberately disabled for controlled scores",
            "bootstrap intervals are exploratory, NOT skill or win-rate confidence claims",
        ],
    }
