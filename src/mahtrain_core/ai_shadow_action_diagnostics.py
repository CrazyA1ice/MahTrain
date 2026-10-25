"""M4.39: NEW-SEED frozen-shadow real match diagnostics, actor-view only.

No online policy replacement; no replay of prior M4.37 games; no fit against
the past evaluation. Captured cuts are genuine choices in each candidate's
OWN trajectory, not single-action paired counterfactuals. Treat a common
original shuffle (five correlated matches) as one independent cluster.
"""
from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from statistics import mean
from typing import Any, Mapping

from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_shadow_headtohead import (
    MAX_EVAL_SEEDS, PROTOCOL as M436_PROTOCOL,
    SHARD_PROTOCOL as M437_SHARD_PROTOCOL, _audit_paired_case,
    _paired_digest, _write_atomic, evaluate_one_seed,
    load_frozen_local_model,
)

PROTOCOL="m439_actor_only_frozen_shadow_real_decision_diagnostics_v1"
SHARD_PROTOCOL="m439_private_actor_decision_cluster_v1"
SHARD_FOLDER="PRIVATE_actor_diagnostic_seed_clusters"
MANIFEST="PRIVATE_actor_diagnostic_plan.json"
SUMMARY="safe_actor_decision_diagnostics.json"
ALLOWED_REASONS={
    "no_better_frozen_margin",
    "no_frozen_weights",
    "no_eligible_discard_oracle",
    "only_one_minimum_shanten_cut",
    "positive_frozen_margin",
}
ACTION_FIELDS={
    "decision_ordinal","overrode","kept_minimum_shanten","baseline_discard",
    "reason","model_margin","chosen_discard",
}
OPTIONAL_FEATURE_FIELDS={
    "minimum_shanten","baseline_effective_tile_count",
    "baseline_next_draw_probability","baseline_effective_types_count",
    "eligible_minimum_shanten_cut_count",
    "chosen_effective_tile_count","chosen_next_draw_probability",
    "chosen_effective_types_count",
}


def _audit_trace(case:dict[str,Any]) -> None:
    for row in case["seat_rotation_results"]:
        trace=row.get("private_actor_discard_trace")
        if type(trace) is not list or len(trace)!=row["shadow_discard_decisions"]:
            raise ValueError("missing original acting-agent discard trace")
        total=0
        for index,step in enumerate(trace,1):
            if (type(step) is not dict or
                    set(step)-ACTION_FIELDS-OPTIONAL_FEATURE_FIELDS or
                    not ACTION_FIELDS.issubset(step) or
                    type(step["decision_ordinal"]) is not int or
                    step["decision_ordinal"]!=index or
                    type(step["overrode"]) is not bool or
                    step["kept_minimum_shanten"] is not True or
                    step["reason"] not in ALLOWED_REASONS or
                    type(step["baseline_discard"]) is not str or
                    type(step["chosen_discard"]) is not str or
                    type(step["model_margin"]) not in (float,int) or
                    not isfinite(step["model_margin"])):
                raise ValueError("invalid actor-only legal discard observation")
            for tile_key in ("baseline_discard","chosen_discard"):
                tile=step[tile_key]
                if len(tile)!=2 or tile[0] not in "mps" or tile[1] not in "123456789":
                    raise ValueError("diagnostic discard does not use valid suit tile")
            for k in OPTIONAL_FEATURE_FIELDS & set(step):
                v=step[k]
                if type(v) not in (float,int) or not isfinite(v):
                    raise ValueError("invalid actor-view feature")
            overridden=step["overrode"]
            if overridden:
                total+=1
                if (step["chosen_discard"]==step["baseline_discard"] or
                        step["reason"]!="positive_frozen_margin" or
                        step["model_margin"]<=1e-9 or
                        not OPTIONAL_FEATURE_FIELDS.issubset(step)):
                    raise ValueError("missing measured legal positive-margin override")
            elif (step["chosen_discard"]!=step["baseline_discard"] or
                    step["reason"]=="positive_frozen_margin" or
                    step["model_margin"]!=0):
                raise ValueError("no-op recorded as model-changed discard")
        if total!=row["shadow_override_count"]:
            raise ValueError("per-decision override trace does not reconcile")


def _case_path(root:Path,i:int)->Path:
    return root/SHARD_FOLDER/f"index-{i:08d}.json"


