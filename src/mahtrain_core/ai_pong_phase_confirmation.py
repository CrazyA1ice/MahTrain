"""M4.50: NEW-shuffle validation of an M4.49 POST-HOC wall-phase hypothesis.

Frozen source M4.49 naturally selects FIRST legal peng when original
Challenge chose pass. The only prespecified comparison is middle wall
(20..39 public draws left) versus early wall (40+). Late and absent
checkpoints are counted but excluded from this conditional contrast.
One original natural shuffle = one independent unit, NOT 2 wall worlds.
No candidate action policy is created, fitted, changed or promoted.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from random import Random
from statistics import mean, median
from typing import Any

from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_pong_actor_strata import (
    PROTOCOL as M449_PROTOCOL, PLAN as M449_PLAN,
    SUMMARY as M449_SUMMARY, SEED_COUNT as M449_N,
    safe_actor_strata, validate_case,
)
from .ai_pong_actor_strata_run import (
    _read_shards as read_m449_shards,
    _check_previous as audit_m448_history,
)
from .ai_pong_pass_replication import _percentile

PROTOCOL="m450_new_shuffles_predeclared_middle_vs_early_peng_pass_v1"
PLAN="PRIVATE_m450_phase_confirmation_plan.json"
SUMMARY="safe_pong_phase_confirmation.json"
SHARDS="PRIVATE_m450_completed_original_shuffle_cases"
SHARD_PROTOCOL="m450_first_natural_actor_only_phase_two_world_paid_v1"
SEED_COUNT=48
RESAMPLES=4096
RANDOM_SEED=450
EARLY="early"
MIDDLE="middle"
LATE="late"
MIN_PER_GROUP=8


def frozen_m449_source_digest()->str:
    root=Path(__file__).resolve().parent
    return sha256(
        (root/"ai_pong_actor_strata.py").read_bytes()+
        (root/"ai_pong_actor_strata_run.py").read_bytes()
    ).hexdigest()


def audit_previous_m449(
    *,prior:Path,training:Path,model:dict[str,Any],start:int,n:int
)->dict[str,Any]:
    """Audit all 24 M4.49 private paid shards and earlier plans, no reuse."""
    old=_get_json(prior/M449_PLAN)
    previous_start=old.get("private_seed_start")
    previous_n=old.get("independent_natural_shuffles")
    old_m448=old.get("private_previous_m448_source")
    if (old.get("protocol")!=M449_PROTOCOL or
        old.get("private_model_source")!=str(training) or
        old.get("model_sha256")!=model["model_sha256"] or
        old.get("frozen_actor_strata_source_sha256")!=frozen_m449_source_digest() or
        old.get("only_first_natural_pass_with_peng") is not True or
        old.get("no_online_change_or_model_fit") is not True or
        old.get("two_original_m447_wall_worlds_unchanged") is not True or
        type(old_m448) is not str or not old_m448 or
        type(previous_start) is not int or type(previous_n) is not int or
        previous_n!=M449_N or not 0<=previous_start<2**32 or
        previous_start+previous_n>2**32 or
        not (start+n<=previous_start or start>=previous_start+previous_n)):
        raise ValueError("M4.50 new seed overlaps M4.49 or frozen policy provenance invalid")
    old_m448_dir=_private_location(Path(old_m448))
    verified_prior=audit_m448_history(
        old=old_m448_dir,train=training,model=model,start=start,n=n
    )
    if old.get("private_previous_m447_source")!=verified_prior["private_previous_m447_source"]:
        raise ValueError("M4.49 recorded M4.47 source does not match history")
    saved=read_m449_shards(
        prior,previous_start,previous_n,model["model_sha256"]
    )
    if len(saved)!=previous_n:
        raise ValueError("M4.49 prior 24 genuinely paid shuffles incomplete")
    computed=safe_actor_strata([saved[i] for i in range(previous_n)])
    published=_get_json(prior/M449_SUMMARY)
    if (type(published) is not dict or
        any(published.get(k)!=v for k,v in computed.items()) or
        type(published.get("verified_original_shuffle_clusters_reused_on_resume")) is not int or
        not 0<=published["verified_original_shuffle_clusters_reused_on_resume"]<=previous_n):
        raise ValueError("M4.49 prior safe summary differs from private paid cases")
    return {
        "private_previous_m448_source":str(old_m448_dir),
        "previous_m449_seed_start":previous_start,
        "previous_m449_shuffle_count":previous_n,
    }


def phase_of(case:dict[str,Any])->str|None:
    validate_case(case,case["private_original_shuffle_seed"])
    labels=case["private_actor_only_pre_action_categories"]
    return None if labels is None else labels["public_wall_segment"]


def _effect(case:dict[str,Any])->float:
    branches=case["private_matched_branches"]
    return mean([x["official_actor_net_delta"] for x in branches]) if branches else 0


def _phase_metrics(rows:list[tuple[str|None,float]])->dict[str,Any]:
    by_phase={
        key:[effect for phase,effect in rows if phase==key]
        for key in (EARLY,MIDDLE,LATE)
    }
    statistics={}
    for name,group in by_phase.items():
        entry={
            "independent_original_shuffle_clusters":len(group),
            "positive":sum(x>0 for x in group),
            "negative":sum(x<0 for x in group),
            "equal":sum(x==0 for x in group),
        }
        if len(group)>=MIN_PER_GROUP:
            entry.update({
                "mean_net_peng_minus_pass_points":round(mean(group),5),
                "median_net_peng_minus_pass_points":round(median(group),5),
            })
        else:
            entry["mean_and_median_suppressed_insufficient_support"]=True
        statistics[name]=entry
    return statistics


def confirm_phase_contrast(cases:list[dict[str,Any]])->dict[str,Any]:
    """Check frozen effect contrast, NEVER fit a new rule from the labels."""
    if len(cases)!=SEED_COUNT:
        raise ValueError("M4.50 requires all 48 new independent original shuffles")
    rows=[(phase_of(case),_effect(case)) for case in cases]
    groups={
        key:[v for group,v in rows if group==key]
        for key in (EARLY,MIDDLE,LATE)
    }
    early=groups[EARLY]
    middle=groups[MIDDLE]
    phase_detail=_phase_metrics(rows)
    n0=len(early)
    n1=len(middle)
    eligible=sum(phase is not None for phase,_ in rows)
    if len(rows)!=sum(len(g) for g in groups.values())+(len(rows)-eligible):
        raise ValueError("unreconciled original shuffle phase allocation")
    report={
        "protocol":PROTOCOL,
        "independent_new_original_shuffle_clusters":len(cases),
        "first_natural_legal_peng_after_challenge_pass_clusters":eligible,
        "original_shuffles_without_eligible_checkpoint":len(cases)-eligible,
        "precommitted_public_wall_phase_groups":phase_detail,
        "prespecified_middle_vs_early_hypothesis":"middle_peng_minus_pass_mean_greater_than_early",
        "minimum_independent_original_shuffles_in_each_comparison_group":MIN_PER_GROUP,
        "prespecified_cluster_bootstrap_resamples":RESAMPLES,
        "bootstrap_random_seed_precommitted":True,
        "previous_m449_twenty_four_shuffles_verified_but_not_pooled":True,
        "policy_actor_and_own_view_features_frozen_from_m449":True,
        "no_training_no_threshold_selection_no_online_challenge_change":True,
        "future_wall_worlds_are_correlated_within_original_shuffle":True,
        "no_hidden_hand_wall_or_seed_values_in_public_report":True,
        "conditional_first_checkpoint_phase_contrast_not_global_action_value":True,
    }
    if n0<MIN_PER_GROUP or n1<MIN_PER_GROUP:
        report.update({
            "comparison_status":"insufficient_group_support",
            "middle_minus_early_mean_net_points":None,
            "cluster_bootstrap_middle_minus_early_95_percentile_interval":None,
            "direction_supported_in_new_independent_shuffles":None,
        })
        return report
    point=mean(middle)-mean(early)
    rng=Random(RANDOM_SEED)
    draws=[]
    for _ in range(RESAMPLES):
        a=mean(early[rng.randrange(n0)] for _ in range(n0))
        b=mean(middle[rng.randrange(n1)] for _ in range(n1))
        draws.append(b-a)
    draws.sort()
    lo=_percentile(draws,.025)
    hi=_percentile(draws,.975)
    report.update({
        "comparison_status":"exploratory_independent_replication_complete",
        "middle_minus_early_mean_net_points":round(point,5),
        "cluster_bootstrap_middle_minus_early_95_percentile_interval":[
            round(lo,5),round(hi,5)
        ],
        "direction_supported_in_new_independent_shuffles":bool(lo>0),
        "bootstrap_interval_is_descriptive_not_global_winning_probability":True,
        "multiple_posthoc_comparisons_not_performed":True,
        "does_not_establish_an_online_middle_peng_policy":True,
    })
    return report
