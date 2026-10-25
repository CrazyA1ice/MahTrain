"""M4.51 aggregate-only research audit; cannot establish policy strength.

Four prior SAFE reports are evidence of completed paired conditional rollouts,
NOT a policy-vs-policy full-game A/B. Never combine their seed-level means or
use study outcomes to select an online rule. This audit does not open secrets.
"""
from __future__ import annotations

from math import isfinite
from pathlib import Path
from typing import Any, Mapping
import json

PROTOCOL="m451_safe_pong_research_evidence_gate_v1"
SOURCES={
    "m447":"m447_first_natural_challenge_pass_peng_matched_branch_v1",
    "m448":"m448_locked_m447_first_pass_peng_new_24_shuffle_replication_v1",
    "m449":"m449_actor_visible_first_pass_peng_precommitted_strata_v1",
    "m450":"m450_new_shuffles_predeclared_middle_vs_early_peng_pass_v1",
}
EXPECTED_SHUFFLES={"m447":8,"m448":24,"m449":24,"m450":48}
NO_PRIVATE=(
    "private_original_shuffle_seed","_hands","future_wall",
    "hand_tiles","opponent_hands","PRIVATE_",
    "model_sha256","original_seed_start",
)

def _value(obj:Mapping[str,Any],key:str,kind:type)->Any:
    value=obj.get(key)
    if type(value) is not kind:
        raise ValueError("safe research field invalid: "+key)
    return value


def _number(obj:Mapping[str,Any],key:str)->float:
    v=obj.get(key)
    if type(v) not in (int,float) or not isfinite(v):
        raise ValueError("non-finite or missing study number: "+key)
    return float(v)


def _counts(*numbers:int)->None:
    if any(type(x) is not int or x<0 for x in numbers):
        raise ValueError("negative or noninteger original-shuffle count")


def _components(mean_delta:float,parts:Mapping[str,Any],name:str)->None:
    total=sum(_number(parts,key) for key in ("win","kong","exhaustive"))
    if abs(total-mean_delta)>0.00005:
        raise ValueError(name+" official win/kong/exhaustive ledger does not reconcile")


def _study(name:str,row:Mapping[str,Any])->dict[str,Any]:
    if type(row) is not dict or row.get("protocol")!=SOURCES[name]:
        raise ValueError("unexpected original research study protocol: "+name)
    if name=="m447":
        n=_value(row,"independent_original_shuffle_clusters",int)
        natural=_value(row,"actual_natural_original_challenge_games",int)
        branches=_value(row,"genuine_full_terminal_branch_games",int)
        total=_value(row,"real_completed_full_games_baseline_plus_branches",int)
        matched=_value(row,"paired_future_wall_worlds",int)
        claimed=_value(row,"branch_pairs_where_peng_was_actually_claimed",int)
        eligible=_value(row,"original_shuffles_with_legal_peng_after_challenge_pass",int)
        missing=_value(row,"original_shuffles_without_such_a_checkpoint",int)
        plus=_value(row,"seed_level_positive_delta",int)
        minus=_value(row,"seed_level_negative_delta",int)
        zero=_value(row,"seed_level_zero_delta",int)
        delta=_number(row,"mean_forced_peng_minus_pass_all_seed_clusters")
        parts=_value(row,"mean_official_component_delta_all_seed_clusters",dict)
    elif name=="m448":
        n=_value(row,"new_independent_original_shuffle_clusters",int)
        natural=_value(row,"real_natural_challenge_baseline_games",int)
        branches=_value(row,"real_terminal_branch_games",int)
        total=_value(row,"total_true_complete_paid_games",int)
        matched=_value(row,"two_world_matched_branch_pairs",int)
        claimed=_value(row,"branch_pairs_with_actual_peng",int)
        eligible=_value(row,"original_shuffles_with_first_pass_peng_checkpoint",int)
        missing=_value(row,"original_shuffles_without_checkpoint",int)
        plus=_value(row,"original_shuffles_positive",int)
        minus=_value(row,"original_shuffles_negative",int)
        zero=_value(row,"original_shuffles_equal",int)
        delta=_number(row,"mean_forced_peng_minus_pass_official_net_points")
        parts=_value(row,"mean_official_component_delta_points",dict)
    elif name=="m449":
        n=_value(row,"independent_original_shuffle_clusters",int)
        natural=_value(row,"natural_complete_games",int)
        branches=_value(row,"true_full_terminal_branch_games",int)
        total=natural+branches
        matched=_value(row,"matched_two_world_action_pairs",int)
        claimed=_value(row,"actual_peng_accepted_pairs",int)
        eligible=_value(row,"eligible_first_peng_after_original_challenge_pass_clusters",int)
        missing=_value(row,"original_shuffles_without_eligible_checkpoint",int)
        plus=_value(row,"original_shuffle_positive",int)
        minus=_value(row,"original_shuffle_negative",int)
        zero=_value(row,"original_shuffle_equal",int)
        delta=_number(row,"all_shuffle_mean_peng_minus_pass_points")
        parts=_value(row,"all_shuffle_mean_real_component_deltas",dict)
    else:
        n=_value(row,"independent_new_original_shuffle_clusters",int)
        natural=_value(row,"actual_natural_challenge_games",int)
        branches=_value(row,"actual_true_full_terminal_branch_games",int)
        total=_value(row,"actual_total_complete_paid_games",int)
        matched=_value(row,"matched_real_two_world_action_pairs",int)
        claimed=_value(row,"true_peng_accepted_pairs",int)
        eligible=_value(row,"first_natural_legal_peng_after_challenge_pass_clusters",int)
        missing=_value(row,"original_shuffles_without_eligible_checkpoint",int)
        plus=_value(row,"original_shuffles_positive",int)
        minus=_value(row,"original_shuffles_negative",int)
        zero=_value(row,"original_shuffles_equal",int)
        delta=_number(row,"overall_all_seed_mean_forced_peng_minus_pass_points")
        parts=_value(row,"official_net_component_means",dict)
    _counts(n,natural,branches,total,matched,claimed,eligible,missing,plus,minus,zero)
    if (n!=EXPECTED_SHUFFLES[name] or natural!=n or
        missing+eligible!=n or plus+minus+zero!=n or
        matched!=2*eligible or branches!=2*matched or
        total!=natural+branches or claimed>matched):
        raise ValueError(name+" independent paid game or actor outcome counts inconsistent")
    _components(delta,parts,name)
    return {
        "original_shuffle_clusters":n,
        "natural_games":natural,
        "real_terminal_branch_games":branches,
        "total_paid_games":total,
        "first_eligible_pass_peng_shuffles":eligible,
        "paired_two_wall_action_comparisons":matched,
        "peng_accepted_pairs":claimed,
        "conditional_peng_minus_pass_mean_points":round(delta,5),
        "positive_original_shuffles":plus,
        "negative_original_shuffles":minus,
        "equal_original_shuffles":zero,
        "not_policy_vs_policy":True,
    }


