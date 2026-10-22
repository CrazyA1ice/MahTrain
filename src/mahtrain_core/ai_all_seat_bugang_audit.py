"""M4.02: all-seat, pre-decision bu-gang exposure -> potential Hu -> real settlement.

OFFLINE only. Four players are observed in each naturally shuffled match without
changing a single action. A tile identity is retained solely in a trusted
in-memory dictionary for matching the same public peng across turns and its
eventual actual declaration. No private tile or opponent hand is exported.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .ai_action_extended_study import _fixed_lineup
from .ai_bugang_repeat_risk import _audited_public_bugang
from .ai_public_bugang_rob_pilot import (
    BANDS, _sealed_potential_robbers, public_bugang_features,
)
from .ai_tournament import simulate_match

PROTOCOL="m402_all_seat_prechoice_bugang_legal_vs_realized_v1"


def observe_game(seed:int, rotation:int)->dict[str,Any]:
    if type(seed) is not int or not 0<=seed<2**32:
        raise ValueError("invalid unsigned initial shuffle seed")
    lineup,challenge=_fixed_lineup(rotation)
    first:dict[tuple[int,str],dict[str,Any]]={}
    latest:dict[tuple[int,str],dict[str,Any]]={}
    public_first=[]
    counters=Counter()

    def before_action(game:Any)->None:
        if game.phase not in ("await_discard","dealer_discard"):
            return
        seat=game.turn
        if seat is None or game._won[seat]:
            return
        options=[row for row in game.kong_options(seat)
                 if row["type"]=="bu_gang"]
        if not options:
            return
        view=game.private_view(seat)
        if view["can_self_draw_win"]:
            return
        if any(row not in view["kong_options"] for row in options):
            raise RuntimeError("observer's legal Kong options disagree with owner")
        board=game.public_state()
        for choice in options:
            tile=choice["tile"]
            key=(seat,tile)  # never returned or hashed into output
            features=public_bugang_features(board,seat,tile)
            hidden=_sealed_potential_robbers(game,seat,tile)
            if not 0<=hidden<=features["dingque_eligible_opponents"]:
                raise RuntimeError("sealed label conflicts with public dingque")
            current={
                "seat":seat,"level":lineup[seat],"features":features,
                "potential_robbers":hidden,"rob_possible":int(hidden>0),
            }
            counters["eligible_candidate_windows"]+=1
            counters["eligible_windows_by_level_"+lineup[seat]]+=1
            if key not in first:
                counters["first_distinct"]+=1
                counters["first_distinct_by_level_"+lineup[seat]]+=1
                first[key]=current
                public_first.append(current)
            else:
                counters["repeated_candidate_windows"]+=1
                if (first[key]["rob_possible"]!=current["rob_possible"]):
                    counters["repeat_label_differs_from_first"]+=1
            latest[key]=current

    outcome=simulate_match(seed,rotation=rotation%3,lineup=lineup,
                           offline_kong_base=1,
                           offline_observer=before_action)
    if (counters["eligible_candidate_windows"]!=counters["first_distinct"]+
        counters["repeated_candidate_windows"]):
        raise RuntimeError("same-bu-gang private de-duplication failed")

    # Match the actual declared bu-gang to its *latest pre-action* eligibility,
    # not the first-ever offer (opponents can change hands across many turns).
    events=outcome["public_events"]
    declared=[e for e in events if e["type"]=="bu_gang_declared"]
    completed={(e["seat"],e["tile"]) for e in events if e["type"]=="bu_gang"}
    robbed_events={(e["seat"],e["tile"]):e
                   for e in events if e["type"]=="rob_kong"}
    robbed=set(robbed_events)
    if completed & robbed:
        raise RuntimeError("the same attempted bu-gang both completed and was robbed")
    if len(declared)!=len(completed)+len(robbed):
        raise RuntimeError("declarations and terminal rob outcomes disagree")
    actual=[]
    for event in declared:
        key=(event["seat"],event["tile"])
        if key not in latest:
            raise RuntimeError("actual public bu-gang had no authorized prior option")
        if key not in completed and key not in robbed:
            raise RuntimeError("declared bu-gang lacks authoritative outcome")
        chosen=latest[key]
        # The public 'rob_kong' resolution binds exactly this owner's
        # visible tile and lists ALL winners (including multi-ron); the
        # terminal tournament winner summary intentionally omits tile names.
        hu_winners=len(robbed_events[key]["seats"]) if key in robbed else 0
        was_robbed=key in robbed
        if (hu_winners>chosen["potential_robbers"] or
            was_robbed != (hu_winners>0)):
            raise RuntimeError("actual rob-Hu contradicts legal pre-decision responders")
        actual.append({
            **chosen,
            "actual_robbed":int(was_robbed),
            "actual_rob_winners":hu_winners,
            "legal_rob_possible_but_not_realized":int(
                chosen["rob_possible"] and not was_robbed),
        })
    byseat=[]
    for seat in range(4):
        summary=_audited_public_bugang(outcome,seat)
        byseat.append(summary)
        if summary["attempted_bu_gang"]!=sum(
                x["seat"]==seat for x in actual):
            raise RuntimeError("public per-seat bu-gang events not reconciled")
    count_sum=Counter()
    for item in byseat:
        count_sum.update(item)
    if (count_sum["attempted_bu_gang"]!=len(actual) or
        count_sum["successful_bu_gang"]!=len(completed) or
        count_sum["robbed_bu_gang"]!=len(robbed)):
        raise RuntimeError("per-seat official kong settlement mismatch")
    if sum(outcome["official_settled_balances"])!=0:
        raise RuntimeError("official terminal settlement not zero-sum")
    if (outcome["physical_count"]!=108 or
        any(outcome["official_settled_balances"][seat]!=(
            outcome["partial_win_balances"][seat]+
            outcome["official_kong_balances"][seat]+
            outcome["official_exhaustive_balances"][seat])
            for seat in range(4))):
        raise RuntimeError("108 conservation or official terminal ledger mismatch")
    return {
        "seed":seed,"rotation":rotation,"challenge_seat":challenge,
        "seat_level":lineup,
        "counts":dict(counters),
        "first_candidates":public_first,
        "actual_bugang_decisions":actual,
        "settlement_by_seat":byseat,
        "official_net_by_seat":outcome["official_settled_balances"],
        "terminal_phase":outcome["terminal_phase"],
    }


def aggregate(seed_start:int,seeds:int)->dict[str,Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
        not 0<=seed_start<2**32 or not 1<=seeds<=12 or
        seed_start+seeds>2**32):
        raise ValueError("invalid preregistered natural seed interval")
    rows=[observe_game(seed,rotation)
          for seed in range(seed_start,seed_start+seeds)
          for rotation in range(4)]
    by_band=defaultdict(Counter)
    by_level=defaultdict(Counter)
    counts=Counter()
    per_seed=[]
    for seed in range(seed_start,seed_start+seeds):
        group=[row for row in rows if row["seed"]==seed]
        if sorted(row["challenge_seat"] for row in group)!=[0,1,2,3]:
            raise RuntimeError("not all independent initial-shuffle rotations present")
        cluster=Counter()
        for trial in group:
            for k,v in trial["counts"].items():
                cluster[k]+=v
            for pos in trial["first_candidates"]:
                level=pos["level"];band=pos["features"]["band"]
                by_band[band]["first"]+=1
                by_band[band]["potential"]+=pos["rob_possible"]
                by_level[level]["first"]+=1
                by_level[level]["potential"]+=pos["rob_possible"]
                cluster["first_potential_rob"]+=pos["rob_possible"]
            for decision in trial["actual_bugang_decisions"]:
                level=decision["level"];band=decision["features"]["band"]
                by_band[band]["attempted"]+=1
                by_band[band]["attempted_potential"]+=decision["rob_possible"]
                by_band[band]["robbed"]+=decision["actual_robbed"]
                by_level[level]["attempted"]+=1
                by_level[level]["attempted_potential"]+=decision["rob_possible"]
                by_level[level]["robbed"]+=decision["actual_robbed"]
                cluster["attempted"]+=1
                cluster["attempted_potential"]+=decision["rob_possible"]
                cluster["robbed"]+=decision["actual_robbed"]
                cluster["rob_winners"]+=decision["actual_rob_winners"]
                cluster["legal_but_not_robbed"]+=decision[
                    "legal_rob_possible_but_not_realized"]
        if cluster["robbed"]>cluster["attempted_potential"]:
            raise RuntimeError("more real rob events than eligible actual attempts")
        counts.update(cluster)
        per_seed.append({"seed":seed,"counts":dict(cluster)})
    status=("unestimable_no_candidates" if not counts["first_distinct"] else
            "unestimable_no_positives" if not counts["first_potential_rob"] else
            "descriptive_only_positives_require_seed_level_validation")
    return {
        "seed_start":seed_start,"independent_initial_shuffle_seeds":seeds,
        "completed_games":len(rows),"observed_seat_positions":len(rows)*4,
        "counts":dict(counts),
        "by_public_band":{s:dict(by_band[s]) for s in
                          ("dingque_excluded","same_suit_focus",
                           "exposed_pressure","unresolved")},
        "by_agent_level":{s:dict(by_level[s]) for s in sorted(by_level)},
        "status":status,"estimated_rob_probability":None,
        "per_seed":per_seed,
        "positions":rows,
    }


def study(*,development:int=28000,holdout:int=29000,
          seeds:int=8)->dict[str,Any]:
    if (type(development) is not int or type(holdout) is not int or
        type(seeds) is not int or not 1<=seeds<=12 or
        not 0<=development<2**32 or not 0<=holdout<2**32 or
        max(development,holdout)+seeds>2**32 or
        (development<holdout+seeds and holdout<development+seeds)):
        raise ValueError("all-seat cohorts must use disjoint fixed seeds")
    return {
        "protocol":PROTOCOL,"live_policy_modified":False,
        "sample_unit":"independent_initial_shuffle_seed",
        "all_seats_observed":True,
        "development_seed_range":[development,development+seeds],
        "holdout_seed_range":[holdout,holdout+seeds],
        "development":aggregate(development,seeds),
        "holdout":aggregate(holdout,seeds),
        "limitations":[
            "Four rotations and all four seats are correlated within one initial-shuffle seed.",
            "Retrospective legal Hu at an available but unchosen bu-gang is not realized rob.",
            "Real robbed upgrades are verified against the latest pre-decision legal label.",
            "Same tile recurs but contributes a single first-offer sample per seat per game.",
            "No probability or deployable online change without independently validated positive labels.",
            "Hidden tile identity is retained only in a local dictionary and never exported.",
            "All policies, 108-tile law, real server and UI remain unchanged.",
        ],
    }
