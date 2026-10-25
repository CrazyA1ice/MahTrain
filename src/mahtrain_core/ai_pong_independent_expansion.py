"""M4.46: 20 independent-shuffle expansion of UNCHANGED M4.45 research policy.

No live Challenge edits, no data-driven threshold changes, no recycling or
pooling already-seen M4.45 seed clusters. Five authentic full paid games per
new seed, using M4.45's existing crash-safe runner and original seed shards.
"""
from __future__ import annotations

import hashlib
import inspect
from pathlib import Path
from statistics import mean
from typing import Any

from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_shadow_headtohead import _write_atomic, load_frozen_local_model
from .ai_pong_threshold_trial import (
    FrozenPengThresholdAgent, LOWER_EXTRA_COPIES, UPPER_EXTRA_COPIES,
    PROTOCOL as OLD_PROTOCOL, PLAN as OLD_PLAN, SUMMARY as OLD_SUMMARY,
    _load_saved, _summary as previous_summary, run_pong_threshold_trial,
)

PROTOCOL="m446_locked_m445_new_20_independent_shuffle_expansion_v1"
PLAN="PRIVATE_m446_frozen_expansion_plan.json"
SUMMARY="safe_pong_independent_expansion.json"
PRIVATE_BATCH="PRIVATE_m446_m445_full_paid_game_batch"
FROZEN_SEED_COUNT=20


def _policy_digest()->str:
    return hashlib.sha256(
        Path(inspect.getfile(FrozenPengThresholdAgent)).read_bytes()
    ).hexdigest()


def _original_evidence(*,prior:Path,train:Path,model:dict[str,Any],
                       start:int,n:int)->Path:
    plan=_get_json(prior/OLD_PLAN)
    old_start=plan.get("private_original_shuffle_start")
    old_n=plan.get("private_original_shuffle_count")
    sha=model["model_sha256"]
    if (plan.get("protocol")!=OLD_PROTOCOL or
            plan.get("private_model_source")!=str(train) or
            plan.get("model_sha256_provenance_only")!=sha or
            plan.get("precommitted_ukeire_gain_min")!=LOWER_EXTRA_COPIES or
            plan.get("precommitted_ukeire_gain_max")!=UPPER_EXTRA_COPIES or
            plan.get("live_challenge_unchanged") is not True or
            type(old_start) is not int or type(old_n) is not int or
            not 0<=old_start<2**32 or not 1<=old_n<=100 or
            old_start+old_n>2**32 or
            not (start+n<=old_start or start>=old_start+old_n)):
        raise ValueError("M4.46 new shuffles overlap old M4.45 or model plan changed")
    old_cases=_load_saved(prior,old_start,old_n,sha)
    if len(old_cases)!=old_n:
        raise ValueError("previous M4.45 pilot lacks completed paid seed shards")
    expected=previous_summary(
        [old_cases[i] for i in range(old_n)],
        model["trained_original_shuffle_clusters"],
    )
    actual=_get_json(prior/OLD_SUMMARY)
    if (type(actual) is not dict or
            any(actual.get(k)!=v for k,v in expected.items())):
        raise ValueError("prior M4.45 public result does not match private shards")
    m444=plan.get("private_source_m444")
    if not isinstance(m444,str) or not m444:
        raise ValueError("original M4.45 private source missing")
    return _private_location(Path(m444))


def _cluster_metrics(cases:list[dict[str,Any]])->dict[str,Any]:
    with_override=0
    total_overrides=0
    all_seat_zero=0
    active_cluster_deltas=[]
    for case in cases:
        rows=case["seat_rotation_results"]
        overrides=sum(x["actor_counts"]["actual_peng_overrides"] for x in rows)
        paired=[x["paired_net_delta"] for x in rows]
        total_overrides+=overrides
        with_override+=int(overrides>0)
        all_seat_zero+=int(all(v==0 for v in paired))
        if overrides:
            active_cluster_deltas.append(mean(paired))
    return {
        "original_shuffles_with_actual_peng_override":with_override,
        "original_shuffles_without_peng_override":len(cases)-with_override,
        "original_shuffles_with_all_four_seat_net_deltas_zero":all_seat_zero,
        "actual_peng_overrides":total_overrides,
        "mean_net_delta_in_clusters_with_override_descriptive_only":
            round(mean(active_cluster_deltas),5)
            if active_cluster_deltas else None,
    }


