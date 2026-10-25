"""M4.40: verify the ACTUAL frozen model's score direction on M4.39 cuts.

Read fully completed M4.39 private actor-only traces and refit the original
M4.35 model from TRAIN shards. Recover each positive model margin by exactly
recomputing the THREE recorded legal own-view features, then decompose score
into per-feature contributions. No retraining, replay, or weight adjustment.

This is a historical *score accounting* audit, not a causal explanation of
terminal payouts or a new policy validation.
"""
from __future__ import annotations

import json
from math import isclose, isfinite
from pathlib import Path
from statistics import mean
from typing import Any

from .ai_selfplay_counterfactual import FEATURE_NAMES
from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_shadow_action_diagnostics import (
    MANIFEST as M439_MANIFEST, PROTOCOL as M439_PROTOCOL,
    SUMMARY as M439_SUMMARY, _aggregate, _read_saved,
)
from .ai_shadow_headtohead import (
    MAX_EVAL_SEEDS, _write_atomic, load_frozen_local_model,
)

PROTOCOL="m440_verified_frozen_actor_score_geometry_v1"
SUMMARY="safe_frozen_score_geometry.json"
PRIOR_POINTS="M4.39 preserved full actor-only trace and frozen model"
FEATURE_LABELS=(
    "effective_tile_count",
    "next_draw_probability",
    "effective_tile_types",
)


def _vec(step:dict[str,Any],prefix:str)->tuple[float,float,float]:
    count=step[prefix+"_effective_tile_count"]
    probability=step[prefix+"_next_draw_probability"]
    types=step[prefix+"_effective_types_count"]
    if (type(count) is not int or not 0<=count<=108 or
            type(types) is not int or not 0<=types<=27 or
            type(probability) not in (int,float) or
            not isfinite(probability) or not 0<=probability<=1):
        raise ValueError("invalid saved actor-observable feature data")
    return (
        round(count/40,7),
        round(float(probability),7),
        round(types/27,7),
    )


def _audit_margins(cases:list[dict[str,Any]],
                   weights:tuple[float,...]|None)->dict[str,Any]:
    if weights is not None and len(weights)!=len(FEATURE_NAMES):
        raise ValueError("frozen weights do not match original three features")
    w=weights if weights is not None else (0.,)*len(FEATURE_NAMES)
    if len(FEATURE_LABELS)!=len(w):
        raise ValueError("feature accounting dimension mismatch")
    rows=[]
    checked_nonoverrides=0
    for case in cases:
        for seat in case["seat_rotation_results"]:
            for action in seat["private_actor_discard_trace"]:
                if not action["overrode"]:
                    checked_nonoverrides+=1
                    continue
                base=_vec(action,"baseline")
                chosen=_vec(action,"chosen")
                components=tuple(
                    weight*(x-b) for weight,x,b in zip(w,chosen,base)
                )
                score=sum(components)
                stored=action["model_margin"]
                # M4.39 features and scores were already rounded to the
                # exact seven decimals of _candidate_features in M4.35.
                if (type(stored) not in (int,float) or
                        not isfinite(stored) or score<=1e-9 or
                        not isclose(score,stored,rel_tol=1e-7,abs_tol=1e-8)):
                    raise ValueError("saved override margin does not match original frozen model")
                rows.append((action,components))
    counts=[]
    mean_points=[]
    for feature_index in range(len(w)):
        contributions=[parts[feature_index] for _,parts in rows]
        counts.append({
            "positive":sum(p>0 for p in contributions),
            "negative":sum(p<0 for p in contributions),
            "zero":sum(p==0 for p in contributions),
        })
        mean_points.append(round(mean(contributions),9)
                           if contributions else 0.)
    decreases=sum(a["chosen_effective_tile_count"]<
                  a["baseline_effective_tile_count"] for a,_ in rows)
    tied=sum(a["chosen_effective_tile_count"]==
             a["baseline_effective_tile_count"] for a,_ in rows)
    increases=len(rows)-decreases-tied
    return {
        "overrides_verified_against_exact_frozen_weights":len(rows),
        "baseline_kept_decisions":checked_nonoverrides,
        "cut_effective_tile_count_decreased":decreases,
        "cut_effective_tile_count_equal":tied,
        "cut_effective_tile_count_increased":increases,
        "frozen_weight_signs_only":{
            label:("positive" if weight>0 else
                   "negative" if weight<0 else "zero")
            for label,weight in zip(FEATURE_LABELS,w)
        },
        "positive_negative_zero_feature_contributions":{
            label:counts[i] for i,label in enumerate(FEATURE_LABELS)
        },
        "mean_model_margin_component_on_override":{
            label:mean_points[i] for i,label in enumerate(FEATURE_LABELS)
        },
        "mean_verified_model_margin":(
            round(mean(sum(parts) for _,parts in rows),9) if rows else 0.
        ),
        "would_abstain_if_effective_tile_count_must_not_decrease":
            decreases,
        "would_still_be_eligible_under_non_decrease_guard":
            increases+tied,
        "zero_override_expected_if_guard_blocks_all_recorded_cuts":
            bool(rows) and decreases==len(rows),
        "no_causal_terminal_score_claim":True,
    }


