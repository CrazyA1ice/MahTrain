"""M3.94: genuine-reference-regret-only offline challenge cut ablation.

A different TILE from the reference rank-1 is not necessarily a worse cut:
public-reference candidates may tie. Intervene only when the actual challenge
discard has reference_best=False, and never use hidden opponent/wall data.
Research-only; not imported by web_server nor the deployed challenge AI.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from random import Random
from statistics import mean
from typing import Any, Mapping, Sequence

from .ai import MahjongAgent
from .ai_challenge_reference_paired import LEVELS, _outcomes, _validate_result
from .ai_tournament import simulate_match
from .classic_hint import classic_archive_seat_hint
from .rules import TILE_INDEX

PROTOCOL = "m394_true_reference_regret_independent_holdout_v1"
REASONS = (
    "agreed_first", "equal_best_other_tile", "unscored",
    "shanten_gap", "tenpai_fan_weighted_gap", "tenpai_ukeire_gap",
    "ukeire_gap", "other_reference_gap",
)
REGRET_REASONS = REASONS[3:]


def classify_disagreement(candidates: Sequence[Mapping[str, Any]],
                          actual: str) -> tuple[str, str | None]:
    """Return honest category and the reference first-place tile, if any.

    'equal_best_other_tile' MUST NOT trigger intervention. Ranking is the
    public-information reference at the actual decision time, not a winning
    chance, omniscient hand strength or a calibrated ron-risk estimate.
    """
    if not candidates:
        return "unscored", None
    best = candidates[0]
    if not best["reference_best"]:
        raise ValueError("reference order does not start with its best cut")
    found = next((c for c in candidates if c["discard"] == actual), None)
    if found is None:
        raise ValueError("actual cut absent from authorized reference candidates")
    if found["reference_best"]:
        return ("agreed_first" if actual == best["discard"] else
                "equal_best_other_tile"), best["discard"]
    if found["shanten"] > best["shanten"]:
        return "shanten_gap", best["discard"]
    if found["shanten"] == 0:
        b_weight = best.get("fan_weighted_unknown_copies")
        a_weight = found.get("fan_weighted_unknown_copies")
        if (type(b_weight) is int and type(a_weight) is int
                and a_weight < b_weight):
            return "tenpai_fan_weighted_gap", best["discard"]
        if (found["effective_tile_count_upper_bound"] <
                best["effective_tile_count_upper_bound"]):
            return "tenpai_ukeire_gap", best["discard"]
    elif (found["effective_tile_count_upper_bound"] <
          best["effective_tile_count_upper_bound"]):
        return "ukeire_gap", best["discard"]
    return "other_reference_gap", best["discard"]


class RegretOnlyResearchAgent(MahjongAgent):
    """Frozen challenge policy except for genuinely below-reference cuts."""

    _offline_reference_cut = True

    def __init__(self, *, seed: int, seat: int) -> None:
        super().__init__("challenge", seed=seed, seat=seat)
        self._counts: Counter[str] = Counter()

    def discard(self, view: Mapping[str, Any]) -> str:
        original = super().discard(view)
        advice = classic_archive_seat_hint(view, self.seat)
        reason, reference = classify_disagreement(
            advice.get("candidates") or [], original)
        self._counts["decisions"] += 1
        self._counts[reason] += 1
        risk_rows = self._last_discard_scores
        if risk_rows is not None:
            raw = min(risk_rows, key=lambda row: (
                -row["expected_fan_weighted_copies"],
                -row["effective_tile_count"],
                TILE_INDEX[row["discard"]],
            ))["discard"]
            risk_flip = raw != original
            self._counts["measurable_risk_decisions"] += 1
            self._counts["public_risk_flip"] += int(risk_flip)
            if reason in REGRET_REASONS:
                self._counts["regret_and_risk_flip"] += int(risk_flip)
                self._counts["regret_and_no_risk_flip"] += int(not risk_flip)
                # Descriptive concordance, NOT causal risk attribution.
                self._counts["risk_flip_from_reference"] += int(
                    risk_flip and raw == reference)
        elif reason in REGRET_REASONS:
            self._counts["regret_without_challenge_ranking"] += 1

        if reason in REGRET_REASONS:
            if reference is None or reference not in view["hand"]:
                raise RuntimeError("intervention must be in own legal hand")
            self._counts["changed_cuts"] += 1
            return reference
        return original

    def safe_counts(self) -> dict[str, int]:
        # Aggregate only: no hidden hand, candidate tile, discard, wall or
        # private observation is returned to the caller or stored in history.
        names = (
            "decisions", *REASONS, "measurable_risk_decisions",
            "public_risk_flip", "regret_and_risk_flip",
            "regret_and_no_risk_flip", "risk_flip_from_reference",
            "regret_without_challenge_ranking", "changed_cuts",
        )
        return {name: self._counts[name] for name in names}


def _pair(seed: int, rotation: int) -> dict[str, Any]:
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("invalid seed")
    if type(rotation) is not int or rotation not in range(4):
        raise ValueError("rotation must be 0..3")
    lineup = [LEVELS[(seat + rotation) % 4] for seat in range(4)]
    seat = lineup.index("challenge")
    baseline = simulate_match(
        seed, rotation=rotation % 3, lineup=lineup, offline_kong_base=1)
    treatment_agent = RegretOnlyResearchAgent(seed=seed, seat=seat)
    treatment = simulate_match(
        seed, rotation=rotation % 3, lineup=lineup, offline_kong_base=1,
        offline_agent_overrides={seat: treatment_agent})
    for game in (baseline, treatment):
        _validate_result(game, lineup)
    first, second = _outcomes(baseline, seat), _outcomes(treatment, seat)
    return {
        "seed": seed, "rotation": rotation, "seat": seat,
        "baseline": first, "regret_only": second,
        "delta_net": second["official_net"] - first["official_net"],
        "decision_counts": treatment_agent.safe_counts(),
    }


def _cohort(seed_start: int, count: int, rotations: int) -> dict[str, Any]:
    pairs = [_pair(seed, rotation)
             for seed in range(seed_start, seed_start + count)
             for rotation in range(rotations)]
    seed_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
    diagnostic: Counter[str] = Counter()
    for row in pairs:
        seed_rows[row["seed"]].append(row)
        diagnostic.update(row["decision_counts"])
    per_seed = [{
        "seed": seed,
        "rotation_deltas": [item["delta_net"] for item in rows],
        "mean_delta_net": round(mean(item["delta_net"] for item in rows), 4),
        "changed_cuts": sum(item["decision_counts"]["changed_cuts"]
                            for item in rows),
    } for seed, rows in sorted(seed_rows.items())]
    means = [item["mean_delta_net"] for item in per_seed]
    return {
        "seed_start": seed_start,
        "independent_seeds": count, "rotations": rotations,
        "paired_games": len(pairs),
        "mean_delta_net": round(mean(means), 4),
        "positive_seed_clusters": sum(x > 0 for x in means),
        "negative_seed_clusters": sum(x < 0 for x in means),
        "tied_seed_clusters": sum(x == 0 for x in means),
        "win_event_delta": sum(p["regret_only"]["wins"] - p["baseline"]["wins"]
                               for p in pairs),
        "deal_in_event_delta": sum(
            p["regret_only"]["deal_ins"] - p["baseline"]["deal_ins"]
            for p in pairs),
        "decision_counts": dict(diagnostic),
        "per_seed": per_seed,
        "pairs": pairs,
    }


def _cluster_bootstrap(seed_means: Sequence[float],
                       *, repeats: int = 2000) -> dict[str, Any]:
    """Exploratory seeded percentile bootstrap; resample SHUFFLE SEEDS."""
    if not seed_means:
        raise ValueError("must have observed independent seeds")
    rng = Random(394)
    n = len(seed_means)
    sampled = sorted(mean(seed_means[rng.randrange(n)] for _ in range(n))
                     for _ in range(repeats))
    return {
        "method": "seed_cluster_percentile_bootstrap_exploratory",
        "unit": "initial_shuffle_seed",
        "independent_seeds": n,
        "resamples": repeats,
        "lower": round(sampled[int(.025 * (repeats - 1))], 4),
        "upper": round(sampled[int(.975 * (repeats - 1))], 4),
        "warning": ("Exploratory interval only; sparse seeds or rare changed "
                    "cuts give weak uncertainty coverage. No proof of superiority."),
    }


def study(*, development_start: int = 8420,
          holdout_start: int = 9400, seeds_per_group: int = 2,
          rotations: int = 4) -> dict[str, Any]:
    """Predeclare disjoint seed cohorts, never select on favorable outcomes."""
    if (type(development_start) is not int or
            type(holdout_start) is not int or
            type(seeds_per_group) is not int or
            type(rotations) is not int or
            not 0 <= development_start < 2**32 or
            not 0 <= holdout_start < 2**32 or
            not 1 <= seeds_per_group <= 16 or
            rotations not in (1, 2, 3, 4) or
            development_start + seeds_per_group > 2**32 or
            holdout_start + seeds_per_group > 2**32 or
            not (development_start + seeds_per_group <= holdout_start or
                 holdout_start + seeds_per_group <= development_start)):
        raise ValueError("invalid, overlapping or incomplete experiment cohorts")
    development = _cohort(development_start, seeds_per_group, rotations)
    holdout = _cohort(holdout_start, seeds_per_group, rotations)
    for group in (development, holdout):
        all_counts = group["decision_counts"]
        evaluated = sum(all_counts.get(reason, 0) for reason in REASONS)
        if (evaluated != all_counts.get("decisions", 0) or
            all_counts.get("changed_cuts", 0) != sum(
                all_counts.get(reason, 0) for reason in REGRET_REASONS)):
            raise RuntimeError("inconsistent intervention/decision attribution")
        group["cluster_interval_exploratory"] = _cluster_bootstrap(
            [row["mean_delta_net"] for row in group["per_seed"]])
    return {
        "protocol": PROTOCOL, "intervention": "true_reference_regret_only",
        "development": development, "holdout": holdout,
        "holdout_predeclared": True,
        "live_ai_modified": False,
        "room_coefficient": 100, "official_kong_base": 1,
        "limits": [
            "An alternate equal-best reference tile is NOT an AI error and is not replaced.",
            "Risk counters describe shared-view ranking, never actual ron probabilities.",
            "Post-intervention trajectories diverge; later cuts are not causal attributions.",
            "Seed clusters, not rotations or decisions, define sample size.",
            "Small exploratory bootstrap intervals cannot establish real-world strength.",
        ],
    }
