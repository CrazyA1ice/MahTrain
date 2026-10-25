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


