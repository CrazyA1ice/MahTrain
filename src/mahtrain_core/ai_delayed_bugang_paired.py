"""M4.24 independent whole-game delayed-bu-gang guard ablation (offline only).

New M4.23 rule ALWAYS governs both arms. We only ablate the live challenge
agent's additional no-cash guard at optional own-kong windows. Previous
historical M3/M4 results must not be used as new holdout samples.
"""
from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Mapping

from .ai import MahjongAgent
from .ai_action_extended_study import _fixed_lineup
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_tournament import simulate_match

PROTOCOL = "m424_new_cash_rule_delayed_bugang_frozen_guard_pair_v1"
ARMS = ("current_guard", "old_guard_ablation")
COMPONENTS = ("official_net", "win_points", "kong_points",
              "exhaustive_points", "win_events", "deal_in_events",
              "realized_kongs")
DEFAULT_GROUPS = {"development": 64000, "holdout": 65000}
DEFAULT_SEEDS = 2


def eligible_delayed_bugang(view: Mapping[str, Any]) -> bool:
    """The fourth copy remains in own hand but wasn't drawn THIS turn."""
    if view.get("legacy_bugang_cash_rule") is True:
        raise ValueError("M4.24 must use current new cash rule")
    offers = view.get("kong_options") or []
    drawn = view.get("drawn_tile")
    return any(
        o.get("type") == "bu_gang" and o.get("tile") != drawn
        for o in offers
    )


class DelayedBuGangPairedAgent(MahjongAgent):
    """Both arms use real public/own data and the SAME true scoring rules."""

    def __init__(self, *, seed: int, seat: int, arm: str) -> None:
        if arm not in ARMS:
            raise ValueError("unregistered M4.24 policy arm")
        super().__init__("challenge", seed=seed, seat=seat)
        self.arm = arm
        self.counts: Counter[str] = Counter()

    def kong(self, view: Mapping[str, Any]) -> dict[str, str] | None:
        if view.get("legacy_bugang_cash_rule") is not False:
            raise ValueError("M4.24 refuses old cash ruleset")
        original = super().kong(view)
        if not eligible_delayed_bugang(view):
            return original
        self.counts["actual_delayed_bugang_opportunities"] += 1
        # Retain identical legal options and entire authorized view; change
        # ONLY the single historical AI guard in this counterfactual copy.
        old_policy_view = {**view, "legacy_bugang_cash_rule": True}
        unguarded = super().kong(old_policy_view)
        if original is not None and original not in view["kong_options"]:
            raise RuntimeError("live agent selected illegal kong")
        if unguarded is not None and unguarded not in view["kong_options"]:
            raise RuntimeError("ablated agent selected illegal kong")
        changed = original != unguarded
        self.counts["disagreements_on_actual_window"] += int(changed)
        actual = original if self.arm == "current_guard" else unguarded
        if changed and self.arm == "old_guard_ablation":
            self.counts["policy_interventions"] += 1
            if actual is None:
                self.counts["changed_to_pass"] += 1
            elif actual["type"] == "bu_gang":
                self.counts["changed_to_delayed_bugang"] += 1
            else:
                self.counts["changed_to_other_kong"] += 1
        if actual is not None and actual["type"] == "bu_gang":
            if view.get("drawn_tile") != actual["tile"]:
                self.counts["realized_agent_cashless_bugang_choices"] += 1
        return actual


def paired_position(seed: int, rotation: int) -> dict[str, Any]:
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("invalid initial shuffle seed")
    if type(rotation) is not int or rotation not in range(4):
        raise ValueError("four balanced seat rotations required")
    lineup, seat = _fixed_lineup(rotation)
    arms = {}
    for arm in ARMS:
        agent = DelayedBuGangPairedAgent(seed=seed, seat=seat, arm=arm)
        game = simulate_match(
            seed, rotation=rotation % 3, lineup=lineup, offline_kong_base=1,
            offline_ruleset="current_m423",
            offline_agent_overrides={seat: agent},
        )
        outcome = _official_outcome(game, seat, lineup)
        # Mandatory authoritative Hu + kong cash + exhaustive check.
        if outcome["official_net"] != (
            outcome["win_points"] + outcome["kong_points"]
            + outcome["exhaustive_points"]
        ):
            raise RuntimeError("authoritative components are inconsistent")
        arms[arm] = {
            "score": outcome,
            "counts": dict(agent.counts),
            "terminal_phase": game["terminal_phase"],
        }
    return {
        "seed": seed, "rotation": rotation, "challenge_seat": seat,
        "arms": arms,
        "component_deltas": {
            metric: arms["current_guard"]["score"][metric]
            - arms["old_guard_ablation"]["score"][metric]
            for metric in COMPONENTS
        },
    }


