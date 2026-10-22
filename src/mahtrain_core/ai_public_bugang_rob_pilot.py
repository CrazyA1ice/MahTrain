"""M4.00 offline PUBLIC pre-bu-gang pressure vs SEALED legal rob-Hu labels.

The public feature function never sees opponent concealed hands or future wall.
Only the separate trusted offline labeler may read hands; the true labels
never modify the live game, policy, network, replay or decision heuristics.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping

from .ai_bugang_repeat_risk import SameTileAuditAgent, _audited_public_bugang
from .ai_action_extended_study import _fixed_lineup
from .ai_challenge_call_kong_ablation import _official_outcome, _wall_band
from .ai_tournament import simulate_match
from .rules import SUITS, TILE_INDEX, is_legal_win

PROTOCOL = "m400_public_bugang_potential_rob_seed_split_v1"
BANDS = ("dingque_excluded", "same_suit_focus", "exposed_pressure", "unresolved")


def public_bugang_features(board: Mapping[str, Any], seat: int,
                           tile: str) -> dict[str, Any]:
    """Public-only candidate signal: owned peng is already publicly exposed."""
    melds, missing, won = (
        board.get("melds"), board.get("missing_suits"), board.get("won"))
    discards, wall = board.get("discards"), board.get("wall_count")
    if (type(seat) is not int or seat not in range(4) or
        type(tile) is not str or tile not in TILE_INDEX or
        board.get("phase") not in ("dealer_discard", "await_discard") or
        board.get("turn")!=seat or
        type(wall) is not int or not 1<=wall<=108 or
        type(melds) not in (list,tuple) or len(melds)!=4 or
        type(missing) not in (list,tuple) or len(missing)!=4 or
        any(x not in SUITS for x in missing) or
        type(won) not in (list,tuple) or len(won)!=4 or
        any(type(x) is not bool for x in won) or won[seat] or
        type(discards) not in (list,tuple)):
        raise ValueError("invalid public pre-bu-gang snapshot")
    if (tile[0]==missing[seat] or not any(
        type(m) is dict and m.get("type")=="peng" and m.get("tile")==tile
        for m in melds[seat])):
        raise ValueError("bu-gang tile is not an already public own peng")
    active=[s for s in range(4) if s!=seat and not won[s]]
    eligible=[s for s in active if missing[s]!=tile[0]]
    exposed=same_suit=focus=0
    for target in eligible:
        groups=melds[target]
        if type(groups) not in (list,tuple):
            raise ValueError("invalid public target melds")
        kinds=[]
        for group in groups:
            if type(group) is not dict:
                raise ValueError("malformed exposed meld")
            show=group.get("tile")
            if show in TILE_INDEX:
                kinds.append(show[0])
        exposed+=len(kinds)
        same_suit+=sum(x==tile[0] for x in kinds)
        focus+=int(len(kinds)>=2 and set(kinds)=={tile[0]})
    matching_discards=suit_discards=0
    for d in discards:
        if (type(d) is not dict or type(d.get("seat")) is not int or
            d["seat"] not in range(4) or d.get("tile") not in TILE_INDEX):
            raise ValueError("malformed public discard")
        if d["seat"]!=seat:
            matching_discards+=int(d["tile"]==tile)
            suit_discards+=int(d["tile"][0]==tile[0])
    category=("dingque_excluded" if not eligible else
              "same_suit_focus" if focus else
              "exposed_pressure" if exposed>=2 else "unresolved")
    return {
        "band":category, "wall_band":_wall_band(board),
        "active_opponents":len(active),
        "dingque_eligible_opponents":len(eligible),
        "eligible_opponent_open_melds":exposed,
        "same_suit_open_melds":same_suit,
        "same_suit_focus_opponents":focus,
        "other_public_identical_discards":matching_discards,
        "other_public_suit_discards":suit_discards,
        "self_public_melds":len(melds[seat]),
    }


def _sealed_potential_robbers(game: Any, owner: int, tile: str) -> int:
    """Retrospective reference label ONLY; never used as an AI input."""
    hits=0
    for target in range(4):
        if target==owner or game._won[target]:
            continue
        if game.missing_suits[target]==tile[0]:
            continue
        hand=game._hands[target]
        melds=game._melds[target]
        if len(hand)+3*len(melds)!=13:
            raise RuntimeError("invalid sealed 13-effective opponent hand")
        hits+=int(is_legal_win([*hand,tile],melds,game.missing_suits[target]))
    return hits


def natural_position(seed:int, rotation:int)->dict[str,Any]:
    if type(seed) is not int or not 0<=seed<2**32:
        raise ValueError("seed must be unsigned 32-bit integer")
    lineup,seat=_fixed_lineup(rotation)
    agent=SameTileAuditAgent(seed=seed,seat=seat)
    seen:set[str]=set()
    first=[]
    windows=repeats=0

    def probe(game:Any)->None:
        nonlocal windows,repeats
        if game.turn!=seat or game._won[seat]:
            return
        # The overwhelming majority of own turns contain no legal bu-gang.
        # Use the authority's cheap legal-option list BEFORE materializing a
        # second full private_view/public_state. The actual MahjongAgent still
        # evaluates its normal private_view exactly as before.
        available=[x for x in game.kong_options(seat)
                   if x["type"]=="bu_gang"]
        if not available:
            return
        private=game.private_view(seat)
        if private["can_self_draw_win"]:
            return  # confirmed win cannot be overridden by analysis
        if any(x not in private["kong_options"] for x in available):
            raise RuntimeError("public-risk probe disagrees with own legal kongs")
        board=game.public_state()
        for option in available:
            windows+=1
            tile=option["tile"]
            if tile in seen:
                repeats+=1
                continue
            seen.add(tile)  # local private identity, never returned
            features=public_bugang_features(board,seat,tile)
            # Features are determined BEFORE consulting any hidden true label.
            hidden=_sealed_potential_robbers(game,seat,tile)
            if hidden>features["dingque_eligible_opponents"]:
                raise RuntimeError("sealed and public rob eligibility disagree")
            if features["band"]=="dingque_excluded" and hidden:
                raise RuntimeError("dingque-excluded tile cannot legally be robbed")
            first.append({"features":features,
                          "rob_possible":int(hidden>0),
                          "potential_robbers":hidden})

    trial=simulate_match(seed,rotation=rotation%3,lineup=lineup,
                         offline_kong_base=1,
                         offline_agent_overrides={seat:agent},
                         offline_observer=probe)
    counts=Counter(agent.counts)
    official=_official_outcome(trial,seat,lineup)
    if (windows!=counts["own_kong_offer_bu_gang"] or
        repeats!=counts["repeat_bu_gang_candidate_windows"] or
        len(first)!=counts["distinct_bu_gang_tiles"]):
        raise RuntimeError("predecision sampling disagrees with natural AI offers")
    actual=_audited_public_bugang(trial,seat)
    if counts["own_kong_original_bu_gang"]!=actual["attempted_bu_gang"]:
        raise RuntimeError("declared bu-gang count does not match chosen actions")
    return {"seed":seed,"rotation":rotation,"challenge_seat":seat,
            "first_distinct_candidates":first,
            "offered_windows":windows,"repeated_windows":repeats,
            "attempts":actual,"official_score":official,
            "terminal_phase":trial["terminal_phase"]}


def cohort(seed_start:int,seeds:int)->dict[str,Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
        not 0<=seed_start<2**32 or not 1<=seeds<=16 or
        seed_start+seeds>2**32):
        raise ValueError("invalid natural cohort")
    positions=[natural_position(seed,r)
               for seed in range(seed_start,seed_start+seeds)
               for r in range(4)]
    total=Counter()
    summary=defaultdict(Counter)
    per_seed=[]
    for seed in range(seed_start,seed_start+seeds):
        items=[p for p in positions if p["seed"]==seed]
        if sorted(p["challenge_seat"] for p in items)!=[0,1,2,3]:
            raise RuntimeError("missing complete four-seat initial-seed cluster")
        part=Counter()
        for pos in items:
            part["windows"]+=pos["offered_windows"]
            part["repeated"]+=pos["repeated_windows"]
            part["first_distinct"]+=len(pos["first_distinct_candidates"])
            part["attempted"]+=pos["attempts"]["attempted_bu_gang"]
            part["successful"]+=pos["attempts"]["successful_bu_gang"]
            part["robbed"]+=pos["attempts"]["robbed_bu_gang"]
            for row in pos["first_distinct_candidates"]:
                group=summary[row["features"]["band"]]
                group["count"]+=1
                group["possible"]+=row["rob_possible"]
                group["potential_robbers"]+=row["potential_robbers"]
        if (part["windows"]!=part["first_distinct"]+part["repeated"]
            or part["attempted"]!=part["successful"]+part["robbed"]):
            raise RuntimeError("public event accounting failed")
        total.update(part)
        per_seed.append({"seed":seed,**dict(part)})
    first=total["first_distinct"]
    positive=sum(v["possible"] for v in summary.values())
    validation=("unestimable_no_candidates" if not first else
                "unestimable_no_positives" if not positive else
                "unestimable_no_negatives" if positive==first else
                "descriptive_only_small_seed_cluster_sample")
    return {
        "independent_seeds":seeds,"four_seat_positions":len(positions),
        "counts":dict(total),
        "by_public_band":{band:{
            "candidate_n":summary[band]["count"],
            "sealed_possible_n":summary[band]["possible"],
            "potential_robber_count":summary[band]["potential_robbers"],
        } for band in BANDS},
        "predictive_validation_status":validation,
        "estimated_rob_probability":None,
        "per_seed":per_seed,
        "positions":positions,
    }


def study(*,development:int=24000,holdout:int=25000,
          seeds:int=8)->dict[str,Any]:
    if (type(development) is not int or type(holdout) is not int or
        type(seeds) is not int or
        not 0<=development<2**32 or not 0<=holdout<2**32 or
        not 1<=seeds<=16 or
        max(development,holdout)+seeds>2**32 or
        (development<holdout+seeds and holdout<development+seeds)):
        raise ValueError("predeclared cohorts must be disjoint")
    return {
        "protocol":PROTOCOL,
        "live_policy_modified":False,
        "feature_source":"public_state_only",
        "label_source":"retrospective_trusted_hidden_legality_only",
        "development_seed_range":[development,development+seeds],
        "holdout_seed_range":[holdout,holdout+seeds],
        "development":cohort(development,seeds),
        "holdout":cohort(holdout,seeds),
        "limitations":[
            "Retrospective rob-possible label is not an observed rob-Hu choice.",
            "Public bu-gang tile is already disclosed by the own peng meld.",
            "Risk categories are coarse, not calibrated probabilities.",
            "Repeated same-tile offers are excluded from first-unique label counts.",
            "Excluding all potential Hu responders by dingque does not prove Kong is globally optimal.",
            "No predictive claims without enough independent positive cases.",
            "No change to online AI, official scoring, or public gameplay APIs.",
        ],
    }
