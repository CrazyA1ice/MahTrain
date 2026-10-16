"""M3.13 reproducible, physically possible public-meld pressure fixtures.

These are *constructed decision snapshots*, not logs from a naturally played
match. Hand, public melds and discard choices are checked by the SAME
shanten/ukeire solver as the production AI, with no patched oracle.
Snapshots prove decision-rule reachability, not downstream win improvement.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from .ai import AblationMahjongAgent, MahjongAgent, visible_tiles
from .ai_pressure_diagnostics import diagnose_pressure_tiebreak
from .efficiency import analyze_discards
from .rules import TILE_INDEX, TILES, _validate

SCENARIOS = (
    "two_same_suit_pungs",
    "one_pung_only",
    "pungs_across_opponents",
    "two_pungs_in_lower_priority_suit",
    "two_pungs_owner_already_won",
)

# Four complete sequences + two singletons; only the last two tiles can
# make a ready hand by discarding one, with symmetric three-copy waits.
# No tile exceeds four physical copies.
HAND = tuple(
    f"{s}{n}" for s in ("m", "s")
    for n in (4, 5, 6) for _ in range(2)
) + ("m9", "s9")


def pressure_scenario_view(name: str) -> dict[str, Any]:
    if type(name) is not str or name not in SCENARIOS:
        raise ValueError("unknown public pressure fixture")
    melds: list[list[dict[str, str]]] = [[], [], [], []]
    if name == "two_same_suit_pungs" or name == "two_pungs_owner_already_won":
        melds[1] = [{"type": "peng", "tile": "m1"},
                    {"type": "peng", "tile": "m2"}]
    elif name == "one_pung_only":
        melds[1] = [{"type": "peng", "tile": "m1"}]
    elif name == "pungs_across_opponents":
        melds[1] = [{"type": "peng", "tile": "m1"}]
        melds[2] = [{"type": "peng", "tile": "m2"}]
    else:
        melds[1] = [{"type": "peng", "tile": "s1"},
                    {"type": "peng", "tile": "s2"}]
    view = {
        "seat": 0,
        # Mid-game draw/discard, not the dealer's first turn: opponents
        # could only have completed the public pungs after earlier discards.
        "phase": "await_discard",
        "hand": sorted(HAND, key=TILE_INDEX.__getitem__),
        "own_melds": [],
        # The exposed pungs are not of the opponent's declared missing suit.
        "missing_suits": ["p",
                          "m" if name == "two_pungs_in_lower_priority_suit"
                          else "s", "p", "p"],
        "discards": [],
        "melds": melds,
        "won": [False, name == "two_pungs_owner_already_won", False, False],
    }
    validate_snapshot(view)
    return view


def validate_snapshot(view: dict[str, Any]) -> dict[str, int]:
    """Check real 108-tile physical feasibility and post-dingque constraints.

    A complete counterfactual wall / full historical turn sequence is NOT
    synthesized. We validate only what this privacy-limited decision view
    itself claims to know.
    """
    own = view["seat"]
    known = [*view["hand"]]
    if len(view["hand"]) + 3*len(view["own_melds"]) != 14:
        raise ValueError("not an effective 14-tile hand")
    if any(t[0] == view["missing_suits"][own] for t in view["hand"]):
        raise ValueError("fixture hand must have completed dingque")
    _validate(view["hand"], view["own_melds"],
              view["missing_suits"][own])
    for seat, exposed in enumerate(view["melds"]):
        if seat == own:
            continue
        if len(exposed) > 4:
            raise ValueError("more than four public groups")
        for m in exposed:
            if m.get("type") != "peng" or m.get("tile") not in TILE_INDEX:
                raise ValueError("fixture requires publicly known pungs")
            if m["tile"][0] == view["missing_suits"][seat]:
                raise ValueError("exposed pung conflicts with opponent dingque")
            known.extend([m["tile"]]*3)
    counts = Counter(known)
    if len(known) > 108 or any(counts[t] > 4 for t in TILES):
        raise ValueError("infeasible physical tile inventory")
    if view["phase"] not in ("dealer_discard", "await_discard"):
        raise ValueError("not an active discard state")
    return {"known_physical_tiles": len(known),
            "unknown_physical_tiles": 108-len(known),
            "maximum_tile_multiplicity": max(counts.values())}


def probe_pressure_scenario(name: str) -> dict[str, Any]:
    """One genuine oracle evaluation, two real agents, privacy-safe result."""
    view = pressure_scenario_view(name)
    oracle = analyze_discards(
        view["hand"], view["own_melds"],
        missing_suit=view["missing_suits"][view["seat"]],
        visible_tiles=visible_tiles(view),
    )
    if oracle["status"] != "choose_discard":
        raise RuntimeError("expected non-winning 14-effective-tile hand")
    full = MahjongAgent("challenge", seed=17, seat=0).discard(view)
    no_pressure = AblationMahjongAgent(
        "challenge_no_pressure", seed=17, seat=0,
    ).discard(view)
    full_probe = diagnose_pressure_tiebreak(
        view, oracle, full, policy="challenge"
    )
    excluded_probe = diagnose_pressure_tiebreak(
        view, oracle, no_pressure, policy="challenge_no_pressure"
    )
    if (full_probe["choice_would_change"] != (full != no_pressure)
            or excluded_probe["choice_would_change"] != (full != no_pressure)):
        raise RuntimeError("diagnostic disagrees with actual AI cuts")
    return {
        "scenario": name,
        "physically_feasible": True,
        "known_physical_tiles": validate_snapshot(view)["known_physical_tiles"],
        "opponent_open_pungs": sum(len(m) for m in view["melds"][1:]),
        "public_pressure_on_active_opponent": any(
            len(m) >= 2 for seat, m in enumerate(view["melds"])
            if seat != view["seat"] and not view["won"][seat]
        ),
        **full_probe,
        "no_pressure_policy_actual_changed": excluded_probe["actual_choice_changed"],
        "same_state_ai_choices_differ": full != no_pressure,
    }


def pressure_scenario_matrix() -> dict[str, Any]:
    rows = [probe_pressure_scenario(name) for name in SCENARIOS]
    return {
        "protocol": "m313_physically_feasible_constructed_public_snapshot_v1",
        "source": "constructed validated 14-effective-tile snapshots; not sampled match outcomes",
        "scenarios": rows,
        "summary": {
            "scenarios": len(rows),
            "pressure_active": sum(r["public_pressure_on_active_opponent"] for r in rows),
            "pressure_discriminates": sum(r["public_pressure_discriminates"] for r in rows),
            "choice_would_change": sum(r["choice_would_change"] for r in rows),
        },
        "limitations": [
            "physical inventory and local decision legality checked, not full replay reachability",
            "no shadow tile, opponent concealed hand or future wall exported",
            "a change of discard is not evidence of better safety or later wins",
        ],
    }
