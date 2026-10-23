"""M4.09: prospective PUBLIC Ming-Gang risk strata versus actual terminal cash.

The risk index is fixed BEFORE a claim from an authorized player view. Only
after termination do we join public Ming-Gang awards and the official
KongLedger, never by future wall identities or opponent concealed tiles.
No probability calibration or online AI intervention is claimed.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
from typing import Any, Mapping

from .ai_action_extended_study import _fixed_lineup
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_minggang_ledger_followthrough import (
    KONG_TYPES, MingGangFollowThroughAgent, audit_official_kong_lifecycle,
)
from .ai_tournament import simulate_match

PROTOCOL = "m409_public_preclaim_strata_vs_actual_minggang_ron_v1"
SEEDS_PER_COHORT = 8
RISK_BANDS = ("low", "mid", "high")


def risk_band(value: float) -> str:
    """Nonnegative unbounded aggregate threat bins, NOT P(Ron) buckets.

    read_discard_threat SUMS up to three opponents. It can exceed 1.
    """
    if type(value) not in (int, float) or not isfinite(value) or value < 0:
        raise ValueError("invalid publicly observed risk index")
    return "low" if value < 0.25 else "mid" if value < 0.5 else "high"


def reconcile_prospective_risk(
    agent: MingGangFollowThroughAgent,
    outcome: Mapping[str, Any],
    board: Mapping[str, Any],
) -> dict[str, int]:
    """Post-terminal join from claim discard index to actual Kong id/refund.

    Never exposes identities: all per-offer details remain temporary in
    memory and only integer totals by precommitted strata are returned.
    """
    seat = agent.seat
    # First audit the ENTIRE physical/financial authority state.
    official = audit_official_kong_lifecycle(outcome, board, seat)
    physical = outcome["public_events"]
    ledger = board["kong_ledger"]["events"]
    discards = board["discards"]
    by_idx: dict[int, dict[str, Any]] = {}
    declarations = 0
    for n, event in enumerate(physical):
        if event.get("type") not in KONG_TYPES:
            continue
        if declarations >= len(ledger):
            raise RuntimeError("extra physical Kong without authoritative record")
        authoritative = ledger[declarations]
        declarations += 1
        if event["type"] != "ming_gang":
            continue
        if n == 0 or physical[n-1].get("type") != "discard":
            raise RuntimeError("actual Ming-Gang lacks immediate public source discard")
        src = physical[n-1]
        idx = src.get("index")
        if type(idx) is not int or idx < 1 or idx in by_idx:
            raise RuntimeError("invalid claim-to-Kong discard index")
        if event.get("source") != src.get("seat"):
            raise RuntimeError("actual Ming-Gang claimed wrong source discard")
        if (authoritative["type"] != "ming_gang" or
                authoritative["seat"] != event["seat"] or
                authoritative["source"] != src["seat"]):
            raise RuntimeError("Ming-Gang public event differs from priced ledger")
        exits = [x for x in discards if x.get("after_kong") is True
                 and x.get("kong_id") == authoritative["id"]]
        if len(exits) > 1:
            raise RuntimeError("multiple immediate post-Kong discards")
        ron = bool(exits and exits[0].get("won_by"))
        if ron != (authoritative["status"] == "voided"):
            raise RuntimeError("actual post-Kong Ron and refund disagree")
        by_idx[idx] = {
            "seat": event["seat"],
            "id": authoritative["id"],
            "ron": ron,
            "exited": bool(exits),
            "nominal_cash": authoritative["amount_per_payer"],
            "final_cash": 0 if ron else authoritative["amount_per_payer"],
            "ron_winners": len(exits[0]["won_by"]) if ron else 0,
        }
    if declarations != len(ledger):
        raise RuntimeError("authoritative events missing in physical game")
    observed = agent._dual_windows
    if len(observed) != agent.public_counts().get("dual_windows", 0):
        raise RuntimeError("precommitted authorized windows count changed")
    counts: Counter[str] = Counter()
    seen: set[int] = set()
    for row in observed:
        idx, action = row["discard_index"], row["choice"]
        if type(idx) is not int or idx in seen or action not in (
                "pass", "peng", "ming_gang"):
            raise RuntimeError("invalid repeated/illegal prospective observation")
        seen.add(idx)
        band = risk_band(row["pre_tail_min_threat"])
        award = by_idx.get(idx)
        ours = award is not None and award["seat"] == seat
        if ours and action != "ming_gang":
            raise RuntimeError("received Ming-Gang despite unchosen response")
        counts["dual_total"] += 1
        counts["dual_"+band] += 1
        counts["original_"+action] += 1
        counts[band+"_offer"] += 1
        if action == "ming_gang":
            counts[band+"_selected"] += 1
            counts["selected"] += 1
            if not ours:
                counts["selected_preempted"] += 1
        if ours:
            counts[band+"_awarded"] += 1
            counts["awarded"] += 1
            counts["awarded_nominal_cash"] += award["nominal_cash"]
            counts["awarded_final_cash"] += award["final_cash"]
            counts[band+"_after_kong_discard"] += int(award["exited"])
            counts["after_kong_discard"] += int(award["exited"])
            counts[band+"_actual_ron"] += int(award["ron"])
            counts["actual_ron"] += int(award["ron"])
            counts["actual_ron_winners"] += award["ron_winners"]
            counts["awarded_without_exit_discard"] += int(not award["exited"])
    if counts["awarded"] != official.get("own_minggang_realized", 0):
        raise RuntimeError("some actual own Ming-Gang has no prospective legal dual")
    if (counts["actual_ron"] != official.get("own_minggang_exit_ron", 0)
            or counts["actual_ron_winners"] != official.get(
                "own_minggang_exit_ron_winners", 0)
            or counts["awarded_nominal_cash"] != official.get(
                "own_minggang_nominal_credit", 0)
            or counts["awarded_final_cash"] != official.get(
                "own_minggang_final_credit", 0)):
        raise RuntimeError("prospective bins fail authority cash/Ron reconciliation")
    if counts["selected_preempted"] != counts["selected"]-counts["awarded"]:
        raise RuntimeError("selected Ming-Gang outcome was not fully resolved")
    if counts["dual_total"] != sum(counts[b+"_offer"] for b in RISK_BANDS):
        raise RuntimeError("missing original risk stratum")
    if counts["awarded"] != sum(counts[b+"_awarded"] for b in RISK_BANDS):
        raise RuntimeError("missing actual-award risk stratum")
    return dict(counts)


def natural_position(seed: int, rotation: int) -> dict[str, Any]:
    if (type(seed) is not int or not 0 <= seed < 2**32 or
            type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid independent shuffle seed or seat rotation")
    lineup, seat = _fixed_lineup(rotation)
    agent = MingGangFollowThroughAgent(seed=seed, seat=seat)
    state: dict[str, Any] = {}

    def save_game_reference(game: Any) -> None:
        # Do not read or forward private internals during play.
        state["game"] = game

    outcome = simulate_match(
        seed, rotation=rotation % 3, lineup=lineup, offline_kong_base=1,
        offline_agent_overrides={seat:agent},
        offline_observer=save_game_reference,
    )
    if ("game" not in state or
            state["game"].phase != outcome["terminal_phase"]):
        raise RuntimeError("terminal authoritative game reference unavailable")
    board = state["game"].public_state()
    counts = reconcile_prospective_risk(agent, outcome, board)
    official = _official_outcome(outcome, seat, lineup)
    if official["official_net"] != (
        official["win_points"] + official["kong_points"] +
        official["exhaustive_points"]):
        raise RuntimeError("official terminal win/kong/exhaustive totals differ")
    return {
        "seed":seed, "rotation":rotation, "challenge_seat":seat,
        "terminal_phase":outcome["terminal_phase"],
        "counts":counts, "official":official,
    }


def cohort(seed_start: int, seeds: int = SEEDS_PER_COHORT) -> dict[str, Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
            not 0 <= seed_start < 2**32 or not 1 <= seeds <= 12 or
            seed_start+seeds > 2**32):
        raise ValueError("invalid preregistered consecutive shuffle seeds")
    results = [natural_position(s,r) for s in range(seed_start,seed_start+seeds)
               for r in range(4)]
    total: Counter[str] = Counter()
    clusters = []
    for s in range(seed_start,seed_start+seeds):
        positions = [p for p in results if p["seed"] == s]
        if sorted(p["challenge_seat"] for p in positions) != list(range(4)):
            raise RuntimeError("incomplete challenge seat rotation per seed")
        c: Counter[str] = Counter()
        for pos in positions:
            c.update(pos["counts"])
        total.update(c)
        clusters.append({
            "seed":s, "dual_total":c["dual_total"],
            "awarded":c["awarded"],"actual_ron":c["actual_ron"],
            "low_awarded":c["low_awarded"],"mid_awarded":c["mid_awarded"],
            "high_awarded":c["high_awarded"],
        })
    for label in RISK_BANDS:
        if total[label+"_actual_ron"] > total[label+"_after_kong_discard"]:
            raise RuntimeError("actual Ron count exceeds observed exited Kong")
        if total[label+"_after_kong_discard"] > total[label+"_awarded"]:
            raise RuntimeError("exits exceed actual Kong awards")
    return {
        "independent_shuffle_seeds":seeds,
        "four_seat_positions":len(results),
        "complete_games":len(results),
        "counts":dict(total), "per_seed":clusters,
        "positions":results, "calibrated_ron_probability":None,
        "causal_treatment_effect":None, "confidence_interval":None,
        "distinct_seeds_with_awarded_minggang":sum(
            s["awarded"] > 0 for s in clusters),
        "distinct_seeds_with_actual_ron":sum(
            s["actual_ron"] > 0 for s in clusters),
    }


def study(*, development: int = 42000, holdout: int = 43000,
          seeds: int = SEEDS_PER_COHORT) -> dict[str, Any]:
    if (type(development) is not int or type(holdout) is not int or
            type(seeds) is not int or not 1 <= seeds <= 12 or
            not 0 <= development < 2**32 or
            not 0 <= holdout < 2**32 or
            max(development,holdout)+seeds > 2**32 or
            (development < holdout+seeds and holdout < development+seeds)):
        raise ValueError("separate predeclared development and holdout cannot overlap")
    return {
        "protocol":PROTOCOL, "online_policy_modified":False,
        "development_seed_range":[development,development+seeds],
        "holdout_seed_range":[holdout,holdout+seeds],
        "development":cohort(development,seeds),
        "holdout":cohort(holdout,seeds),
        "limitations":[
            "Baseline freely SELECTS Ming-Gang; only awarded calls are exposed to actual post-Kong Ron, so outcome groups are selection biased.",
            "The existing-hand pre-tail heuristic ignores the unknown tail replacement and is not a P(Ron) forecast.",
            "No intervention or matched counterfactual policy was run: there is no causal effect estimate.",
            "Four seat rotations and multiple windows share a shuffle seed; only seeds are independent sampling units.",
            "Descriptive bins are fixed at 0.25 and 0.5 before samples; rare natural outcomes do not support calibration.",
            "All compared authority money is at an explicitly fixed offline Kong base of one.",
        ],
    }
