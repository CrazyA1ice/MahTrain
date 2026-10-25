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
    '"private_original_shuffle_seed"', '"_hands"', '"hand":',
    '"future_wall":', '"opponent_hands"', '"private_case"',
    '"model_sha256"', '"original_seed_start"',
    "PRIVATE_",
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


def _wall_phase(row:Mapping[str,Any],name:str)->dict[str,Any]:
    if name=="m449":
        source=_value(row,"pre_action_actor_only_strata",dict)
        phases=_value(source,"public_wall_segment",dict)
        mean_key="mean_peng_minus_pass_points_exploratory"
        size_key="independent_original_shuffles"
    else:
        phases=_value(row,"precommitted_public_wall_phase_groups",dict)
        mean_key="mean_net_peng_minus_pass_points"
        size_key="independent_original_shuffle_clusters"
    result={}
    for name in ("early","middle","late"):
        phase=_value(phases,name,dict)
        count=_value(phase,size_key,int)
        if count<0:
            raise ValueError("invalid previous wall phase cluster count")
        value=phase.get(mean_key)
        if value is None:
            if count>=8:
                raise ValueError("missing phase result for adequately covered group")
            result[name]={"independent_original_shuffles":count,"mean_points":None}
        else:
            result[name]={
                "independent_original_shuffles":count,
                "mean_points":round(_number(phase,mean_key),5),
            }
    return result


def audit_safe_reports(reports:Mapping[str,Mapping[str,Any]])->dict[str,Any]:
    if type(reports) is not dict or set(reports)!=set(SOURCES):
        raise ValueError("M4.51 requires all four authentic SAFE reports")
    for label,field in (
        ("m447","new_candidate_policy_not_fitted_or_promoted"),
        ("m448","online_challenge_ai_unchanged"),
        ("m449","original_challenge_agent_unchanged"),
        ("m450","no_training_no_threshold_selection_no_online_challenge_change"),
    ):
        if reports[label].get(field) is not True:
            raise ValueError("cannot verify unchanged Challenge in "+label)
    for label,field in (
        ("m447","same_original_shuffle_future_worlds_not_independent_samples"),
        ("m448","same_shuffle_two_future_worlds_not_independent"),
        ("m449","two_worlds_not_independent_original_shuffles"),
        ("m450","future_wall_worlds_are_correlated_within_original_shuffle"),
    ):
        if reports[label].get(field) is not True:
            raise ValueError("missing same-original-shuffle dependence warning: "+label)
    for label,field in (
        ("m448","previous_m447_original_shuffles_audited_but_not_pooled"),
        ("m449","old_m447_m448_outcomes_not_fitted_or_pooled"),
        ("m450","previous_m449_twenty_four_shuffles_verified_but_not_pooled"),
    ):
        if reports[label].get(field) is not True:
            raise ValueError("missing historical holdout non-pooling evidence: "+label)
    studies={name:_study(name,reports[name]) for name in SOURCES}
    phases449=_wall_phase(reports["m449"],"m449")
    phases450=_wall_phase(reports["m450"],"m450")
    confirmed=_value(reports["m450"],"comparison_status",str)
    comparison=_number(reports["m450"],"middle_minus_early_mean_net_points") if (
        confirmed=="exploratory_independent_replication_complete"
    ) else None
    interval=reports["m450"].get(
        "cluster_bootstrap_middle_minus_early_95_percentile_interval"
    )
    supported=reports["m450"].get(
        "direction_supported_in_new_independent_shuffles"
    )
    if confirmed=="exploratory_independent_replication_complete":
        if (type(interval) is not list or len(interval)!=2 or
            any(type(x) not in (int,float) or not isfinite(x) for x in interval) or
            type(supported) is not bool or
            interval[0]>interval[1] or
            supported!=(interval[0]>0)):
            raise ValueError("invalid M4.50 predeclared bootstrap comparison")
        if (phases450["middle"]["mean_points"] is None or
            phases450["early"]["mean_points"] is None or
            phases450["middle"]["independent_original_shuffles"]<8 or
            phases450["early"]["independent_original_shuffles"]<8 or
            abs(comparison-(phases450["middle"]["mean_points"]-
                            phases450["early"]["mean_points"]))>0.00007):
            raise ValueError("M4.50 wall-phase official-net contrast does not reconcile")
    elif confirmed=="insufficient_group_support":
        if (comparison is not None or interval is not None or supported is not None or
            (phases450["middle"]["independent_original_shuffles"]>=8 and
             phases450["early"]["independent_original_shuffles"]>=8)):
            raise ValueError("M4.50 falsely reports incomplete evidence")
    else:
        raise ValueError("unsupported final M4.50 comparison status")
    if (sum(phases449[x]["independent_original_shuffles"] for x in
            ("early","middle","late"))!=studies["m449"]["first_eligible_pass_peng_shuffles"] or
        sum(phases450[x]["independent_original_shuffles"] for x in
            ("early","middle","late"))!=studies["m450"]["first_eligible_pass_peng_shuffles"]):
        raise ValueError("wall-phase categories do not cover eligible first decisions")
    means=[studies[k]["conditional_peng_minus_pass_mean_points"]
           for k in SOURCES]
    flips=sum((a>0)!=(b>0) for a,b in zip(means,means[1:])
              if a!=0 and b!=0)
    return {
        "protocol":PROTOCOL,
        "source_protocols_verified":list(SOURCES.values()),
        "studies_in_natural_chronological_order":studies,
        "mean_effect_sign_reversals_between_consecutive_studies":flips,
        "actor_only_wall_phase": {
            "m449_exploratory":phases449,
            "m450_fresh_independent_validation":phases450,
        },
        "m450_predeclared_middle_minus_early_points":(
            round(comparison,5) if comparison is not None else None
        ),
        "m450_predeclared_direction_supported":supported,
        "m450_exploratory_interval":interval,
        "m449_midwall_claim_not_independently_supported":
            confirmed=="exploratory_independent_replication_complete"
            and supported is False,
        "formal_candidate_full_game_ab_evaluation_provided":False,
        "recommendation":"HOLD_CURRENT_CHALLENGE_POLICY_NO_PROMOTION",
        "next_research_method":"PREDECLARE_FULL_GAME_POLICY_VS_POLICY_HEAD_TO_HEAD_WITH_UNSEEN_SHUFFLE_CLUSTERS",
        "all_past_conditional_rollout_outcomes_excluded_from_training":True,
        "previous_report_counts_reconciled_not_private_seed_provenance_reverified":True,
        "no_statistical_independence_claim_for_wall_worlds_or_seat_rotations":True,
        "no_causal_population_ev_or_pong_always_bad_claim":True,
        "no_original_seed_cards_hidden_wall_or_private_plan_paths_exported":True,
    }


def _no_duplicate_keys(pairs:list[tuple[str,Any]])->dict[str,Any]:
    obj={}
    for k,value in pairs:
        if k in obj:
            raise ValueError("duplicate field in SAFE evidence JSON: "+k)
        obj[k]=value
    return obj


def load_safe_json(path:Path)->dict[str,Any]:
    path=Path(path)
    if path.stat().st_size>250_000:
        raise ValueError("SAFE evidence JSON exceeds aggregate-only size limit")
    text=path.read_text(encoding="utf8")
    for token in NO_PRIVATE:
        if token in text:
            raise ValueError("unsafe private data marker in nominal SAFE report")
    data=json.loads(
        text,object_pairs_hook=_no_duplicate_keys,
        parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("nonfinite SAFE JSON number")
        ),
    )
    if type(data) is not dict:
        raise ValueError("SAFE study must be a JSON object")
    return data