def _verify_prior_m437(root:Path,training:Path,digest:str,
                       eval_start:int,eval_n:int) -> None:
    """Use old metadata only, never prior policy outcomes to optimize weights."""
    prior=_get_json(root/"PRIVATE_frozen_benchmark_plan.json")
    start=prior.get("private_evaluation_seed_start")
    count=prior.get("private_eval_original_shuffle_count")
    if (prior.get("protocol")!=M436_PROTOCOL or
            prior.get("resumable_shards_protocol")!=M437_SHARD_PROTOCOL or
            prior.get("private_source_training_directory")!=str(training) or
            prior.get("private_frozen_model_sha256")!=digest or
            type(start) is not int or type(count) is not int or
            not 1<=count<=MAX_EVAL_SEEDS or
            not 0<=start<2**32 or start+count>2**32):
        raise ValueError("prior M4.37 evaluation model/plan does not match frozen source")
    if not (eval_start+eval_n<=start or eval_start>=start+count):
        raise ValueError("new diagnostic shuffles overlap the already seen M4.37 batch")


def _read_saved(root:Path,n:int,seed_start:int,model_hash:str
               ) -> dict[int,dict[str,Any]]:
    folder=root/SHARD_FOLDER
    if not folder.is_dir():
        return {}
    result={}
    for p in folder.iterdir():
        if ".tmp-" in p.name and p.is_file():
            continue
        if (not p.is_file() or len(p.name)!=19 or
                not p.name.startswith("index-") or
                not p.name.endswith(".json") or
                not p.name[6:14].isdigit()):
            raise ValueError("unexpected diagnostic shard file")
        i=int(p.name[6:14])
        if i<0 or i>=n or i in result:
            raise ValueError("out-of-plan or repeated diagnostic shard")
        wrapper=_get_json(p)
        if (set(wrapper)!={"protocol","index","model_sha256",
                           "sha256_case","private_case"} or
                wrapper["protocol"]!=SHARD_PROTOCOL or
                type(wrapper["index"]) is not int or wrapper["index"]!=i or
                wrapper["model_sha256"]!=model_hash or
                type(wrapper["private_case"]) is not dict):
            raise ValueError("diagnostic shard has wrong immutable provenance")
        case=wrapper["private_case"]
        _audit_paired_case(case,seed_start+i)
        _audit_trace(case)
        if wrapper["sha256_case"]!=_paired_digest(case):
            raise ValueError("saved diagnostic shard checksum mismatch")
        result[i]=case
    return result


def _aggregate(cases:list[dict[str,Any]])->dict[str,Any]:
    n=len(cases)
    changed=[]
    opportunities=0
    no_override=0
    by_seat=[[] for _ in range(4)]
    per_seed=[]
    for case in cases:
        rows=case["seat_rotation_results"]
        per_seed.append(mean(r["delta_shadow_minus_challenge"] for r in rows))
        for r in rows:
            by_seat[r["seat"]].append(r["delta_shadow_minus_challenge"])
            trace=r["private_actor_discard_trace"]
            opportunities+=len(trace)
            no_override+=sum(not s["overrode"] for s in trace)
            changed.extend(s for s in trace if s["overrode"])
    lowered=sum(s["chosen_effective_tile_count"]<
                s["baseline_effective_tile_count"] for s in changed)
    raised=sum(s["chosen_effective_tile_count"]>
               s["baseline_effective_tile_count"] for s in changed)
    tied=len(changed)-lowered-raised
    score=round(mean(per_seed),5)
    return {
        "protocol":PROTOCOL,
        "original_shuffle_seed_clusters":n,
        "actual_real_complete_games":5*n,
        "correlated_seat_rotated_actor_matches":4*n,
        "actor_discard_opportunities":opportunities,
        "actual_model_override_count":len(changed),
        "baseline_kept_discard_count":no_override,
        "actor_visible_effective_tile_count_lower_on_override":lowered,
        "actor_visible_effective_tile_count_higher_on_override":raised,
        "actor_visible_effective_tile_count_tied_on_override":tied,
        "mean_actor_visible_effective_tile_delta_on_override":(
            round(mean(s["chosen_effective_tile_count"]-
                       s["baseline_effective_tile_count"] for s in changed),5)
            if changed else 0.),
        "mean_frozen_model_margin_on_override":(
            round(mean(s["model_margin"] for s in changed),7)
            if changed else 0.),
        "paired_mean_official_net_delta_points":score,
        "per_seat_paired_mean_official_net_delta_points":[
            round(mean(s),5) for s in by_seat],
        "original_shuffle_clusters_with_negative_paired_mean":
            sum(x<0 for x in per_seed),
        "original_shuffle_clusters_with_positive_paired_mean":
            sum(x>0 for x in per_seed),
        "original_shuffle_clusters_with_zero_paired_mean":
            sum(x==0 for x in per_seed),
        "online_challenge_unchanged":True,
        "no_training_or_threshold_selection_using_prior_test_results":True,
        "observations_are_actor_only_not_hidden_opponent_hands":True,
        "diagnosed_cuts_are_not_single_action_counterfactual_effects":True,
        "too_few_independent_seeds_for_exploratory_inference":n<20,
        "no_statistical_significance_claim":True,
        "no_population_strength_claim":True,
        "no_private_seed_tile_or_model_weights_in_safe_summary":True,
    }


