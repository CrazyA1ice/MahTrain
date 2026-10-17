"""M3.9 four-policy, four-seat-rotated independent-rule baseline experiment.

Each shuffle seed is a paired cluster of four games. Baseline is an entirely
separate shape-only rule policy, NOT an external trained AI and NOT an
independent scoring oracle. Game rules and cut diagnostics remain those of
the prototype; official settlement and true human win rates are unverified.
"""
from __future__ import annotations

from random import Random
from typing import Any

from .ai import AI_LEVELS
from .ai_tournament import simulate_match
from .ai_independent_scores import controlled_four_policy_scores
from .ai_decision_score_diagnostics import analyze_decision_score_diagnostics

LEVELS=("baseline",*AI_LEVELS)
EXPLORATORY_MIN_SEEDS=5


def independent_lineup(rotation: int) -> list[str]:
    if type(rotation) is not int or rotation not in range(4):
        raise ValueError("four-policy rotation must be in 0..3")
    return [LEVELS[(seat+rotation)%4] for seat in range(4)]


def _empty() -> dict[str, int]:
    return {"exposures":0,"wins":0,"deal_ins":0,
            "discards":0,"minimum_shanten":0,"local_optimal":0}


def _totals(games: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    results={level:_empty() for level in LEVELS}
    for game in games:
        if len(game["assignment"])!=4:
            raise ValueError("invalid four-player assignment")
        for seat,level in enumerate(game["assignment"]):
            if level not in results:
                raise ValueError("unexpected opponent in baseline benchmark")
            results[level]["exposures"]+=1
        for win in game["winners"]:
            s,source=win["seat"],win["source"]
            results[game["assignment"][s]]["wins"]+=1
            if source!=s:
                results[game["assignment"][source]]["deal_ins"]+=1
        for event in game["trace"]:
            if event["action"]!="discard":
                continue
            row=results[game["assignment"][event["seat"]]]
            row["discards"]+=1
            row["minimum_shanten"]+=int(event["shanten_regret"]==0)
            row["local_optimal"]+=int(event["locally_optimal"])
    return results


def _ratio(row: dict[str,int], metric: str) -> float | None:
    numerator,denominator={
        "win_event_fraction":("wins","exposures"),
        "min_shanten_fraction":("minimum_shanten","discards"),
        "local_optimal_fraction":("local_optimal","discards"),
    }[metric]
    return row[numerator]/row[denominator] if row[denominator] else None


def _measure(games: list[dict[str,Any]]) -> dict[str,dict[str,float|None]]:
    totals=_totals(games)
    return {
        level:{metric:(
            round(value,4) if (value:=_ratio(totals[level],metric)) is not None
            else None
        ) for metric in ("win_event_fraction","min_shanten_fraction",
                         "local_optimal_fraction")} for level in LEVELS
    }


def _quantiles(vals: list[float]) -> list[float] | None:
    if not vals:
        return None
    vals.sort()
    n=len(vals)
    return [round(vals[int((n-1)*.025)],4),
            round(vals[int((n-1)*.975)],4)]


def independent_benchmark(seed_start: int=11, seeds: int=1, *,
                          on_match: Any=None, include_traces: bool=False,
                          bootstrap_replicates: int=400) -> dict[str,Any]:
    if (type(seed_start) is not int or not 0<=seed_start<2**32 or
        type(seeds) is not int or not 1<=seeds<=50 or
        seed_start+seeds>2**32):
        raise ValueError("seed_start must be uint32 and seeds 1..50")
    if (type(bootstrap_replicates) is not int or
        not 100<=bootstrap_replicates<=2000):
        raise ValueError("bootstrap replications must be 100..2000")
    by_seed=[]
    all_games=[]
    for seed in range(seed_start,seed_start+seeds):
        batch=[]
        for rotation in range(4):
            match=simulate_match(
                seed,rotation=rotation,lineup=independent_lineup(rotation))
            batch.append(match)
            all_games.append(match)
            if on_match is not None:
                on_match(len(all_games),seeds*4)
        totals=_totals(batch)
        if any(v["exposures"]!=4 for v in totals.values()):
            raise RuntimeError("unbalanced four-seat baseline exposure")
        by_seed.append({
            "seed":seed,"rotations":4,
            "levels":totals,
        })
    official_score_analysis=controlled_four_policy_scores(
        all_games,bootstrap_replicates=bootstrap_replicates)
    decision_score_diagnostics=analyze_decision_score_diagnostics(
        all_games,official_score_analysis)
    totals=_totals(all_games)
    results=_measure(all_games)
    metrics=("win_event_fraction","min_shanten_fraction",
             "local_optimal_fraction")
    comparisons={
        level:{metric:(
            round(results[level][metric]-results["baseline"][metric],4)
            if results[level][metric] is not None
            and results["baseline"][metric] is not None else None
        ) for metric in metrics} for level in AI_LEVELS
    }
    intervals=None
    if seeds>=EXPLORATORY_MIN_SEEDS:
        rng=Random(20261016)
        samples={
            level:{metric:[] for metric in metrics} for level in AI_LEVELS
        }
        for _ in range(bootstrap_replicates):
            chosen=[by_seed[rng.randrange(seeds)] for _ in range(seeds)]
            summed={level:_empty() for level in LEVELS}
            for group in chosen:
                for level in LEVELS:
                    for key,value in group["levels"][level].items():
                        summed[level][key]+=value
            for level in AI_LEVELS:
                for metric in metrics:
                    a=_ratio(summed[level],metric)
                    b=_ratio(summed["baseline"],metric)
                    if a is not None and b is not None:
                        samples[level][metric].append(a-b)
        intervals={
            "method":"whole_shuffle_seed_paired_bootstrap_exploratory",
            "replications":bootstrap_replicates,
            "paired_differences_vs_baseline":{
                level:{metric:_quantiles(values)
                       for metric,values in metrics_map.items()}
                for level,metrics_map in samples.items()
            },
        }
    return {
        "protocol":"independent_shape_baseline_four_seat_rotation_v1",
        "independent_shuffle_seeds":seeds,
        "games":len(all_games),
        "seed_start":seed_start,
        "rotations_per_seed":4,
        "opponents":list(LEVELS),
        "policy_independence":(
            "baseline does not import shanten, efficiency or effective-draw models; "
            "other three AI tiers and diagnostic evaluator remain internal"
        ),
        "terminal_phase_counts":{
            phase:sum(g["terminal_phase"]==phase for g in all_games)
            for phase in ("finished","wall_exhausted")
        },
        "levels":{level:{
            **totals[level],
            **results[level],
        } for level in LEVELS},
        "paired_differences_vs_baseline":comparisons,
        "official_score_analysis":official_score_analysis,
        "decision_score_diagnostics":decision_score_diagnostics,
        "per_seed":by_seed,
        "interval_status":(
            "exploratory_only" if intervals is not None
            else "insufficient_independent_seeds_need_5"
        ),
        "intervals":intervals,
        "matches":all_games if include_traces else [
            {key:value for key,value in game.items()
             if key not in ("trace","public_events","public_replay")}
            for game in all_games
        ],
        "limitations":[
            "four rotations of one shuffle are dependent observations",
            "independent baseline is a specified simple policy, not external trained AI",
            "diagnostic shanten metrics still use project's internal evaluation oracle",
            "win events are not fully settled official win rates",
            "kong amounts remain unpriced; verified active-only exhaustive-draw amounts are included only in official_score_analysis",
            "unresolved wall settlements are excluded by whole shuffle-seed cluster from official score comparison",
        ],
    }
