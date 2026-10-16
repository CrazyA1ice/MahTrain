"""Round-by-round decision review for completed solo training turns.

Do not use future wall knowledge. All statistics derive exclusively from the
already-graded historical analyses, each based on player's tiles and visible
discards at that point in time. 'Trend' compares sequential after-discard
states; this is descriptive, NOT proof that a specific discard caused change.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .error_focus import ERROR_LABELS

# Solo training presents only discard and prompted legal win actions.  There
# is no button for an illegal win, nor an exact-tiles listening-set question.
SOLO_ERROR_ORDER = (
    "missed_win", "shanten_regression", "ukeire_loss", "other_error",
)
SOLO_PRACTICE = {
    "missed_win": {"mode": "pure_suit_discard", "focus": "missed_win"},
    "shanten_regression": {
        "mode": "one_shanten", "focus": "shanten_regression"
    },
    "ukeire_loss": {"mode": "tenpai_discard", "focus": "ukeire_loss"},
}


def diagnose_solo_round(item: Mapping[str, Any]) -> list[str]:
    """Diagnose a completed solo decision from contemporaneous frozen facts.

    Missed legal wins take precedence: the after-discard shanten/ukeire from
    that hand is descriptive, not an alternative reason for the missed win.
    A completed self-draw win is never assigned an error.
    """
    if item["correct"]:
        return []
    if item["choice"] != "win" and "win" in item.get("best_actions", ()):
        return ["missed_win"]
    if (item.get("shanten_loss") or 0) > 0:
        return ["shanten_regression"]
    if (item.get("ukeire_loss") or 0) > 0:
        return ["ukeire_loss"]
    # Historic records may not have numeric losses: use verified candidates.
    analysis = item.get("analysis") or {}
    candidate = item.get("selected_candidate") or {}
    minimum = analysis.get("minimum_shanten")
    if minimum is not None and candidate.get("shanten") is not None:
        if candidate["shanten"] > minimum:
            return ["shanten_regression"]
        best = max((
            row.get("effective_tile_count", 0)
            for row in analysis.get("candidates", ())
            if row.get("shanten") == minimum
        ), default=0)
        if candidate.get("effective_tile_count", 0) < best:
            return ["ukeire_loss"]
    return ["other_error"]


def summarize_solo_errors(rounds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Count decisions, not across-round probability fluctuations."""
    groups = {
        category: {"label": ERROR_LABELS[category], "count": 0, "rounds": []}
        for category in SOLO_ERROR_ORDER
    }
    for row in rounds:
        for category in row.get("error_types", ()):
            if category in groups:
                groups[category]["count"] += 1
                groups[category]["rounds"].append(row["round"])
    rank = sorted(SOLO_ERROR_ORDER,
                  key=lambda key: (-groups[key]["count"],
                                   SOLO_ERROR_ORDER.index(key)))
    primary = next((key for key in rank if groups[key]["count"] > 0), None)
    recommendations = [
        {"error_type": key, "label": ERROR_LABELS[key],
         "count": groups[key]["count"], "rounds": list(groups[key]["rounds"]),
         "mode": SOLO_PRACTICE[key]["mode"],
         "focus": SOLO_PRACTICE[key]["focus"]}
        for key in rank
        if groups[key]["count"] > 0 and key in SOLO_PRACTICE
    ]
    return {
        "error_rounds": sum(not row["correct"] for row in rounds),
        "correct_rounds": sum(bool(row["correct"]) for row in rounds),
        "counts": groups,
        "primary_error": primary,
        "primary_label": ERROR_LABELS[primary] if primary else None,
        "recommendations": recommendations,
        "unmapped_error_rounds": groups["other_error"]["count"],
    }



