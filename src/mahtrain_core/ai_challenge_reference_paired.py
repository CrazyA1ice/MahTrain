"""M3.93: offline, paired challenge-policy vs public-reference cut study.

The *only* intervention is the challenge seat's discard. Both arms replay
the same real Sichuan rules from the same initial seed and seat assignment.
This module is research-only; it is NEVER imported by the live web server.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Mapping

from .ai import MahjongAgent
from .ai_tournament import simulate_match
from .classic_hint import classic_archive_seat_hint
from .rules import TILE_INDEX

PROTOCOL = "m393_offline_same_seed_challenge_vs_reference_cut_v1"
LEVELS = ("challenge", "advanced", "basic", "baseline")


class ReferenceCutResearchAgent(MahjongAgent):
    """Ablation: ordinary challenge agent, except use public-reference cuts."""

    _offline_reference_cut = True

    def __init__(self, *, seed: int, seat: int) -> None:
        super().__init__("challenge", seed=seed, seat=seat)
        self.decisions = 0
        self.reference_available = 0
        self.baseline_reference_disagreement = 0
        self.replaced_cuts = 0
        self.challenge_public_risk_switches = 0
        self.deviations_with_risk_switch = 0
        self.deviations_without_risk_switch = 0
        self.unknown_challenge_ranking = 0

    def discard(self, view: Mapping[str, Any]) -> str:
        # This legal action is measured using the SAME authorized current
        # view. The counterfactual does not inspect the actual hidden world.
        baseline = super().discard(view)
        self.decisions += 1
        advice = classic_archive_seat_hint(view, self.seat)
        candidates = advice.get("candidates") or []
        if not candidates:
            return baseline
        reference = candidates[0]["discard"]
        self.reference_available += 1
        differs = baseline != reference
        self.baseline_reference_disagreement += int(differs)
        self.replaced_cuts += int(differs)

        # Pressure relevance is observable ONLY when the actual challenge
        # ranked more than one same-shanten candidate. It is not a causal
        # decomposition of outcome, and these are not calibrated ron odds.
        ranking = self._last_discard_scores
        if ranking is None:
            self.unknown_challenge_ranking += int(differs)
        else:
            no_risk = min(ranking, key=lambda row: (
                -row["expected_fan_weighted_copies"],
                -row["effective_tile_count"],
                TILE_INDEX[row["discard"]],
            ))["discard"]
            risk_switch = no_risk != baseline
            self.challenge_public_risk_switches += int(risk_switch)
            if differs:
                self.deviations_with_risk_switch += int(risk_switch)
                self.deviations_without_risk_switch += int(not risk_switch)
        # Intentionally leave the real challenge AI implementation unchanged.
        return reference

    def safe_counts(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in (
            "decisions", "reference_available",
            "baseline_reference_disagreement", "replaced_cuts",
            "challenge_public_risk_switches",
            "deviations_with_risk_switch",
            "deviations_without_risk_switch", "unknown_challenge_ranking",
        )}


def _validate_result(game: dict[str, Any], lineup: list[str]) -> None:
    if (game["assignment"] != lineup or
            game["physical_count"] != 108 or
            sum(game["official_settled_balances"]) != 0 or
            len(game["official_settled_balances"]) != 4 or
            game["scoring_rules"]["kong_base"] != 1 or
            game["terminal_phase"] not in ("finished", "wall_exhausted") or
            (game["terminal_phase"] == "wall_exhausted" and
             not game["official_exhaustive_posted"])):
        raise RuntimeError("paired sample failed 108-tile, zero-sum or official settlement audit")


def _outcomes(result: dict[str, Any], seat: int) -> dict[str, int]:
    wins = result["winners"]
    return {
        "official_net": result["official_settled_balances"][seat],
        "wins": sum(row["seat"] == seat for row in wins),
        "deal_ins": sum(row["source"] == seat and row["seat"] != seat
                        for row in wins),
    }


def compare_pair(seed: int, rotation: int) -> dict[str, Any]:
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must fit 32 bits")
    if type(rotation) is not int or rotation not in range(4):
        raise ValueError("rotation must be 0..3")
    lineup = [LEVELS[(seat + rotation) % 4] for seat in range(4)]
    seat = lineup.index("challenge")
    normal = simulate_match(seed, rotation=rotation % 3,
                            lineup=lineup, offline_kong_base=1)
    agent = ReferenceCutResearchAgent(seed=seed, seat=seat)
    intervention = simulate_match(
        seed, rotation=rotation % 3, lineup=lineup, offline_kong_base=1,
        offline_agent_overrides={seat: agent},
    )
    _validate_result(normal, lineup)
    _validate_result(intervention, lineup)
    first = _outcomes(normal, seat)
    second = _outcomes(intervention, seat)
    return {
        "seed": seed, "rotation": rotation, "challenge_seat": seat,
        "baseline": first, "reference_cut": second,
        "delta_reference_minus_challenge": (
            second["official_net"] - first["official_net"]),
        "decision_counts": agent.safe_counts(),
    }


def compare_reference_cuts(
    *, seed_start: int = 8407, seeds: int = 2, rotations: int = 4,
) -> dict[str, Any]:
    """Run independently paired seeds with four seat rotations when requested.

    Four rotations are one seed-cluster, NOT four independent random samples.
    Do not interpret observed deltas as a proven improvement or win chance.
    """
    if (type(seed_start) is not int or seed_start < 0 or
            type(seeds) is not int or not 1 <= seeds <= 32 or
            seed_start + seeds > 2**32 or
            type(rotations) is not int or rotations not in range(1, 5)):
        raise ValueError("invalid bounded seed or seat-rotation design")
    pairs = []
    for seed in range(seed_start, seed_start + seeds):
        for rotation in range(rotations):
            pairs.append(compare_pair(seed, rotation))
    cluster = defaultdict(list)
    counts = defaultdict(int)
    for row in pairs:
        cluster[row["seed"]].append(row["delta_reference_minus_challenge"])
        for key, value in row["decision_counts"].items():
            counts[key] += value
    per_seed = [{
        "seed": seed,
        "rotations": len(delta),
        "mean_net_delta": round(mean(delta), 4),
        "rotation_deltas": list(delta),
    } for seed, delta in sorted(cluster.items())]
    seed_means = [row["mean_net_delta"] for row in per_seed]
    return {
        "protocol": PROTOCOL,
        "seed_start": seed_start, "independent_seeds": seeds,
        "rotations_per_seed": rotations, "paired_games": len(pairs),
        "room_coefficient": 100, "official_kong_base": 1,
        "mean_delta_net_reference_minus_challenge": round(mean(seed_means), 4),
        "seed_clusters_positive": sum(x > 0 for x in seed_means),
        "seed_clusters_negative": sum(x < 0 for x in seed_means),
        "seed_clusters_tied": sum(x == 0 for x in seed_means),
        "total_win_event_delta": sum(
            r["reference_cut"]["wins"] - r["baseline"]["wins"]
            for r in pairs),
        "total_deal_in_event_delta": sum(
            r["reference_cut"]["deal_ins"] - r["baseline"]["deal_ins"]
            for r in pairs),
        "decision_counts": dict(counts),
        "per_seed": per_seed,
        "pairs": pairs,
        "interpretation": (
            "Seed-cluster paired realized official net score, not theoretical "
            "expected value or independent turn-level samples."
        ),
        "limitations": [
            "Reference ranking is a one-step public-information comparator, not a perfect oracle.",
            "Only challenge discard differs; no change to live agents or other actions.",
            "Small samples and seat/agent path dependence preclude superiority claims.",
            "Risk-switch attribution is descriptive, not a causal effect on game outcome.",
        ],
    }
