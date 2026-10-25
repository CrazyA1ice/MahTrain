"""M4.50 fresh-shuffle runner: unchanged M4.49 genuine engine, paired paid branches."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_shadow_headtohead import _paired_digest, _write_atomic, load_frozen_local_model
from .ai_pong_actor_strata import (
    one_actor_stratified_shuffle, safe_actor_strata, validate_case
)
from .ai_pong_phase_confirmation import (
    PROTOCOL, SHARD_PROTOCOL, PLAN, SHARDS, SUMMARY, SEED_COUNT,
    RESAMPLES, RANDOM_SEED, MIN_PER_GROUP, audit_previous_m449,
    confirm_phase_contrast, frozen_m449_source_digest,
)


def _file(out:Path,i:int)->Path:
    return out/SHARDS/f"index-{i:08d}.json"


def _verified_shards(out:Path,start:int,n:int,model_sha:str)->dict[int,dict[str,Any]]:
    folder=out/SHARDS
    if not folder.exists():
        return {}
    if not folder.is_dir():
        raise ValueError("M4.50 checkpoint folder is not a directory")
    saved={}
    for p in folder.iterdir():
        if p.is_file() and ".tmp-" in p.name:
            continue
        if (not p.is_file() or
            len(p.name)!=19 or not p.name.startswith("index-") or
            not p.name.endswith(".json") or not p.name[6:14].isdigit()):
            raise ValueError("unrecognized M4.50 original shuffle shard")
        i=int(p.name[6:14])
        if i>=n or i in saved:
            raise ValueError("duplicate or out-of-range M4.50 shard")
        envelope=_get_json(p)
        if (type(envelope) is not dict or
            set(envelope)!={"protocol","index","model_sha256","case_sha256","private_case"} or
            envelope["protocol"]!=SHARD_PROTOCOL or
            type(envelope["index"]) is not int or envelope["index"]!=i or
            envelope["model_sha256"]!=model_sha or
            type(envelope["private_case"]) is not dict):
            raise ValueError("M4.50 signed shard envelope invalid")
        case=envelope["private_case"]
        validate_case(case,start+i)
        if envelope["case_sha256"]!=_paired_digest(case):
            raise ValueError("M4.50 original shuffle case SHA-256 mismatch")
        saved[i]=case
    return saved


def run_phase_confirmation(
    *,training_dir:Path,prior_m449_dir:Path,
    seed_start:int,seeds:int,out_dir:Path,resume:bool=False,
)->dict[str,Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
        type(resume) is not bool or seeds!=SEED_COUNT or
        not 0<=seed_start<2**32 or seed_start+seeds>2**32):
        raise ValueError("M4.50 requires a fixed 48 new original shuffle seeds")
    train=_private_location(Path(training_dir))
    previous=_private_location(Path(prior_m449_dir))
    out=_private_location(Path(out_dir))
    if (len({train,previous,out})!=3 or any(
        a in b.parents or b in a.parents
        for a,b in ((train,previous),(train,out),(previous,out))
    )):
        raise ValueError("M4.50 private input/output directories must not overlap")
    _,model=load_frozen_local_model(train)
    t0=model["source_m434_train_seed_start"]
    t1=model["source_m434_seed_end_exclusive"]
    if not (seed_start+seeds<=t0 or seed_start>=t1):
        raise ValueError("M4.50 seed overlaps M4.34 train or holdout")
    prior=audit_previous_m449(
        prior=previous,training=train,model=model,start=seed_start,n=seeds,
    )
    root=Path(__file__).resolve().parent
    code_sha=sha256(
        (root/"ai_pong_phase_confirmation.py").read_bytes()+
        Path(__file__).read_bytes()
    ).hexdigest()
    frozen={
        "protocol":PROTOCOL,
        "private_training_source":str(train),
        "private_prior_m449_source":str(previous),
        "private_prior_m448_source":prior["private_previous_m448_source"],
        "private_seed_start":seed_start,
        "independent_original_shuffle_count":seeds,
        "model_sha256":model["model_sha256"],
        "m449_source_sha256":frozen_m449_source_digest(),
        "m450_source_sha256":code_sha,
        "precommitted_early_wall_min":40,
        "precommitted_middle_wall_min":20,
        "precommitted_middle_wall_max":39,
        "precommitted_min_group_size":MIN_PER_GROUP,
        "precommitted_bootstrap_resamples":RESAMPLES,
        "precommitted_bootstrap_seed":RANDOM_SEED,
        "first_checkpoint_only":True,
        "no_policy_fit_or_live_challenge_change":True,
    }
    if resume:
        if not out.is_dir() or not (out/PLAN).is_file():
            raise ValueError("M4.50 resume requires the original frozen private plan")
        if _get_json(out/PLAN)!=frozen:
            raise ValueError("M4.50 source, code, seed range or frozen protocol changed")
        if any(p.name not in {PLAN,SUMMARY,SHARDS} and ".tmp-" not in p.name
               for p in out.iterdir()):
            raise ValueError("unknown item in M4.50 private output")
        saved=_verified_shards(out,seed_start,seeds,model["model_sha256"])
        if (out/SUMMARY).is_file() and len(saved)!=seeds:
            raise ValueError("completed report lacks complete full-game evidence")
    else:
        if out.exists() and any(out.iterdir()):
            raise ValueError("M4.50 requires a new empty output directory")
        out.mkdir(parents=True,exist_ok=True)
        _write_atomic(out/PLAN,frozen)
        saved={}
    (out/SHARDS).mkdir(exist_ok=True)
    for i in range(seeds):
        if i in saved:
            continue
        case=one_actor_stratified_shuffle(seed_start+i)
        validate_case(case,seed_start+i)
        _write_atomic(_file(out,i),{
            "protocol":SHARD_PROTOCOL,
            "index":i,
            "model_sha256":model["model_sha256"],
            "case_sha256":_paired_digest(case),
            "private_case":case,
        })
    verified=_verified_shards(out,seed_start,seeds,model["model_sha256"])
    if len(verified)!=seeds:
        raise RuntimeError("M4.50 not all 48 original shuffles are fully completed")
    cases=[verified[i] for i in range(seeds)]
    base=safe_actor_strata(cases)
    result={
        **confirm_phase_contrast(cases),
        "actual_natural_challenge_games":base["natural_complete_games"],
        "actual_true_full_terminal_branch_games":base["true_full_terminal_branch_games"],
        "actual_total_complete_paid_games":
            base["natural_complete_games"]+base["true_full_terminal_branch_games"],
        "matched_real_two_world_action_pairs":base["matched_two_world_action_pairs"],
        "true_peng_accepted_pairs":base["actual_peng_accepted_pairs"],
        "overall_all_seed_mean_forced_peng_minus_pass_points":
            base["all_shuffle_mean_peng_minus_pass_points"],
        "official_net_component_means":base["all_shuffle_mean_real_component_deltas"],
        "original_shuffles_positive":base["original_shuffle_positive"],
        "original_shuffles_negative":base["original_shuffle_negative"],
        "original_shuffles_equal":base["original_shuffle_equal"],
        "verified_original_shuffles_reused_after_resume":len(saved),
    }
    if sum(result[k] for k in (
        "original_shuffles_positive","original_shuffles_negative",
        "original_shuffles_equal"
    ))!=seeds:
        raise RuntimeError("M4.50 original-shuffle direction census invalid")
    _write_atomic(out/SUMMARY,result)
    return result