def run_actor_diagnostics(
    *,training_dir:Path,prior_evaluation_dir:Path,
    seed_start:int,seeds:int,out_dir:Path,resume:bool=False
) -> dict[str,Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
            type(resume) is not bool or not 0<=seed_start<2**32 or
            not 1<=seeds<=MAX_EVAL_SEEDS or seed_start+seeds>2**32):
        raise ValueError("invalid bounded new diagnostic seed plan or resume flag")
    training=_private_location(Path(training_dir))
    prior=_private_location(Path(prior_evaluation_dir))
    output=_private_location(Path(out_dir))
    if output==training or output==prior or output in (training,prior):
        raise ValueError("diagnostic output must be separate from source artifacts")
    if training in output.parents or prior in output.parents:
        raise ValueError("cannot write inside private input directories")
    weights,meta=load_frozen_local_model(training)
    train_start=meta["source_m434_train_seed_start"]
    train_end=meta["source_m434_seed_end_exclusive"]
    if not (seed_start+seeds<=train_start or seed_start>=train_end):
        raise ValueError("new diagnostic seed overlaps training or original holdout")
    _verify_prior_m437(prior,training,meta["model_sha256"],seed_start,seeds)
    plan={
        "protocol":PROTOCOL,
        "private_frozen_model_sha256":meta["model_sha256"],
        "private_source_training_directory":str(training),
        "private_source_m437_directory":str(prior),
        "private_eval_seed_start":seed_start,
        "private_eval_seed_count":seeds,
        "online_policy_changed":False,
        "source_m437_used_only_for_exclusion_and_provenance":True,
    }
    if resume:
        if not output.is_dir() or not (output/MANIFEST).is_file():
            raise ValueError("resume requires a saved M4.39 plan")
        if _get_json(output/MANIFEST)!=plan:
            raise ValueError("diagnostic resume plan or model changed")
        allowed={MANIFEST,SHARD_FOLDER,SUMMARY}
        if any(p.name not in allowed and ".tmp-" not in p.name
               for p in output.iterdir()):
            raise ValueError("unexpected entries in diagnostic resume folder")
        saved=_read_saved(output,seeds,seed_start,meta["model_sha256"])
        if (output/SUMMARY).exists() and len(saved)!=seeds:
            raise ValueError("finished diagnostic summary missing complete seed shards")
    else:
        if output.exists() and any(output.iterdir()):
            raise ValueError("new diagnostic output folder must be empty")
        output.mkdir(parents=True,exist_ok=True)
        _write_atomic(output/MANIFEST,plan)
        saved={}
    (output/SHARD_FOLDER).mkdir(exist_ok=True)
    all_cases=[]
    for offset in range(seeds):
        case=saved.get(offset)
        if case is None:
            case=evaluate_one_seed(seed_start+offset,weights,
                                   capture_diagnostics=True)
            _audit_paired_case(case,seed_start+offset)
            _audit_trace(case)
            _write_atomic(_case_path(output,offset),{
                "protocol":SHARD_PROTOCOL,
                "index":offset,
                "model_sha256":meta["model_sha256"],
                "sha256_case":_paired_digest(case),
                "private_case":case,
            })
        all_cases.append(case)
    safe=_aggregate(all_cases)
    safe["reused_completed_original_shuffle_clusters"]=len(saved)
    _write_atomic(output/SUMMARY,safe)
    return safe
