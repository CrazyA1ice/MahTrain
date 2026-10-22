"""M3.95 offline call/kong opportunity audit and frozen-policy ablations.

Retain challenge's exchange, dingque, draw, discard and Hu decisions. Compare:
  baseline: original challenge calls and kongs
  no_tie_peng: decline only a peng chosen with unchanged exact shanten
  no_kong: decline ming_gang and own an_gang/bu_gang, preserve peng and Hu
The online MahjongAgent and authoritative rules are never modified.

Only OWN authorized private_view and already-public information enter policies.
Returned diagnostics contain no tile identities, concealed hands or wall draws.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any, Mapping

from .ai import MahjongAgent, _own_view, _cut_shanten
from .ai_challenge_reference_paired import LEVELS
from .ai_tournament import simulate_match
from .efficiency import shanten_13
from .rules import TILE_INDEX

PROTOCOL = "m395_offline_challenge_call_kong_ablation_v1"
ARMS = ("baseline", "no_tie_peng", "no_kong")
CALL_KINDS = ("peng", "ming_gang", "an_gang", "bu_gang")
# Scenarios are deliberately COARSE categories, not reconstructible snapshots.
SCENARIO_LIMIT = 12


def _peng_shanten_comparison(view: Mapping[str, Any]) -> tuple[int, int]:
    """Exact structural comparison for a legal pong, no hypothetical wall."""
    if "peng" not in view["claim_options"]:
        raise ValueError("cannot diagnose a peng with no legal peng option")
    hand, melds, missing = _own_view(view)
    tile = view["pending_discard"]["tile"]
    if hand.count(tile) < 2:
        raise ValueError("authorized hand lacks a legal pair")
    before = shanten_13(hand, melds, missing)
    remainder = list(hand)
    remainder.remove(tile)
    remainder.remove(tile)
    next_melds = [*melds, {"type": "peng", "tile": tile}]
    allowed = sorted(set(remainder), key=TILE_INDEX.__getitem__)
    forced = [t for t in allowed if t[0] == missing]
    if forced:
        allowed = forced
    if not allowed:
        raise ValueError("peng has no lawful next discard")
    best = min(_cut_shanten(remainder, next_melds, missing, cut)
               for cut in allowed)
    return before, best


def _wall_band(view: Mapping[str, Any]) -> str:
    remaining = view.get("wall_count")
    if type(remaining) is not int or remaining < 0:
        return "unknown"
    if remaining <= 12:
        return "critical"
    return "late" if remaining <= 24 else "early"


def _scenario(view: Mapping[str, Any], original: str, revised: str,
              *, trigger: str) -> dict[str, Any]:
    """Share only aggregate public-category metadata, NEVER tile identities."""
    seat = view["seat"]
    public_melds = view.get("melds") or [[], [], [], []]
    opponents = view.get("won") or [False] * 4
    return {
        "trigger": trigger,
        "original": original,
        "revised": revised,
        "wall_band": _wall_band(view),
        "self_exposed_groups": len(view.get("own_melds") or []),
        "opponents_with_melds": sum(
            bool(public_melds[s]) and s != seat for s in range(4)),
        "active_opponents": sum(
            s != seat and not opponents[s] for s in range(4)),
    }


class CallKongResearchAgent(MahjongAgent):
    """Same challenge policy; only declared study arm changes calls/kongs."""

    def __init__(self, *, seed: int, seat: int, arm: str) -> None:
        if arm not in ARMS:
            raise ValueError("unknown frozen call/kong ablation arm")
        super().__init__("challenge", seed=seed, seat=seat)
        self.arm = arm
        self._counts: Counter[str] = Counter()
        self._scenarios: dict[tuple[str, ...], dict[str, Any]] = {}

    def _observe(self, view: Mapping[str, Any], original: str,
                 revised: str, *, trigger: str) -> None:
        self._counts["interventions"] += int(original != revised)
        self._counts[f"original_{original}"] += 1
        if original != revised:
            self._counts[f"changed_{trigger}"] += 1
            # Coarse example library, limited and independent of tile kind,
            # hand contents, seed and other hidden game state.
            note = _scenario(view, original, revised, trigger=trigger)
            key = tuple(str(v) for v in note.values())
            if key in self._scenarios:
                self._scenarios[key]["count"] += 1
            elif len(self._scenarios) < SCENARIO_LIMIT:
                self._scenarios[key] = {**note, "count": 1}

    def response(self, view: Mapping[str, Any], *, rob: bool = False) -> str:
        original = super().response(view, rob=rob)
        options = view["rob_options"] if rob else view["claim_options"]
        if len(options) < 2:
            return original
        if "peng" not in options and "ming_gang" not in options:
            # Hu or pass-only; no optional call being ablated.
            return original
        self._counts["optional_claim_opportunities"] += 1
        chosen = original
        if self.arm == "no_kong" and original == "ming_gang":
            chosen = "pass"
        elif self.arm == "no_tie_peng" and original == "peng":
            baseline, after = _peng_shanten_comparison(view)
            if after >= baseline:
                chosen = "pass"
                self._counts["nonimproving_peng_rejected"] += 1
        if chosen not in options:
            raise RuntimeError("ablation produced an illegal response")
        self._observe(view, original, chosen, trigger="claim")
        return chosen

    def kong(self, view: Mapping[str, Any]) -> dict[str, str] | None:
        # A choice is legal only if provided by the game engine.
        original = super().kong(view)
        if not view["kong_options"]:
            return original
        self._counts["own_kong_opportunities"] += 1
        original_kind = original["type"] if original else "pass"
        selected = None if self.arm == "no_kong" else original
        chosen_kind = selected["type"] if selected else "pass"
        self._observe(view, original_kind, chosen_kind, trigger="own_kong")
        return selected

    def safe_counts(self) -> dict[str, int]:
        names = (
            "optional_claim_opportunities", "own_kong_opportunities",
            "interventions", "changed_claim", "changed_own_kong",
            "nonimproving_peng_rejected",
            *(f"original_{k}" for k in (*CALL_KINDS, "pass")),
        )
        return {name: self._counts[name] for name in names}

    def safe_scenarios(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._scenarios.values()]


def _official_outcome(game: dict[str, Any], seat: int,
                      lineup: list[str]) -> dict[str, int]:
    """Verify authoritative total equals each separately settled component."""
    if game["assignment"] != lineup or game["physical_count"] != 108:
        raise RuntimeError("paired sample violates lineup or physical 108")
    if game["scoring_rules"]["kong_base"] != 1:
        raise RuntimeError("paired sample did not price kongs")
    if game["terminal_phase"] not in ("finished", "wall_exhausted"):
        raise RuntimeError("research game is not terminal")
    if (game["terminal_phase"] == "wall_exhausted"
            and not game["official_exhaustive_posted"]):
        raise RuntimeError("exhaustive-wall settlement was not posted")
    pieces = (
        game["official_settled_balances"],
        game["partial_win_balances"],
        game["official_kong_balances"],
        game["official_exhaustive_balances"],
    )
    if any(type(x) is not list or len(x) != 4
           or any(type(v) is not int for v in x) or sum(x) != 0
           for x in pieces):
        raise RuntimeError("invalid zero-sum official component ledger")
    total, win, kong, wall = pieces
    if any(total[s] != win[s] + kong[s] + wall[s] for s in range(4)):
        raise RuntimeError("official ledger components do not reconcile")
    return {
        "official_net": total[seat],
        "win_points": win[seat],
        "kong_points": kong[seat],
        "exhaustive_points": wall[seat],
        "win_events": sum(w["seat"] == seat for w in game["winners"]),
        "deal_in_events": sum(
            w["source"] == seat and w["seat"] != seat
            for w in game["winners"]),
        "realized_kongs": sum(
            e["type"] in ("ming_gang", "an_gang", "bu_gang")
            and e.get("seat") == seat for e in game["public_events"]),
    }


def _paired(seed: int, rotation: int) -> dict[str, Any]:
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("invalid shuffle seed")
    if type(rotation) is not int or rotation not in range(4):
        raise ValueError("invalid seating rotation")
    lineup = [LEVELS[(seat + rotation) % 4] for seat in range(4)]
    seat = lineup.index("challenge")
    row: dict[str, Any] = {
        "seed": seed, "rotation": rotation, "challenge_seat": seat,
        "arms": {},
    }
    for arm in ARMS:
        agent = CallKongResearchAgent(seed=seed, seat=seat, arm=arm)
        game = simulate_match(
            seed, rotation=rotation % 3, lineup=lineup, offline_kong_base=1,
            offline_agent_overrides={seat: agent})
        row["arms"][arm] = {
            "score": _official_outcome(game, seat, lineup),
            "opportunities": agent.safe_counts(),
            "scenario_examples": agent.safe_scenarios(),
        }
    return row


def _cohort(seed_start: int, count: int) -> dict[str, Any]:
    rows = [_paired(seed, rotation)
            for seed in range(seed_start, seed_start + count)
            for rotation in range(4)]
    seeds = defaultdict(list)
    for row in rows:
        seeds[row["seed"]].append(row)
    per_seed = []
    for seed, games in sorted(seeds.items()):
        if sorted(x["challenge_seat"] for x in games) != [0, 1, 2, 3]:
            raise RuntimeError("incomplete seat rotation")
        comparison = {}
        for arm in ARMS[1:]:
            comparison[arm] = {
                metric: round(mean(
                    item["arms"][arm]["score"][metric] -
                    item["arms"]["baseline"]["score"][metric]
                    for item in games), 4)
                for metric in (
                    "official_net", "win_points", "kong_points",
                    "exhaustive_points", "win_events",
                    "deal_in_events", "realized_kongs")
            }
        per_seed.append({"seed": seed, "four_seat_delta": comparison})
    comparisons = {}
    for arm in ARMS[1:]:
        differences = [
            row["four_seat_delta"][arm]["official_net"] for row in per_seed]
        counts: Counter[str] = Counter()
        examples: list[dict[str, Any]] = []
        observed = set()
        for row in rows:
            trial = row["arms"][arm]
            counts.update(trial["opportunities"])
            for note in trial["scenario_examples"]:
                # Example categories only, not a selected population of games.
                key = tuple((k, v) for k, v in note.items() if k != "count")
                if key not in observed and len(examples) < SCENARIO_LIMIT:
                    observed.add(key)
                    examples.append(note)
        comparisons[arm] = {
            "mean_seed_cluster_net_delta": round(mean(differences), 4),
            "positive_seeds": sum(v > 0 for v in differences),
            "negative_seeds": sum(v < 0 for v in differences),
            "tied_seeds": sum(v == 0 for v in differences),
            "opportunity_counts": dict(counts),
            "scenario_examples": examples,
            "interval_95pct": None,  # fewer than eight independent seeds
            "interval_status": "not_estimated_for_small_seed_cohort",
        }
    return {
        "independent_seeds": count,
        "seat_rotations": 4,
        "paired_positions": count * 4,
        "complete_games": len(rows) * len(ARMS),
        "per_seed": per_seed,
        "comparisons": comparisons,
    }


def study(*, development_start: int = 12000,
          holdout_start: int = 13000,
          seeds_per_group: int = 2) -> dict[str, Any]:
    """Pre-declare disjoint cohorts and fixed arms before seeing outcomes."""
    if (type(development_start) is not int or
            type(holdout_start) is not int or
            type(seeds_per_group) is not int or
            not 0 <= development_start < 2**32 or
            not 0 <= holdout_start < 2**32 or
            not 1 <= seeds_per_group <= 4 or
            development_start + seeds_per_group > 2**32 or
            holdout_start + seeds_per_group > 2**32 or
            not (development_start + seeds_per_group <= holdout_start or
                 holdout_start + seeds_per_group <= development_start)):
        raise ValueError("overlapping or invalid predeclared seed cohorts")
    return {
        "protocol": PROTOCOL,
        "frozen_arms": list(ARMS),
        "development": _cohort(development_start, seeds_per_group),
        "holdout": _cohort(holdout_start, seeds_per_group),
        "live_policy_changed": False,
        "limits": [
            "Only the challenge seat's call/kong decisions differ between arms.",
            "Other decisions remain unchanged policies, but future game paths diverge.",
            "Scenario examples are coarse public categories, not hidden hands.",
            "No confidence interval from fewer than eight independent seeds.",
            "Individual calls are not independent score observations.",
            "This controlled experiment does not establish which policy is stronger.",
        ],
    }