def cohort(start: int, count: int = DEFAULT_SEEDS) -> dict[str, Any]:
    if (type(start) is not int or type(count) is not int
            or not 0 <= start < 2**32 or not 1 <= count <= 4
            or start + count > 2**32):
        raise ValueError("invalid independent cohort")
    rows = [paired_position(seed, rot)
            for seed in range(start, start + count)
            for rot in range(4)]
    per_seed = []
    for seed in range(start, start + count):
        games = [r for r in rows if r["seed"] == seed]
        if sorted(r["challenge_seat"] for r in games) != [0, 1, 2, 3]:
            raise RuntimeError("incomplete four-seat rotation")
        per_seed.append({
            "seed": seed,
            "mean_four_seat_deltas": {
                key: round(mean(r["component_deltas"][key] for r in games), 5)
                for key in COMPONENTS
            },
            "unguarded_interventions": sum(
                r["arms"]["old_guard_ablation"]["counts"].get(
                    "policy_interventions", 0)
                for r in games
            ),
        })
    opportunities = Counter()
    for row in rows:
        for arm in ARMS:
            opportunities.update({
                arm + "_" + k: v for k, v in row["arms"][arm]["counts"].items()
            })
    per_seed_net = [row["mean_four_seat_deltas"]["official_net"]
                    for row in per_seed]
    all_delta = {key: round(mean(r["component_deltas"][key] for r in rows), 5)
                 for key in COMPONENTS}
    if abs(all_delta["official_net"] - sum(
        all_delta[k] for k in ("win_points", "kong_points", "exhaustive_points")
    )) > 0.0001:
        raise RuntimeError("paired official deltas do not reconcile")
    return {
        "independent_shuffle_seeds": count,
        "four_seat_rotations": 4,
        "paired_positions": len(rows),
        "complete_games": len(rows) * len(ARMS),
        "mean_current_minus_unguarded": all_delta,
        "seed_cluster_net_deltas": per_seed_net,
        "positive_seed_clusters": sum(x > 0 for x in per_seed_net),
        "negative_seed_clusters": sum(x < 0 for x in per_seed_net),
        "tied_seed_clusters": sum(x == 0 for x in per_seed_net),
        "opportunity_counts": dict(opportunities),
        "per_seed": per_seed,
        "positions": rows,
        "confidence_interval_95pct": None,
    }


def study(*, development: int = DEFAULT_GROUPS["development"],
          holdout: int = DEFAULT_GROUPS["holdout"],
          seeds: int = DEFAULT_SEEDS) -> dict[str, Any]:
    if (type(development) is not int or type(holdout) is not int or
            type(seeds) is not int or seeds < 1 or seeds > 4 or
            development < 0 or holdout < 0 or
            max(development, holdout) + seeds > 2**32 or
            (development < holdout + seeds and holdout < development + seeds)):
        raise ValueError("fresh cohorts must be nonoverlapping uint32 blocks")
    return {
        "protocol": PROTOCOL,
        "official_ruleset": "current_m423",
        "seed_ranges": {
            "development": [development, development + seeds],
            "holdout": [holdout, holdout + seeds],
        },
        "arms": list(ARMS),
        "development": cohort(development, seeds),
        "holdout": cohort(holdout, seeds),
        "live_agent_changed": False,
        "limitations": [
            "Paired only by original shuffle and seat; paths diverge after changed actions.",
            "Seat rotations within a shuffle are correlated, not independent samples.",
            "Tiny prespecified seed clusters do not establish improved win rate or EV.",
            "If no actual policy interventions occur, no causal improvement is observed.",
            "No concealed enemy tiles or real future wall enter policy decisions.",
        ],
    }
