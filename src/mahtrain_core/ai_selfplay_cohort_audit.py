"""M4.33 audited multi-seed self-play cohort: honest coverage before promotion.

This is NOT a new playing policy. Run M4.32 on a prespecified group of
independent natural shuffles; audit every real legal terminal score, verify
that training and holdout seed CLUSTERS are disjoint, and export aggregate
coverage without actor-private tiles or original random seeds.

2 paired unknown-wall orders per action point are conditional worlds, NOT
independent real games. Label quality can be too low for model evaluation.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
from typing import Any, Mapping

from .ai_selfplay_learning import _assert_public
from .ai_selfplay_multicheckpoint import (
    PROTOCOL as SOURCE_PROTOCOL, MODEL_PROTOCOL, LEDGER_COMPONENTS,
    _safe_seed_labels, _validate, run_study,
)

PROTOCOL = "m433_independent_selfplay_shuffle_cohort_audit_v1"
SPLITS = ("train", "holdout")
SIGN_CLASSES = (
    "alternative_better_in_all_test_worlds",
    "original_better_in_all_test_worlds",
    "mixed_or_tied_world_outcomes",
)
ALL_COMPONENTS = ("official_net", *LEDGER_COMPONENTS)


def _check_private_cluster(cluster: Mapping[str, Any], expected_seed: int,
                           *, quota: int) -> dict[str, Any]:
    if (type(cluster) is not dict or
            type(cluster.get("private_shuffle_seed")) is not int or
            cluster["private_shuffle_seed"] != expected_seed or
            cluster.get("original_natural_games") != 1 or
            cluster.get("actor_only_observations") is not True or
            type(cluster.get("captured_decisions")) is not int or
            not 0 <= cluster["captured_decisions"] <= quota or
            type(cluster.get("conditional_rollout_games")) is not int or
            cluster["conditional_rollout_games"] !=
            4 * cluster["captured_decisions"]):
        raise ValueError("private original shuffle cluster missing or altered")
    # Full audit: each arm really finished, 108 tiles, zero-sum official
    # components; all deltas exactly reconcile and two worlds agree on view.
    eligible = _safe_seed_labels(cluster)
    checkpoint_rows = cluster["checkpoints"]
    signs = Counter(x["two_world_sign_consensus"] for x in checkpoint_rows)
    if any(k not in SIGN_CLASSES for k in signs):
        raise ValueError("unregistered outcome label")
    if sum(signs.values()) != cluster["captured_decisions"]:
        raise ValueError("invalid natural decision count")
    if len(eligible) != sum(signs[k] for k in SIGN_CLASSES[:2]):
        raise ValueError("strict two-world label counts changed")
    # Classify actual settlement mechanism deltas: no causal attribution.
    nonzero_components = {
        field: sum(
            x["alternative_minus_original"][field] != 0
            for row in checkpoint_rows for x in row["physical_worlds"]
        )
        for field in ALL_COMPONENTS
    }
    # Two futures × two first actions are correlated with the SAME natural
    # initial shuffle. Only the seed contributes an independent unit.
    return {
        "natural_decisions":len(checkpoint_rows),
        "terminal_counterfactual_games":cluster["conditional_rollout_games"],
        "strict_consensus_labels":len(eligible),
        "direction_counts":{k:signs[k] for k in SIGN_CLASSES},
        "nonzero_paired_component_counts":nonzero_components,
    }


def _aggregate_split(clusters: list[dict[str,Any]], *,
                     initial_seed: int, quota: int) -> dict[str,Any]:
    if type(clusters) is not list or not clusters:
        raise ValueError("missing independent seed cohort")
    metrics=[
        _check_private_cluster(row,initial_seed+i,quota=quota)
        for i,row in enumerate(clusters)
    ]
    return {
        "independent_initial_shuffle_clusters":len(metrics),
        "clusters_with_any_eligible_action":sum(
            x["natural_decisions"]>0 for x in metrics),
        "clusters_with_consensus_action_label":sum(
            x["strict_consensus_labels"]>0 for x in metrics),
        "natural_eligible_decision_points":sum(
            x["natural_decisions"] for x in metrics),
        "conditionally_simulated_terminal_games":sum(
            x["terminal_counterfactual_games"] for x in metrics),
        "strict_two_world_consensus_labels":sum(
            x["strict_consensus_labels"] for x in metrics),
        "direction_counts":{
            key:sum(x["direction_counts"][key] for x in metrics)
            for key in SIGN_CLASSES
        },
        "nonzero_real_terminal_pair_component_counts":{
            key:sum(x["nonzero_paired_component_counts"][key]
                    for x in metrics)
            for key in ALL_COMPONENTS
        },
        "independence_unit":"original_natural_shuffle_seed",
    }


def audit_completed_study(study: Mapping[str,Any]) -> dict[str,Any]:
    """Whitelist-only, safe research summary; no private seed, actor hand,
    unseen world, public per-step replay, or raw model weights included.
    """
    if (type(study) is not dict or study.get("protocol")!=SOURCE_PROTOCOL or
            study.get("no_online_ai_change") is not True or
            study.get("no_validated_improvement_claim") is not True or
            study.get("cluster_independence_unit")!=
                "original_natural_shuffle_seed"):
        raise ValueError("unsupported self-play study or deployment claim")
    first=study.get("train_seed_start")
    ntrain=study.get("train_seed_clusters")
    ntest=study.get("test_seed_clusters")
    train=study.get("private_train")
    held=study.get("private_holdout")
    pub=study.get("public_replays")
    _validate(first,ntrain,ntest)
    if (study.get("test_seed_start")!=first+ntrain or
            type(train) is not list or type(held) is not list or
            type(pub) is not list or len(train)!=ntrain or
            len(held)!=ntest or len(pub)!=ntrain+ntest or
            study.get("natural_full_games")!=len(pub)):
        raise ValueError("train and truly untouched seed ranges mismatch")
    for i,game in enumerate(pub):
        _assert_public(game)
        balances=game.get("official_final_balances")
        if (game.get("protocol")!=SOURCE_PROTOCOL or
                game.get("game_id")!=f"game-{i:04d}" or
                game.get("players")!=["challenge"]*4 or
                game.get("rule_set")!="current_m423" or
                game.get("terminal_phase") not in ("finished","wall_exhausted") or
                type(balances) is not list or len(balances)!=4 or
                any(type(v) is not int for v in balances) or
                sum(balances) != 0 or
                type(game.get("public_frames")) is not list or
                not game["public_frames"] or
                game["public_frames"][-1]["board"]["phase"]!=game["terminal_phase"]):
            raise ValueError("natural four-challenge public terminal tape invalid")
    counts={
        "train":_aggregate_split(train,initial_seed=first,quota=2),
        "holdout":_aggregate_split(held,initial_seed=first+ntrain,quota=2),
    }
    total_forks=sum(v["conditionally_simulated_terminal_games"]
                    for v in counts.values())
    if study.get("counterfactual_full_games")!=total_forks:
        raise ValueError("missing real terminal action-paired games")
    model=study.get("model")
    eval_report=study.get("heldout")
    if (type(model) is not dict or
            model.get("protocol")!=MODEL_PROTOCOL or
            model.get("online_promotion_allowed") is not False or
            model.get("seed_clusters_seen")!=ntrain or
            model.get("total_action_labels")!=
                counts["train"]["strict_two_world_consensus_labels"] or
            model.get("independent_seed_clusters_with_labels")!=
                counts["train"]["clusters_with_consensus_action_label"] or
            type(eval_report) is not dict or
            eval_report.get("protocol")!=MODEL_PROTOCOL or
            eval_report.get("untouched_shuffle_seed_clusters")!=ntest or
            eval_report.get("total_natural_checkpoints")!=
                counts["holdout"]["natural_eligible_decision_points"] or
            eval_report.get("consensus_action_checkpoints")!=
                counts["holdout"]["strict_two_world_consensus_labels"] or
            eval_report.get("offline_model_only") is not True or
            eval_report.get("evidence_of_population_strength") is not False):
        raise ValueError("model fit and held-out conditional labels mismatch")
    nscored=eval_report.get("scored_decisions")
    ncorrect=eval_report.get("correct_conditional_directions")
    if (type(nscored) is not int or type(ncorrect) is not int or
            not 0<=ncorrect<=nscored<=
            counts["holdout"]["strict_two_world_consensus_labels"] or
            type(eval_report.get("seed_report")) is not list or
            len(eval_report["seed_report"])!=ntest or
            any(type(row.get("private_shuffle_seed")) is not int or
                row["private_shuffle_seed"]!=first+ntrain+i
                for i,row in enumerate(eval_report["seed_report"]))):
        raise ValueError("invented held-out model evaluation")
    # We explicitly suppress accuracy when there are insufficient scored
    # decisions; a 0/0 outcome cannot be written as 0%.
    ratio=(round(ncorrect/nscored,5) if nscored>=5 else None)
    return {
        "protocol":PROTOCOL,
        "source_protocol":SOURCE_PROTOCOL,
        "original_natural_full_games":len(pub),
        "conditioned_full_terminal_action_branch_games":total_forks,
        "total_genuine_complete_games":len(pub)+total_forks,
        "splits":counts,
        "offline_model_status":model.get("status"),
        "holdout_scored_consensus_decisions":nscored,
        "holdout_correct_direction_decisions":ncorrect,
        "holdout_exploratory_direction_accuracy_if_at_least_five":ratio,
        "holdout_accuracy_status":(
            "exploratory_only_not_strength_proof" if ratio is not None else
            "insufficient_scored_consensus_decisions"),
        "training_and_holdout_seed_ranges_disjoint":True,
        "real_terminal_components_reconciled":True,
        "private_state_and_shuffle_seed_exported":False,
        "model_released_to_live_ai":False,
        "real_policy_strength_proven":False,
        "limitations":[
            "Two wall permutations sharing the same original game are correlated conditional futures, not independent shuffle seeds.",
            "Seed-level statistics do not establish causal or population-level action value.",
            "First naturally eligible opportunity per seat is not uniformly sampled among all decisions.",
            "A sign-consensus filter can discard a majority of true legal decision points; report coverage, never silently drop them.",
            "Prediction direction accuracy is withheld for fewer than five scored decisions and never means win-rate improvement.",
            "The frozen public challenge policy remains unchanged.",
        ],
    }


def run_audited_cohort(seed_start: int, train_seeds: int,
                       holdout_seeds: int, *, max_checkpoints: int = 2
                       ) -> tuple[dict[str,Any],dict[str,Any]]:
    _validate(seed_start,train_seeds,holdout_seeds,max_checkpoints)
    study=run_study(seed_start,train_seeds,holdout_seeds,
                    max_checkpoints=max_checkpoints)
    audit=audit_completed_study(study)
    return study,audit
