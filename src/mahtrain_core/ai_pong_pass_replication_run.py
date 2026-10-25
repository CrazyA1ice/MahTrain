"""M4.48 fixed 24 new original shuffle rollout engine, no online change."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_shadow_headtohead import _write_atomic, _paired_digest, load_frozen_local_model
from .ai_pong_pass_branch_rollouts import (
    SHARD_DIR, SHARD_PROTOCOL, WORLDS, CHECKPOINTS_PER_SHUFFLE,
    _private_shard, _read_verified, _validate_case, _aggregate,
    one_natural_shuffle,
)
from .ai_pong_pass_replication import (
    PROTOCOL, PLAN, SUMMARY, PRIVATE_BATCH, SEED_COUNT,
    BOOTSTRAPS, BOOTSTRAP_SEED, _frozen_m447_sha256,
    _prior_provenance, _additional_statistics,
)


def run_independent_branch_replication(
    *,training_dir:Path,prior_m447_dir:Path,seed_start:int,
    seeds:int,out_dir:Path,resume:bool=False
)->dict[str,Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
        type(resume) is not bool or seeds!=SEED_COUNT or
        not 0<=seed_start<2**32 or seed_start+seeds>2**32):
        raise ValueError("M4.48 requires 24 new original shuffle seeds")
    train=_private_location(Path(training_dir))
    prior=_private_location(Path(prior_m447_dir))
    out=_private_location(Path(out_dir))
    if (len({train,prior,out})!=3 or any(
        a in b.parents or b in a.parents
        for a,b in ((train,prior),(train,out),(prior,out))
    )):
        raise ValueError("M4.48 private sources and output must be separate")
    _,model=load_frozen_local_model(train)
    t0=model["source_m434_train_seed_start"]
    t1=model["source_m434_seed_end_exclusive"]
    if not (seed_start+seeds<=t0 or seed_start>=t1):
        raise ValueError("M4.48 overlaps original training/holdout")
    old=_prior_provenance(prior=prior,training=train,model=model,
                          start=seed_start,n=seeds)
    plan={
        "protocol":PROTOCOL,
        "private_model_source":str(train),
        "private_prior_m447_source":str(prior),
        "private_prior_m446_source":old["private_m446_source"],
        "private_natural_seed_start":seed_start,
        "private_original_seed_count":seeds,
        "model_sha256":model["model_sha256"],
        "m447_source_sha256":_frozen_m447_sha256(),
        "worlds":list(WORLDS),
        "first_checkpoint_per_shuffle":CHECKPOINTS_PER_SHUFFLE,
        "precommitted_bootstrap_count":BOOTSTRAPS,
        "precommitted_bootstrap_seed":BOOTSTRAP_SEED,
        "original_m447_seed_start":old["private_previous_m447_start"],
        "original_m447_seed_count":old["private_previous_m447_clusters"],
        "no_policy_training_or_promotion":True,
    }
    batch=out/PRIVATE_BATCH
    if resume:
        if not out.is_dir() or not (out/PLAN).is_file():
            raise ValueError("resume requires original M4.48 private plan")
        if _get_json(out/PLAN)!=plan:
            raise ValueError("M4.48 frozen source, seed range or plan changed")
        if any(p.name not in {PLAN,PRIVATE_BATCH,SUMMARY}
               and ".tmp-" not in p.name for p in out.iterdir()):
            raise ValueError("unexpected file in private M4.48 output")
        saved=_read_verified(batch,seed_start,seeds,model["model_sha256"])
        if (out/SUMMARY).exists() and len(saved)!=seeds:
            raise ValueError("completed safe report missing full private shards")
    else:
        if out.exists() and any(out.iterdir()):
            raise ValueError("new M4.48 evaluation requires empty output")
        out.mkdir(parents=True,exist_ok=True)
        _write_atomic(out/PLAN,plan)
        saved={}
    (batch/SHARD_DIR).mkdir(parents=True,exist_ok=True)
    for i in range(seeds):
        if i in saved:
            continue
        case=one_natural_shuffle(seed_start+i)
        _validate_case(case,seed_start+i)
        _write_atomic(_private_shard(batch,i),{
            "protocol":SHARD_PROTOCOL,
            "index":i,
            "model_sha256":model["model_sha256"],
            "case_sha256":_paired_digest(case),
            "private_case":case,
        })
    verified=_read_verified(batch,seed_start,seeds,model["model_sha256"])
    if len(verified)!=seeds:
        raise RuntimeError("private evidence missing completed original shuffle")
    original=_aggregate([verified[i] for i in range(seeds)])
    enhanced=_additional_statistics([verified[i] for i in range(seeds)])
    result={
        "protocol":PROTOCOL,
        "new_independent_original_shuffle_clusters":seeds,
        "previous_m447_original_shuffles_audited_but_not_pooled":True,
        "old_m447_original_shuffle_count":old["private_previous_m447_clusters"],
        "real_natural_challenge_baseline_games":
            original["actual_natural_original_challenge_games"],
        "real_terminal_branch_games":
            original["genuine_full_terminal_branch_games"],
        "total_true_complete_paid_games":
            original["real_completed_full_games_baseline_plus_branches"],
        "original_shuffles_with_first_pass_peng_checkpoint":
            original["original_shuffles_with_legal_peng_after_challenge_pass"],
        "original_shuffles_without_checkpoint":
            original["original_shuffles_without_such_a_checkpoint"],
        "two_world_matched_branch_pairs":original["paired_future_wall_worlds"],
        "branch_pairs_with_actual_peng":
            original["branch_pairs_where_peng_was_actually_claimed"],
        "branch_pairs_preempted_by_opponent":
            original["branch_pairs_where_other_calls_preempted_peng"],
        "mean_forced_peng_minus_pass_official_net_points":
            original["mean_forced_peng_minus_pass_all_seed_clusters"],
        "mean_official_component_delta_points":
            original["mean_official_component_delta_all_seed_clusters"],
        "original_shuffles_positive":original["seed_level_positive_delta"],
        "original_shuffles_negative":original["seed_level_negative_delta"],
        "original_shuffles_equal":original["seed_level_zero_delta"],
        **enhanced,
        "first_real_checkpoint_not_selected_from_future_payout":True,
        "same_shuffle_two_future_worlds_not_independent":True,
        "all_actions_share_identical_preintervention_state_and_rng":True,
        "no_hidden_tiles_or_wall_given_to_online_policy":True,
        "old_and_new_results_not_used_for_training":True,
        "online_challenge_ai_unchanged":True,
        "no_strength_causality_or_population_ev_claim":True,
        "no_private_seeds_tiles_sha_or_wall_in_public_json":True,
        "verified_original_clusters_reused_on_resume":len(saved),
    }
    if (result["original_shuffles_positive"]+
        result["original_shuffles_negative"]+
        result["original_shuffles_equal"]!=seeds):
        raise RuntimeError("missing an independent original shuffle result")
    _write_atomic(out/SUMMARY,result)
    return result
