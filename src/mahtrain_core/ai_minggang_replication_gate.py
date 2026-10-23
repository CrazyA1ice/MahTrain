"""M4.12: new independent M4.11 paired replication + fail-closed evidence gate.

No live AI change, no new policy, no threshold search, no opponent private data.
Only already-frozen M4.11 baseline/risk_peng is re-run on unseen seeds.
Evidence gates determine if MORE prospective research is sensible, NEVER
authorize online deployment. True independent sampling units are shuffles.
"""
from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Mapping

from .ai_minggang_preclaim_paired import (
    ARMS, METRICS, PUBLIC_THREAT_GATE, cohort as original_paired_cohort,
)

PROTOCOL = "m412_frozen_m411_new_independent_seed_replication_gate_v1"
DEVELOPMENT_START = 48000
HOLDOUT_START = 49000
SEEDS_PER_BLOCK = 8
# Freeze minimum evidence requirements BEFORE inspecting new seed blocks.
MIN_INTERVENTIONS_PER_BLOCK = 8
MIN_TREATED_SEED_CLUSTERS = 4
MIN_POSITIVE_SEED_CLUSTERS = 3


def _nonnegative_integer(n: object) -> bool:
    return type(n) is int and n >= 0


def evaluate_block(
    trial: Mapping[str, Any], *, start: int, seeds: int,
) -> dict[str, Any]:
    """Fail closed on corrupt/overcounted M4.11 data, export aggregates only.

    A source position (seat rotation) is *not* a sampling unit. A genuine
    intervention's whole-game score is measured by the two offline arms.
    """
    if type(start) is not int or type(seeds) is not int or not (
            0 <= start < 2**32 and 1 <= seeds <= 8 and start+seeds <= 2**32):
        raise ValueError("invalid independent shuffle range")
    if (trial.get("independent_shuffle_seeds") != seeds
            or trial.get("paired_seat_positions") != 4*seeds
            or trial.get("complete_games") != 8*seeds
            or trial.get("public_threat_gate") != PUBLIC_THREAT_GATE
            or trial.get("risk_is_probability") is not False
            or trial.get("confidence_interval") is not None):
        raise RuntimeError("noncomparable or nonofficial trial report")
    per_seed = trial.get("per_seed")
    positions = trial.get("positions")
    counts = trial.get("counts_by_arm")
    metrics = trial.get("official_component_deltas")
    if (not isinstance(per_seed, list) or len(per_seed) != seeds
            or not isinstance(positions,list) or len(positions) != 4*seeds
            or not isinstance(counts,dict)
            or set(counts) != set(ARMS)
            or not isinstance(metrics,dict)):
        raise RuntimeError("missing complete natural-shuffle paired evidence")
    if not all(type(metrics.get(k)) is int for k in METRICS):
        raise RuntimeError("missing or noninteger paired official score metric")
    if metrics["official_net"]!=sum(metrics[k] for k in (
            "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("official paired components do not reconcile")
    calculated = Counter()
    total_changes = 0
    actual_seed_rows = []
    for seed in range(start,start+seeds):
        p=[r for r in positions if r.get("seed")==seed]
        if (len(p)!=4 or sorted(r.get("rotation") for r in p)!=[0,1,2,3]
                or sorted(r.get("challenge_seat") for r in p)!=[0,1,2,3]):
            raise RuntimeError("unbalanced four-seat shuffle cluster")
        deltas=Counter()
        changes=0
        for row in p:
            arms=row.get("arms")
            if not isinstance(arms,dict) or set(arms)!=set(ARMS):
                raise RuntimeError("missing original and proposed policy arms")
            for arm in ARMS:
                official=arms[arm].get("official",{})
                if (not isinstance(official,dict) or
                    any(type(official.get(k)) is not int for k in METRICS) or
                    official["official_net"]!=sum(official[k] for k in (
                            "win_points","kong_points","exhaustive_points"))):
                    raise RuntimeError("invalid full-game authority score")
                if arm=="baseline" and arms[arm].get("counts",{}).get("actual_changes",0):
                    raise RuntimeError("baseline arm illegally intervened")
            original=arms["baseline"]["official"]
            revised=arms["risk_peng"]["official"]
            d=row.get("paired_deltas")
            if not isinstance(d,dict) or any(
                    d.get(k)!=revised[k]-original[k] for k in METRICS):
                raise RuntimeError("candidate delta is not real authority difference")
            c=row.get("actual_interventions")
            if (not _nonnegative_integer(c) or c!=arms["risk_peng"].get(
                    "counts",{}).get("actual_changes",0)
                    or (c==0 and any(d[k] for k in METRICS))
                    or (c==0 and row.get("same_state_when_unchanged") is not True)):
                raise RuntimeError("missing intervention / incorrect no-change proof")
            changes+=c
            deltas.update(d)
            calculated.update(d)
        row=per_seed[seed-start]
        net=round(deltas["official_net"]/4,4)
        if (type(row.get("seed")) is not int or row["seed"] != seed or
                row.get("actual_interventions") != changes or
                row.get("mean_four_seat_net_delta") != net):
            raise RuntimeError("seed-cluster outcome disagrees with the positions")
        total_changes+=changes
        actual_seed_rows.append({
            "seed":seed, "actual_interventions":changes,
            "mean_four_seat_net_delta":net,
            "treated_seed_cluster":changes>0,
        })
    if (any(calculated[k] != metrics[k] for k in METRICS) or
            trial.get("candidate_real_policy_changes") != total_changes
            or counts["risk_peng"].get("actual_changes",0)!=total_changes
            or counts["baseline"].get("actual_changes",0)!=0):
        raise RuntimeError("aggregate official paired outcome does not reconcile")
    p=sum(row["mean_four_seat_net_delta"]>0 for row in actual_seed_rows)
    n=sum(row["mean_four_seat_net_delta"]<0 for row in actual_seed_rows)
    neutral=seeds-p-n
    if (trial.get("positive_delta_seeds")!=p or
            trial.get("negative_delta_seeds")!=n or
            trial.get("unchanged_delta_seeds")!=neutral or
            trial.get("seed_mean_official_net_delta")!=round(
                mean(x["mean_four_seat_net_delta"] for x in actual_seed_rows),4)):
        raise RuntimeError("independent-seed signs / averages differ")
    exposure=sum(x["treated_seed_cluster"] for x in actual_seed_rows)
    blockers=[]
    if total_changes < MIN_INTERVENTIONS_PER_BLOCK:
        blockers.append("insufficient_actual_policy_changes")
    if exposure < MIN_TREATED_SEED_CLUSTERS:
        blockers.append("too_few_independent_shuffle_clusters_with_changes")
    if p < MIN_POSITIVE_SEED_CLUSTERS or p <= n:
        blockers.append("no_replicated_positive_independent_seed_effect")
    return {
        "shuffle_seeds":seeds, "seed_start":start,
        "complete_games":8*seeds,"paired_seat_positions":4*seeds,
        "public_threat_gate":PUBLIC_THREAT_GATE,
        "actual_interventions":total_changes,
        "independent_seeds_with_interventions":exposure,
        "positive_seed_clusters":p, "negative_seed_clusters":n,
        "unchanged_seed_clusters":neutral,
        "mean_four_seat_official_net_delta":round(
            mean(x["mean_four_seat_net_delta"] for x in actual_seed_rows),4),
        "official_component_deltas":{k:metrics[k] for k in METRICS},
        "predeclared_more_research_gate_passed":not blockers,
        "blockers":blockers,"per_seed":actual_seed_rows,
        "policy_deployable":False,
        "calibrated_ron_probability":None,
        "confidence_interval":None,
        "study_is_causal_local_claim_value":False,
    }


def study(
    *, development: int=DEVELOPMENT_START,
    holdout: int=HOLDOUT_START, seeds: int=SEEDS_PER_BLOCK,
) -> dict[str, Any]:
    """Both blocks: never choose seed windows according to observed wins."""
    if (type(development) is not int or type(holdout) is not int or
            type(seeds) is not int or not 1 <= seeds <= SEEDS_PER_BLOCK or
            not 0 <= development < 2**32 or
            not 0 <= holdout < 2**32 or
            max(development,holdout)+seeds > 2**32 or
            (development < holdout+seeds and holdout < development+seeds)):
        raise ValueError("independent precommitted development/holdout only")
    blocks = {}
    for name,start in (("development",development),("holdout",holdout)):
        trials=original_paired_cohort(start,seeds)
        blocks[name]=evaluate_block(trials,start=start,seeds=seeds)
    more=all(blocks[x]["predeclared_more_research_gate_passed"]
             for x in ("development","holdout"))
    return {
        "protocol":PROTOCOL,"online_policy_modified":False,
        "candidate_only_offline":True,
        "development_seed_range":[development,development+seeds],
        "holdout_seed_range":[holdout,holdout+seeds],
        "development":blocks["development"],"holdout":blocks["holdout"],
        "decision":{
            "eligible_for_larger_fresh_seed_study":more,
            "deploy_live_policy":False,
            "rationale":("Even a passed evidence gate authorizes only fresh "
                         "independent research, never a live policy change."),
        },
        "evidence_thresholds":{
            "min_changes_per_block":MIN_INTERVENTIONS_PER_BLOCK,
            "min_treated_seed_clusters":MIN_TREATED_SEED_CLUSTERS,
            "min_positive_seed_clusters":MIN_POSITIVE_SEED_CLUSTERS,
            "both_blocks_required":True,
        },
        "limitations":[
            "A frozen public threat >=0.25 is an ordinal heuristic, not P(Ron).",
            "The full-game paired-score change is path-wide, not a single-call value.",
            "The M4.11 development/holdout already failed to replicate any active intervention in the holdout.",
            "New seed blocks are genuinely unseen; no threshold search or cherry-picked events.",
            "Four seats under a single initial shuffle are correlated, not four independent samples.",
            "No hidden opponents, known tail, or live AI policy was used or modified.",
        ],
    }
