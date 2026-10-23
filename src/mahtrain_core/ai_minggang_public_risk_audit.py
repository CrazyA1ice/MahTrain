"""M4.07 research-only, public-information Ming-Gang exit-risk audit.

This is not a P(ron) or an expected-score predictor. In particular the tail
replacement tile is hidden, and the live challenge policy is unchanged.
"""
from __future__ import annotations
from collections import Counter
from statistics import mean
from typing import Any, Mapping

from .ai import MahjongAgent
from .ai_action_extended_study import _fixed_lineup
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_dual_claim_fastpath_paired import _dual_optional_options
from .ai_table_read import read_discard_threat
from .ai_tournament import simulate_match
from .rules import SUITS, TILE_INDEX

PROTOCOL = "m407_public_minggang_pre_tail_exit_risk_v1"


def public_minggang_exit_risk(view: Mapping[str, Any]) -> dict[str, Any]:
    """Bound public threat among EXISTING lawful post-Ming-Gang cut kinds.

    The unknown wall-tail supplement may be a better/different discard.
    Consequently these min/max values are NOT bounds on all possible exits.
    Neither hidden hands nor unseen wall identities are consulted.
    """
    if not _dual_optional_options(view, rob=False):
        raise ValueError("requires authorized simultaneous peng/ming_gang")
    wall = view.get("wall_count")
    if type(wall) is not int or not 1 <= wall <= 108:
        raise ValueError("cannot supplement from an empty/invalid wall")
    seat = view.get("seat")
    pending = view.get("pending_discard") or {}
    source, tile = pending.get("seat"), pending.get("tile")
    if (type(seat) is not int or seat not in range(4) or
            type(source) is not int or source not in range(4) or source == seat):
        raise ValueError("invalid public claimant/source")
    hand = view.get("hand")
    if (not isinstance(hand, list) or tile not in TILE_INDEX or
            hand.count(tile) < 3 or any(t not in TILE_INDEX for t in hand)):
        raise ValueError("invalid authorized claimant hand")
    suits = view.get("missing_suits")
    if (not isinstance(suits, (list, tuple)) or len(suits) != 4 or
            suits[seat] not in SUITS):
        raise ValueError("invalid declared dingque")
    remaining = list(hand)
    for _ in range(3):
        remaining.remove(tile)
    candidates = sorted(set(remaining), key=TILE_INDEX.__getitem__)
    forced = [t for t in candidates if t[0] == suits[seat]]
    if forced:
        candidates = forced
    if not candidates:
        raise ValueError("no pre-existing legal discard")
    risks = [read_discard_threat(t, view) for t in candidates]
    rule = view.get("win_ledger") or {}
    coeff, cap = rule.get("room_coefficient"), rule.get("fan_cap")
    if (type(coeff) is not int or coeff < 1 or
            type(cap) is not int or not 0 <= cap <= 12):
        raise ValueError("invalid official Hu payment parameters")
    kong = view.get("kong_ledger") or {}
    base = kong.get("base")
    if base is not None and (type(base) is not int or not 1 <= base <= 10**6):
        raise ValueError("invalid explicit Kong base")
    won = view.get("won")
    melds = view.get("melds")
    if (not isinstance(won, (list, tuple)) or len(won) != 4 or
            any(type(x) is not bool for x in won) or
            not isinstance(melds, (list, tuple)) or len(melds) != 4):
        raise ValueError("invalid public opponent state")
    active = sum(s != seat and not won[s] for s in range(4))
    exposed = sum(s != seat and not won[s] and len(melds[s]) >= 2
                  for s in range(4))
    one_ron_ceiling = coeff * 2**cap
    return {
        "pre_tail_candidate_kinds": len(candidates),
        "dingque_forced_pre_tail_candidates": bool(forced),
        "min_existing_cut_threat_index": min(x["risk_index"] for x in risks),
        "max_existing_cut_threat_index": max(x["risk_index"] for x in risks),
        "min_candidate_threatening_seats": min(x["active_threats"] for x in risks),
        "max_candidate_threatening_seats": max(x["active_threats"] for x in risks),
        "active_opponents": active,
        "active_opponents_with_two_melds": exposed,
        "wall_band": "critical" if wall <= 12 else ("late" if wall <= 24 else "early"),
        "nominal_reversible_minggang_payment": 2*base if base is not None else None,
        "max_ron_per_opponent_fan_cap": one_ron_ceiling,
        "extreme_all_active_opponents_ron_cap": active*one_ron_ceiling,
        "supplement_tile_known": False,
        "risk_index_is_probability": False,
        "forecast_official_net": None,
    }


