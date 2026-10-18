"""M3.57 OFFLINE sealed labels for candidate-specific ron risk and payout.

Prediction inputs are public action history and the observer's own legal cut.
True opponent concealed hands are examined ONLY by a trusted offline observer
and are never returned to network clients, replays, or saved JSON. Outputs are
aggregate held-out metrics, not a live predictor or calibrated odds.

Each row = one visible candidate discard × one still-active opponent × one
pre-action checkpoint. Rows share games, opponents and candidate tiles; train
and test MUST split by distinct shuffle seeds, not individual rows.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Mapping, Sequence

from .ai_tenpai_calibration import public_tenpai_features
from .ai_tournament import simulate_match
from .four_player import FourPlayerOpening
from .rules import TILE_INDEX, TILES, score_win, winning_tiles

PROTOCOL = "offline_candidate_ron_seed_split_v1"
NAMES = (
    "bias", "progress", "meld_fraction", "river_length", "river_nondingque",
    "recent_dingque", "open_suit_concentration",
    "tile_m", "tile_s", "tile_p", "target_dingque_safe",
    "open_meld_same_suit", "prior_identical_discard",
    "river_same_suit", "other_public_matching_discards",
)
SAFE_INDEX = NAMES.index("target_dingque_safe")


def public_candidate_features(view: Mapping[str, Any], target: int,
                              tile: str) -> tuple[float, ...]:
    """Predictor input, intentionally independent of target's private hand."""
    if type(tile) is not str or tile not in TILE_INDEX:
        raise ValueError("invalid proposed discard kind")
    base = public_tenpai_features(view, target)
    own = view.get("seat")
    hand = view.get("hand")
    if (not isinstance(hand, list) or
        any(t not in TILE_INDEX for t in hand) or tile not in hand):
        raise ValueError("tile must be physically held by observer")
    missing = view["missing_suits"][own]
    # Keep candidate cuts legal under the enforced dingque discard rule.
    if any(t[0] == missing for t in hand) and tile[0] != missing:
        raise ValueError("cut would retain forced dingque tiles")
    melds = view["melds"][target]
    public_suits = [
        m["tile"][0] for m in melds
        if isinstance(m, dict) and m.get("tile") in TILE_INDEX
    ]
    river = [e["tile"] for e in view["discards"]
             if e["seat"] == target]
    others = [e["tile"] for e in view["discards"]
              if e["seat"] != target]
    suit = tile[0]
    return (*base,
            float(suit == "m"), float(suit == "s"), float(suit == "p"),
            float(view["missing_suits"][target] == suit),
            sum(s == suit for s in public_suits)/max(1,len(public_suits)),
            min(1., river.count(tile)/4),
            sum(t[0] == suit for t in river)/max(1,len(river)),
            min(1., others.count(tile)/4))


def _sealed_target_payoffs(game: FourPlayerOpening,
                           target: int) -> dict[str, int] | None:
    """Trusted evaluator: actual ron waits with rule-engine payout multipliers.

    This method alone can inspect opponent concealed hands. A 14-tile
    transient state/finished seat is excluded. No concealed hand escapes.
    """
    if game._won[target]:
        return None
    hand = game._hands[target]
    melds = game._melds[target]
    missing = game.missing_suits[target]
    if len(hand) + 3*len(melds) != 13:
        return None
    waits = winning_tiles(hand, melds, missing)
    return {
        tile: int(score_win([*hand,tile], melds, missing,
                            cap=game.ledger.fan_cap,
                            context={
                                "tian_ting_verified": bool(
                                    game._tian_ting[target].get("eligible",False))
                            })["multiplier"])
        for tile in waits
    }


def collect_ron_labels(seed: int, *, stride: int = 4,
                       lineup: list[str] | None = None
                       ) -> list[dict[str, Any]]:
    """Simulate one match, collect only public features + sealed numeric labels."""
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be uint32")
    if type(stride) is not int or not 1 <= stride <= 32:
        raise ValueError("stride must be 1..32")
    result: list[dict[str, Any]] = []
    count = 0

    def probe(game: FourPlayerOpening) -> None:
        nonlocal count
        count += 1
        if count % stride != 0 or game.turn is None:
            return
        observer = game.turn
        view = game.private_view(observer)
        hand = view["hand"]
        suit = view["missing_suits"][observer]
        forced = {t for t in hand if t[0] == suit}
        candidates = sorted(forced or set(hand), key=TILE_INDEX.__getitem__)
        for target in range(4):
            if target == observer or game._won[target]:
                continue
            payoffs = _sealed_target_payoffs(game, target)
            if payoffs is None:
                continue
            for tile in candidates:
                # Feature extraction is public-only and has no access to
                # payoffs, other hands, or upcoming wall.
                features = public_candidate_features(view, target, tile)
                multiplier = payoffs.get(tile, 0)
                result.append({
                    "seed": seed, "features": features,
                    "ron": int(multiplier > 0),
                    "payout_multiplier": multiplier,
                })

    options = {"offline_observer": probe}
    if lineup is not None:
        options["lineup"] = lineup
    simulate_match(seed, rotation=seed%3, **options)
    return result


