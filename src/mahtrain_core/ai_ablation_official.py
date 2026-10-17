"""M3.33: auditable official scores for five-policy, four-seat incomplete blocks.

One initial shuffle seed => five dependent rotated games; each strategy
occupies every seat exactly once. Exclude the WHOLE seed if any exhausted-wall
payment cannot be verified. No private hands, shadow discards or future wall
orders appear in results.
"""
from __future__ import annotations

from collections import defaultdict
from random import Random
from typing import Any

POLICIES = ("baseline", "advanced", "challenge_no_ukeire",
            "challenge_no_pressure", "challenge")
CONTRASTS = (
    ("challenge", "challenge_no_pressure"),
    ("challenge", "challenge_no_ukeire"),
    ("challenge_no_pressure", "advanced"),
    ("challenge_no_ukeire", "advanced"),
    ("challenge", "baseline"),
)
MIN_INTERVAL_SEEDS = 5


def _lineup(rotation: int) -> list[str]:
    return [POLICIES[(seat + rotation) % 5] for seat in range(4)]


def _quantiles(values: list[float]) -> list[float] | None:
    if not values:
        return None
    values.sort()
    n = len(values)
    return [round(values[int((n - 1) * .025)], 3),
            round(values[int((n - 1) * .975)], 3)]


def _empty() -> dict[str, int]:
    return {"seat_exposures": 0, "official_total": 0,
            "discards": 0, "min_shanten_cuts": 0,
            "local_optimal_cuts": 0, "effective_copies_total": 0,
            "deal_in_events": 0}


def _validate_game(game: dict) -> None:
    seed, rotation = game.get("seed"), game.get("rotation")
    if (type(seed) is not int or not 0 <= seed < 2**32 or
            type(rotation) is not int or rotation not in range(5) or
            game.get("assignment") != _lineup(rotation)):
        raise ValueError("bad seed or unbalanced five-policy rotation")
    rules = game.get("scoring_rules")
    if (type(rules) is not dict or
            type(rules.get("room_coefficient")) is not int or
            not 1 <= rules["room_coefficient"] <= 10**6 or
            type(rules.get("fan_cap")) is not int or
            not 0 <= rules["fan_cap"] <= 12 or
            rules.get("kong_base") is not None):
        raise ValueError("fixed valid room rules and unpriced kongs required")
    phase, posted = game.get("terminal_phase"), game.get("official_exhaustive_posted")
    if phase not in ("finished", "wall_exhausted") or type(posted) is not bool:
        raise ValueError("unknown terminal settlement state")
    hu, settled = game.get("partial_win_balances"), game.get("official_settled_balances")
    for row in (hu, settled):
        if (type(row) is not list or len(row) != 4 or
                any(type(x) is not int for x in row) or sum(row) != 0):
            raise ValueError("HU and official payoffs require four integer zero-sum seats")
    if phase == "finished" and (posted or settled != hu):
        raise ValueError("finished non-exhaustive game cannot charge wall money")
    if phase == "wall_exhausted" and not posted and settled != hu:
        raise ValueError("unverified wall-draw cannot pretend settlement was posted")
    if type(game.get("winners")) is not list or type(game.get("trace")) is not list:
        raise ValueError("missing authoritative post-game decisions")


def _diagnostics(matches: list[dict]) -> dict[str, dict]:
    rows = {level: _empty() for level in POLICIES}
    for game in matches:
        assignment = game["assignment"]
        for level in assignment:
            rows[level]["seat_exposures"] += 1
        for win in game["winners"]:
            if (type(win) is not dict or
                    type(win.get("seat")) is not int or
                    type(win.get("source")) is not int or
                    win["seat"] not in range(4) or
                    win["source"] not in range(4)):
                raise ValueError("invalid finished game win event")
            if win["seat"] != win["source"]:
                rows[assignment[win["source"]]]["deal_in_events"] += 1
        for event in game["trace"]:
            if type(event) is not dict:
                raise ValueError("malformed post-game decision")
            if event.get("action") != "discard":
                continue
            seat = event.get("seat")
            if type(seat) is not int or seat not in range(4):
                raise ValueError("invalid discard seat")
            level = assignment[seat]
            if event.get("level", level) != level:
                raise ValueError("wrong AI attribution")
            regret = event.get("shanten_regret")
            optimal = event.get("locally_optimal")
            copies = event.get("effective_copies")
            if (type(regret) is not int or not 0 <= regret <= 20 or
                    type(optimal) is not bool or
                    type(copies) is not int or not 0 <= copies <= 108):
                raise ValueError("invalid post-game internal efficiency diagnostic")
            row = rows[level]
            row["discards"] += 1
            row["min_shanten_cuts"] += int(regret == 0)
            row["local_optimal_cuts"] += int(optimal)
            row["effective_copies_total"] += copies
        for seat, level in enumerate(assignment):
            rows[level]["official_total"] += game["official_settled_balances"][seat]
    return rows


