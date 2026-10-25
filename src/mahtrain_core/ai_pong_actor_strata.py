"""M4.49: first natural pass/peng, stratified by PRE-ACTION actor-only facts.

Research-only matched paid branches; never let agent see the wall or other
concealed hands, train a new policy, or infer a global action advantage.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from statistics import mean
from typing import Any, Mapping

from .ai import _call_outlook, _call_settings, _cut_shanten, _own_view
from .ai_selfplay_counterfactual import KONG_BASE, MAX_ACTIONS, _agents, _opening
from .ai_tournament import _take_action
from .four_player import FourPlayerOpening
from .rules import TILE_INDEX
from .ai_pong_pass_branch_rollouts import (
    _find_candidate, _finish, _force_one, _validate_case, WORLDS, PARTS,
    _aggregate as branch_aggregate,
)

PROTOCOL="m449_actor_visible_first_pass_peng_precommitted_strata_v1"
SHARD_PROTOCOL="m449_independent_original_shuffle_unchanged_two_world_branches_v1"
PLAN="PRIVATE_m449_actor_only_strata_plan.json"
SHARDS="PRIVATE_m449_seed_cluster_shards"
SUMMARY="safe_pong_actor_strata.json"
SEED_COUNT=24
# Small precommitted categories. No thresholds fitted on old paid outcomes.
STAGES=("improve","same","regress")
DRAWS=("loss","equal","gain")
WALL=("early","middle","late")
OPEN=("none","one","multiple")


def actor_only_pong_features(view:Mapping[str,Any])->dict[str,str]:
    if (view["phase"]!="claim_window" or
            "peng" not in view["claim_options"] or
            "pass" not in view["claim_options"]):
        raise ValueError("actor-visible legal pass/peng options required")
    hand,melds,missing=_own_view(view)
    public,cap,tian=_call_settings(view)
    target=view["pending_discard"]["tile"]
    if target not in public or hand.count(target)<2:
        raise ValueError("invalid actor-only real pending peng")
    baseline=_call_outlook(hand,melds,missing,public,cap,tian)
    leftover=list(hand)
    leftover.remove(target)
    leftover.remove(target)
    groups=[*melds,{"type":"peng","tile":target}]
    cuts=sorted(set(leftover),key=TILE_INDEX.__getitem__)
    must_cut=[t for t in cuts if t[0]==missing]
    if must_cut:
        cuts=must_cut
    if not cuts:
        raise RuntimeError("no legal immediate post-peng discard")
    best_stage=min(_cut_shanten(leftover,groups,missing,t) for t in cuts)
    known=list(public)
    known.remove(target)
    best_copies=None
    for cut in cuts:
        if _cut_shanten(leftover,groups,missing,cut)!=best_stage:
            continue
        after=list(leftover)
        after.remove(cut)
        result=_call_outlook(after,groups,missing,[*known,cut],cap,tian)
        if result["shanten"]!=best_stage:
            raise RuntimeError("call checkpoint shanten calculators disagree")
        if best_copies is None or result["ukeire"]>best_copies:
            best_copies=result["ukeire"]
    if best_copies is None:
        raise RuntimeError("no canonical optimal-stage post-peng cut")
    prior_stage=baseline["shanten"]
    stage="improve" if best_stage<prior_stage else (
        "regress" if best_stage>prior_stage else "same"
    )
    gain=best_copies-baseline["ukeire"]
    draw="gain" if gain>0 else ("loss" if gain<0 else "equal")
    wall=view["wall_count"]
    if type(wall) is not int or wall<0:
        raise ValueError("invalid actor-visible public wall count")
    stage_of_wall="early" if wall>=40 else ("middle" if wall>=20 else "late")
    melds_by_seat=view["melds"]
    others=sum(len(x) for seat,x in enumerate(melds_by_seat)
               if seat!=view["seat"])
    exposed="none" if others==0 else ("one" if others==1 else "multiple")
    return {
        "shanten_change":stage,
        "effective_copies_change":draw,
        "public_wall_segment":stage_of_wall,
        "opponents_open_melds_count_band":exposed,
        "verified_tian_ting":"yes" if tian.get("eligible") is True else "no",
    }


def one_actor_stratified_shuffle(seed:int)->dict[str,Any]:
    if type(seed) is not int or not 0<=seed<2**32:
        raise ValueError("invalid registered new original shuffle")
    game=FourPlayerOpening(seed,kong_base=KONG_BASE,legacy_bugang_cash=False)
    agents=_agents(seed)
    _opening(game,agents,[])
    trace=[]
    duration=defaultdict(list)
    snapshot=None
    snapshot_agents=None
    actor=None
    features=None
    for _ in range(MAX_ACTIONS):
        if game.phase in ("finished","wall_exhausted"):
            break
        if snapshot is None:
            candidate=_find_candidate(game,agents)
            if candidate is not None:
                actor=candidate
                features=actor_only_pong_features(game.private_view(actor))
                snapshot=deepcopy(game)
                snapshot_agents=deepcopy(agents)
        _take_action(game,agents,trace,duration)
        if len(trace)>4:
            trace.clear()
    else:
        raise RuntimeError("natural four-Challenge seed did not settle")
    real=_finish(game,agents)
    case={
        "private_original_shuffle_seed":seed,
        "natural_complete_challenge_games":1,
        "natural_terminal_baseline":real,
        "first_natural_challenge_pass_with_peng_found":snapshot is not None,
        "private_first_actor_seat":actor,
        "private_matched_branches":[],
        "checkpoints_selected_by_first_opportunity_only":True,
        "no_hidden_actor_input_or_online_policy_change":True,
        "private_actor_only_pre_action_categories":features,
    }
    if snapshot is not None:
        for world in WORLDS:
            pass_game=_force_one(snapshot,snapshot_agents,actor,"pass",world,seed)
            peng_game=_force_one(snapshot,snapshot_agents,actor,"peng",world,seed)
            if world==0:
                for key in ("official_net",*PARTS):
                    if pass_game[key]!=real[key]:
                        raise RuntimeError("natural original-wall pass branch failed replay")
            delta={
                name:peng_game[name][actor]-pass_game[name][actor]
                for name in ("official_net",*PARTS)
            }
            if delta["official_net"]!=sum(delta[k] for k in PARTS):
                raise RuntimeError("real terminal actor paid score not reconciled")
            case["private_matched_branches"].append({
                "world":world,
                "forced_pass_terminal_actor_net":pass_game["official_net"][actor],
                "forced_peng_terminal_actor_net":peng_game["official_net"][actor],
                "peng_claim_actually_accepted":peng_game["peng_actually_claimed"],
                "official_actor_net_delta":delta["official_net"],
                "win_actor_delta":delta["win_points"],
                "kong_actor_delta":delta["kong_points"],
                "exhaustive_actor_delta":delta["exhaustive_points"],
                "both_arms_genuine_terminal_ledgers":True,
                "no_opponent_hidden_hand_given_to_actors":True,
            })
    validate_case(case,seed)
    return case


def validate_case(case:dict[str,Any],seed:int)->None:
    _validate_case(case,seed)
    x=case.get("private_actor_only_pre_action_categories")
    present=case["first_natural_challenge_pass_with_peng_found"]
    if (present!=(x is not None)):
        raise ValueError("actor feature status does not match real first checkpoint")
    if not present:
        return
    if (type(x) is not dict or set(x)!={
        "shanten_change","effective_copies_change","public_wall_segment",
        "opponents_open_melds_count_band","verified_tian_ting",
    } or x["shanten_change"] not in STAGES or
        x["effective_copies_change"] not in DRAWS or
        x["public_wall_segment"] not in WALL or
        x["opponents_open_melds_count_band"] not in OPEN or
        x["verified_tian_ting"] not in ("yes","no")):
        raise ValueError("only pre-registered actor-visible categorical data allowed")


def _factor(cases:list[dict[str,Any]],name:str,values:tuple[str,...])->dict[str,Any]:
    result={}
    for label in values:
        matches=[
            case for case in cases
            if case["private_matched_branches"] and
            case["private_actor_only_pre_action_categories"][name]==label
        ]
        effects=[mean(r["official_actor_net_delta"]
                      for r in case["private_matched_branches"])
                 for case in matches]
        # Suppress tiny outcome groups to avoid publishing individual
        # full-paid actor outcome, but retain categorical support counts.
        row={"independent_original_shuffles":len(matches)}
        if len(matches)>=3:
            row.update({
                "mean_peng_minus_pass_points_exploratory":round(mean(effects),5),
                "positive_shuffles":sum(x>0 for x in effects),
                "negative_shuffles":sum(x<0 for x in effects),
                "equal_shuffles":sum(x==0 for x in effects),
            })
        else:
            row["small_group_outcomes_suppressed"]=True
        result[label]=row
    return result


def safe_actor_strata(cases:list[dict[str,Any]])->dict[str,Any]:
    if not cases:
        raise ValueError("no original shuffles")
    core=branch_aggregate(cases)
    return {
        "protocol":PROTOCOL,
        "independent_original_shuffle_clusters":len(cases),
        "natural_complete_games":core["actual_natural_original_challenge_games"],
        "true_full_terminal_branch_games":core["genuine_full_terminal_branch_games"],
        "matched_two_world_action_pairs":core["paired_future_wall_worlds"],
        "eligible_first_peng_after_original_challenge_pass_clusters":
            core["original_shuffles_with_legal_peng_after_challenge_pass"],
        "original_shuffles_without_eligible_checkpoint":
            core["original_shuffles_without_such_a_checkpoint"],
        "actual_peng_accepted_pairs":
            core["branch_pairs_where_peng_was_actually_claimed"],
        "all_shuffle_mean_peng_minus_pass_points":
            core["mean_forced_peng_minus_pass_all_seed_clusters"],
        "all_shuffle_mean_real_component_deltas":
            core["mean_official_component_delta_all_seed_clusters"],
        "original_shuffle_positive":core["seed_level_positive_delta"],
        "original_shuffle_negative":core["seed_level_negative_delta"],
        "original_shuffle_equal":core["seed_level_zero_delta"],
        "pre_action_actor_only_strata":{
            "shanten_change":_factor(cases,"shanten_change",STAGES),
            "effective_copies_change":_factor(cases,"effective_copies_change",DRAWS),
            "public_wall_segment":_factor(cases,"public_wall_segment",WALL),
            "opponents_open_melds_count_band":
                _factor(cases,"opponents_open_melds_count_band",OPEN),
            "verified_tian_ting":_factor(cases,"verified_tian_ting",("no","yes")),
        },
        "strata_are_analytical_not_a_new_peng_policy":True,
        "small_strata_fewer_than_three_shuffles_have_no_outcome_means":True,
        "old_m447_m448_outcomes_not_fitted_or_pooled":True,
        "two_worlds_not_independent_original_shuffles":True,
        "identical_real_checkpoint_and_all_actor_rng_states":True,
        "no_hidden_wall_or_rival_hand_as_actor_feature":True,
        "offline_conditional_branches_not_population_action_ev":True,
        "original_challenge_agent_unchanged":True,
    }
