"""M4.35: uncertainty-attenuated OFFLINE study of every lawful discard pair.

This analyses EXISTING M4.34 local per-natural-seed shards without running or
altering any games. We retain every pair's two conditional world net-score
differences, even when opposite-sign. Relative-world gap attenuation is a
heuristic training weight, NOT calibrated confidence, expectation under
unknown concealed opponent hands, nor an unbiased real policy improvement.

Never read holdout labels when constructing model weights. No live AI changes.
"""
from __future__ import annotations

from collections import Counter
from contextlib import ExitStack
import gzip
import json
from math import isfinite
import os
from pathlib import Path
from statistics import mean
import uuid
from typing import Any, Iterator

from .ai_selfplay_counterfactual import FEATURE_NAMES
from .ai_selfplay_local_batch import (
    BatchPlan, _atomic_json, _audit_record, _get_json, _manifest,
    _private_location, _shard,
)
from .ai_selfplay_multicheckpoint import _safe_seed_labels

PROTOCOL="m435_local_conditional_two_world_uncertainty_attenuation_v1"
MAX_WEIGHT=0.2
SCALE_POINTS=1000.0
DISAGREEMENT_PRIOR_POINTS=100.0
MIN_HOLDOUT_SCORED=5


def _finite_number(x: Any) -> bool:
    return type(x) in (int,float) and isfinite(x)


def _case_metrics(item: dict[str,Any]) -> dict[str,Any]:
    # _audit_record and _safe_seed_labels already verified 108 physical
    # tiles, legal authentic terminal payout arms, arithmetic, actor-only
    # features and two matched world IDs before calling this function.
    worlds=item["physical_worlds"]
    if type(worlds) is not list or len(worlds)!=2:
        raise ValueError("requires exactly two paired physical future walls")
    deltas=[
        w["alternative_minus_original"]["official_net"] for w in worlds
    ]
    if any(type(v) is not int for v in deltas):
        raise ValueError("unverified official real payout delta")
    average=mean(deltas)
    gap=abs(deltas[0]-deltas[1])
    # Shrink high-spread, low-mean labels without discarding observations.
    # +100 points regularizes tiny outcomes and prevents 0/0. The 2 walls
    # SHARE the exact hidden opponents, thus do not yield an unbiased
    # variance or a valid frequentist confidence interval.
    reliability=abs(average)/(abs(average)+gap/2+DISAGREEMENT_PRIOR_POINTS)
    target=max(-1.,min(1.,average/SCALE_POINTS))*reliability
    if not (0<=reliability<1.0 and -1<=target<=1):
        raise RuntimeError("invalid bounded conditional research label")
    choice=item["actor_observation"]
    features=choice["features"]
    a=features[choice["alternative"]]
    b=features[choice["baseline"]]
    if (type(a) is not list or type(b) is not list or
            len(a)!=len(FEATURE_NAMES) or len(b)!=len(FEATURE_NAMES) or
            any(not _finite_number(x) for x in a+b)):
        raise ValueError("missing finite authorized actor-only features")
    diff=[x-y for x,y in zip(a,b)]
    signs=(1 if deltas[0]>0 else -1 if deltas[0]<0 else 0,
           1 if deltas[1]>0 else -1 if deltas[1]<0 else 0)
    return {
        "checkpoint_index":item["checkpoint_index"],
        "paired_conditional_deltas":deltas,
        "conditional_mean_net_delta":average,
        "conditional_world_abs_gap":gap,
        "world_signs_agree_nonzero":signs[0]==signs[1] and signs[0]!=0,
        "conditional_mean_nonzero":average!=0,
        "attenuation":reliability,
        "bounded_training_target":target,
        "feature_difference":diff,
        "explicitly_not_population_ev":True,
    }


def _cases(actor: dict[str,Any]) -> list[dict[str,Any]]:
    # Structural and true official complete-game checks.
    _safe_seed_labels(actor)
    return [_case_metrics(item) for item in actor["checkpoints"]]


def _records(plan: BatchPlan,output: Path,start: int,stop: int
             ) -> Iterator[tuple[int,dict[str,Any],list[dict[str,Any]]]]:
    for index in range(start,stop):
        path=_shard(output,index)
        if not path.is_file():
            raise ValueError(f"incomplete natural game shard at index {index}")
        record=_get_json(path)
        _audit_record(record,plan,index)
        yield index,record,_cases(record["actor_private"])


