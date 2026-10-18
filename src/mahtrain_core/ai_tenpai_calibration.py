"""M3.56 OFFLINE ONLY: public tenpai features and sealed truth-label evaluation.

A trusted simulator may inspect a target player's *actual* concealed hand to
make a retrospective yes/no label. Feature extraction and predictions MUST
only see the observer's public board fields, never that hand. No fitted
coefficient is deployed to online challenge AI in this research pilot.

The sample unit is an observer/target/turn. Tests and evaluation split by
shuffle seed, not by rows or seat rotations. This is an observational
self-play estimate with substantial policy-specific selection bias.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Mapping, Sequence

from .rules import SUITS, TILE_INDEX
from .efficiency import shanten_13
from .four_player import FourPlayerOpening
from .ai_tournament import simulate_match

FEATURE_NAMES = (
    "bias",
    "progress",
    "exposed_meld_fraction",
    "river_length_fraction",
    "river_nondingque_fraction",
    "recent_dingque_fraction",
    "open_meld_suit_concentration",
)
REPORT_PROTOCOL = "offline_tenpai_seed_split_pilot_v1"


def public_tenpai_features(view: Mapping[str, Any], target: int) -> tuple[float, ...]:
    """Public inputs ONLY. No concealed hands, original deck, private draws."""
    own = view.get("seat")
    missing = view.get("missing_suits")
    melds = view.get("melds")
    won = view.get("won")
    discards = view.get("discards")
    wall = view.get("wall_count")
    if (type(own) is not int or own not in range(4)
        or type(target) is not int or target not in range(4) or target == own
        or not isinstance(missing, (list, tuple)) or len(missing) != 4
        or any(x not in SUITS for x in missing)
        or not isinstance(melds, (list, tuple)) or len(melds) != 4
        or not isinstance(won, (list, tuple)) or len(won) != 4 or won[target]
        or not isinstance(discards, (list, tuple))
        or type(wall) is not int or not 0 <= wall <= 108):
        raise ValueError("tenpai feature extractor requires valid public turn data")
    for group in melds[target]:
        if not isinstance(group, dict):
            raise ValueError("invalid public meld")
    river = []
    for entry in discards:
        if (not isinstance(entry, dict) or
            type(entry.get("seat")) is not int or entry["seat"] not in range(4)
            or entry.get("tile") not in TILE_INDEX):
            raise ValueError("invalid public discard")
        if entry["seat"] == target:
            river.append(entry["tile"])
    kinds = [m["tile"][0] for m in melds[target]
             if m.get("tile") in TILE_INDEX]
    concentration = (max(Counter(kinds).values()) / len(kinds)
                     if kinds else 0.0)
    suit = missing[target]
    return (
        1.0,
        max(0.0, min(1.0, (55 - wall) / 55)),
        min(1.0, len(melds[target]) / 4),
        min(1.0, len(river) / 20),
        sum(t[0] != suit for t in river) / max(1, len(river)),
        sum(t[0] == suit for t in river[-3:]) / max(1, len(river[-3:])),
        concentration,
    )


def _truth_label(game: FourPlayerOpening, seat: int) -> int | None:
    """Only trusted OFFLINE evaluator may inspect these hidden labels."""
    if game._won[seat]:
        return None
    hand = game._hands[seat]
    melds = game._melds[seat]
    if len(hand) + 3 * len(melds) != 13:
        return None
    return int(shanten_13(hand, melds, game.missing_suits[seat]) == 0)


def collect_offline_observations(seed: int, *, stride: int = 3
                                 ) -> list[dict[str, Any]]:
    """Run one sealed-label game; NEVER serialize opponent tile identities."""
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be a uint32 integer")
    if type(stride) is not int or not 1 <= stride <= 32:
        raise ValueError("sampling stride must be 1..32")
    rows: list[dict[str, Any]] = []
    checkpoints = 0

    def _trusted_snapshot(game: FourPlayerOpening) -> None:
        nonlocal checkpoints
        checkpoints += 1
        if checkpoints % stride != 0:
            return
        if game.turn is None:
            return
        view = game.private_view(game.turn)
        for seat in range(4):
            if seat == game.turn or game._won[seat]:
                continue
            truth = _truth_label(game, seat)
            if truth is None:
                continue
            rows.append({
                "seed": seed,
                "features": public_tenpai_features(view, seat),
                "tenpai": truth,
            })

    # Fixed agents/seating protocol; the recorder is NOT an online AI feature.
    simulate_match(seed, rotation=seed % 3, offline_observer=_trusted_snapshot)
    return rows


def _validated_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("nonempty training/evaluation observations required")
    for row in rows:
        if (type(row.get("seed")) is not int
            or row.get("tenpai") not in (0, 1)
            or type(row["tenpai"]) is not int
            or not isinstance(row.get("features"), (tuple, list))
            or len(row["features"]) != len(FEATURE_NAMES)
            or any(type(v) not in (float, int) or not math.isfinite(v)
                   or not 0 <= v <= 1 for v in row["features"])):
            raise ValueError("malformed public feature/true label record")


def _predict(features: Sequence[float], weights: Sequence[float]) -> float:
    z = sum(x * w for x, w in zip(features, weights))
    return 1 / (1 + math.exp(-max(-25.0, min(25.0, z))))


def fit_public_logistic(rows: Sequence[Mapping[str, Any]], *,
                        epochs: int = 360) -> tuple[float, ...]:
    """Small, deterministic L2-logistic model; no external ML dependency."""
    _validated_rows(rows)
    if type(epochs) is not int or not 1 <= epochs <= 2000:
        raise ValueError("epochs must be 1..2000")
    by_seed = Counter(r["seed"] for r in rows)
    # Weight each independent shuffle seed equally; late, long matches
    # should not drown out shorter games in the same experimental cluster.
    weights_per_row = [
        1.0 / (len(by_seed) * by_seed[row["seed"]])
        for row in rows
    ]
    prevalence = sum(w * row["tenpai"]
                     for w, row in zip(weights_per_row, rows))
    smoothed = min(0.99, max(0.01, prevalence))
    fitted = [math.log(smoothed / (1 - smoothed))] + [
        0.0] * (len(FEATURE_NAMES) - 1)
    for _ in range(epochs):
        grad = [0.0] * len(fitted)
        for row, scale in zip(rows, weights_per_row):
            error = (_predict(row["features"], fitted) - row["tenpai"]) * scale
            for i, value in enumerate(row["features"]):
                grad[i] += error * value
        for i in range(1, len(grad)):
            grad[i] += 0.018 * fitted[i]
        for i in range(len(fitted)):
            fitted[i] = max(-10.0, min(10.0, fitted[i] - 0.55 * grad[i]))
    return tuple(round(x, 9) for x in fitted)


def evaluate_calibration(rows: Sequence[Mapping[str, Any]],
                         weights: Sequence[float] | None, *,
                         prior: float | None = None,
                         bins: int = 5) -> dict[str, Any]:
    """Reliability diagram data + Brier and log loss on HELD-OUT seeds."""
    _validated_rows(rows)
    if type(bins) is not int or not 2 <= bins <= 20:
        raise ValueError("bins must be 2..20")
    if (weights is None) == (prior is None):
        raise ValueError("provide either trained weights or training prior")
    if weights is not None and (
        len(weights) != len(FEATURE_NAMES) or
        any(type(w) not in (float, int) or not math.isfinite(w)
            for w in weights)
    ):
        raise ValueError("invalid model coefficients")
    if prior is not None and (
        type(prior) not in (float, int) or not 0 <= prior <= 1
    ):
        raise ValueError("training prior must be between 0 and 1")
    result = [{"count": 0, "sum_p": 0.0, "sum_y": 0.0}
              for _ in range(bins)]
    brier = 0.0
    loss = 0.0
    positives = 0
    for row in rows:
        p = (_predict(row["features"], weights)
             if weights is not None else float(prior))
        p = max(1e-7, min(1 - 1e-7, p))
        y = row["tenpai"]
        bucket = result[min(bins - 1, int(p * bins))]
        bucket["count"] += 1
        bucket["sum_p"] += p
        bucket["sum_y"] += y
        brier += (p - y) ** 2
        loss -= y * math.log(p) + (1 - y) * math.log(1 - p)
        positives += y
    reliability = []
    ece = 0.0
    for i, b in enumerate(result):
        count = b["count"]
        actual = b["sum_y"] / count if count else None
        predicted = b["sum_p"] / count if count else None
        if count:
            ece += count / len(rows) * abs(actual - predicted)
        reliability.append({
            "range": [round(i / bins, 3), round((i + 1) / bins, 3)],
            "count": count,
            "predicted": round(predicted, 6) if count else None,
            "observed": round(actual, 6) if count else None,
        })
    return {
        "n": len(rows), "positives": positives,
        "prevalence": round(positives / len(rows), 6),
        "brier": round(brier / len(rows), 6),
        "log_loss": round(loss / len(rows), 6),
        "ece": round(ece, 6),
        "reliability": reliability,
    }


def run_seed_split_pilot(train_seeds: Sequence[int], test_seeds: Sequence[int],
                         *, stride: int = 3) -> dict[str, Any]:
    """Pilot metrics, not a learned-on-all-seeds score or an online policy."""
    train_ids = list(train_seeds)
    test_ids = list(test_seeds)
    if (not train_ids or not test_ids or len(train_ids) != len(set(train_ids))
        or len(test_ids) != len(set(test_ids))
        or set(train_ids) & set(test_ids)):
        raise ValueError("train/test shuffle seeds must be nonempty and disjoint")
    if any(type(s) is not int or not 0 <= s < 2**32
           for s in [*train_ids, *test_ids]):
        raise ValueError("all shuffle seeds must be uint32 integers")
    train = [r for seed in train_ids
             for r in collect_offline_observations(seed, stride=stride)]
    test = [r for seed in test_ids
            for r in collect_offline_observations(seed, stride=stride)]
    _validated_rows(train)
    _validated_rows(test)
    params = fit_public_logistic(train)
    prior = sum(r["tenpai"] for r in train) / len(train)
    model = evaluate_calibration(test, params)
    baseline = evaluate_calibration(test, None, prior=prior)
    return {
        "protocol": REPORT_PROTOCOL,
        "status": "exploratory_only_no_online_deployment",
        "train_seeds": train_ids,
        "test_seeds": test_ids,
        "features": list(FEATURE_NAMES),
        "train_n": len(train),
        "train_positives": sum(r["tenpai"] for r in train),
        "test_n": len(test),
        "baseline": baseline,
        "candidate": model,
        "brier_delta_vs_prior": round(model["brier"] - baseline["brier"], 6),
        "can_claim_improvement": False,
        "contains_hidden_hands": False,
        "calibration_note": (
            "Labels from simulator's true hand, but predictions use public "
            "features only. Seed-disjoint observational self-play; not a "
            "validated probability suitable for online AI."
        ),
    }