class PublicMingGangRiskObserver(MahjongAgent):
    """Challenge-policy clone. Only adds aggregate counters off-line."""

    def __init__(self, *, seed: int, seat: int) -> None:
        super().__init__("challenge", seed=seed, seat=seat)
        self._risk_counts: Counter[str] = Counter()

    def response(self, view: Mapping[str, Any], *, rob: bool = False) -> str:
        choice = super().response(view, rob=rob)
        if not _dual_optional_options(view, rob=rob):
            return choice
        risk = public_minggang_exit_risk(view)
        c = self._risk_counts
        c["dual_windows"] += 1
        c["original_"+choice] += 1
        c["wall_"+risk["wall_band"]] += 1
        c["priced_windows"] += int(risk["nominal_reversible_minggang_payment"] is not None)
        c["dingque_forced_windows"] += int(risk["dingque_forced_pre_tail_candidates"])
        c["two_meld_opponent_windows"] += int(risk["active_opponents_with_two_melds"] > 0)
        c["min_risk_at_least_half_windows"] += int(risk["min_existing_cut_threat_index"] >= 0.5)
        c["candidate_kinds_total"] += risk["pre_tail_candidate_kinds"]
        c["min_risk_milli_total"] += round(risk["min_existing_cut_threat_index"]*1000)
        if choice not in view["claim_options"]:
            raise RuntimeError("observer must preserve authorized baseline choice")
        return choice

    def public_counts(self) -> dict[str, int]:
        c = self._risk_counts
        if c["dual_windows"] != sum(c["original_"+x] for x in ("pass","peng","ming_gang")):
            raise RuntimeError("unaccounted baseline claim choice")
        return dict(c)


def paired_position(seed: int, rotation: int) -> dict[str, Any]:
    if (type(seed) is not int or not 0 <= seed < 2**32 or
            type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid seed/rotation")
    lineup, seat = _fixed_lineup(rotation)
    base = simulate_match(seed, rotation=rotation % 3, lineup=lineup,
                          offline_kong_base=1)
    observer = PublicMingGangRiskObserver(seed=seed, seat=seat)
    observed = simulate_match(seed, rotation=rotation % 3, lineup=lineup,
                              offline_kong_base=1,
                              offline_agent_overrides={seat: observer})
    official = _official_outcome(base, seat, lineup)
    shadow = _official_outcome(observed, seat, lineup)
    if (official != shadow or base["terminal_phase"] != observed["terminal_phase"] or
            base["public_events"] != observed["public_events"] or
            base["trace"] != observed["trace"]):
        raise RuntimeError("risk observer changed a decision, trace or terminal result")
    return {"seed": seed, "rotation": rotation, "challenge_seat": seat,
            "baseline_official": official, "observer_official": shadow,
            "terminal_phase": observed["terminal_phase"],
            "risk_counts": observer.public_counts(), "unchanged_official": True}


def cohort(start: int, seeds: int) -> dict[str, Any]:
    if (type(start) is not int or type(seeds) is not int or
            not 0 <= start < 2**32 or not 1 <= seeds <= 8 or start+seeds > 2**32):
        raise ValueError("invalid fixed independent shuffle seeds")
    rows = [paired_position(seed, rotation)
            for seed in range(start, start+seeds) for rotation in range(4)]
    totals: Counter[str] = Counter()
    per_seed = []
    for seed in range(start, start+seeds):
        fours = [row for row in rows if row["seed"] == seed]
        if sorted(x["challenge_seat"] for x in fours) != [0,1,2,3]:
            raise RuntimeError("incomplete independent seat rotation")
        windows = 0
        for row in fours:
            if not row["unchanged_official"]:
                raise RuntimeError("unexpected intervention")
            totals.update(row["risk_counts"])
            windows += row["risk_counts"].get("dual_windows", 0)
        per_seed.append({"seed": seed, "dual_windows": windows})
    return {
        "independent_initial_shuffle_seeds": seeds,
        "paired_seat_positions": len(rows),
        "complete_games": len(rows)*2,
        "natural_dual_windows": totals["dual_windows"],
        "windows_per_seed_average": round(mean(x["dual_windows"] for x in per_seed),4),
        "risk_counters": dict(totals), "per_seed": per_seed, "positions": rows,
        "policy_interventions": 0, "confidence_interval": None,
    }


def study(*, development: int = 38000, holdout: int = 39000,
          seeds: int = 4) -> dict[str, Any]:
    if (type(development) is not int or type(holdout) is not int or
            type(seeds) is not int or not 1 <= seeds <= 8 or
            not 0 <= development < 2**32 or not 0 <= holdout < 2**32 or
            max(development, holdout)+seeds > 2**32 or
            (development < holdout+seeds and holdout < development+seeds)):
        raise ValueError("invalid separate preregistered seed blocks")
    return {
        "protocol": PROTOCOL, "online_policy_modified": False,
        "development_seed_range": [development,development+seeds],
        "holdout_seed_range": [holdout,holdout+seeds],
        "development": cohort(development,seeds),
        "holdout": cohort(holdout,seeds),
        "limitations": [
            "Existing legal cuts exclude the unknown tail tile, not a complete risk distribution.",
            "Heuristic public threat is not actual P(ron).",
            "The maximal legal Hu amount is a ceiling, not expected loss.",
            "No changed policy means identical official outcomes are only a safety check.",
            "Independent shuffle seeds, not seat rotations or windows, are sample units.",
        ],
    }
