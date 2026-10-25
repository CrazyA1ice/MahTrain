"""M4.38: forensic, read-only analysis of SAVED M4.37 official match pairs.

Reuse existing five fully paid games per original natural shuffle; do NOT
rerun outcomes or peek at concealed tiles. Eight seat comparisons from two
shuffle seeds are NOT eight independent observations. Attribution here is
accounting decomposition (win/kong/exhaustive), NOT causal credit for a cut.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
from pathlib import Path
from statistics import mean
from typing import Any
import uuid

from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_shadow_headtohead import (
    PROTOCOL as MATCH_PROTOCOL, SHARD_PROTOCOL, MAX_EVAL_SEEDS,
    _resume_cases, _write_atomic,
)

PROTOCOL="m438_saved_shadow_loss_accounting_audit_v1"
COMPONENTS={
    "win":"real_win_delta",
    "kong":"real_kong_delta",
    "exhaustive":"real_exhaustive_delta",
}
CSV_FIELDS=(
    "private_shuffle_seed","seat","challenge_baseline_official_net",
    "shadow_official_net","delta_shadow_minus_challenge",
    "shadow_discard_decisions","shadow_override_count",
    "real_win_delta","real_kong_delta","real_exhaustive_delta",
    "candidate_better_than_baseline",
)
PRIVACY_KEYS=("private_shuffle_seed","hand","future_wall","opponent_hand",
              "private_case","model_sha256","training_directory")


def _verified_plan(folder:Path) -> tuple[dict[str,Any],int,int,str]:
    plan=_get_json(folder/"PRIVATE_frozen_benchmark_plan.json")
    seed=plan.get("private_evaluation_seed_start")
    n=plan.get("private_eval_original_shuffle_count")
    digest=plan.get("private_frozen_model_sha256")
    if (plan.get("protocol")!=MATCH_PROTOCOL or
            plan.get("resumable_shards_protocol")!=SHARD_PROTOCOL or
            plan.get("training_from_original_only") is not True or
            plan.get("online_policy_unchanged") is not True or
            type(seed) is not int or type(n) is not int or
            not 0<=seed<2**32 or not 1<=n<=MAX_EVAL_SEEDS or
            seed+n>2**32 or type(digest) is not str or len(digest)!=64 or
            any(ch not in "0123456789abcdef" for ch in digest)):
        raise ValueError("requires a complete M4.37 original frozen evaluation plan")
    return plan,seed,n,digest


def _read_and_verify(evaluation:Path) -> tuple[list[dict[str,Any]],dict[str,Any]]:
    """Validate every shard, the historical compressed copy and safe summary."""
    _,start,n,model_digest=_verified_plan(evaluation)
    shards=_resume_cases(evaluation,n,start,model_digest)
    if len(shards)!=n:
        raise ValueError("evaluation incomplete: all original seed shards required")
    games=[shards[index] for index in range(n)]
    path=evaluation/"PRIVATE_four_seat_paired_matches.jsonl.gz"
    if not path.is_file():
        raise ValueError("missing complete M4.37 compressed private outcome ledger")
    with gzip.open(path,"rt",encoding="utf8") as f:
        stored=[json.loads(line) for line in f if line.strip()]
    if stored!=games:
        raise ValueError("compressed paid match record differs from audited shards")
    safe=_get_json(evaluation/"safe_four_seat_shadow_summary.json")
    rows=[row for g in games for row in g["seat_rotation_results"]]
    count=sum(r["shadow_override_count"] for r in rows)
    opportunities=sum(r["shadow_discard_decisions"] for r in rows)
    per_seat=[
        round(mean(g["seat_rotation_results"][s][
            "delta_shadow_minus_challenge"] for g in games),5)
        for s in range(4)
    ]
    by_seed=[
        mean(r["delta_shadow_minus_challenge"] for r in g["seat_rotation_results"])
        for g in games
    ]
    if (safe.get("protocol")!=MATCH_PROTOCOL or
            safe.get("official_score_ledger_reconciled") is not True or
            safe.get("no_change_to_online_ai") is not True or
            safe.get("trained_on_only_original_training_split") is not True or
            safe.get("evaluation_shuffles_disjoint_from_train_and_original_holdout") is not True or
            safe.get("actual_real_complete_games")!=5*n or
            safe.get("baseline_games")!=n or
            safe.get("experimental_shadow_games")!=4*n or
            safe.get("independent_initial_shuffle_seed_clusters")!=n or
            safe.get("interruption_safe_completed_seed_shards")!=n or
            safe.get("candidate_discard_opportunities")!=opportunities or
            safe.get("candidate_legal_minimum_shanten_overrides")!=count or
            safe.get("per_seat_conditional_net_delta_means")!=per_seat or
            safe.get("seat_rotated_seed_cluster_mean_delta_points")!=round(mean(by_seed),5) or
            safe.get("seed_clusters_with_positive_rotated_mean")!=sum(v>0 for v in by_seed) or
            safe.get("seed_clusters_with_negative_rotated_mean")!=sum(v<0 for v in by_seed) or
            safe.get("seed_clusters_with_zero_rotated_mean")!=sum(v==0 for v in by_seed)):
        raise ValueError("original safe summary cannot be reconciled to private games")
    return games,safe


def _write_private_csv(path:Path,rows:list[dict[str,Any]],
                       fields:tuple[str,...]) -> None:
    temp=path.with_name(path.name+".tmp-"+uuid.uuid4().hex)
    try:
        with temp.open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=fields,extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


def audit_saved_shadow_results(*,evaluation_dir:Path,
                               report_dir:Path) -> dict[str,Any]:
    """Read a completed private M4.37 batch; never fit weights/run matches."""
    evaluation=_private_location(Path(evaluation_dir))
    report=_private_location(Path(report_dir))
    if evaluation==report or evaluation in report.parents or report in evaluation.parents:
        raise ValueError("audit outputs must be outside the input evaluation tree")
    if report.exists() and any(report.iterdir()):
        raise ValueError("new audit directory required: do not overwrite old evidence")
    games,original=_read_and_verify(evaluation)  # full audit before any writes
    by_seat=[[] for _ in range(4)]
    detailed=[]
    clusters=[]
    for g in games:
        seed=g["private_evaluation_shuffle_seed"]
        one=[]
        for row in g["seat_rotation_results"]:
            delta=row["delta_shadow_minus_challenge"]
            r={
                "private_shuffle_seed":seed,
                "seat":row["seat"],
                **{k:row[k] for k in CSV_FIELDS
                   if k not in ("private_shuffle_seed","seat",
                                "candidate_better_than_baseline")},
                "candidate_better_than_baseline":int(delta>0),
            }
            detailed.append(r)
            by_seat[row["seat"]].append(r)
            one.append(r)
        clusters.append({
            "private_shuffle_seed":seed,
            "four_seat_mean_net_delta":mean(
                r["delta_shadow_minus_challenge"] for r in one),
            "four_seat_total_overrides":sum(
                r["shadow_override_count"] for r in one),
            "four_seat_mean_win_delta":mean(r["real_win_delta"] for r in one),
            "four_seat_mean_kong_delta":mean(r["real_kong_delta"] for r in one),
            "four_seat_mean_exhaustive_delta":mean(
                r["real_exhaustive_delta"] for r in one),
        })
    n=len(clusters)
    def per_cluster(key:str) -> float:
        return round(mean(
            mean(r[key] for r in by_seed_rows) for by_seed_rows in (
                detailed[i*4:(i+1)*4] for i in range(n)
            )
        ),5)
    component_mean={
        label:per_cluster(field) for label,field in COMPONENTS.items()
    }
    net=per_cluster("delta_shadow_minus_challenge")
    if abs(sum(component_mean.values())-net)>0.00002:
        raise RuntimeError("component ledger decomposition is not reconciled")
    positive=sum(c["four_seat_mean_net_delta"]>0 for c in clusters)
    negative=sum(c["four_seat_mean_net_delta"]<0 for c in clusters)
    zero=n-positive-negative
    safe={
        "protocol":PROTOCOL,
        "source_protocol":MATCH_PROTOCOL,
        "original_shuffle_seed_clusters":n,
        "total_complete_authoritative_games":5*n,
        "correlated_rotated_seat_comparisons":4*n,
        "paired_mean_official_net_delta_points":net,
        "paid_net_delta_accounting_by_component_points":component_mean,
        "paired_delta_by_seat_points":[
            round(mean(r["delta_shadow_minus_challenge"] for r in items),5)
            for items in by_seat
        ],
        "per_seat_negative_comparison_counts":[
            sum(r["delta_shadow_minus_challenge"]<0 for r in items)
            for items in by_seat
        ],
        "per_seat_positive_comparison_counts":[
            sum(r["delta_shadow_minus_challenge"]>0 for r in items)
            for items in by_seat
        ],
        "per_seat_zero_comparison_counts":[
            sum(r["delta_shadow_minus_challenge"]==0 for r in items)
            for items in by_seat
        ],
        "seed_clusters_positive":positive,
        "seed_clusters_negative":negative,
        "seed_clusters_tied":zero,
        "observed_discard_opportunities":
            sum(r["shadow_discard_decisions"] for r in detailed),
        "observed_actual_overrides":
            sum(r["shadow_override_count"] for r in detailed),
        "paired_rotations_with_overrides":
            sum(r["shadow_override_count"]>0 for r in detailed),
        "paired_rotations_without_overrides":
            sum(r["shadow_override_count"]==0 for r in detailed),
        "negative_rotations_with_overrides":
            sum(r["shadow_override_count"]>0 and
                r["delta_shadow_minus_challenge"]<0 for r in detailed),
        "zero_override_rotations_with_nonzero_delta":
            sum(r["shadow_override_count"]==0 and
                r["delta_shadow_minus_challenge"]!=0 for r in detailed),
        "private_rows_available_locally":len(detailed),
        "read_only_existing_m437_games":True,
        "no_replay_or_retraining":True,
        "online_challenge_unchanged":True,
        "no_action_level_causal_attribution":True,
        "no_independent_seat_replication_claim":True,
        "too_few_shuffles_for_exploratory_comparison":n<20,
        "not_evidence_of_population_policy_improvement":True,
        "seed_ids_and_training_weights_redacted":True,
    }
    if (safe["observed_actual_overrides"]!=original[
            "candidate_legal_minimum_shanten_overrides"] or
            safe["observed_discard_opportunities"]!=original[
            "candidate_discard_opportunities"] or
            safe["paired_mean_official_net_delta_points"]!=original[
            "seat_rotated_seed_cluster_mean_delta_points"]):
        raise RuntimeError("M4.38 aggregates differ from source M4.37")
    serialized=json.dumps(safe,ensure_ascii=False,allow_nan=False)
    if any(k in serialized for k in PRIVACY_KEYS):
        raise RuntimeError("private names leaked into whitelisted aggregate")
    report.mkdir(parents=True,exist_ok=True)
    _write_private_csv(report/"PRIVATE_seat_rotations.csv",detailed,CSV_FIELDS)
    _write_private_csv(report/"PRIVATE_seed_cluster_totals.csv",clusters,(
        "private_shuffle_seed","four_seat_mean_net_delta",
        "four_seat_total_overrides","four_seat_mean_win_delta",
        "four_seat_mean_kong_delta","four_seat_mean_exhaustive_delta",
    ))
    _write_atomic(report/"safe_shadow_loss_attribution_summary.json",safe)
    return safe