def fit_all_conditional_actions(
    source: Iterator[tuple[int,dict[str,Any],list[dict[str,Any]]]],
    train_clusters: int,
) -> dict[str,Any]:
    """One ORIGINAL shuffled game is at most one equally weighted sample.

    Within a shuffled game, use average checkpoint contribution (not 2x
    importance); across original shuffles with legal checkpoints, each
    contributes equally. Conflicting-sign checkpoints REMAIN in training.
    """
    if type(train_clusters) is not int or train_clusters<1:
        raise ValueError("positive independent train seed count required")
    sums=[0.]*len(FEATURE_NAMES)
    seen=0
    contributing=0
    checkpoints=0
    opposite_or_tied=0
    nonzero_mean=0
    for index,record,cases in source:
        if type(index) is not int or index!=seen or record.get("split")!="train":
            raise ValueError("training seed shards reordered or mixed with holdout")
        seen+=1
        checkpoints+=len(cases)
        opposite_or_tied+=sum(not c["world_signs_agree_nonzero"] for c in cases)
        nonzero_mean+=sum(c["conditional_mean_nonzero"] for c in cases)
        if cases:
            contributing+=1
            for i in range(len(sums)):
                sums[i]+=mean(
                    c["feature_difference"][i]*c["bounded_training_target"]
                    for c in cases
                )
    if seen!=train_clusters:
        raise ValueError("missing train seed cluster")
    if contributing:
        weights=[
            round(max(-MAX_WEIGHT,min(MAX_WEIGHT,s/contributing)),8)
            for s in sums
        ]
    else:
        weights=None
    return {
        "protocol":PROTOCOL,
        "features":list(FEATURE_NAMES),
        "status":("conditional_two_world_offline_diagnostic" if contributing
                  else "no_legal_training_action_points"),
        "train_seed_clusters":seen,
        "train_seed_clusters_with_legal_checkpoints":contributing,
        "all_legal_train_action_points":checkpoints,
        "strict_sign_mixed_or_tied_but_retained":opposite_or_tied,
        "nonzero_mean_train_action_points":nonzero_mean,
        "weights":weights,
        "weight_bound":MAX_WEIGHT,
        "attenuation_prior_points":DISAGREEMENT_PRIOR_POINTS,
        "no_test_labels_used_for_training":True,
        "online_policy_promotion_allowed":False,
        "estimated_population_action_ev":False,
    }


def _blank_counts() -> dict[str,int|float]:
    return {
        "independent_original_shuffle_seeds":0,
        "seeds_with_natural_decision":0,
        "all_natural_legal_actions":0,
        "both_world_signs_strictly_agree":0,
        "world_signs_conflict_or_tie":0,
        "nonzero_two_world_means":0,
        "nonzero_training_targets":0,
        "sum_world_abs_delta_gap_points":0,
        "max_world_abs_delta_gap_points":0,
    }


def _update_counts(counters: dict[str,Any],cases: list[dict[str,Any]]) -> None:
    counters["independent_original_shuffle_seeds"]+=1
    if cases:
        counters["seeds_with_natural_decision"]+=1
    counters["all_natural_legal_actions"]+=len(cases)
    counters["both_world_signs_strictly_agree"]+=sum(
        c["world_signs_agree_nonzero"] for c in cases)
    counters["world_signs_conflict_or_tie"]+=sum(
        not c["world_signs_agree_nonzero"] for c in cases)
    counters["nonzero_two_world_means"]+=sum(
        c["conditional_mean_nonzero"] for c in cases)
    counters["nonzero_training_targets"]+=sum(
        c["bounded_training_target"]!=0 for c in cases)
    counters["sum_world_abs_delta_gap_points"]+=sum(
        c["conditional_world_abs_gap"] for c in cases)
    counters["max_world_abs_delta_gap_points"]=max(
        counters["max_world_abs_delta_gap_points"],
        *(c["conditional_world_abs_gap"] for c in cases),
    )


def _validate_plan(output: Path) -> BatchPlan:
    path=output/"PRIVATE_plan.json"
    if not path.is_file():
        raise ValueError("missing private batch manifest; no guessing or reruns")
    manifest=_get_json(path)
    raw=manifest.get("private_reproduction_plan")
    if type(raw) is not dict:
        raise ValueError("missing sealed original M4.34 plan")
    if (set(raw)!={"protocol","source_protocol","seed_start",
                   "train_seeds","holdout_seeds","max_checkpoints",
                   "independence_unit","online_policy_changed"}):
        raise ValueError("unrecognized local private plan structure")
    plan=BatchPlan(raw["seed_start"],raw["train_seeds"],
                   raw["holdout_seeds"],raw["max_checkpoints"])
    if manifest!=_manifest(plan):
        raise ValueError("private batch plan fingerprint mismatch")
    return plan


