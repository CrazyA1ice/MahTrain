"""M4.49 first pass/peng actor-only subgroup research, safe old-source proof."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_shadow_headtohead import (
    _paired_digest, _write_atomic, load_frozen_local_model
)
from .ai_pong_pass_branch_rollouts import (
    _aggregate as old_aggregate, _read_verified as old_read,
)
from .ai_pong_pass_replication import (
    PROTOCOL as P448, PLAN as PLAN448, SUMMARY as SUMMARY448,
    PRIVATE_BATCH as BATCH448, SEED_COUNT as N448,
    _prior_provenance as prior_m447_provenance,
    _additional_statistics as m448_stats, _frozen_m447_sha256,
)
from .ai_pong_actor_strata import (
    PROTOCOL, SHARD_PROTOCOL, PLAN, SHARDS, SUMMARY, SEED_COUNT,
    one_actor_stratified_shuffle, validate_case, safe_actor_strata,
)


def _check_previous(*,old:Path,train:Path,model:dict[str,Any],
                    start:int,n:int)->dict[str,str]:
    p=_get_json(old/PLAN448)
    earlier=p.get("private_prior_m447_source")
    old_start=p.get("private_natural_seed_start")
    old_n=p.get("private_original_seed_count")
    if (p.get("protocol")!=P448 or
        p.get("private_model_source")!=str(train) or
        p.get("model_sha256")!=model["model_sha256"] or
        p.get("m447_source_sha256")!=_frozen_m447_sha256() or
        p.get("no_policy_tuning_or_live_promotion") is not True or
        type(earlier) is not str or not earlier or
        type(old_start) is not int or type(old_n) is not int or
        old_n!=N448 or not 0<=old_start<2**32 or
        old_start+old_n>2**32 or
        not (start+n<=old_start or start>=old_start+old_n)):
        raise ValueError("M4.49 seed/model/source overlaps completed M4.48 study")
    earlier_path=_private_location(Path(earlier))
    history=prior_m447_provenance(
        prior=earlier_path,training=train,model=model,start=start,n=n
    )
    if p.get("private_prior_m446_source")!=history["private_m446_source"]:
        raise ValueError("M4.48 historical source path does not reconcile")
    verified=old_read(old/BATCH448,old_start,old_n,model["model_sha256"])
    if len(verified)!=old_n:
        raise ValueError("M4.48 previous paid-game shards not complete")
    cases=[verified[i] for i in range(old_n)]
    original=old_aggregate(cases)
    details=m448_stats(cases)
    report=_get_json(old/SUMMARY448)
    checks={
        "protocol":P448,
        "new_independent_original_shuffle_clusters":old_n,
        "total_true_complete_paid_games":
            original["real_completed_full_games_baseline_plus_branches"],
        "mean_forced_peng_minus_pass_official_net_points":
            original["mean_forced_peng_minus_pass_all_seed_clusters"],
        "original_shuffles_positive":original["seed_level_positive_delta"],
        "original_shuffles_negative":original["seed_level_negative_delta"],
        "original_shuffles_equal":original["seed_level_zero_delta"],
        "branch_pairs_with_actual_peng":
            original["branch_pairs_where_peng_was_actually_claimed"],
        "seed_cluster_bootstrap_mean_delta_percentile_95_exploratory":
            details["seed_cluster_bootstrap_mean_delta_percentile_95_exploratory"],
    }
    if type(report) is not dict or any(report.get(k)!=v for k,v in checks.items()):
        raise ValueError("old M4.48 safe report mismatches verified complete paid games")
    return {"private_previous_m447_source":str(earlier_path)}


def _shard(out:Path,index:int)->Path:
    return out/SHARDS/f"index-{index:08d}.json"


def _read_shards(out:Path,start:int,n:int,digest:str)->dict[int,dict[str,Any]]:
    folder=out/SHARDS
    if not folder.exists():
        return {}
    if not folder.is_dir():
        raise ValueError("invalid M4.49 private original seed folder")
    saved={}
    for p in folder.iterdir():
        if p.is_file() and ".tmp-" in p.name:
            continue
        if (not p.is_file() or len(p.name)!=19 or
            not p.name.startswith("index-") or not p.name.endswith(".json") or
            not p.name[6:14].isdigit()):
            raise ValueError("invalid M4.49 private original seed shard name")
        i=int(p.name[6:14])
        if i>=n or i in saved:
            raise ValueError("duplicate or unexpected original shuffle shard")
        env=_get_json(p)
        if (type(env) is not dict or set(env)!={
            "protocol","index","model_sha256","case_sha256","private_case"
        } or env["protocol"]!=SHARD_PROTOCOL or
            type(env["index"]) is not int or env["index"]!=i or
            env["model_sha256"]!=digest or type(env["private_case"]) is not dict):
            raise ValueError("private M4.49 checksum envelope invalid")
        case=env["private_case"]
        validate_case(case,start+i)
        if env["case_sha256"]!=_paired_digest(case):
            raise ValueError("private M4.49 original shuffle SHA-256 mismatch")
        saved[i]=case
    return saved


def run_actor_strata(
    *,training_dir:Path,prior_m448_dir:Path,seed_start:int,seeds:int,
    out_dir:Path,resume:bool=False
)->dict[str,Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
        type(resume) is not bool or seeds!=SEED_COUNT or
        not 0<=seed_start<2**32 or seed_start+seeds>2**32):
        raise ValueError("M4.49 requires 24 new original shuffle seeds")
    train=_private_location(Path(training_dir))
    old=_private_location(Path(prior_m448_dir))
    out=_private_location(Path(out_dir))
    if (len({train,old,out})!=3 or any(
        a in b.parents or b in a.parents
        for a,b in ((train,old),(train,out),(old,out))
    )):
        raise ValueError("private research inputs and output must not overlap")
    _,model=load_frozen_local_model(train)
    t0=model["source_m434_train_seed_start"]
    t1=model["source_m434_seed_end_exclusive"]
    if not (seed_start+seeds<=t0 or seed_start>=t1):
        raise ValueError("M4.49 seed overlap with original train/holdout")
    validated=_check_previous(
        old=old,train=train,model=model,start=seed_start,n=seeds,
    )
    protocol_source=Path(__file__).with_name("ai_pong_actor_strata.py")
    digest=sha256(protocol_source.read_bytes()+Path(__file__).read_bytes()).hexdigest()
    plan={
        "protocol":PROTOCOL,
        "private_model_source":str(train),
        "private_previous_m448_source":str(old),
        **validated,
        "private_seed_start":seed_start,
        "independent_natural_shuffles":seeds,
        "model_sha256":model["model_sha256"],
        "frozen_actor_strata_source_sha256":digest,
        "two_original_m447_wall_worlds_unchanged":True,
        "only_first_natural_pass_with_peng":True,
        "no_online_change_or_model_fit":True,
    }
    if resume:
        if not out.is_dir() or not (out/PLAN).is_file():
            raise ValueError("resume requires original M4.49 private plan")
        if _get_json(out/PLAN)!=plan:
            raise ValueError("M4.49 original source, seed range or code changed")
        if any(p.name not in {PLAN,SHARDS,SUMMARY}
               and ".tmp-" not in p.name for p in out.iterdir()):
            raise ValueError("unexpected private M4.49 output file")
        saved=_read_shards(out,seed_start,seeds,model["model_sha256"])
        if (out/SUMMARY).is_file() and len(saved)!=seeds:
            raise ValueError("M4.49 safe report lacks completed private shards")
    else:
        if out.exists() and any(out.iterdir()):
            raise ValueError("M4.49 new research output must be empty")
        out.mkdir(parents=True,exist_ok=True)
        _write_atomic(out/PLAN,plan)
        saved={}
    (out/SHARDS).mkdir(exist_ok=True)
    for i in range(seeds):
        if i in saved:
            continue
        case=one_actor_stratified_shuffle(seed_start+i)
        validate_case(case,seed_start+i)
        _write_atomic(_shard(out,i),{
            "protocol":SHARD_PROTOCOL,"index":i,
            "model_sha256":model["model_sha256"],
            "case_sha256":_paired_digest(case),
            "private_case":case,
        })
    final=_read_shards(out,seed_start,seeds,model["model_sha256"])
    if len(final)!=seeds:
        raise RuntimeError("missing a complete original shuffle stratum case")
    safe=safe_actor_strata([final[i] for i in range(seeds)])
    safe["verified_original_shuffle_clusters_reused_on_resume"]=len(saved)
    _write_atomic(out/SUMMARY,safe)
    return safe
