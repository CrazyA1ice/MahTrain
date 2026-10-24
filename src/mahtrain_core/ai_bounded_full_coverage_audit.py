"""M4.22 OFFLINE coverage audit of frozen M4.20's actual altered discards.

Only after the original agent has chosen a cut, recompute the same hypothetical
next-draw/next-discard score using *all* PUBLICLY possible improving draw
types. No wall peeking, opponent hands, policy changes or new thresholds.
Historical seeds were already used in M4.20/21: NOT independent validation.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

from .ai import _own_view, visible_tiles
from .ai_action_extended_study import _fixed_lineup
from .ai_bounded_first_split_tenpai_audit import paired_audit_position, FirstSplitBoundedAuditAgent
from .ai_bounded_public_lookahead_paired import (
    MAX_DRAW_TYPES_PER_CUT, MIN_PROJECTED_SCORE_GAIN,
    next_discard_wait_value, projected_branch_score,
)
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_tournament import simulate_match
from .efficiency import effective_draws
from .rules import TILE_INDEX

PROTOCOL = "m422_m420_actual_cut_all_public_effective_draw_type_coverage_v1"
HISTORICAL_CHANGED = (("development", 60001, 1), ("holdout", 61000, 1))
COMPONENTS = ("win_points", "kong_points", "exhaustive_points")


def complete_branch_profile(view: Mapping[str, Any], first_cut: str) -> dict[str, Any]:
    """Reproduce M4.20's top-six numerator and also score ALL effective types.

    The complete *structural proxy* still conditions on an imaginary next draw,
    best-case next cut, and potential waits. It is NOT a calibrated probability,
    official expected cash, or an oracle using the actual remaining wall.
    """
    hand, melds, missing = _own_view(view)
    if first_cut not in hand:
        raise ValueError("cut not in authorized own hand")
    cap = (view.get("win_ledger") or {}).get("fan_cap", 3)
    if type(cap) is not int or not 0 <= cap <= 12:
        raise ValueError("invalid authoritative cap")
    after = list(hand)
    after.remove(first_cut)
    seen = [*visible_tiles(view), first_cut]
    info = effective_draws(after, melds, missing, seen)
    if info["shanten"] != 1:
        raise ValueError("not exact one-shanten after first cut")
    details = sorted(
        info["effective_details"],
        key=lambda d: (-d["remaining"], TILE_INDEX[d["tile"]]),
    )
    if len(details) > len(TILE_INDEX):
        raise RuntimeError("duplicate effective draw tile types")
    selected_mass = total_mass = 0
    selected_score = complete_score = 0.0
    extra_second_cuts = 0
    for i, item in enumerate(details):
        copies = item["remaining"]
        if type(copies) is not int or copies <= 0:
            raise RuntimeError("invalid publicly possible draw copies")
        potential, examined = next_discard_wait_value(
            after, item["tile"], melds, missing, seen, cap,
        )
        if not isfinite(potential) or potential < 0:
            raise RuntimeError("invalid next-discard structural score")
        weighted = copies * potential
        complete_score += weighted
        total_mass += copies
        if i < MAX_DRAW_TYPES_PER_CUT:
            selected_score += weighted
            selected_mass += copies
        else:
            extra_second_cuts += examined
    if total_mass != info["effective_tile_count"]:
        raise RuntimeError("public effective draw mass not conserved")
    frozen = projected_branch_score(view, first_cut)
    if (round(selected_score, 5) != frozen["proxy"]
            or selected_mass != frozen["draw_copy_mass"]
            or len(details[:MAX_DRAW_TYPES_PER_CUT]) != frozen["draw_types"]
            or total_mass != frozen["all_effective_copies"]):
        raise RuntimeError("full branch audit failed to reproduce frozen M4.20")
    if complete_score + 1e-8 < selected_score:
        raise RuntimeError("unexpected negative omitted structural mass")
    return {
        "truncated_proxy": frozen["proxy"],
        "complete_proxy": round(complete_score, 5),
        "omitted_proxy": round(complete_score - selected_score, 5),
        "all_effective_draw_types": len(details),
        "scanned_draw_types": frozen["draw_types"],
        "omitted_draw_types": len(details) - frozen["draw_types"],
        "all_effective_copies": total_mass,
        "scanned_copies": selected_mass,
        "coverage_fraction": frozen["coverage_fraction"],
        "additional_second_cuts_checked": extra_second_cuts,
    }


class FullCoverageAuditAgent(FirstSplitBoundedAuditAgent):
    """Never changes the selected action; only annotates actual M4.20 changes."""

    def __init__(self, *, seed: int, seat: int, arm: str) -> None:
        super().__init__(seed=seed, seat=seat, arm=arm)
        self.coverage_records: list[dict[str, Any]] = []

    def discard(self, view: Mapping[str, Any]) -> str:
        previous = len(self.anonymous_changes)
        selected = super().discard(view)
        if len(self.anonymous_changes) == previous:
            return selected
        if self.arm != "bounded_two_transition" or len(self.anonymous_changes) != previous + 1:
            raise RuntimeError("only an actual candidate cut may trigger audit")
        ranked = self._last_discard_scores
        original = ranked[0]["discard"]
        if selected == original:
            raise RuntimeError("annotated cut did not actually change")
        baseline = complete_branch_profile(view, original)
        candidate = complete_branch_profile(view, selected)
        base_total = baseline["complete_proxy"]
        candidate_total = candidate["complete_proxy"]
        ratio = candidate_total / base_total if base_total > 0 else None
        if ratio is not None and not isfinite(ratio):
            raise RuntimeError("invalid complete proxy ratio")
        prior = self.anonymous_changes[-1]
        self.coverage_records.append({
            "own_discard_ordinal": prior["own_discard_ordinal"],
            "original_truncated_ratio": prior["projected_ratio"],
            "full_branch_ratio": round(ratio, 5) if ratio is not None else None,
            "full_branch_retains_gain_gate": (
                candidate_total > base_total
                and candidate_total + 1e-8 >= MIN_PROJECTED_SCORE_GAIN * base_total
                if base_total > 0 else False
            ),
            "reverses_original_proxy_order": candidate_total <= base_total,
            "baseline": baseline,
            "candidate": candidate,
        })
        return selected


def historical_changed_position(seed: int, rotation: int) -> dict[str, Any]:
    """Recompute only a known M4.20 changed position, with authoritative checks.

    Private game traces never leave the simulator. The original M4.21 helper
    independently replays both official arms and checks the first true split.
    """
    if (type(seed) is not int or type(rotation) is not int
            or not 0 <= seed < 2**32 or rotation not in range(4)):
        raise ValueError("invalid historical seed or seating rotation")
    prior = paired_audit_position(seed, rotation)
    if prior["actual_changes"] == 0 or prior["first_split"] is None:
        raise RuntimeError("selected historical position was not truly changed")
    lineup, seat = _fixed_lineup(rotation)
    if seat != prior["challenge_seat"]:
        raise RuntimeError("seat rotation did not match prior audit")
    agent = FullCoverageAuditAgent(seed=seed, seat=seat, arm="bounded_two_transition")
    match = simulate_match(
        seed, rotation=rotation % 3, lineup=lineup, offline_kong_base=1,
        offline_agent_overrides={seat: agent},
    )
    official = _official_outcome(match, seat, lineup)
    original = prior["arms"]["bounded_two_transition"]
    if (match["physical_count"] != 108 or official != original["official"]
            or match["terminal_phase"] != original["terminal_phase"]
            or len(agent.coverage_records) != prior["actual_changes"]
            or len(agent.anonymous_changes) != prior["actual_changes"]):
        raise RuntimeError("audit drifted from official frozen M4.21 full-game replay")
    first = prior["first_split"]
    if (agent.coverage_records[0]["own_discard_ordinal"]
            != first["own_discard_ordinal"]
            or agent.coverage_records[0]["original_truncated_ratio"]
            != first["first_policy_change"]["projected_ratio"]):
        raise RuntimeError("not the same actual first cut")
    delta = prior["authoritative_deltas"]
    if delta["official_net"] != sum(delta[k] for k in COMPONENTS):
        raise RuntimeError("official M4.21 ledger components do not reconcile")
    return {
        "seed": seed,
        "rotation": rotation,
        "challenge_seat": seat,
        "actual_changes": prior["actual_changes"],
        "original_first_split_event_ordinal": first["event_ordinal"],
        "coverage": agent.coverage_records,
        "official_component_deltas": {k: delta[k] for k in ("official_net", *COMPONENTS)},
        "retrospective_not_independent_validation": True,
        "online_ai_modified": False,
        "local_causal_ev": None,
    }


def study() -> dict[str, Any]:
    return {
        "protocol": PROTOCOL,
        "historical_selected_after_m421": True,
        "retrospective_not_independent_validation": True,
        "online_ai_modified": False,
        "positions": [
            {"cohort": cohort, **historical_changed_position(seed, rotation)}
            for cohort, seed, rotation in HISTORICAL_CHANGED
        ],
        "limitations": [
            "Only two already-identified historical changed games are audited; this is NOT a new holdout.",
            "Full effective type coverage remains a hypothetical public draw and best-case future cut proxy.",
            "All possible public effective tiles are not an actual draw probability distribution.",
            "A numerical rank reversal is not proof of a better deployed action or outcome.",
            "Official scores are whole-match outcomes, not one-cut causal expected cash.",
            "No raw hand, tile, hidden wall, opponents' holdings or full traces leave the simulator.",
        ],
    }
