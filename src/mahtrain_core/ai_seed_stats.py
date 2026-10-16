"""M3.8 seed-clustered, paired AI event statistics.

Three seat rotations with the SAME shuffled tiles are one correlated
experimental unit. This module reports descriptive per-seed aggregates
and (for >=5 distinct seeds) explicitly exploratory cluster-bootstrap
intervals. No formal, independent human-game win-rate claims.
"""
from __future__ import annotations

from collections import defaultdict
from random import Random
from typing import Any, Sequence

from .ai import AI_LEVELS

BOOTSTRAP_REPLICATES = 400
MIN_INTERVAL_SEEDS = 5


def _metric(groups: Sequence[dict[str, Any]], level: str,
            metric: str) -> float | None:
    rows=[g["levels"][level] for g in groups]
    if metric=="win_event_fraction":
        num=sum(row["win_events"] for row in rows)
        den=sum(row["seat_exposures"] for row in rows)
    elif metric=="local_optimal_fraction":
        num=sum(row["locally_optimal_discards"] for row in rows)
        den=sum(row["discards"] for row in rows)
    elif metric=="min_shanten_fraction":
        num=sum(row["min_shanten_discards"] for row in rows)
        den=sum(row["discards"] for row in rows)
    else:
        raise ValueError("unknown seed-cluster statistic")
    return num/den if den else None


def _interval(values: list[float]) -> list[float]:
    values.sort()
    if not values:
        raise ValueError("cannot calculate interval from zero replications")
    n=len(values)
    return [
        round(values[int((n-1)*0.025)],4),
        round(values[int((n-1)*0.975)],4),
    ]


def analyze_seed_clusters(
    matches: Sequence[dict[str, Any]],
    *, bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    if (type(bootstrap_replicates) is not int
            or not 100<=bootstrap_replicates<=2000):
        raise ValueError("bootstrap_replicates must be an integer 100..2000")
    by_seed: dict[int,list[dict[str,Any]]] = defaultdict(list)
    for match in matches:
        seed=match["seed"]
        if type(seed) is not int or not 0<=seed<2**32:
            raise ValueError("invalid seed")
        by_seed[seed].append(match)
    if not by_seed:
        raise ValueError("no AI matches supplied")

    groups=[]
    for seed in sorted(by_seed):
        games=by_seed[seed]
        if sorted(g["rotation"] for g in games)!=[0,1,2]:
            raise ValueError("each seed must have exactly three rotations")
        lv={level:{
            "seat_exposures":0,"win_events":0,"deal_in_events":0,
            "discards":0,"min_shanten_discards":0,
            "locally_optimal_discards":0,
        } for level in AI_LEVELS}
        for match in games:
            if len(match["assignment"])!=4:
                raise ValueError("each match needs four assigned seats")
            if any(level not in lv for level in match["assignment"]):
                raise ValueError("invalid AI difficulty in match")
            for level in match["assignment"]:
                lv[level]["seat_exposures"]+=1
            for win in match["winners"]:
                seat=win["seat"]
                source=win["source"]
                if (type(seat) is not int or seat not in range(4) or
                    type(source) is not int or source not in range(4)):
                    raise ValueError("invalid winner or source seat")
                lv[match["assignment"][seat]]["win_events"]+=1
                if source != seat:
                    lv[match["assignment"][source]]["deal_in_events"]+=1
            for event in match["trace"]:
                if event["action"]!="discard":
                    continue
                seat=event["seat"]
                if type(seat) is not int or seat not in range(4):
                    raise ValueError("invalid discard seat")
                row=lv[match["assignment"][seat]]
                row["discards"]+=1
                row["min_shanten_discards"]+=int(
                    event["shanten_regret"]==0)
                row["locally_optimal_discards"]+=int(
                    bool(event["locally_optimal"]))
        for level,row in lv.items():
            if row["seat_exposures"]!=4:
                raise ValueError("seat rotations must be balanced per seed")
            row["win_event_fraction"]=round(
                row["win_events"]/row["seat_exposures"],4)
            row["local_optimal_fraction"]=(
                round(row["locally_optimal_discards"]/row["discards"],4)
                if row["discards"] else None)
            row["min_shanten_fraction"]=(
                round(row["min_shanten_discards"]/row["discards"],4)
                if row["discards"] else None)
        groups.append({"seed":seed,"games":3,"levels":lv})

    count=len(groups)
    metrics=("win_event_fraction","local_optimal_fraction",
             "min_shanten_fraction")
    summary={
        metric:{level:(
            round(value,4) if (value:=_metric(groups,level,metric)) is not None
            else None
        ) for level in AI_LEVELS} for metric in metrics
    }
    comparisons={
        metric:{f"challenge_minus_{other}":(
            round(summary[metric]["challenge"]-summary[metric][other],4)
            if (summary[metric]["challenge"] is not None and
                summary[metric][other] is not None) else None
        ) for other in ("basic","advanced")} for metric in metrics
    }
    intervals=None
    if count>=MIN_INTERVAL_SEEDS:
        rng=Random(20261016)
        draws={
            metric:{
                level:[] for level in AI_LEVELS
            } for metric in metrics
        }
        differences={
            metric:{
                f"challenge_minus_{other}":[] for other in
                ("basic","advanced")
            } for metric in metrics
        }
        for _ in range(bootstrap_replicates):
            selection=[groups[rng.randrange(count)] for _ in range(count)]
            for metric in metrics:
                values={level:_metric(selection,level,metric) for level in AI_LEVELS}
                for level,value in values.items():
                    if value is not None:
                        draws[metric][level].append(value)
                for other in ("basic","advanced"):
                    if values["challenge"] is not None and values[other] is not None:
                        differences[metric][f"challenge_minus_{other}"].append(
                            values["challenge"]-values[other])
        intervals={
            "level_intervals":{
                metric:{level:(_interval(values) if values else None)
                        for level,values in by_level.items()}
                for metric,by_level in draws.items()
            },
            "paired_difference_intervals":{
                metric:{key:(_interval(values) if values else None)
                        for key,values in rows.items()}
                for metric,rows in differences.items()
            },
            "replications":bootstrap_replicates,
            "method":"paired_shuffle_seed_cluster_bootstrap_exploratory",
        }

    return {
        "independence_unit":"shuffle_seed",
        "distinct_seed_count":count,
        "rotations_per_seed":3,
        "per_seed":groups,
        "pooled_event_rates":summary,
        "paired_challenge_differences":comparisons,
        "intervals":intervals,
        "interval_status":(
            "exploratory_only" if intervals is not None
            else f"insufficient_distinct_seeds_need_{MIN_INTERVAL_SEEDS}"
        ),
        "limitations":[
            "three rotations of one seed are dependent, not three independent samples",
            "bootstrap estimates reflect variation over selected shuffle seeds only",
            "small seed samples, heuristic opponents and draft rules limit inference",
            "win event frequencies are NOT complete-settlement or human-vs-AI win rates",
            "shared policy evaluation targets prevent external skill validation",
        ],
    }
