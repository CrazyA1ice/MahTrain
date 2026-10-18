"""M3.59 OFFLINE research-only policy generalization and paired net-score trial.

Train just once using sealed oracle labels. Cross-policy evaluation and paired
full matches receive frozen weights but NEVER opponent concealed hands. No
weights or sampled private hands are deployed, exposed through web, or
serialized. All statistical units are independent shuffle seeds, not turns.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from statistics import mean
from typing import Any, Mapping, Sequence

from .ai import MahjongAgent
from .ai_ron_calibration import (
    NAMES, SAFE_INDEX, _predict, _check, collect_ron_labels,
    evaluate_candidate_ron, fit_ron_model, public_candidate_features,
)
from .ai_ron_stratified import _seed_bootstrap
from .ai_tournament import simulate_match

PROTOCOL = "offline_frozen_ron_cross_policy_paired_v1"
POLICY_FAMILIES = {
    "four_policy": ["challenge", "advanced", "basic", "baseline"],
    "no_pressure": ["challenge_no_pressure", "advanced", "basic", "baseline"],
}


def _frozen_candidate_scores(
    view: Mapping[str, Any], ranking: Sequence[Mapping[str, Any]],
    coefficients: Sequence[float], *,
    risk_scale: float = 1.8, mean_payout: float = 1.0,
) -> list[dict[str, Any]]:
    """Rerank ONLY challenge's min-shanten rows by a bounded ron penalty.

    The base challenge already balances ukeire, scoring and weak public risk.
    Our frozen model is a controlled perturbation, not a new heuristic oracle.
    """
    if (len(coefficients) != len(NAMES) or
        not 0 < risk_scale <= 5 or not 0 < mean_payout <= 4096):
        raise ValueError("invalid frozen risk scale / coefficients")
    if not ranking:
        raise ValueError("nonempty challenge candidate ranking required")
    values=[]
    best_shanten=ranking[0]["shanten"]
    for row in ranking:
        if row["shanten"] != best_shanten:
            raise ValueError("risk may never override minimum shanten")
        candidate=row["discard"]
        expected_ron_multiplier=0.
        for target in range(4):
            if target == view["seat"] or view["won"][target]:
                continue
            # Only the current legal cut, public board and own concealed
            # hand reach the model. Never access game._hands / private wall.
            features=public_candidate_features(view,target,candidate)
            expected_ron_multiplier+=_predict(
                {"features":features},coefficients,0.0
            )*mean_payout
        penalty=min(.12,risk_scale*expected_ron_multiplier)
        updated=dict(row)
        updated["offline_expected_ron_multiplier"]=round(
            expected_ron_multiplier,7)
        updated["offline_risk_penalty"]=round(penalty,7)
        updated["offline_score"]=round(
            row["score"]*(1-penalty),7)
        values.append(updated)
    return sorted(values,key=lambda item: (
        -item["offline_score"],-item["effective_tile_count"],
        item["discard"],
    ))


class FrozenRonResearchAgent(MahjongAgent):
    """Same normal challenge opening/claims; only discard ranking is ablated."""

    def __init__(self, *, seed: int, seat: int,
                 coefficients: Sequence[float],
                 conditional_multiplier: float,
                 risk_scale: float = 1.8) -> None:
        super().__init__("challenge",seed=seed,seat=seat)
        self._frozen_coefficients=tuple(coefficients)
        self._mean_payout=conditional_multiplier
        self._risk_scale=risk_scale
        self.risk_observations=0
        self.changed_decisions=0
        self.risk_applied=0

    def discard(self, view: Mapping[str, Any]) -> str:
        original=super().discard(view)
        ranking=self._last_discard_scores
        if ranking is None or len(ranking)<2:
            return original
        self.risk_observations+=1
        revised=_frozen_candidate_scores(
            view,ranking,self._frozen_coefficients,
            risk_scale=self._risk_scale,mean_payout=self._mean_payout,
        )
        self.risk_applied+=int(any(
            row["offline_risk_penalty"]>0 for row in revised))
        self._last_discard_scores=revised
        chosen=revised[0]["discard"]
        self.changed_decisions+=int(chosen != original)
        return chosen


def _check_seed_sets(train: Sequence[int],
                     cross: Sequence[int],
                     paired: Sequence[int]) -> None:
    groups=[list(train),list(cross),list(paired)]
    if (any(not xs or len(set(xs)) != len(xs) for xs in groups)
        or sum(len(xs) for xs in groups) != len(set(
            x for xs in groups for x in xs))
        or any(type(x) is not int or not 0<=x<2**32
               for xs in groups for x in xs)):
        raise ValueError("training, cross-policy and paired seeds must be unique/disjoint")


def _cross_policy_report(
    records: Sequence[Mapping[str,Any]], coefficients: Sequence[float],
    *, prior: float, mean_multiplier: float,
) -> dict[str, Any]:
    _check(records)
    baseline=evaluate_candidate_ron(
        records,None,actionable_prior=prior,
        conditional_multiplier=mean_multiplier
    )
    model=evaluate_candidate_ron(
        records,coefficients,actionable_prior=prior,
        conditional_multiplier=mean_multiplier
    )
    return {
        "samples":model["n"],
        "true_ron_events":model["ron_events"],
        "eligible":model["actionable_n"],
        "eligible_ron_events":model["actionable_ron_events"],
        "baseline_brier":baseline["brier"],
        "model_brier":model["brier"],
        "brier_delta":round(model["brier"]-baseline["brier"],8),
        "log_loss_delta":round(model["log_loss"]-baseline["log_loss"],8),
        "payout_mse_delta":round(
            model["payout_multiplier_mse"]-
            baseline["payout_multiplier_mse"],8
        ),
    }


def _pair(seed: int,rotation: int,coefficients: Sequence[float],
          mean_multiplier: float, *,
          risk_scale: float) -> dict[str,Any]:
    levels=POLICY_FAMILIES["four_policy"]
    lineup=[levels[(seat+rotation)%4] for seat in range(4)]
    challenge_seat=lineup.index("challenge")
    baseline=simulate_match(
        seed,rotation=rotation%3,lineup=lineup,offline_kong_base=1
    )
    experimental_agent=FrozenRonResearchAgent(
        seed=seed,seat=challenge_seat,coefficients=coefficients,
        conditional_multiplier=mean_multiplier,risk_scale=risk_scale,
    )
    treatment=simulate_match(
        seed,rotation=rotation%3,lineup=lineup,offline_kong_base=1,
        offline_agent_overrides={challenge_seat:experimental_agent},
    )
    for result in (baseline,treatment):
        if (result["assignment"]!=lineup
            or result["physical_count"]!=108
            or result["scoring_rules"]["kong_base"]!=1
            or result["unpriced_kong_events"]!=0
            or sum(result["official_settled_balances"])!=0
            or result["exhaustive_preview_not_posted"]):
            raise RuntimeError("paired contest lacks a completely settled zero-sum ledger")
    base_net=baseline["official_settled_balances"][challenge_seat]
    trial_net=treatment["official_settled_balances"][challenge_seat]
    return {
        "seed":seed,"rotation":rotation,"treated_seat":challenge_seat,
        "baseline_net":base_net,"treatment_net":trial_net,
        "delta_net":trial_net-base_net,
        "baseline_win_events":sum(
            w["seat"]==challenge_seat for w in baseline["winners"]),
        "treatment_win_events":sum(
            w["seat"]==challenge_seat for w in treatment["winners"]),
        "baseline_discard_ron_sources":sum(
            w["source"]==challenge_seat and w["seat"]!=challenge_seat
            for w in baseline["winners"]),
        "treatment_discard_ron_sources":sum(
            w["source"]==challenge_seat and w["seat"]!=challenge_seat
            for w in treatment["winners"]),
        "risk_observations":experimental_agent.risk_observations,
        "changed_discard_decisions":experimental_agent.changed_decisions,
        "baseline_terminal_phase":baseline["terminal_phase"],
        "treatment_terminal_phase":treatment["terminal_phase"],
    }


def run_frozen_risk_research(
    train_seeds: Sequence[int],
    cross_test_seeds: Sequence[int],
    paired_test_seeds: Sequence[int],
    *, stride: int = 3,
    risk_scale: float = 1.8,
    bootstrap: int = 512,
) -> dict[str,Any]:
    """Freeze one model on native AI; evaluate unseen strategy families and nets."""
    _check_seed_sets(train_seeds,cross_test_seeds,paired_test_seeds)
    if type(stride) is not int or not 1<=stride<=32:
        raise ValueError("invalid sampling stride")
    if type(bootstrap) is not int or not 100<=bootstrap<=10000:
        raise ValueError("invalid number of seed-cluster bootstrap trials")
    train=[
        r for seed in train_seeds for r in
        collect_ron_labels(seed,stride=stride)
    ]
    _check(train)
    relevant=[r for r in train if not r["features"][SAFE_INDEX]]
    if not relevant:
        raise ValueError("training observations contain no legally actionable cuts")
    prior=(sum(r["ron"] for r in relevant)+1)/(len(relevant)+2)
    positives=[r["payout_multiplier"] for r in train if r["ron"]]
    conditional_multiplier=mean(positives) if positives else 1.
    coefficients=fit_ron_model(train)
    fingerprint=hashlib.sha256(
        json.dumps(coefficients,separators=(",",":")).encode()
    ).hexdigest()[:16]
    cross={}
    for family,lineup in POLICY_FAMILIES.items():
        records=[
            r for seed in cross_test_seeds for r in collect_ron_labels(
                seed,stride=stride,
                lineup=[lineup[(seat+seed)%4] for seat in range(4)]
            )
        ]
        by_seed=[]
        for seed in cross_test_seeds:
            group=[r for r in records if r["seed"]==seed]
            if not group:
                continue
            by_seed.append({
                "seed":seed,
                **_cross_policy_report(
                    group,coefficients,prior=prior,
                    mean_multiplier=conditional_multiplier
                ),
            })
        cross[family]={
            **_cross_policy_report(
                records,coefficients,prior=prior,
                mean_multiplier=conditional_multiplier,
            ),
            "seed_deltas":by_seed,
            "cluster_bootstrap":_seed_bootstrap(
                [x["brier_delta"] for x in by_seed],trials=bootstrap
            ),
        }
    contests=[]
    by_pair_seed=[]
    for seed in paired_test_seeds:
        games=[_pair(seed,rotation,coefficients,conditional_multiplier,
                     risk_scale=risk_scale) for rotation in range(4)]
        contests.extend(games)
        by_pair_seed.append({
            "seed":seed,
            "four_rotations":4,
            "net_delta":sum(x["delta_net"] for x in games),
            "mean_net_delta":round(mean(x["delta_net"] for x in games),6),
            "changed_discards":sum(x["changed_discard_decisions"] for x in games),
        })
    result={
        "protocol":PROTOCOL,
        "status":"offline_shadow_only_not_live",
        "train_seeds":list(train_seeds),
        "cross_test_seeds":list(cross_test_seeds),
        "paired_test_seeds":list(paired_test_seeds),
        "training_samples":len(train),
        "training_ron_events":sum(r["ron"] for r in train),
        "frozen_model_fingerprint":fingerprint,
        "mean_train_ron_multiplier":round(conditional_multiplier,6),
        "cross_policy":cross,
        "paired": {
            "game_pairs":len(contests),
            "full_rule_kong_base":1,
            "seat_rotations":4,
            "baseline_net_sum":sum(x["baseline_net"] for x in contests),
            "treatment_net_sum":sum(x["treatment_net"] for x in contests),
            "paired_net_delta":sum(x["delta_net"] for x in contests),
            "total_risk_aware_decisions":sum(x["risk_observations"]
                                            for x in contests),
            "total_changed_discards":sum(x["changed_discard_decisions"]
                                         for x in contests),
            "baseline_discard_ron_sources":sum(
                x["baseline_discard_ron_sources"] for x in contests
            ),
            "treatment_discard_ron_sources":sum(
                x["treatment_discard_ron_sources"] for x in contests
            ),
            "by_shuffle_seed":by_pair_seed,
            "seed_bootstrap_net_delta":_seed_bootstrap(
                [x["mean_net_delta"] for x in by_pair_seed],trials=bootstrap
            ),
        },
        "contains_private_hands":False,
        "contains_row_level_predictions":False,
        "online_policy_modified":False,
        "can_claim_superior_policy":False,
        "limitations":(
            "Every arm uses the same initial shuffle and seat, but diverging "
            "actions change subsequent trajectories. Seeds, not turns or "
            "rotations, are independent clusters. This tiny pilot tests "
            "entire zero-sum game ledgers including priced kong payments, "
            "not causal per-discard regret or statistical superiority."
        ),
    }
    return result