def _check(rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("nonempty observations required")
    for row in rows:
        x = row.get("features")
        y = row.get("ron")
        payout = row.get("payout_multiplier")
        if (type(row.get("seed")) is not int or
            not isinstance(x, (tuple,list)) or len(x) != len(NAMES) or
            any(type(v) not in (int,float) or not math.isfinite(v)
                or not 0 <= v <= 1 for v in x) or
            type(y) is not int or y not in (0,1) or
            type(payout) is not int or not 0 <= payout <= 4096 or
            (y == 0 and payout != 0) or (y == 1 and payout < 1) or
            (x[SAFE_INDEX] == 1 and y != 0)):
            raise ValueError("invalid legal-candidate public row or sealed label")


def _logistic(x: Sequence[float], coefficients: Sequence[float]) -> float:
    score = max(-20., min(20., sum(a*b for a,b in zip(x,coefficients))))
    return 1/(1+math.exp(-score))


def fit_ron_model(rows: Sequence[Mapping[str, Any]], *,
                  epochs: int = 260) -> tuple[float,...]:
    """Fit exclusively on actionable candidates; rules mask dingque-safe."""
    _check(rows)
    if type(epochs) is not int or not 1 <= epochs <= 2000:
        raise ValueError("epochs must be in 1..2000")
    actionable = [r for r in rows if not r["features"][SAFE_INDEX]]
    if not actionable:
        raise ValueError("no eligible candidate discard rows")
    n_by_seed = Counter(row["seed"] for row in actionable)
    scales = [1/(len(n_by_seed)*n_by_seed[r["seed"]]) for r in actionable]
    positives = sum(w*r["ron"] for w,r in zip(scales,actionable))
    prior = min(.98,max(.002,positives))
    fitted = [math.log(prior/(1-prior))]+[0.]* (len(NAMES)-1)
    # Class imbalance is real; avoid artificial 50:50 oversampling.
    for _ in range(epochs):
        grad=[0.]*len(NAMES)
        for r,w in zip(actionable,scales):
            error=(_logistic(r["features"], fitted)-r["ron"])*w
            for i,val in enumerate(r["features"]):
                if i != SAFE_INDEX:
                    grad[i]+=error*val
        for i in range(1,len(grad)):
            grad[i]+= .012*fitted[i]
        for i in range(len(grad)):
            fitted[i]=max(-12.,min(12.,fitted[i]-.65*grad[i]))
    fitted[SAFE_INDEX] = 0.0  # strict logic mask applies separately
    return tuple(round(t,9) for t in fitted)


def _predict(row: Mapping[str, Any],
             params: Sequence[float] | None,
             actionable_prior: float) -> float:
    if row["features"][SAFE_INDEX]:
        return 0.0
    return _logistic(row["features"],params) if params is not None else actionable_prior


def evaluate_candidate_ron(
    rows: Sequence[Mapping[str, Any]],
    params: Sequence[float] | None, *,
    actionable_prior: float,
    conditional_multiplier: float,
    bins: int = 5,
) -> dict[str, Any]:
    """Brier/log loss/reliability + payout-regret by true direct-ron rules."""
    _check(rows)
    if (type(bins) is not int or not 2 <= bins <= 20 or
        type(actionable_prior) not in (int,float) or not 0 <= actionable_prior <= 1
        or type(conditional_multiplier) not in (int,float)
        or not math.isfinite(conditional_multiplier)
        or not 0 <= conditional_multiplier <= 4096):
        raise ValueError("invalid evaluation parameters")
    if params is not None and (len(params)!=len(NAMES)
       or any(type(z) not in (int,float) or not math.isfinite(z) for z in params)):
        raise ValueError("bad prediction coefficients")
    hist=[{"count":0,"sum_probability":0.,"sum_hits":0}
          for _ in range(bins)]
    brier=log_loss=mse_payoff=0.
    positives=actionable_count=actionable_hits=0
    for row in rows:
        y=row["ron"]
        if row["features"][SAFE_INDEX] == 0:
            actionable_count+=1
            actionable_hits+=y
        p=_predict(row,params,actionable_prior)
        brier+=(p-y)**2
        clipped=max(1e-8,min(1-1e-8,p))
        log_loss-=y*math.log(clipped)+(1-y)*math.log(1-clipped)
        mse_payoff+=(p*conditional_multiplier-row["payout_multiplier"])**2
        bucket=hist[min(bins-1,int(p*bins))]
        bucket["count"]+=1
        bucket["sum_probability"]+=p
        bucket["sum_hits"]+=y
        positives+=y
    table=[]
    ece=0.
    for i,b in enumerate(hist):
        n=b["count"]
        pred=b["sum_probability"]/n if n else None
        actual=b["sum_hits"]/n if n else None
        if n:
            ece+=n/len(rows)*abs(pred-actual)
        table.append({
            "band":[round(i/bins,3),round((i+1)/bins,3)],
            "n":n,
            "predicted":round(pred,6) if n else None,
            "observed":round(actual,6) if n else None,
        })
    return {
        "n":len(rows),"ron_events":positives,
        "actionable_n":actionable_count,
        "actionable_ron_events":actionable_hits,
        "brier":round(brier/len(rows),8),
        "log_loss":round(log_loss/len(rows),8),
        "ece":round(ece,8),
        "payout_multiplier_mse":round(mse_payoff/len(rows),8),
        "reliability":table,
    }


def run_candidate_ron_pilot(train_seeds: Sequence[int],
                            test_seeds: Sequence[int], *,
                            stride: int=4) -> dict[str, Any]:
    """Seed-disjoint research evaluation; no deployment or row-level export."""
    train_ids=list(train_seeds)
    test_ids=list(test_seeds)
    if (not train_ids or not test_ids or
        len(train_ids)!=len(set(train_ids)) or
        len(test_ids)!=len(set(test_ids)) or
        set(train_ids)&set(test_ids) or
        any(type(s) is not int or not 0 <= s < 2**32
            for s in [*train_ids,*test_ids])):
        raise ValueError("train and test seeds must be unique/disjoint uint32")
    if type(stride) is not int or not 1 <= stride <= 32:
        raise ValueError("invalid stride")
    train=[row for seed in train_ids
           for row in collect_ron_labels(seed,stride=stride)]
    test=[row for seed in test_ids
          for row in collect_ron_labels(seed,stride=stride)]
    _check(train)
    _check(test)
    train_eligible=[r for r in train if not r["features"][SAFE_INDEX]]
    if not train_eligible:
        raise ValueError("no training candidate in legal claim suits")
    smoothed_prior=(sum(r["ron"] for r in train_eligible)+1)/(
        len(train_eligible)+2)
    positive=[r["payout_multiplier"] for r in train if r["ron"]]
    mean_multiplier=(sum(positive)/len(positive)) if positive else 1.0
    fitted=fit_ron_model(train)
    baseline=evaluate_candidate_ron(test,None,
        actionable_prior=smoothed_prior,
        conditional_multiplier=mean_multiplier)
    candidate=evaluate_candidate_ron(test,fitted,
        actionable_prior=smoothed_prior,
        conditional_multiplier=mean_multiplier)
    by_seed=[]
    for seed in test_ids:
        subset=[r for r in test if r["seed"]==seed]
        m=evaluate_candidate_ron(subset,fitted,
            actionable_prior=smoothed_prior,
            conditional_multiplier=mean_multiplier)
        b=evaluate_candidate_ron(subset,None,
            actionable_prior=smoothed_prior,
            conditional_multiplier=mean_multiplier)
        by_seed.append({
            "seed":seed,"observations":m["n"],
            "ron_events":m["ron_events"],
            "brier_delta":round(m["brier"]-b["brier"],8),
        })
    from .ai_ron_stratified import analyze_ron_validation
    strata=analyze_ron_validation(
        test, fitted, actionable_prior=smoothed_prior,
        conditional_multiplier=mean_multiplier
    )
    return {
        "protocol":PROTOCOL,
        "status":"exploratory_offline_no_model_deployment",
        "stratified_validation":strata,
        "train_seeds":train_ids,"test_seeds":test_ids,
        "sample_unit":"legal_cut_x_active_opponent_x_turn",
        "features":list(NAMES),
        "train_n":len(train),"train_ron_events":sum(r["ron"] for r in train),
        "test_n":len(test),"test_ron_events":candidate["ron_events"],
        "actionable_train_n":len(train_eligible),
        "baseline":baseline,"candidate":candidate,
        "by_test_seed":by_seed,
        "brier_delta_vs_legal_suit_prior":round(
            candidate["brier"]-baseline["brier"],8),
        "payout_mse_delta":round(
            candidate["payout_multiplier_mse"]-baseline["payout_multiplier_mse"],
            8),
        "train_conditional_mean_multiplier":round(mean_multiplier,6),
        "can_claim_generalization":False,
        "contains_private_hands":False,
        "note":(
            "Offline labels use true concealed hands solely inside trusted "
            "simulator; all predictions use public features plus observer's "
            "own legal discard. Records share opponent and game histories; "
            "seed-disjoint pilot is not a validated live ron probability."
        ),
    }
