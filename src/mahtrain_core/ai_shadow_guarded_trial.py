"""M4.41: preregistered fresh-shuffle controlled REAL nine-game comparison.

One untouched original wall seed -> 1 Challenge baseline + 4 seat rotations
of original frozen shadow + 4 guarded seat rotations. Correlated rotations
belong to ONE original shuffle cluster. No model refit on historical tests,
no promotion to live Challenge, and no inferred single-action causal effect.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
from typing import Any

from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_shadow_headtohead import (
    MAX_EVAL_SEEDS, _finish_real_full_game,
    _paired_digest, _write_atomic, load_frozen_local_model,
)
from .ai_shadow_action_diagnostics import (
    MANIFEST as M439_MANIFEST, PROTOCOL as M439_PROTOCOL,
    _verify_prior_m437,
)

PROTOCOL="m441_preregistered_fresh_shuffle_shadow_guard_trial_v1"
SHARD_PROTOCOL="m441_nine_real_matches_per_original_shuffle_v1"
SHARD_DIR="PRIVATE_nine_game_seed_clusters"
PLAN="PRIVATE_guard_trial_plan.json"
SUMMARY="safe_guarded_frozen_shadow_trial.json"
POLICIES=("unguarded","guarded")
COMPONENTS=("win","kong","exhaustive")


def _score(game:dict[str,Any],seat:int,component:str)->int:
    return game[f"{component}_points_by_seat"][seat]


def _one_original_shuffle(seed:int,weights:tuple[float,...]|None)->dict[str,Any]:
    baseline=_finish_real_full_game(seed,None,weights)
    if baseline["phase"] not in ("finished","wall_exhausted"):
        raise RuntimeError("incomplete baseline")
    seat_rows=[]
    for seat in range(4):
        samples={}
        for guarded,policy in ((False,"unguarded"),(True,"guarded")):
            game=_finish_real_full_game(
                seed,seat,weights,minimum_ukeire_guard=guarded,
            )
            before=baseline["official_net_by_seat"][seat]
            after=game["official_net_by_seat"][seat]
            row={
                "official_net":after,
                "official_net_delta":after-before,
                "discard_opportunities":game["shadow_discard_decisions"],
                "accepted_overrides":game["shadow_override_count"],
                "phase":game["phase"],
                "paid_component_delta":{
                    name:_score(game,seat,name)-_score(baseline,seat,name)
                    for name in COMPONENTS
                },
            }
            if guarded:
                row["blocked_lower_effective_tiles"]=game[
                    "shadow_guard_blocked_count"]
            samples[policy]=row
        seat_rows.append({
            "seat":seat,
            "baseline_official_net":baseline["official_net_by_seat"][seat],
            "policies":samples,
        })
    return {
        "private_original_shuffle_seed":seed,
        "complete_authoritative_games":9,
        "same_natural_shuffle_all_nine_games":True,
        "baseline_phase":baseline["phase"],
        "baseline_all_seat_official_net":baseline["official_net_by_seat"],
        "seat_rotation_results":seat_rows,
        "no_online_promotion":True,
    }


def _audit_case(case:dict[str,Any],expected_seed:int) -> None:
    if (type(case) is not dict or
            type(case.get("private_original_shuffle_seed")) is not int or
            case["private_original_shuffle_seed"]!=expected_seed or
            case.get("complete_authoritative_games")!=9 or
            case.get("same_natural_shuffle_all_nine_games") is not True or
            case.get("no_online_promotion") is not True or
            case.get("baseline_phase") not in ("finished","wall_exhausted")):
        raise ValueError("missing or mismatched nine real-game seed cluster")
    baseline=case.get("baseline_all_seat_official_net")
    rows=case.get("seat_rotation_results")
    if (type(baseline) is not list or len(baseline)!=4 or
            any(type(x) is not int for x in baseline) or sum(baseline)!=0 or
            type(rows) is not list or len(rows)!=4):
        raise ValueError("invalid common Challenge baseline official ledger")
    for seat,record in enumerate(rows):
        if (type(record) is not dict or type(record.get("seat")) is not int or
                record["seat"]!=seat or
                record.get("baseline_official_net")!=baseline[seat] or
                type(record.get("policies")) is not dict or
                set(record["policies"])!=set(POLICIES)):
            raise ValueError("missing or repeated authentic four-seat policy rotation")
        for policy in POLICIES:
            game=record["policies"][policy]
            if type(game) is not dict or game.get("phase") not in ("finished","wall_exhausted"):
                raise ValueError("incomplete policy game")
            names=("official_net","official_net_delta",
                   "discard_opportunities","accepted_overrides")
            if any(type(game.get(k)) is not int for k in names):
                raise ValueError("invalid policy real ledger or discard counters")
            opportunities=game["discard_opportunities"]
            accepted=game["accepted_overrides"]
            if (not 0<=accepted<=opportunities or
                    game["official_net_delta"]!=
                        game["official_net"]-baseline[seat] or
                    type(game.get("paid_component_delta")) is not dict or
                    set(game["paid_component_delta"])!=set(COMPONENTS) or
                    any(type(x) is not int for x in
                        game["paid_component_delta"].values()) or
                    sum(game["paid_component_delta"].values())!=
                        game["official_net_delta"]):
                raise ValueError("unreconciled real policy payout")
            if policy=="guarded":
                blocked=game.get("blocked_lower_effective_tiles")
                if (type(blocked) is not int or not
                        0<=blocked<=opportunities-accepted):
                    raise ValueError("impossible guard rejected-overrides count")
            elif "blocked_lower_effective_tiles" in game:
                raise ValueError("unguarded policy cannot claim blocked actions")
            if accepted==0 and game["official_net_delta"]!=0:
                raise ValueError("unchanged Challenge choices must have baseline payout")


def _path(output:Path,i:int)->Path:
    return output/SHARD_DIR/f"index-{i:08d}.json"


def _load_shards(output:Path,n:int,start:int,digest:str)->dict[int,dict[str,Any]]:
    root=output/SHARD_DIR
    if not root.exists():
        return {}
    if not root.is_dir():
        raise ValueError("saved nine-game shards path is not a folder")
    saved={}
    for f in root.iterdir():
        if f.is_file() and ".tmp-" in f.name:
            continue
        if (not f.is_file() or len(f.name)!=19 or
                not f.name.startswith("index-") or
                not f.name[6:14].isdigit() or not f.name.endswith(".json")):
            raise ValueError("unexpected file in nine-game shard folder")
        i=int(f.name[6:14])
        if i<0 or i>=n or i in saved:
            raise ValueError("duplicate or out-of-plan fresh seed shard")
        env=_get_json(f)
        if (set(env)!={"protocol","index","model_sha256","sha256_case","private_case"} or
                env["protocol"]!=SHARD_PROTOCOL or
                type(env["index"]) is not int or env["index"]!=i or
                env["model_sha256"]!=digest or
                type(env["private_case"]) is not dict):
            raise ValueError("invalid immutable nine-game checkpoint")
        case=env["private_case"]
        _audit_case(case,start+i)
        if env["sha256_case"]!=_paired_digest(case):
            raise ValueError("private nine-game case checksum mismatch")
        saved[i]=case
    return saved


def _aggregate(cases:list[dict[str,Any]],provenance:dict[str,Any])->dict[str,Any]:
    count=len(cases)
    data={}
    for policy in POLICIES:
        per_seat=[[] for _ in range(4)]
        per_seed=[]
        attempts=accepted=blocked=0
        component_seed_means={name:[] for name in COMPONENTS}
        for case in cases:
            vals=[]
            components={name:[] for name in COMPONENTS}
            for row in case["seat_rotation_results"]:
                s=row["seat"]
                one=row["policies"][policy]
                delta=one["official_net_delta"]
                vals.append(delta)
                per_seat[s].append(delta)
                attempts+=one["discard_opportunities"]
                accepted+=one["accepted_overrides"]
                blocked+=one.get("blocked_lower_effective_tiles",0)
                for name in COMPONENTS:
                    components[name].append(one["paid_component_delta"][name])
            per_seed.append(mean(vals))
            for name in COMPONENTS:
                component_seed_means[name].append(mean(components[name]))
        data[policy]={
            "mean_paired_official_net_delta_points":round(mean(per_seed),5),
            "mean_paired_paid_components_points":{
                key:round(mean(value),5)
                for key,value in component_seed_means.items()
            },
            "per_seat_mean_official_net_delta_points":[
                round(mean(values),5) for values in per_seat
            ],
            "independent_shuffles_negative":sum(x<0 for x in per_seed),
            "independent_shuffles_positive":sum(x>0 for x in per_seed),
            "independent_shuffles_zero":sum(x==0 for x in per_seed),
            "candidate_discard_opportunities":attempts,
            "actual_model_overrides":accepted,
            "guard_blocked_lower_ukeire_overrides":blocked,
            "seat_rotations_with_no_model_override":sum(
                row["policies"][policy]["accepted_overrides"]==0
                for case in cases for row in case["seat_rotation_results"]
            ),
        }
        if (abs(sum(data[policy]["mean_paired_paid_components_points"].values())-
                data[policy]["mean_paired_official_net_delta_points"])>0.00002):
            raise RuntimeError("nine-game report payout totals do not reconcile")
    return {
        "protocol":PROTOCOL,
        "completed_original_shuffle_clusters":count,
        "actual_complete_paid_games":9*count,
        "challenge_baseline_games":count,
        "unguarded_four_seat_games":4*count,
        "guarded_four_seat_games":4*count,
        "original_training_seed_clusters":
            provenance["trained_original_shuffle_clusters"],
        "two_candidate_policies_same_original_shuffle_per_cluster":True,
        "correlated_rotations_not_independent_shuffles":True,
        "unguarded":data["unguarded"],
        "guarded":data["guarded"],
        "guard_has_strict_own_view_no_decrease_effective_tile_count_veto":True,
        "no_model_weight_changes_from_historical_evaluations":True,
        "online_challenge_ai_unchanged":True,
        "only_actor_own_view_for_policy_decisions":True,
        "comparison_is_observational_across_divergent_game_trajectories":True,
        "not_action_level_causal_attribution":True,
        "not_evidence_of_population_policy_improvement":True,
        "insufficient_original_shuffles_for_exploratory_comparison":count<20,
        "no_statistical_significance_claim":True,
        "private_shuffles_and_exact_model_weights_absent_from_safe_report":True,
    }


def run_guarded_trial(
    *,training_dir:Path,prior_m437_dir:Path,prior_m439_dir:Path,
    seed_start:int,seeds:int,out_dir:Path,resume:bool=False
) ->dict[str,Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
            type(resume) is not bool or
            not 0<=seed_start<2**32 or
            not 1<=seeds<=MAX_EVAL_SEEDS or seed_start+seeds>2**32):
        raise ValueError("invalid new independent shuffle seed plan")
    training=_private_location(Path(training_dir))
    prior437=_private_location(Path(prior_m437_dir))
    prior439=_private_location(Path(prior_m439_dir))
    output=_private_location(Path(out_dir))
    if len({training,prior437,prior439,output})!=4 or any(
        source in output.parents or output in source.parents
        for source in (training,prior437,prior439)
    ):
        raise ValueError("nine-game output must not overlap private input directories")
    weights,prov=load_frozen_local_model(training)
    original_start=prov["source_m434_train_seed_start"]
    original_end=prov["source_m434_seed_end_exclusive"]
    if not (seed_start+seeds<=original_start or seed_start>=original_end):
        raise ValueError("new shuffle seed overlaps original TRAIN or holdout")
    _verify_prior_m437(
        prior437,training,prov["model_sha256"],seed_start,seeds,
    )
    m439=_get_json(prior439/M439_MANIFEST)
    previous_start=m439.get("private_eval_seed_start")
    previous_n=m439.get("private_eval_seed_count")
    if (m439.get("protocol")!=M439_PROTOCOL or
            m439.get("private_source_training_directory")!=str(training) or
            m439.get("private_source_m437_directory")!=str(prior437) or
            m439.get("private_frozen_model_sha256")!=prov["model_sha256"] or
            m439.get("online_policy_changed") is not False or
            type(previous_start) is not int or type(previous_n) is not int or
            not 0<=previous_start<2**32 or
            not 1<=previous_n<=MAX_EVAL_SEEDS or
            previous_start+previous_n>2**32):
        raise ValueError("M4.39 previous actor diagnostic plan/model is not auditable")
    if not (seed_start+seeds<=previous_start or seed_start>=previous_start+previous_n):
        raise ValueError("new shuffle seed overlaps M4.39 already viewed outcomes")
    plan={
        "protocol":PROTOCOL,
        "private_training_dir":str(training),
        "private_prior_m437_dir":str(prior437),
        "private_prior_m439_dir":str(prior439),
        "frozen_model_sha256":prov["model_sha256"],
        "private_seed_start":seed_start,
        "original_shuffle_clusters":seeds,
        "pre_registered_policy_guard":"veto_if_lower_visible_effective_tile_count",
        "live_online_promotion":False,
        "no_retuning_from_m437_m439_m440_test_scores":True,
    }
    if resume:
        if not output.is_dir() or not (output/PLAN).is_file():
            raise ValueError("resume requires existing M4.41 private plan")
        if _get_json(output/PLAN)!=plan:
            raise ValueError("M4.41 resume plan, model or seed parameters changed")
        if any(p.name not in {PLAN,SHARD_DIR,SUMMARY} and ".tmp-" not in p.name
               for p in output.iterdir()):
            raise ValueError("unexpected file in guarded trial resume folder")
        saved=_load_shards(output,seeds,seed_start,prov["model_sha256"])
        if (output/SUMMARY).exists() and len(saved)!=seeds:
            raise ValueError("complete summary exists but saved original-shuffle shard missing")
    else:
        if output.exists() and any(output.iterdir()):
            raise ValueError("nine-game trial requires new empty output folder")
        output.mkdir(parents=True,exist_ok=True)
        _write_atomic(output/PLAN,plan)
        saved={}
    (output/SHARD_DIR).mkdir(exist_ok=True)
    cases=[]
    for index in range(seeds):
        case=saved.get(index)
        if case is None:
            case=_one_original_shuffle(seed_start+index,weights)
            _audit_case(case,seed_start+index)
            _write_atomic(_path(output,index),{
                "protocol":SHARD_PROTOCOL,
                "index":index,
                "model_sha256":prov["model_sha256"],
                "sha256_case":_paired_digest(case),
                "private_case":case,
            })
        cases.append(case)
    safe=_aggregate(cases,prov)
    safe["completed_seed_shards_reused_on_resume"]=len(saved)
    _write_atomic(output/SUMMARY,safe)
    return safe