def build_round_review(history: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return stable, JSON-ready compact review plus descriptive change summary.

    - shanten: resulting 13-effective-tile hand after the chosen discard.
    - ukeire: physically unknown effective next-draw tile copies.
    - probability: estimated next-draw improvement for currently unknown tiles.
    - deltas: difference from PREVIOUS COMPLETED DISCARD (new tile was drawn).
    - winning turns have None for post-discard measurements and are excluded
      from shanten/ukeire trends, never mislabeled as a zero-shanten discard.
    """
    rounds: list[dict[str, Any]] = []
    last_discard: dict[str, Any] | None = None
    for item in history:
        number = item["round"]
        action = item["choice"]
        chosen = item.get("selected_candidate")
        alternatives = item.get("analysis", {}).get("candidates", ())
        best = set(item.get("best_actions", ()))
        comparison = [
            entry for entry in alternatives
            if entry["discard"] in best
        ]
        best_ukeire = max(
            (entry["effective_tile_count"] for entry in comparison),
            default=None,
        )
        best_prob = max(
            (entry["next_draw_probability"] for entry in comparison),
            default=None,
        )
        shanten = chosen["shanten"] if chosen else None
        ukeire = chosen["effective_tile_count"] if chosen else None
        probability = chosen["next_draw_probability"] if chosen else None
        baseline = last_discard
        change = (
            {
                "shanten": shanten - baseline["shanten"],
                "effective_tile_count": ukeire - baseline["effective_tile_count"],
                "next_draw_probability": (
                    probability - baseline["next_draw_probability"]
                ),
            }
            if chosen and baseline else None
        )
        errors = diagnose_solo_round(item)
        round_review = {
            "error_types": errors,
            "error_labels": [ERROR_LABELS[e] for e in errors],
            "round": number,
            "drawn_tile": item.get("drawn_tile"),
            "choice": action,
            "correct": bool(item["correct"]),
            "best_actions": list(item.get("best_actions", ())),
            "hand_before": list(item.get("hand_before", ())),
            "is_win": action == "win",
            "win_type": item.get("win_type"),
            "shanten": shanten,
            "effective_tile_count": ukeire,
            "next_draw_probability": probability,
            "effective_details": (
                list(chosen.get("effective_details", ())) if chosen else []
            ),
            "best_effective_tile_count": best_ukeire,
            "best_next_draw_probability": best_prob,
            "shanten_loss": item.get("shanten_loss"),
            "ukeire_loss": item.get("ukeire_loss"),
            "change_from_previous_discard": change,
            "explanation": item.get("explanation", ""),
        }
        rounds.append(round_review)
        if chosen is not None:
            last_discard = round_review

    discards = [row for row in rounds if row["shanten"] is not None]
    first = discards[0] if discards else None
    last = discards[-1] if discards else None
    comparisons = [
        r for r in discards if r["change_from_previous_discard"] is not None
    ]
    progress = {
        "first_shanten": first["shanten"] if first else None,
        "last_shanten": last["shanten"] if last else None,
        "shanten_change": (
            last["shanten"] - first["shanten"] if first and last else None
        ),
        "first_effective_tile_count": (
            first["effective_tile_count"] if first else None
        ),
        "last_effective_tile_count": (
            last["effective_tile_count"] if last else None
        ),
        "effective_tile_count_change": (
            last["effective_tile_count"] - first["effective_tile_count"]
            if first and last else None
        ),
        "first_next_draw_probability": (
            first["next_draw_probability"] if first else None
        ),
        "last_next_draw_probability": (
            last["next_draw_probability"] if last else None
        ),
        "probability_change": (
            last["next_draw_probability"] - first["next_draw_probability"]
            if first and last else None
        ),
        "shanten_improved_rounds": sum(
            r["change_from_previous_discard"]["shanten"] < 0
            for r in comparisons
        ),
        "shanten_worsened_rounds": sum(
            r["change_from_previous_discard"]["shanten"] > 0
            for r in comparisons
        ),
        "shanten_unchanged_rounds": sum(
            r["change_from_previous_discard"]["shanten"] == 0
            for r in comparisons
        ),
        "same_shanten_ukeire_increased_rounds": sum(
            r["change_from_previous_discard"]["shanten"] == 0
            and r["change_from_previous_discard"]["effective_tile_count"] > 0
            for r in comparisons
        ),
        "missed_ukeire_total_at_same_shanten": sum(
            r["ukeire_loss"] or 0 for r in rounds
        ),
        "missed_win_rounds": sum(
            r["choice"] != "win" and "win" in r["best_actions"]
            for r in rounds
        ),
        "discard_rounds": len(discards),
        "win_rounds": sum(r["is_win"] for r in rounds),
    }
    return {"rounds": rounds, "progress": progress,
            "errors": summarize_solo_errors(rounds)}
