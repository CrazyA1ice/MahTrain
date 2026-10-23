"""M4.03: preregistered public-signal evidence gates on NEW natural seed clusters.

Read only the M4.02 anonymized, audited all-seat results. All qualitative
signals were defined before seeing these independent cohorts. This is NOT a
fitted probability estimator, and a first-offer label cannot explain a
decision at a later offer without its latest pre-choice ground truth.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping

from .ai_all_seat_bugang_audit import aggregate

PROTOCOL = "m403_independent_all_seat_public_rob_signal_holdout_v1"
BANDS = ("dingque_excluded", "same_suit_focus", "exposed_pressure", "unresolved")
WARNING_BANDS = ("same_suit_focus", "exposed_pressure")
MIN_POSITIVE_SEEDS = 3
MIN_NEGATIVE_SEEDS = 3
MIN_BAND_SEEDS = 3
DEFAULT_SEEDS = 12


def _as_count(value:Any,name:str)->int:
    if type(value) is not int or value < 0:
        raise ValueError("invalid "+name)
    return value


def summarize(group:Mapping[str,Any])->dict[str,Any]:
    """Summarize correlated repeated matches as *initial-seed* clusters.

    Do not treat one seat, optional candidate, window or rotation as an
    independent sample. Expose fixed descriptive count matrices even if
    insufficient positive Hu labels prevent validation of a risk heuristic.
    """
    n = _as_count(group["independent_initial_shuffle_seeds"],"seed count")
    rows = group["positions"]
    if not 1 <= n <= 12 or type(rows) is not list or len(rows)!=4*n:
        raise ValueError("invalid full all-seat cohort")
    seed_groups:dict[int,list[dict[str,Any]]] = defaultdict(list)
    for row in rows:
        if type(row["seed"]) is not int:
            raise ValueError("seed must be an integer")
        seed_groups[row["seed"]].append(row)
    if len(seed_groups)!=n:
        raise ValueError("cohort has missing or duplicate independent seeds")

    bands=defaultdict(Counter)
    walls=defaultdict(Counter)
    agent_levels=defaultdict(Counter)
    confusion=defaultdict(Counter)
    totals=Counter()
    seed_rows=[]
    positive_seeds=set()
    negative_seeds=set()
    warning_seeds=set()
    unwarned_seeds=set()
    band_seed_map:dict[str,set[int]]=defaultdict(set)
    for seed in sorted(seed_groups):
        fours=seed_groups[seed]
        if (len(fours)!=4 or sorted(r["rotation"] for r in fours)!=[0,1,2,3]
            or sorted(r["challenge_seat"] for r in fours)!=[0,1,2,3]):
            raise ValueError("one initial shuffle seed must contain four seats")
        local=Counter()
        for game in fours:
            if (sum(game["official_net_by_seat"])!=0 or
                len(game["seat_level"])!=4):
                raise RuntimeError("official balance or seat lineup invalid")
            source=game["counts"]
            if _as_count(source.get("eligible_candidate_windows",0),"windows") != (
                _as_count(source.get("first_distinct",0),"first")+
                _as_count(source.get("repeated_candidate_windows",0),"repeat")):
                raise RuntimeError("same-tile repeat conservation failed")
            local["game_count"]+=1
            local["all_seat_positions"]+=4
            local["offered_candidate_windows"]+=source.get("eligible_candidate_windows",0)
            local["repeated_candidate_windows"]+=source.get("repeated_candidate_windows",0)
            local["distinct_first"]+=len(game["first_candidates"])
            local["first_latest_label_changes"]+=source.get(
                "repeat_label_differs_from_first",0)
            if len(game["first_candidates"])!=source.get("first_distinct",0):
                raise RuntimeError("first candidate count and actual labels disagree")
            for candidate in game["first_candidates"]:
                features=candidate["features"]
                band=features["band"]
                wall=features["wall_band"]
                if band not in BANDS or wall not in ("early","late","critical","unknown"):
                    raise RuntimeError("unfrozen risk category")
                truth=_as_count(candidate["potential_robbers"],"sealed label")
                if (truth>features["dingque_eligible_opponents"]
                    or truth>3 or candidate["rob_possible"]!=int(truth>0)
                    or (band=="dingque_excluded" and truth>0)):
                    raise RuntimeError("sealed legal Hu contradicts structural public mask")
                pos=int(truth>0)
                local["first_positive"]+=pos
                local["first_negative"]+=1-pos
                key=("warning" if band in WARNING_BANDS else
                     "rule_excluded" if band=="dingque_excluded" else
                     "not_warned_unresolved")
                confusion[key]["label_positive"]+=pos
                confusion[key]["label_negative"]+=1-pos
                confusion[key]["first_distinct"]+=1
                bands[band]["first_distinct"]+=1
                bands[band]["label_positive"]+=pos
                bands[band]["label_negative"]+=1-pos
                walls[wall]["first_distinct"]+=1
                walls[wall]["label_positive"]+=pos
                walls[wall]["label_negative"]+=1-pos
                level=candidate["level"]
                agent_levels[level]["first_distinct"]+=1
                agent_levels[level]["label_positive"]+=pos
                band_seed_map[band].add(seed)
                if pos:positive_seeds.add(seed)
                else:negative_seeds.add(seed)
                if key=="warning":warning_seeds.add(seed)
                if key=="not_warned_unresolved":unwarned_seeds.add(seed)
            for event in game["actual_bugang_decisions"]:
                truth=_as_count(event["potential_robbers"],"latest legal responders")
                winners=_as_count(event["actual_rob_winners"],"actual winners")
                if (winners>truth or event["actual_robbed"]!=int(winners>0)
                    or event["rob_possible"]!=int(truth>0)):
                    raise RuntimeError("latest legal rob eligibility != actual Hu resolution")
                local["attempted"]+=1
                local["attempted_legal_possible"]+=int(truth>0)
                local["robbed"]+=event["actual_robbed"]
                local["rob_hu_winners"]+=winners
                agent_levels[event["level"]]["attempted"]+=1
                agent_levels[event["level"]]["attempted_legal_possible"]+=int(truth>0)
                agent_levels[event["level"]]["robbed"]+=event["actual_robbed"]
        if local["first_positive"]+local["first_negative"]!=local["distinct_first"]:
            raise RuntimeError("seed-cluster distinct positive/negative counts mismatch")
        totals.update(local)
        seed_rows.append({"seed":seed,"counts":dict(local)})
    if totals["attempted"]!=sum(
        row["counts"].get("attempted",0) for row in seed_rows):
        raise RuntimeError("independent seed cluster event tally mismatch")

    # A positive and negative in the SAME seed are not two independent seeds.
    # Requiring >=3 each is a minimum for a DESCRIPTIVE holdout check only.
    # A calibrated population probability requires more rigorous inference.
    if totals["distinct_first"]==0:
        status="no_natural_bugang_candidates"
    elif not positive_seeds:
        status="no_natural_legal_rob_positives"
    elif len(positive_seeds)<MIN_POSITIVE_SEEDS:
        status="fewer_than_three_positive_seed_clusters"
    elif len(negative_seeds)<MIN_NEGATIVE_SEEDS:
        status="fewer_than_three_negative_seed_clusters"
    elif (len(warning_seeds)<MIN_BAND_SEEDS or
          len(unwarned_seeds)<MIN_BAND_SEEDS):
        status="insufficient_public_warning_and_unresolved_seed_coverage"
    else:
        status="descriptive_association_check_only_not_calibrated"

    return {
        "independent_initial_shuffle_seeds":n,
        "complete_games":totals["game_count"],
        "correlated_seat_positions":totals["all_seat_positions"],
        "counts":dict(totals),
        "seed_support":{
            "positive_label_seeds":len(positive_seeds),
            "negative_label_seeds":len(negative_seeds),
            "public_warning_seeds":len(warning_seeds),
            "unresolved_nonwarning_seeds":len(unwarned_seeds),
            "by_band":{band:len(band_seed_map[band]) for band in BANDS},
        },
        "public_band_counts":{band:dict(bands[band]) for band in BANDS},
        "wall_band_counts":{band:dict(walls[band])
                           for band in ("early","late","critical","unknown")},
        "frozen_warning_cross_counts":{
            band:dict(confusion[band]) for band in
            ("warning","not_warned_unresolved","rule_excluded")},
        "agent_level_counts":{level:dict(agent_levels[level])
                              for level in ("baseline","basic","advanced","challenge")},
        "validation_status":status,
        "calibrated_rob_probability":None,
        "per_seed":seed_rows,
    }


def compare(dev:Mapping[str,Any],hold:Mapping[str,Any])->dict[str,Any]:
    a=summarize(dev)
    b=summarize(hold)
    da={row["seed"] for row in a["per_seed"]}
    db={row["seed"] for row in b["per_seed"]}
    if da & db:
        raise ValueError("development and holdout reused an initial shuffle seed")
    status=("cannot_validate_public_risk_warning_on_this_holdout"
            if a["validation_status"]!=
               "descriptive_association_check_only_not_calibrated" or
               b["validation_status"]!=
               "descriptive_association_check_only_not_calibrated"
            else "descriptive_candidate_association_only_no_online_policy_change")
    return {
        "protocol":PROTOCOL,
        "feature_source":"public_state_only",
        "truth_source":"offline_authoritative_hidden_hand_legality_only",
        "live_policy_modified":False,
        "seed_sets_disjoint":True,
        "dev":a,
        "holdout":b,
        "cross_cohort_decision":status,
        "calibrated_rob_probability":None,
        "limitations":[
            "A seed and its four rotations are ONE clustered sampling unit, not sixteen independent seats.",
            "Thresholds were fixed before the new seed groups were evaluated; they only permit descriptive checks.",
            "Public warning means same-suit focus OR exposed pressure; absence of warning is NOT safe.",
            "The dingque rule-excluded band is a structural impossibility for that tile, not all-purpose safety.",
            "All candidate labels are retrospective; no opponent private hand enters a live agent.",
            "Constructed M4.01 physical positives never enter prevalence or classifier tallies.",
            "Sparse natural positive seeds block inference; null is not zero percent.",
            "Only the latest legal pre-decision label is matched to actual robbed/declined results.",
        ],
    }


def study(*,development:int=30000,holdout:int=31000,
          seeds:int=DEFAULT_SEEDS)->dict[str,Any]:
    if (type(development) is not int or type(holdout) is not int or
        type(seeds) is not int or not 1<=seeds<=12 or
        not 0<=development<2**32 or not 0<=holdout<2**32 or
        max(development,holdout)+seeds>2**32 or
        (development<holdout+seeds and holdout<development+seeds)):
        raise ValueError("development and holdout must use disjoint uint32 ranges")
    result=compare(aggregate(development,seeds),aggregate(holdout,seeds))
    result["development_seed_range"]=[development,development+seeds]
    result["holdout_seed_range"]=[holdout,holdout+seeds]
    return result