def audit_frozen_score_geometry(
    *,training_dir:Path,actor_evaluation_dir:Path,report_dir:Path
) -> dict[str,Any]:
    train=_private_location(Path(training_dir))
    evaluation=_private_location(Path(actor_evaluation_dir))
    output=_private_location(Path(report_dir))
    if (len({train,evaluation,output})!=3 or
            train in output.parents or evaluation in output.parents or
            output in evaluation.parents):
        raise ValueError("score audit output must be separate from private input trees")
    if output.exists() and any(output.iterdir()):
        raise ValueError("score audit report directory must be new or empty")

    # Refit and verify ONLY the M4.34 original TRAIN shards, not M4.39
    # evaluation outcomes. Hash and plan are immutable comparison guards.
    weights,provenance=load_frozen_local_model(train)
    manifest=_get_json(evaluation/M439_MANIFEST)
    first=manifest.get("private_eval_seed_start")
    clusters=manifest.get("private_eval_seed_count")
    if (manifest.get("protocol")!=M439_PROTOCOL or
            manifest.get("online_policy_changed") is not False or
            manifest.get("private_source_training_directory")!=str(train) or
            manifest.get("private_frozen_model_sha256")!=provenance["model_sha256"] or
            type(first) is not int or type(clusters) is not int or
            not 0<=first<2**32 or not 1<=clusters<=MAX_EVAL_SEEDS or
            first+clusters>2**32):
        raise ValueError("M4.39 diagnostic plan/model mismatch")
    saved=_read_saved(evaluation,clusters,first,provenance["model_sha256"])
    if len(saved)!=clusters:
        raise ValueError("incomplete saved M4.39 original seed clusters")
    cases=[saved[i] for i in range(clusters)]
    original=_get_json(evaluation/M439_SUMMARY)
    expected=_aggregate(cases)
    if any(original.get(key)!=value for key,value in expected.items()):
        raise ValueError("M4.39 safe summary no longer matches audited paid games")
    scores=_audit_margins(cases,weights)
    if (scores["overrides_verified_against_exact_frozen_weights"]!=
            original["actual_model_override_count"] or
            scores["baseline_kept_decisions"]!=original["baseline_kept_discard_count"] or
            scores["cut_effective_tile_count_decreased"]!=
                original["actor_visible_effective_tile_count_lower_on_override"] or
            scores["cut_effective_tile_count_equal"]!=
                original["actor_visible_effective_tile_count_tied_on_override"] or
            scores["cut_effective_tile_count_increased"]!=
                original["actor_visible_effective_tile_count_higher_on_override"]):
        raise ValueError("saved actor-observable decision totals do not reconcile")
    public={
        "protocol":PROTOCOL,
        "source_protocol":M439_PROTOCOL,
        "original_independent_shuffle_seed_clusters":clusters,
        "real_finished_games_already_reused":5*clusters,
        "no_new_matches":True,
        "no_model_retraining_or_weight_edits":True,
        "no_live_challenge_policy_changes":True,
        "weights_are_recomputed_from_original_training_split_only":True,
        "features":list(FEATURE_LABELS),
        **scores,
        "source_paired_mean_official_net_delta_points":
            original["paired_mean_official_net_delta_points"],
        "source_score_comparison_is_not_action_causal_attribution":True,
        "no_statistical_significance_or_population_strength_claim":True,
        "raw_frozen_weights_hidden":True,
        "specific_tile_choices_and_original_seed_ids_hidden":True,
    }
    text=json.dumps(public,ensure_ascii=False,sort_keys=True,allow_nan=False)
    for forbidden in ("private_actor_discard_trace",'"hand":',
                      "private_shuffle_seed","private_eval_seed_start",
                      "private_frozen_model_sha256"):
        if forbidden in text:
            raise RuntimeError("unsafe data in intended public aggregate")
    output.mkdir(parents=True,exist_ok=True)
    _write_atomic(output/SUMMARY,public)
    return public