def analyze_official_ablation(
    matches: list[dict], *, bootstrap_replicates: int = 400,
) -> dict[str, Any]:
    """Compare component removal on matched valid seed clusters only."""
    if (type(bootstrap_replicates) is not int or
            not 100 <= bootstrap_replicates <= 2000):
        raise ValueError("bootstrap_replicates must be integer 100..2000")
    if type(matches) is not list or not matches:
        raise ValueError("experiment requires games")
    groups: dict[int, dict[int, dict]] = defaultdict(dict)
    fixed = None
    for game in matches:
        if type(game) is not dict:
            raise ValueError("game must be dictionary")
        _validate_game(game)
        seed, rotation = game["seed"], game["rotation"]
        if rotation in groups[seed]:
            raise ValueError("duplicate rotation for seed")
        groups[seed][rotation] = game
        rules = game["scoring_rules"]
        config = (rules["room_coefficient"], rules["fan_cap"])
        if fixed is None:
            fixed = config
        elif config != fixed:
            raise ValueError("mixed rules invalidate paired official scores")
    seeds = sorted(groups)
    if (seeds != list(range(seeds[0], seeds[0] + len(seeds))) or
            any(sorted(rotations) != list(range(5)) for rotations in groups.values())):
        raise ValueError("every contiguous seed requires all five rotated matches")
    accepted = []
    excluded = []
    accepted_games = []
    all_totals = {level: _empty() for level in POLICIES}
    per_seed = []
    for seed in seeds:
        games = [groups[seed][r] for r in range(5)]
        if any(game["terminal_phase"] == "wall_exhausted" and
               not game["official_exhaustive_posted"] for game in games):
            excluded.append(seed)
            continue
        counts = _diagnostics(games)
        if (sum(row["official_total"] for row in counts.values()) != 0 or
                any(row["seat_exposures"] != 4 for row in counts.values())):
            raise ValueError("unbalanced scores or seat exposure")
        for level, row in counts.items():
            for key, value in row.items():
                all_totals[level][key] += value
        accepted.append(seed)
        accepted_games.extend(games)
        per_seed.append({"seed": seed,
                         "levels": {
                             level: {
                                 "seat_exposures": 4,
                                 "official_total": counts[level]["official_total"],
                                 "official_mean_per_exposure": round(
                                     counts[level]["official_total"]/4,3),
                                 "discards": counts[level]["discards"],
                                 "min_shanten_cuts": counts[level]["min_shanten_cuts"],
                                 "local_optimal_cuts": counts[level]["local_optimal_cuts"],
                                 "effective_copies_total":
                                     counts[level]["effective_copies_total"],
                                 "deal_in_events": counts[level]["deal_in_events"],
                             } for level in POLICIES}})
    n = len(accepted)
    summaries = {}
    for level in POLICIES:
        row = all_totals[level]
        cuts = row["discards"]
        summaries[level] = {
            **row,
            "official_mean_per_exposure": (
                round(row["official_total"] / (4*n), 3) if n else None),
            "min_shanten_fraction": (
                round(row["min_shanten_cuts"]/cuts,4) if cuts else None),
            "local_optimal_fraction": (
                round(row["local_optimal_cuts"]/cuts,4) if cuts else None),
            "mean_effective_copies": (
                round(row["effective_copies_total"]/cuts,3) if cuts else None),
            "deal_in_events_per_100_discards": (
                round(100*row["deal_in_events"]/cuts,3) if cuts else None),
        }
    comparisons = {}
    for left, right in CONTRASTS:
        a,b=summaries[left],summaries[right]
        key=left+"_vs_"+right
        comparisons[key]={
            "official_mean_delta": (
                round(a["official_mean_per_exposure"]-
                      b["official_mean_per_exposure"],3) if n else None),
            "min_shanten_fraction_delta": (
                round(a["min_shanten_fraction"]-b["min_shanten_fraction"],4)
                if a["min_shanten_fraction"] is not None and
                   b["min_shanten_fraction"] is not None else None),
            "effective_copies_delta": (
                round(a["mean_effective_copies"]-b["mean_effective_copies"],3)
                if a["mean_effective_copies"] is not None and
                   b["mean_effective_copies"] is not None else None),
            "deal_in_per_100_delta": (
                round(a["deal_in_events_per_100_discards"]-
                      b["deal_in_events_per_100_discards"],3)
                if a["deal_in_events_per_100_discards"] is not None and
                   b["deal_in_events_per_100_discards"] is not None else None),
            "score_sign_counts": {"positive":0,"negative":0,"tied":0},
            "quality_higher_score_lower_seeds": 0,
            "comparable_quality_seeds":0,
        }
        for seed in per_seed:
            aa, bb = seed["levels"][left], seed["levels"][right]
            diff=aa["official_total"]-bb["official_total"]
            comparisons[key]["score_sign_counts"][
                "positive" if diff>0 else "negative" if diff<0 else "tied"
            ]+=1
            if aa["discards"] and bb["discards"]:
                comparisons[key]["comparable_quality_seeds"]+=1
                if (aa["min_shanten_cuts"]*bb["discards"] >
                        bb["min_shanten_cuts"]*aa["discards"] and diff<0):
                    comparisons[key]["quality_higher_score_lower_seeds"]+=1
    intervals = None
    if n >= MIN_INTERVAL_SEEDS:
        rng=Random(20261017)
        boot={key:[] for key in comparisons}
        for _ in range(bootstrap_replicates):
            sampled=[per_seed[rng.randrange(n)] for _ in range(n)]
            averages={
                level:sum(r["levels"][level]["official_total"] for r in sampled)/(4*n)
                for level in POLICIES
            }
            for left,right in CONTRASTS:
                boot[left+"_vs_"+right].append(averages[left]-averages[right])
        intervals={
            "method":"paired_initial_shuffle_cluster_bootstrap_exploratory",
            "replications":bootstrap_replicates,
            "official_mean_delta":{key:_quantiles(vals) for key,vals in boot.items()},
        }
    if sum(row["official_total"] for row in summaries.values())!=0:
        raise ValueError("five-policy official outcomes must remain zero sum")
    return {
        "protocol":"five_policy_incomplete_block_official_a_v1",
        "requested_seeds":len(seeds),
        "valid_seeds":n,
        "excluded_seed_count":len(excluded),
        "excluded_seed_ids":excluded,
        "games_per_seed":5,
        "complete_games":5*n,
        "independence_unit":"initial_shuffle_seed",
        "room_coefficient":fixed[0], "fan_cap":fixed[1],
        "kong_included":False, "zero_sum":True,
        "levels":summaries,
        "contrasts":comparisons,
        "per_seed":per_seed,
        "interval_status":("exploratory_only" if intervals else
                           "insufficient_valid_independent_seeds_need_5"),
        "intervals":intervals,
        "limitations":[
            "one initial shuffle gives five dependent incomplete-block games",
            "four seats per policy per seed; one policy rests each rotation",
            "verified rule-A exhaustive payouts and HU count as official, kong money excluded",
            "one unresolved terminal wall excludes the entire five-game seed",
            "effective-copies measures internally scored available tiles, not future draws",
            "deal-in events per 100 discards are descriptive, NOT prediction risk",
            "paired different policies diverge in future draws, not identical causal trials",
            "seed-cluster bootstrap bounds are exploratory, not human win-rate claims",
            "concealed per-decision data never leaves server-side aggregate analyzer",
        ],
    }
