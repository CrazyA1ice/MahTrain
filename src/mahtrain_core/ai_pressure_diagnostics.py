"""M3.12 shadow diagnostics of the *public-meld* pressure tie-break.

This compares two legal candidate choices on the SAME observed decision state,
without mutating the game or re-playing a counterfactual wall. Only boolean
aggregates leave the server; never export the alternative concealed tile.
"""
from __future__ import annotations

from typing import Any, Mapping

from .ai import public_suit_pressure
from .rules import TILE_INDEX


def diagnose_pressure_tiebreak(view: Mapping[str, Any],
                               oracle: Mapping[str, Any],
                               actual_discard: str, *,
                               policy: str) -> dict[str, bool]:
    """Compare pressure / no-pressure ties using an already computed oracle.

    The candidate restriction exactly mirrors the legal missing-suit-first
    policy and then the same minimum-shanten and maximum-ukeire priorities.
    Called only for 'challenge' and 'challenge_no_pressure'.
    """
    if policy not in ("challenge", "challenge_no_pressure"):
        raise ValueError("pressure telemetry only supports challenge variants")
    hand = view["hand"]
    missing = view["missing_suits"][view["seat"]]
    eligible = {tile for tile in hand if tile.startswith(missing)}
    if not eligible:
        eligible = set(hand)
    rows = {entry["discard"]: entry for entry in oracle["candidates"]}
    if not eligible or not eligible <= rows.keys():
        raise ValueError("discard oracle is missing valid choices")
    min_shanten = min(rows[t]["shanten"] for t in eligible)
    shanten_best = [t for t in eligible if rows[t]["shanten"] == min_shanten]
    max_ukeire = max(rows[t]["effective_tile_count"] for t in shanten_best)
    tied = sorted(
        (t for t in shanten_best
         if rows[t]["effective_tile_count"] == max_ukeire),
        key=TILE_INDEX.__getitem__,
    )
    # With single candidate or no visible pressure differences, a shadow
    # comparison cannot change the action even if a public meld is exposed.
    exposures = [public_suit_pressure(t, view) for t in tied]
    no_pressure_cut = tied[0]
    pressure_cut = min(tied, key=lambda t: (
        public_suit_pressure(t, view), TILE_INDEX[t],
    ))
    expected = (pressure_cut if policy == "challenge" else no_pressure_cut)
    if actual_discard != expected:
        raise RuntimeError("AI pressure probe disagrees with legal policy")
    return {
        "effective_tie": len(tied) > 1,
        "public_pressure_present": any(value > 0 for value in exposures),
        "public_pressure_discriminates": len(set(exposures)) > 1,
        "choice_would_change": pressure_cut != no_pressure_cut,
        "actual_choice_changed": (
            policy == "challenge" and pressure_cut != no_pressure_cut
        ),
    }
