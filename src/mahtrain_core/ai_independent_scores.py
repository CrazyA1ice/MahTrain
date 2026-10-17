"""M3.31 paired four-policy official scoring under active-only (rule A).

Each initial shuffle seed produces FOUR dependent matches: a cyclic rotation
places baseline/basic/advanced/challenge in every seat exactly once. Exclude
a WHOLE seed cluster if any terminal wall settlement is unresolved. Paired
initial seeds do not force identical later trajectories under different AI.
"""
from __future__ import annotations

from collections import defaultdict
from random import Random
from typing import Any, Sequence

from .ai_independent_benchmark import LEVELS, independent_lineup

MIN_INTERVAL_SEEDS = 5


def _interval(values: list[float]) -> list[float]:
    values.sort()
    n = len(values)
    return [round(values[int((n - 1) * .025)], 3),
            round(values[int((n - 1) * .975)], 3)]


def controlled_four_policy_scores(
    matches: Sequence[dict[str, Any]], *,
    bootstrap_replicates: int = 400,
) -> dict[str, Any]:
    """Reconcile trusted HU and rule-A official balances per seed cluster."""
    if (type(bootstrap_replicates) is not int or
            not 100 <= bootstrap_replicates <= 2000):
        raise ValueError("bootstrap replicates must be an integer 100..2000")
    if not matches:
        raise ValueError("need at least one seed cluster")
    groups: dict[int, dict[int, dict[str, Any]]] = defaultdict(dict)
    fixed: tuple[int, int] | None = None
    for item in matches:
        if not isinstance(item, dict):
            raise ValueError("malformed game")
        seed, rotation = item.get("seed"), item.get("rotation")
        if (type(seed) is not int or not 0 <= seed < 2**32 or
                type(rotation) is not int or rotation not in range(4)):
            raise ValueError("invalid seed or four-seat rotation")
        if rotation in groups[seed]:
            raise ValueError("duplicate seed/rotation")
        if item.get("assignment") != independent_lineup(rotation):
            raise ValueError("four strategies must rotate through all four seats")
        rules = item.get("scoring_rules")
        if (type(rules) is not dict or
                type(rules.get("room_coefficient")) is not int or
                not 1 <= rules["room_coefficient"] <= 10**6 or
                type(rules.get("fan_cap")) is not int or
                not 0 <= rules["fan_cap"] <= 12 or
                rules.get("kong_base") is not None):
            raise ValueError("fixed scoring requires legitimate room rules and unpriced kongs")
        parameters = (rules["room_coefficient"], rules["fan_cap"])
        if fixed is None:
            fixed = parameters
        if parameters != fixed:
            raise ValueError("different scoring configurations cannot share a paired experiment")
        phase, posted = item.get("terminal_phase"), item.get("official_exhaustive_posted")
        if phase not in ("finished", "wall_exhausted") or type(posted) is not bool:
            raise ValueError("game must have a trusted terminal official-settlement status")
        hu, official = (item.get("partial_win_balances"),
                        item.get("official_settled_balances"))
        if any(type(v) is not list or len(v) != 4 or
               any(type(score) is not int for score in v) or sum(v) != 0
               for v in (hu, official)):
            raise ValueError("all authoritative scores must be four-seat integer zero sum")
        if phase == "finished" and (posted or hu != official):
            raise ValueError("completed three-winner game cannot add wall money")
        if phase == "wall_exhausted" and not posted and hu != official:
            raise ValueError("unresolved terminal draw claims extra official payment")
        groups[seed][rotation] = item
    seeds = sorted(groups)
    if (seeds != list(range(seeds[0], seeds[0] + len(seeds))) or
            any(sorted(group) != [0, 1, 2, 3] for group in groups.values())):
        raise ValueError("four complete rotations per contiguous shuffle seed are required")

    included, excluded = [], []
    for seed in seeds:
        games = [groups[seed][rotation] for rotation in range(4)]
        if any(g["terminal_phase"] == "wall_exhausted" and
               not g["official_exhaustive_posted"] for g in games):
            excluded.append(seed)
            continue
        totals = {level: 0 for level in LEVELS}
        by_seat = {level: [0] * 4 for level in LEVELS}
        for game in games:
            for seat, level in enumerate(game["assignment"]):
                totals[level] += game["official_settled_balances"][seat]
                by_seat[level][seat] += 1
        if (any(exposure != [1, 1, 1, 1] for exposure in by_seat.values())
                or sum(totals.values()) != 0):
            raise ValueError("strategy exposures or official payoff ledger not zero-sum")
        included.append({
            "seed": seed, "games": 4,
            "levels": {
                level: {
                    "seat_exposures": 4,
                    "official_total": totals[level],
                    "official_mean_per_exposure": round(totals[level] / 4, 3),
                } for level in LEVELS
            },
        })
    valid = len(included)
    level_stats = {}
    for level in LEVELS:
        score = sum(cluster["levels"][level]["official_total"] for cluster in included)
        level_stats[level] = {
            "seat_exposures": valid * 4,
            "official_total": score,
            "official_mean_per_exposure": (
                round(score / (valid * 4), 3) if valid else None
            ),
        }
    differences = {
        level: (round(level_stats[level]["official_mean_per_exposure"] -
                      level_stats["baseline"]["official_mean_per_exposure"], 3)
                if valid else None)
        for level in LEVELS if level != "baseline"
    }
    intervals = None
    if valid >= MIN_INTERVAL_SEEDS:
        rng = Random(20261017)
        samples = {level: [] for level in LEVELS}
        contrast = {level: [] for level in differences}
        for _ in range(bootstrap_replicates):
            chosen = [included[rng.randrange(valid)] for _ in range(valid)]
            averages = {
                level: sum(group["levels"][level]["official_total"]
                           for group in chosen) / (valid * 4)
                for level in LEVELS
            }
            for level in LEVELS:
                samples[level].append(averages[level])
            for level in contrast:
                contrast[level].append(averages[level] - averages["baseline"])
        intervals = {
            "method": "paired_shuffle_seed_cluster_bootstrap_exploratory",
            "replications": bootstrap_replicates,
            "levels": {level: _interval(values) for level, values in samples.items()},
            "differences_vs_baseline": {
                level: _interval(values) for level, values in contrast.items()
            },
        }
    if sum(row["official_total"] for row in level_stats.values()) != 0:
        raise ValueError("non-zero-sum four-policy experiment")
    return {
        "protocol": "paired_initial_shuffle_4_rotation_official_a_v1",
        "independence_unit": "initial_shuffle_seed",
        "room_coefficient": fixed[0],
        "fan_cap": fixed[1],
        "kong_included": False,
        "requested_seeds": len(seeds),
        "valid_seeds": valid,
        "excluded_seed_count": len(excluded),
        "excluded_seed_ids": excluded,
        "games_per_seed": 4,
        "complete_games": valid * 4,
        "levels": level_stats,
        "paired_differences_vs_baseline": differences,
        "per_seed": included,
        "interval_status": (
            "exploratory_only" if intervals is not None
            else "insufficient_valid_independent_seeds_need_5"
        ),
        "intervals": intervals,
        "zero_sum": True,
        "limitations": [
            "four seat rotations using the same shuffle are ONE dependent seed cluster",
            "same initial shuffle does not imply identical later draw trajectories",
            "standalone shape baseline is independent in choice rule but not a trained external model",
            "only posted HU and verified active-only rule-A exhausted-wall payments are official",
            "one unresolved wall draw excludes the whole four-rotation seed cluster",
            "kong money excluded, other rule details remain part of a local prototype",
            "exploratory seed bootstrap intervals are not human or online win-rate intervals",
        ],
    }
