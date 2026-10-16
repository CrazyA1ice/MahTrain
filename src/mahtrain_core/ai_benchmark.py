"""M3.5 paired, per-position AI cut-quality benchmark; no win-rate claims.

Each level sees the SAME legal seed-derived board state, chosen independently.
Counterfactual 'cleaned' hands have missing-suit tiles exchanged with physical
wall tiles by the FIXTURE BUILDER (never shown to an AI); these are controlled
snapshots, not claims of completed real games or simulation of future draws.
"""
from __future__ import annotations

import copy
from collections import Counter
from statistics import mean
from time import perf_counter_ns
from typing import Any

from .ai import AI_LEVELS, MahjongAgent, visible_tiles
from .efficiency import analyze_discards
from .four_player import FourPlayerOpening
from .rules import TILES, is_legal_win


def _opening_view(seed: int) -> tuple[FourPlayerOpening, int]:
    game=FourPlayerOpening(seed)
    bots={s: MahjongAgent("advanced",seed=seed,seat=s) for s in range(4)}
    for seat in range(4):
        game.select_exchange(seat,bots[seat].exchange(game.private_view(seat)))
    for seat in range(4):
        game.select_missing(seat,bots[seat].missing(game.private_view(seat)))
    if game.phase!="dealer_discard":
        raise RuntimeError("invalid benchmark opening")
    game.debug_tile_counts()
    return game,game.dealer


def _cleaned_view(game: FourPlayerOpening, dealer: int) -> dict[str, Any] | None:
    """Construct physical-count-valid controlled no-missing-suit snapshot."""
    scenario=copy.deepcopy(game)
    missing=scenario.missing_suits[dealer]
    concealed=scenario._hands[dealer]
    removed=[t for t in concealed if t.startswith(missing)]
    if not removed:
        return None
    replacement=[
        t for t in scenario._wall if not t.startswith(missing)
    ][:len(removed)]
    if len(replacement)!=len(removed):
        return None
    for tile in removed:
        concealed.remove(tile)
    for tile in replacement:
        scenario._wall.remove(tile)
        concealed.append(tile)
    scenario._wall.extend(removed)
    scenario.debug_tile_counts()
    view=scenario.private_view(dealer)
    if any(t.startswith(missing) for t in view["hand"]):
        raise RuntimeError("cleaned sample still contains missing suit")
    return view


def sample_views(seed_start: int, seeds: int) -> list[dict[str, Any]]:
    if (type(seed_start) is not int or seed_start<0 or
        type(seeds) is not int or not 1<=seeds<=1000 or
        seed_start+seeds>2**32):
        raise ValueError("seed range must fit 32 bits and seeds be 1..1000")
    samples=[]
    for seed in range(seed_start,seed_start+seeds):
        game,dealer=_opening_view(seed)
        opening=game.private_view(dealer)
        samples.append({"seed":seed,"scenario":"post_exchange_dealer",
                        "view":opening})
        cleaned=_cleaned_view(game,dealer)
        if cleaned is not None:
            samples.append({"seed":seed,"scenario":"controlled_no_missing",
                            "view":cleaned})
    return samples


def benchmark(seed_start: int = 0, seeds: int = 12) -> dict[str, Any]:
    """Return quality metrics paired by sample; latency is machine-dependent.

    'best_shanten_rate' compares with an exhaustive one-discard oracle on the
    SAME hand; 'best_ukeire_rate' also breaks equal-shanten ties by publicly
    remaining effective tile copies. These are NOT opponent win rates.
    """
    samples=sample_views(seed_start,seeds)
    measured={level:[] for level in AI_LEVELS}
    skipped=0
    for sample in samples:
        view=sample["view"]
        hand=view["hand"]
        seat=view["seat"]
        missing=view["missing_suits"][seat]
        melds=view["own_melds"]
        if is_legal_win(hand,melds,missing):
            skipped+=1
            continue
        oracle=analyze_discards(
            hand,melds,missing_suit=missing,
            visible_tiles=visible_tiles(view),
        )
        rows={r["discard"]:r for r in oracle["candidates"]}
        optimum=oracle["minimum_shanten"]
        optimum_ukeire=max(
            item["effective_tile_count"] for item in rows.values()
            if item["shanten"]==optimum
        )
        for level in AI_LEVELS:
            agent=MahjongAgent(level,seed=sample["seed"],seat=seat)
            start=perf_counter_ns()
            chosen=agent.discard(view)
            elapsed_ms=(perf_counter_ns()-start)/1_000_000
            if chosen not in rows:
                raise RuntimeError("AI produced an illegal discard")
            chosen_row=rows[chosen]
            selected_min=chosen_row["shanten"]==optimum
            measured[level].append({
                "seed":sample["seed"],"scenario":sample["scenario"],
                "chosen":chosen, "chosen_shanten":chosen_row["shanten"],
                "minimum_shanten":optimum,
                "chosen_effective_copies":chosen_row["effective_tile_count"],
                "best_effective_copies_at_minimum":optimum_ukeire,
                "best_shanten":selected_min,
                "best_ukeire":(selected_min and
                    chosen_row["effective_tile_count"]==optimum_ukeire),
                "shanten_regret":chosen_row["shanten"]-optimum,
                "ukeire_regret_if_best_shanten":(
                    optimum_ukeire-chosen_row["effective_tile_count"]
                    if selected_min else None),
                "decision_ms":round(elapsed_ms,4),
            })

    stats={}
    for level,records in measured.items():
        if not records:
            raise RuntimeError("benchmark generated no usable decisions")
        n=len(records)
        on_min=[r for r in records if r["best_shanten"]]
        stats[level]={
            "decisions":n,
            "best_shanten_rate":round(sum(r["best_shanten"] for r in records)/n,4),
            "best_ukeire_rate":round(sum(r["best_ukeire"] for r in records)/n,4),
            "average_shanten_regret":round(mean(
                r["shanten_regret"] for r in records),4),
            "average_ukeire_regret_given_best_shanten":(
                round(mean(r["ukeire_regret_if_best_shanten"] for r in on_min),4)
                if on_min else None),
            "average_decision_ms":round(mean(
                r["decision_ms"] for r in records),4),
            "decisions_detail":records,
        }

    return {
        "protocol":"paired_same_public_position_v1",
        "seed_start":seed_start,"seeds":seeds,
        "samples_generated":len(samples),
        "skipped_already_winning":skipped,
        "usable_positions":len(next(iter(measured.values()))),
        "meanings":{
            "best_shanten_rate":"fraction attaining lowest one-cut shanten",
            "best_ukeire_rate":"fraction attaining both lowest shanten and highest public effective copies",
            "average_decision_ms":"local wall-clock policy time only, hardware dependent",
        },
        "limitations":[
            "not a game win-rate estimate",
            "opening dealer snapshots plus controlled no-missing replacements",
            "no future wall or opponent hidden hand supplied to the AI",
            "formal end-of-game settlement still incomplete",
        ],
        "levels":stats,
    }
