"""Public-meld risk diagnostic for M3.52 expected-value challenge AI.

This is an observational shadow comparison on the SAME authorized view.
Never expose either the counterfactual tile or opponent hidden information.
"""
from __future__ import annotations

from typing import Any, Mapping

from .ai import challenge_discard_scores
from .rules import TILE_INDEX


def diagnose_pressure_tiebreak(view: Mapping[str, Any],
                               oracle: Mapping[str, Any],
                               actual_discard: str, *,
                               policy: str) -> dict[str, bool]:
    """Compare full EV policy vs identical EV policy without risk weights.

    Historical output keys are retained for compatible trend reports, but
    'effective_tie' now means equal top unadjusted EV (not equal ukeire).
    Risk is only a weak modifier of viable minimum-shanten cuts; therefore
    it can change decisions even when raw EV is not tied exactly.
    """
    if policy not in ("challenge", "challenge_no_pressure"):
        raise ValueError("pressure telemetry only supports challenge variants")
    ranked = challenge_discard_scores(view)
    if not ranked:
        raise ValueError("no legal challenge EV candidates")
    rows = {
        item["discard"]: item for item in oracle["candidates"]
    }
    if any(item["discard"] not in rows for item in ranked):
        raise ValueError("discard oracle is missing legal candidate")
    chosen = min(ranked, key=lambda item: (
        -item["expected_fan_weighted_copies"],
        -item["effective_tile_count"],
        TILE_INDEX[item["discard"]],
    ))["discard"]
    pressure_choice = ranked[0]["discard"]
    expected = pressure_choice if policy == "challenge" else chosen
    if actual_discard != expected:
        raise RuntimeError("AI pressure probe disagrees with legal EV policy")
    maximum = max(item["expected_fan_weighted_copies"] for item in ranked)
    equal_best = [
        item for item in ranked
        if abs(item["expected_fan_weighted_copies"] - maximum) < 1e-9
    ]
    pressure = [item["public_pressure"] for item in ranked]
    return {
        "effective_tie": len(equal_best) > 1,
        "public_pressure_present": any(value > 0 for value in pressure),
        "public_pressure_discriminates": len(set(pressure)) > 1,
        "choice_would_change": pressure_choice != chosen,
        "actual_choice_changed": (
            policy == "challenge" and pressure_choice != chosen
        ),
    }