def run_independent_pong_expansion(
    *,training_dir:Path,prior_m445_dir:Path,
    seed_start:int,seeds:int,out_dir:Path,resume:bool=False,
)->dict[str,Any]:
    # Sample size is deliberately precommitted to 20 independent original
    # shuffle clusters; four rotated seat matches are correlated.
    if (type(seed_start) is not int or type(seeds) is not int or
            type(resume) is not bool or seeds!=FROZEN_SEED_COUNT or
            not 0<=seed_start<2**32 or seed_start+seeds>2**32):
        raise ValueError("M4.46 requires exactly 20 independent new shuffle seeds")
    train=_private_location(Path(training_dir))
    prior=_private_location(Path(prior_m445_dir))
    output=_private_location(Path(out_dir))
    if (len({train,prior,output})!=3 or
            any(a in b.parents or b in a.parents
                for a,b in ((train,prior),(train,output),(prior,output)))):
        raise ValueError("sources and evaluation output must not overlap")
    _,model=load_frozen_local_model(train)
    t0=model["source_m434_train_seed_start"]
    t1=model["source_m434_seed_end_exclusive"]
    if not (seed_start+seeds<=t0 or seed_start>=t1):
        raise ValueError("M4.46 evaluation overlaps original train/holdout seeds")
    m444=_original_evidence(
        prior=prior,train=train,model=model,start=seed_start,n=seeds,
    )
    plan={
        "protocol":PROTOCOL,
        "private_training_source":str(train),
        "private_previous_m445_source":str(prior),
        "private_previous_m444_source":str(m444),
        "private_original_shuffle_start":seed_start,
        "private_new_original_shuffle_clusters":seeds,
        "training_model_sha256_provenance_only":model["model_sha256"],
        "unchanged_m445_source_sha256":_policy_digest(),
        "precommitted_min_extra_ukeire":LOWER_EXTRA_COPIES,
        "precommitted_max_extra_ukeire":UPPER_EXTRA_COPIES,
        "challenge_live_policy_untouched":True,
    }
    batch=output/PRIVATE_BATCH
    if resume:
        if not output.is_dir() or not (output/PLAN).is_file():
            raise ValueError("resume requires the original M4.46 frozen plan")
        if _get_json(output/PLAN)!=plan:
            raise ValueError("M4.46 frozen source, seeds, or plan changed")
        if any(p.name not in {PLAN,PRIVATE_BATCH,SUMMARY} and
               ".tmp-" not in p.name for p in output.iterdir()):
            raise ValueError("unknown file in M4.46 expansion report folder")
        batch_resume=batch.exists()
    else:
        if output.exists() and any(output.iterdir()):
            raise ValueError("M4.46 requires a new empty output directory")
        output.mkdir(parents=True,exist_ok=True)
        _write_atomic(output/PLAN,plan)
        batch_resume=False
    # Existing M4.45 engine performs the real 5-game shuffle batches,
    # complete score reconciliation, immutable shard validation and resume.
    old_result=run_pong_threshold_trial(
        training_dir=train,prior_m444_dir=m444,
        seed_start=seed_start,seeds=seeds,
        out_dir=batch,resume=batch_resume,
    )
    verified=_load_saved(batch,seed_start,seeds,model["model_sha256"])
    if len(verified)!=seeds:
        raise RuntimeError("reported complete batch is missing paid-game shards")
    result={
        "protocol":PROTOCOL,
        "frozen_original_m445_policy_used_without_retraining":True,
        "old_pilot_not_pooled_with_new_evaluation":True,
        "independent_original_shuffle_clusters":seeds,
        "real_complete_paid_games":seeds*5,
        "baseline_challenge_games":seeds,
        "candidate_four_seat_rotated_games":seeds*4,
        "precommitted_equal_shanten_peng_extra_ukeire_range":[
            LOWER_EXTRA_COPIES,UPPER_EXTRA_COPIES,
        ],
        "actor_only_response_counts":old_result["actor_only_response_counts"],
        "mean_official_net_delta_points":
            old_result["mean_official_net_delta_points"],
        "mean_official_component_delta_points":
            old_result["mean_official_component_delta_points"],
        "per_seat_mean_official_net_delta_points":
            old_result["per_seat_mean_official_net_delta_points"],
        "independent_shuffles_positive":old_result["clusters_positive"],
        "independent_shuffles_negative":old_result["clusters_negative"],
        "independent_shuffles_equal":old_result["clusters_equal"],
        **_cluster_metrics([verified[i] for i in range(seeds)]),
        "same_shuffle_seat_rotations_not_independent":True,
        "experimental_intervention_not_promoted_to_online_challenge":True,
        "no_parameter_tuning_using_old_or_new_test_outcomes":True,
        "no_private_seed_tiles_model_weights_or_wall_data_in_safe_report":True,
        "not_single_action_causal_impact":True,
        "no_general_strength_or_significance_claim":True,
        "completed_original_shuffles_reused_on_resume":
            old_result["reused_completed_original_shuffle_clusters"],
    }
    _write_atomic(output/SUMMARY,result)
    return result
