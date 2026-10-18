"""M3.58 offline held-out risk validation, stratified by PUBLIC state only.

Separates already rule-safe cuts from statistically actionable opponent/cut
pairs, and reports seed-cluster rather than row-level uncertainty. No online
AI changes and no serialization of concealed tiles / individual labels.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any, Mapping, Sequence

from .ai_ron_calibration import (
    NAMES, SAFE_INDEX, _check, evaluate_candidate_ron,
)

MELD_INDEX = NAMES.index("meld_fraction")
STAGE_INDEX = NAMES.index("progress")
PROTOCOL = "candidate_ron_public_strata_seed_cluster_v1"


def public_risk_strata(features: Sequence[float]) -> dict[str, str]:
    """Read strata only from authorized feature vector, never label or hand."""
    if (len(features) != len(NAMES) or
        any(type(v) not in (float, int) or not math.isfinite(v)
            or not 0 <= v <= 1 for v in features)):
        raise ValueError("invalid public candidate features")
    # progress=max(0,min(1,(55-wall)/55)), with integer wall_count.
    progress=features[STAGE_INDEX]
    stage=("critical" if progress >= 43/55 - 1e-9 else
           "late" if progress >= 31/55 - 1e-9 else "early")
    exposure=features[MELD_INDEX]
    melds=("two_plus" if exposure >= .5 - 1e-9 else
           "one" if exposure >= .25 - 1e-9 else "zero")
    return {
        "wall_stage":stage,
        "target_public_melds":melds,
        "candidate_rule":("dingque_safe"
                          if features[SAFE_INDEX] else "ron_eligible"),
    }


def _comparison(rows: Sequence[Mapping[str, Any]],
                params: Sequence[float], prior: float,
                multiplier: float) -> dict[str, Any]:
    baseline=evaluate_candidate_ron(rows,None,actionable_prior=prior,
                                    conditional_multiplier=multiplier)
    model=evaluate_candidate_ron(rows,params,actionable_prior=prior,
                                 conditional_multiplier=multiplier)
    return {
        "n":model["n"],
        "true_ron_events":model["ron_events"],
        "actionable_n":model["actionable_n"],
        "baseline_brier":baseline["brier"],
        "candidate_brier":model["brier"],
        "brier_delta":round(model["brier"]-baseline["brier"],8),
        "baseline_log_loss":baseline["log_loss"],
        "candidate_log_loss":model["log_loss"],
        "log_loss_delta":round(model["log_loss"]-baseline["log_loss"],8),
        "payout_mse_delta":round(
            model["payout_multiplier_mse"]-baseline["payout_multiplier_mse"],8
        ),
    }


def _seed_bootstrap(deltas: Sequence[float], *, trials: int = 2048
                    ) -> dict[str, Any]:
    """Percentile interval of unweighted seed means; NOT iid-row CI."""
    if not deltas:
        raise ValueError("bootstrap needs nonempty independent clusters")
    if type(trials) is not int or not 100 <= trials <= 10000:
        raise ValueError("invalid bootstrap repetitions")
    n=len(deltas)
    rng=random.Random(3582026)
    values=[]
    for _ in range(trials):
        values.append(sum(deltas[rng.randrange(n)] for _ in range(n))/n)
    values.sort()
    return {
        "seed_clusters":n,
        "seed_macro_mean_delta":round(sum(deltas)/n,8),
        "bootstrap_95pct_range":[
            round(values[int(.025*(trials-1))],8),
            round(values[int(.975*(trials-1))],8),
        ],
        "seeds_better":sum(v < -1e-12 for v in deltas),
        "seeds_worse":sum(v > 1e-12 for v in deltas),
        "seeds_equal":sum(abs(v) <= 1e-12 for v in deltas),
        "repetitions":trials,
        "note":("Illustrative seed-cluster bootstrap (with replacement), "
                "not a confidence guarantee: adjacent seeds and repeated "
                "hands may remain strongly correlated."),
    }


def analyze_ron_validation(
    rows: Sequence[Mapping[str, Any]],
    params: Sequence[float], *,
    actionable_prior: float,
    conditional_multiplier: float,
    trials: int = 2048,
) -> dict[str, Any]:
    """Return ONLY summary metrics; prohibit individual observation export."""
    _check(rows)
    if (not isinstance(params, (list,tuple)) or len(params)!=len(NAMES)
        or any(type(v) not in (float,int) or not math.isfinite(v) for v in params)
        or type(actionable_prior) not in (float,int) or
        not 0<=actionable_prior<=1 or type(conditional_multiplier)
        not in (float,int) or not math.isfinite(conditional_multiplier) or
        not 0<=conditional_multiplier<=4096):
        raise ValueError("invalid fitted model / train-only prior")

    subsets: dict[tuple[str,str],list[Mapping[str,Any]]]=defaultdict(list)
    seeds: dict[int,list[Mapping[str,Any]]]=defaultdict(list)
    for row in rows:
        for key,value in public_risk_strata(row["features"]).items():
            subsets[(key,value)].append(row)
        seeds[row["seed"]].append(row)

    strata={}
    for key in ("wall_stage","target_public_melds","candidate_rule"):
        values={
            "wall_stage":("early","late","critical"),
            "target_public_melds":("zero","one","two_plus"),
            "candidate_rule":("dingque_safe","ron_eligible"),
        }[key]
        strata[key]={}
        for value in values:
            sample=subsets.get((key,value),[])
            strata[key][value]=(_comparison(sample,params,actionable_prior,
                                            conditional_multiplier)
                                if sample else {
                "n":0,"true_ron_events":0,"actionable_n":0,
                "baseline_brier":None,"candidate_brier":None,
                "brier_delta":None,"baseline_log_loss":None,
                "candidate_log_loss":None,"log_loss_delta":None,
                "payout_mse_delta":None,
            })

    by_seed=[]
    for seed in sorted(seeds):
        row=_comparison(seeds[seed],params,actionable_prior,
                        conditional_multiplier)
        by_seed.append({"seed":seed,**row})
    summary=_comparison(rows,params,actionable_prior,
                        conditional_multiplier)
    return {
        "protocol":PROTOCOL,
        "status":"offline_unvalidated_no_deployment",
        "overall":summary,
        "strata":strata,
        "by_seed":by_seed,
        "cluster_bootstrap_brier":_seed_bootstrap(
            [r["brier_delta"] for r in by_seed],trials=trials
        ),
        "cluster_bootstrap_payout":_seed_bootstrap(
            [r["payout_mse_delta"] for r in by_seed],trials=trials
        ),
        "has_hidden_hands":False,
        "row_level_predictions_exported":False,
        "study_limitations":(
            "Strata describe repeated within-game candidate observations; "
            "zero ron in sparse subgroups does not prove safety. "
            "Independent shuffle-seed count, not row count, is the effective "
            "starting point for uncertainty assessment."
        ),
    }
