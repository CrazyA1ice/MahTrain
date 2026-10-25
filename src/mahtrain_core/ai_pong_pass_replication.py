"""M4.48: locked M4.47 first-natural-pass/peng matched-branch replication.

Twenty-four fresh independently shuffled complete four-player Challenge games,
plus 2 worlds * 2 authentic terminal actions for the first eligible call.
No policy fitted/promoted. Previous M4.47 outcomes are verified but NEVER
pooled into the new estimate or used to modify the branch selection rule.
"""
from __future__ import annotations

import hashlib
import inspect
from pathlib import Path
from random import Random
from statistics import mean, median
from typing import Any

from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_shadow_headtohead import _paired_digest, _write_atomic, load_frozen_local_model
from .ai_pong_pass_branch_rollouts import (
    PROTOCOL as PRIOR_PROTOCOL, PLAN as PRIOR_PLAN,
    SUMMARY as PRIOR_SUMMARY, SHARD_DIR as PRIOR_SHARD_DIR,
    SHARD_PROTOCOL as PRIOR_SHARD_PROTOCOL, WORLDS, SEED_COUNT as OLD_COUNT,
    CHECKPOINTS_PER_SHUFFLE, _aggregate as original_aggregate,
    _read_verified, _private_shard, _source_plan_and_exclusion,
    _validate_case, one_natural_shuffle,
)

PROTOCOL="m448_locked_m447_first_pass_peng_new_24_shuffle_replication_v1"
PLAN="PRIVATE_m448_precommitted_24_shuffle_plan.json"
SUMMARY="safe_pong_pass_replication.json"
PRIVATE_BATCH="PRIVATE_m448_original_shuffle_branch_checkpoints"
SEED_COUNT=24
BOOTSTRAPS=4096
BOOTSTRAP_SEED=448


def _frozen_m447_sha256()->str:
    return hashlib.sha256(
        Path(inspect.getfile(one_natural_shuffle)).read_bytes()
    ).hexdigest()


def _prior_provenance(
    *,prior:Path,training:Path,model:dict[str,Any],start:int,n:int
)->dict[str,Any]:
    old=_get_json(prior/PRIOR_PLAN)
    previous_start=old.get("private_natural_shuffle_start")
    previous_n=old.get("private_independent_shuffle_count")
    m446=old.get("private_m446_source")
    sha=model["model_sha256"]
    if (old.get("protocol")!=PRIOR_PROTOCOL or
        old.get("private_model_source")!=str(training) or
        old.get("model_sha256_provenance_only")!=sha or
        old.get("frozen_m447_protocol_source_sha256")!=_frozen_m447_sha256() or
        old.get("no_new_policy_or_refit") is not True or
        old.get("worlds")!=list(WORLDS) or
        old.get("max_first_checkpoints_per_shuffle")!=CHECKPOINTS_PER_SHUFFLE or
        type(previous_start) is not int or type(previous_n) is not int or
        previous_n!=OLD_COUNT or
        not 0<=previous_start<2**32 or previous_start+previous_n>2**32 or
        not (start+n<=previous_start or start>=previous_start+previous_n) or
        type(m446) is not str or not m446):
        raise ValueError("M4.48 prior M4.47 model, source or seed overlap invalid")
    m446_path=_private_location(Path(m446))
    source=_source_plan_and_exclusion(
        train=training,prior=m446_path,model=model,start=start,n=n,
    )
    if (old.get("private_m444_source")!=source["private_m444_source"] or
        old.get("private_m445_source")!=source["private_m445_source"]):
        raise ValueError("M4.47 recorded earlier source paths do not match")
    recorded=_read_verified(prior,previous_start,previous_n,sha)
    if len(recorded)!=previous_n:
        raise ValueError("previous eight original M4.47 shuffles incomplete")
    recomputed=original_aggregate(
        [recorded[i] for i in range(previous_n)]
    )
    published=_get_json(prior/PRIOR_SUMMARY)
    if (type(published) is not dict or
        any(published.get(k)!=v for k,v in recomputed.items()) or
        type(published.get("verified_original_seed_shards_reused_on_resume")) is not int or
        not 0<=published["verified_original_seed_shards_reused_on_resume"]<=previous_n):
        raise ValueError("M4.47 uploaded safe result disagrees with paid branch shards")
    return {
        "private_m446_source":str(m446_path),
        "private_previous_m447_start":previous_start,
        "private_previous_m447_clusters":previous_n,
    }


def _percentile(sorted_values:list[float],percent:float)->float:
    # Linear-interpolated empirical percentile; deterministic no dependencies.
    at=(len(sorted_values)-1)*percent
    lower=int(at)
    fraction=at-lower
    if fraction==0:
        return sorted_values[lower]
    return sorted_values[lower]*(1-fraction)+sorted_values[lower+1]*fraction


def _additional_statistics(cases:list[dict[str,Any]])->dict[str,Any]:
    if len(cases)!=SEED_COUNT:
        raise ValueError("M4.48 requires complete independent replication clusters")
    cluster_means=[]
    first_world=[]
    second_world=[]
    positive=negative=equal=0
    between_world_sign_disagreement=0
    between_world_sign_agreement=0
    first_seat_counts=[0]*4
    covered=[]
    for case in cases:
        rows=case["private_matched_branches"]
        assert len(rows) in (0,2)
        if rows:
            if (rows[0]["world"],rows[1]["world"])!=WORLDS:
                raise ValueError("matched future wall order changed")
            seat=case["private_first_actor_seat"]
            first_seat_counts[seat]+=1
            a=rows[0]["official_actor_net_delta"]
            b=rows[1]["official_actor_net_delta"]
            average=(a+b)/2
            covered.append(average)
            sgna=(a>0)-(a<0)
            sgnb=(b>0)-(b<0)
            between_world_sign_disagreement+=int(sgna!=sgnb)
            between_world_sign_agreement+=int(sgna==sgnb)
        else:
            a=b=average=0
        cluster_means.append(average)
        first_world.append(a)
        second_world.append(b)
        positive+=int(average>0)
        negative+=int(average<0)
        equal+=int(average==0)

    rng=Random(BOOTSTRAP_SEED)
    resample_means=[]
    for _ in range(BOOTSTRAPS):
        resample_means.append(mean(
            cluster_means[rng.randrange(SEED_COUNT)]
            for _ in range(SEED_COUNT)
        ))
    resample_means.sort()
    return {
        "independent_cluster_median_net_delta":round(median(cluster_means),5),
        "mean_world0_net_delta_across_all_original_shuffles":
            round(mean(first_world),5),
        "mean_world1_net_delta_across_all_original_shuffles":
            round(mean(second_world),5),
        "covered_shuffles_world0_world1_sign_agree":between_world_sign_agreement,
        "covered_shuffles_world0_world1_sign_disagree":
            between_world_sign_disagreement,
        "first_eligible_actor_seat_histogram":first_seat_counts,
        "covered_clusters_mean_net_delta_descriptive_only":
            round(mean(covered),5) if covered else None,
        "seed_cluster_bootstrap_resamples":BOOTSTRAPS,
        "seed_cluster_bootstrap_mean_delta_percentile_95_exploratory":[
            round(_percentile(resample_means,.025),5),
            round(_percentile(resample_means,.975),5),
        ],
        "bootstrap_is_descriptive_not_inference_about_all_possible_walls":True,
        "bootstrap_samples_original_shuffles_not_branch_games":True,
        "bootstrap_random_seed_fixed_before_new_outcomes":True,
    }