def analyze_saved_local_batch(outdir: Path) -> dict[str,Any]:
    """No new games. Reuse the exact local shards already simulated.

    Stores the model and per-heldout-decision private report in the SAME
    gitignored private output folder. Only whitelist-safe aggregate is
    separately publishable.
    """
    output=_private_location(Path(outdir))
    plan=_validate_plan(output)
    # Validate EVERY shard before writing any fitted result.
    for _ in _records(plan,output,0,plan.total):
        pass
    model=fit_all_conditional_actions(
        _records(plan,output,0,plan.train_seeds),plan.train_seeds
    )
    if model["train_seed_clusters"]!=plan.train_seeds:
        raise ValueError("trained with wrong independent seed split")
    weights=model["weights"]
    train=_blank_counts()
    holdout=_blank_counts()
    n_scored=0
    n_correct=0
    n_abstain=0
    diagnostic=output/"PRIVATE_uncertainty_holdout_diagnostics.jsonl.gz"
    temp=diagnostic.with_name(diagnostic.name+".incomplete-"+uuid.uuid4().hex)
    try:
        with gzip.open(temp,"wt",encoding="utf8") as dest:
            for split,start,stop in (
                ("train",0,plan.train_seeds),
                ("holdout",plan.train_seeds,plan.total),
            ):
                counters=train if split=="train" else holdout
                for index,record,cases in _records(plan,output,start,stop):
                    _update_counts(counters,cases)
                    if split=="holdout":
                        rows=[]
                        for c in cases:
                            margin=(sum(
                                a*w for a,w in zip(
                                    c["feature_difference"],weights)
                            ) if weights is not None else 0.)
                            # A zero conditional mean has no signed direction;
                            # retain it in coverage and explicitly abstain.
                            scored=(margin!=0 and
                                    c["conditional_mean_nonzero"])
                            if scored:
                                n_scored+=1
                                n_correct+=int(
                                    (margin>0)==
                                    (c["conditional_mean_net_delta"]>0)
                                )
                            else:
                                n_abstain+=1
                            rows.append({
                                "checkpoint_index":c["checkpoint_index"],
                                "paired_conditional_deltas":
                                    c["paired_conditional_deltas"],
                                "conditional_mean_net_delta":
                                    c["conditional_mean_net_delta"],
                                "conditional_world_abs_gap":
                                    c["conditional_world_abs_gap"],
                                "attenuation":c["attenuation"],
                                "model_score_margin":margin,
                                "model_abstained":not scored,
                                "direction_agrees_if_scored":(
                                    ((margin>0)==(
                                        c["conditional_mean_net_delta"]>0))
                                    if scored else None),
                                "not_actual_playing_policy_eval":True,
                            })
                        dest.write(json.dumps({
                            "private_local_index":index,
                            "private_original_shuffle_seed":
                                record["private_shuffle_seed"],
                            "original_natural_game_is_independence_unit":True,
                            "decisions":rows,
                        },allow_nan=False,ensure_ascii=False)+"\n")
        os.replace(temp,diagnostic)
    finally:
        temp.unlink(missing_ok=True)
    # Publish only aggregate GROUP counts and summary direction scores.
    if n_scored>holdout["all_natural_legal_actions"]:
        raise RuntimeError("invalid heldout denominator")
    for counts,required in ((train,plan.train_seeds),
                            (holdout,plan.holdout_seeds)):
        if (counts["independent_original_shuffle_seeds"]!=required or
                counts["all_natural_legal_actions"]!=
                    counts["both_world_signs_strictly_agree"]+
                    counts["world_signs_conflict_or_tie"]):
            raise RuntimeError("lost naturally sampled decision point")
    accuracy=round(n_correct/n_scored,5) if n_scored>=MIN_HOLDOUT_SCORED else None
    summary={
        "protocol":PROTOCOL,
        "source_batch_protocol":"m434_local_resumable_independent_seed_clusters_v1",
        "original_natural_seed_clusters":plan.total,
        "train":train,"holdout":holdout,
        "all_natural_legal_actions_retained":
            train["all_natural_legal_actions"]+
            holdout["all_natural_legal_actions"],
        "new_offline_train_points":
            model["all_legal_train_action_points"],
        "train_points_excluded_due_to_world_sign_disagreement":0,
        "train_conditional_mean_near_zero_included":True,
        "heldout_scored_directions":n_scored,
        "heldout_correct_conditional_mean_directions":n_correct,
        "heldout_abstained_directions":n_abstain,
        "heldout_direction_accuracy_if_at_least_five":accuracy,
        "heldout_accuracy_status":(
            "exploratory_conditional_only_not_policy_strength"
            if accuracy is not None else
            "insufficient_scored_conditional_decisions"),
        "only_two_conditional_wall_permutations":True,
        "hidden_opponent_hands_fixed_across_worlds":True,
        "wall_permutations_are_correlated_with_same_initial_shuffle":True,
        "heuristic_attenuation_not_calibrated_uncertainty":True,
        "population_effect_or_q_value_established":False,
        "online_ai_modified":False,
        "actual_live_head_to_head_benchmark_completed":False,
        "private_seed_or_hand_values_in_safe_summary":False,
    }
    # Committing private and public aggregates with atomic single-file saves.
    # Exported safe summary uses whitelist values; no raw private actions.
    _atomic_json(output/"PRIVATE_uncertainty_offline_model.json",model)
    _atomic_json(output/"safe_uncertainty_summary.json",summary)
    return summary
