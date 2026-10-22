"""M3.98: natural OPTIONAL operation coverage, and larger M3.97 holdout.

Strictly OFFLINE research. Every observation is from the *acting seat's*
authorized view. No opponent private hand, future wall, card identity, or
reversible digest is included in returned aggregates.

Coverage is sampled from consecutive, predeclared seeds without conditioning
on whether an opportunity occurred. It is NOT a collection of curated kongs.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any, Mapping

from .ai import MahjongAgent
from .ai_challenge_action_counterfactual import (
    TARGETS, POLICIES, METRICS, _one,
)
from .ai_challenge_call_kong_ablation import _official_outcome, _wall_band
from .ai_challenge_reference_paired import LEVELS
from .ai_tournament import simulate_match

PROTOCOL = "m398_unselected_kong_coverage_and_independent_counterfactual_v1"
COVERAGE_SEEDS = 8
PAIRED_SEEDS = 4
COVERAGE_BANDS = ("early", "late", "critical", "unknown")


class NaturalOpportunityAgent(MahjongAgent):
    """Observe every lawful OPTIONAL peng, ming-gang and own kong opportunity."""

    def __init__(self, *, seed: int, seat: int) -> None:
        super().__init__("challenge", seed=seed, seat=seat)
        self.counts: Counter[str] = Counter()

    def response(self, view: Mapping[str, Any], *, rob: bool = False) -> str:
        choice = super().response(view, rob=rob)
        # Hu and robbing Hu do not belong to the voluntary kong/claim
        # experiment: never classify an available winning response as "pass".
        if rob or "hu" in (view.get("claim_options") or []):
            return choice
        options = view.get("claim_options") or []
        if not any(x in options for x in ("peng", "ming_gang")):
            return choice
        self.counts["claim_windows"] += 1
        self.counts["claim_"+_wall_band(view)] += 1
        self.counts["claim_original_"+choice] += 1
        for option in ("peng", "ming_gang"):
            self.counts["claim_offer_"+option] += int(option in options)
        return choice

    def kong(self, view: Mapping[str, Any]) -> dict[str, str] | None:
        original = super().kong(view)
        offered = view.get("kong_options") or []
        if not offered or view.get("can_self_draw_win"):
            return original
        self.counts["own_kong_windows"] += 1
        self.counts["own_kong_"+_wall_band(view)] += 1
        self.counts["own_kong_original_"+(
            original["type"] if original else "pass")] += 1
        for kind in ("an_gang", "bu_gang"):
            self.counts["own_kong_offer_"+kind] += sum(
                x["type"] == kind for x in offered)
            self.counts["own_kong_window_with_"+kind] += int(any(
                x["type"] == kind for x in offered))
        self.counts["own_kong_simultaneous_choices"] += int(len(offered)>1)
        return original


def _fixed_lineup(rotation: int) -> tuple[list[str], int]:
    if type(rotation) is not int or rotation not in range(4):
        raise ValueError("rotation must be one of the four unique seats")
    lineup = [LEVELS[(seat + rotation) % 4] for seat in range(4)]
    return lineup, lineup.index("challenge")


def _coverage_pair(seed: int, rotation: int) -> dict[str, Any]:
    if type(seed) is not int or seed not in range(2**32):
        raise ValueError("seed must be uint32")
    lineup, seat = _fixed_lineup(rotation)
    spy = NaturalOpportunityAgent(seed=seed, seat=seat)
    game = simulate_match(seed, rotation=rotation%3, lineup=lineup,
                          offline_kong_base=1,
                          offline_agent_overrides={seat:spy})
    outcome = _official_outcome(game, seat, lineup)
    counts = dict(spy.counts)
    if (counts.get("claim_windows", 0) != sum(
            counts.get("claim_"+band, 0) for band in COVERAGE_BANDS) or
        counts.get("own_kong_windows", 0) != sum(
            counts.get("own_kong_"+band, 0) for band in COVERAGE_BANDS) or
        counts.get("own_kong_windows", 0) != sum(
            counts.get("own_kong_original_"+kind, 0)
            for kind in ("pass","an_gang","bu_gang"))):
        raise RuntimeError("natural opportunity counts do not reconcile")
    return {
        "seed":seed, "rotation":rotation, "challenge_seat":seat,
        "counts":counts,
        "official_score":outcome,
        "terminal_phase":game["terminal_phase"],
    }


def natural_coverage(seed_start: int, seeds: int) -> dict[str, Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
            seed_start<0 or seeds<1 or seeds>32 or
            seed_start+seeds > 2**32):
        raise ValueError("invalid natural-coverage seed cohort")
    rows = [_coverage_pair(seed,rotation)
            for seed in range(seed_start,seed_start+seeds)
            for rotation in range(4)]
    totals = Counter()
    per_seed = []
    for seed in range(seed_start,seed_start+seeds):
        group=[x for x in rows if x["seed"]==seed]
        if sorted(x["challenge_seat"] for x in group)!=[0,1,2,3]:
            raise RuntimeError("not all four seats were observed")
        subtotal=Counter()
        for x in group:
            subtotal.update(x["counts"])
        totals.update(subtotal)
        per_seed.append({
            "seed":seed,
            "with_own_kong_opportunity":sum(
                row["counts"].get("own_kong_windows",0)>0 for row in group),
            "with_peng_or_ming_gang_opportunity":sum(
                row["counts"].get("claim_windows",0)>0 for row in group),
            "counts":dict(subtotal),
        })
    return {
        "seed_start":seed_start,"independent_seeds":seeds,
        "four_seat_positions":len(rows),
        "positions_with_own_kong":sum(
            row["counts"].get("own_kong_windows",0)>0 for row in rows),
        "positions_with_claim":sum(
            row["counts"].get("claim_windows",0)>0 for row in rows),
        "total_counts":dict(totals),
        "per_seed":per_seed,"positions":rows,
    }


def _stratum(offer: Mapping[str, Any]) -> str:
    # A public-only, preregistered small set of categories; no tile
    # names/hand summaries, and no post-outcome grouping.
    return (offer["wall_band"]+
            (":pass" if offer["original_is_pass"] else ":active"))


def paired_cohort(seed_start: int, seeds: int) -> dict[str, Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
            seed_start<0 or seeds<1 or seeds>16 or
            seed_start+seeds>2**32):
        raise ValueError("invalid paired-cohort seed range")
    rows=[_one(seed,rotation,target)
          for seed in range(seed_start,seed_start+seeds)
          for rotation in range(4)
          for target in TARGETS]
    summary={}
    for target in TARGETS:
        sample=[r for r in rows if r["target"]==target]
        seeded=[]
        for seed in range(seed_start,seed_start+seeds):
            group=[r for r in sample if r["seed"]==seed]
            if sorted(r["challenge_seat"] for r in group)!=[0,1,2,3]:
                raise RuntimeError("paired cohort skipped a challenge seat")
            shifts={}
            for policy in POLICIES[1:]:
                shifts[policy]=sum(
                    r["alternatives"][policy]["delta"]["official_net"]
                    if r["offered"] else 0
                    for r in group)/4
            seeded.append({
                "seed":seed,
                "offered":sum(r["offered"] for r in group),
                "four_seat_delta":shifts,
            })
        policies={}
        for policy in POLICIES[1:]:
            all_changes=[r for r in sample if r["offered"] and
                         r["alternatives"][policy]["changed"]]
            values=[r["four_seat_delta"][policy] for r in seeded]
            effects=Counter()
            strata:dict[str,dict[str,Any]] = defaultdict(
                lambda:{"offered_positions":0,"changed_positions":0,
                        "sum_realized_net_delta":0})
            for r in sample:
                if not r["offered"]:
                    continue
                a=r["alternatives"][policy]
                effects.update(a["delta"])
                group=strata[_stratum(r["baseline"]["opportunity"])]
                group["offered_positions"]+=1
                group["changed_positions"]+=int(a["changed"])
                group["sum_realized_net_delta"]+=a["delta"]["official_net"]
            policies[policy]={
                "mean_seed_cluster_net_delta":round(mean(values),4),
                "changed_positions":len(all_changes),
                "positive_seed_clusters":sum(v>0 for v in values),
                "negative_seed_clusters":sum(v<0 for v in values),
                "tied_seed_clusters":sum(v==0 for v in values),
                "cumulative_official_component_deltas":{
                    k:effects[k] for k in METRICS},
                "public_prechoice_strata":dict(sorted(strata.items())),
                # Fewer than 8 independent seeds in each validation group.
                "confidence_interval_95pct":None,
                "interval_status":"insufficient_independent_seeds_for_interval"
                    if seeds<8 else "interval_not_estimated",
            }
        summary[target]={
            "opportunities":sum(r["offered"] for r in sample),
            "eligible_positions":len(sample),
            "per_seed":seeded,"policies":policies,
        }
    return {
        "seed_start":seed_start,"independent_seeds":seeds,
        "four_seat_positions":seeds*4,
        "target_positions":len(rows),
        "target_summaries":summary,
        "positions":rows,
    }


def study(*, coverage_development: int = 16000,
          coverage_holdout: int = 17000,
          paired_development: int = 18000,
          paired_holdout: int = 19000,
          coverage_seeds: int = COVERAGE_SEEDS,
          paired_seeds: int = PAIRED_SEEDS,
          mode: str = "all") -> dict[str, Any]:
    if mode not in ("all","coverage","paired") or type(mode) is not str:
        raise ValueError("unsupported study mode")
    values=(coverage_development,coverage_holdout,
            paired_development,paired_holdout)
    if (any(type(v) is not int or not 0<=v<2**32 for v in values)
            or type(coverage_seeds) is not int or
            not 1<=coverage_seeds<=32 or
            type(paired_seeds) is not int or
            not 1<=paired_seeds<=16):
        raise ValueError("invalid independent seed ranges")
    ranges=[
        (coverage_development,coverage_development+coverage_seeds),
        (coverage_holdout,coverage_holdout+coverage_seeds),
        (paired_development,paired_development+paired_seeds),
        (paired_holdout,paired_holdout+paired_seeds),
    ]
    if (any(end>2**32 for _,end in ranges)
        or any(a[0]<b[1] and b[0]<a[1]
               for i,a in enumerate(ranges)
               for b in ranges[i+1:])):
        raise ValueError("experiment cohorts overlap or exceed uint32")
    result={
        "protocol":PROTOCOL,
        "coverage_seed_ranges":[ranges[0],ranges[1]],
        "paired_seed_ranges":[ranges[2],ranges[3]],
        "live_ai_modified":False,
        "mode":mode,
        "limitations":[
            "Consecutive seeds are unselected: never filter to seeds containing kongs.",
            "Independent initial-shuffle seeds, not actions or four rotations, are sample units.",
            "First optional action is studied separately from total opportunities per match.",
            "Public strata are DESCRIPTIVE only; do not pick a favorable one to tune live AI.",
            "A fixed-world counterfactual terminal delta is not online expected value.",
            "A missing own-kong opportunity is absent exposure, not a zero-value success.",
        ],
    }
    if mode in ("all","coverage"):
        result["coverage"]={
            "development":natural_coverage(
                coverage_development,coverage_seeds),
            "holdout":natural_coverage(
                coverage_holdout,coverage_seeds),
        }
    if mode in ("all","paired"):
        result["paired"]={
            "development":paired_cohort(
                paired_development,paired_seeds),
            "holdout":paired_cohort(
                paired_holdout,paired_seeds),
        }
    return result
