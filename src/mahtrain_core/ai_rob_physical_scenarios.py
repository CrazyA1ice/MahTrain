"""M4.01: physically complete 108-tile ROB-KONG scenario stress tests.

These are DESIGN-BY-CONSTRUCTION fixtures to test rules and preaction public
features, NOT samples from natural shuffle distributions. No constructed
positive/negative should ever be treated as a calibrated event frequency.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from .four_player import FourPlayerOpening
from .rules import TILES
from .ai_public_bugang_rob_pilot import (
    public_bugang_features, _sealed_potential_robbers,
)
from .ai_bugang_repeat_risk import _audited_public_bugang

PROTOCOL="m401_physical_108_bugang_rob_stress_v1"
TILE="m9"

# Every scenario is preregistered, including intentionally deceptive PUBLIC
# signals where a focused opponent is NOT actually legally waiting on m9.
SCENARIOS={
    "one_robber":{"ready":1,"open":"none","behavior":"hu","missing":"p","wall":"full"},
    "two_robbers":{"ready":2,"open":"none","behavior":"hu","missing":"p","wall":"full"},
    "decline_legal_hu":{"ready":1,"open":"none","behavior":"pass","missing":"p","wall":"full"},
    "all_dingque_excluded":{"ready":1,"open":"none","behavior":"hu","missing":"m","wall":"full"},
    "focused_positive":{"ready":1,"open":"focused","behavior":"hu","missing":"p","wall":"full"},
    "focused_false_alarm":{"ready":1,"open":"focused_bad","behavior":"hu","missing":"p","wall":"full"},
    "mixed_meld_positive":{"ready":1,"open":"mixed","behavior":"hu","missing":"p","wall":"full"},
    "critical_wall_positive":{"ready":1,"open":"none","behavior":"hu","missing":"p","wall":"critical"},
}


def _ready(index:int)->list[str]:
    if index==0:
        return ["m1"]*3+["m4"]*3+["s1"]*3+["s4"]*2+["m7","m8"]
    if index==1:
        return ["m2"]*3+["m5"]*3+["s2"]*3+["s5"]*2+["m7","m8"]
    raise ValueError("only two preregistered robber roles")


def build_physical_scenario(name:str)->tuple[FourPlayerOpening,int,list[int]]:
    """Deal four complete private hands plus public peng(s) and a real wall.

    All four copies of the added tile are reserved for the declarer's 3-tile
    exposed peng and one private 4th. Robber hand/meld patterns are subtracted
    from the SAME global 108 physical tiles before filling other seats.
    """
    if name not in SCENARIOS:
        raise ValueError("unknown constructed scenario")
    cfg=SCENARIOS[name]
    game=FourPlayerOpening(42,kong_base=1)
    owner=game.dealer
    robbers=[(owner+1)%4,(owner+2)%4][:cfg["ready"]]
    hands:dict[int,list[str]]={owner:[TILE]}
    melds:list[list[dict[str,str]]]=[[] for _ in range(4)]
    melds[owner]=[{"type":"peng","tile":TILE}]
    for i,seat in enumerate(robbers):
        full=_ready(i)
        open_kinds=[]
        if i==0:
            if cfg["open"] in ("focused","focused_bad"):
                open_kinds=["m1","m4"]
            elif cfg["open"]=="mixed":
                open_kinds=["m1","s1"]
            if cfg["open"]=="focused_bad":
                full.remove("m8")
                full.append("p2")  # public focus does not imply Hu
        for kind in open_kinds:
            for _ in range(3):full.remove(kind)
            melds[seat].append({"type":"peng","tile":kind})
        hands[seat]=full
    pool=Counter({tile:4 for tile in TILES})
    pool[TILE]-=4  # owner hand 1 and visible peng 3
    for seat in robbers:
        for t in hands[seat]:pool[t]-=1
        for m in melds[seat]:
            pool[m["tile"]]-=3
    if any(v<0 for v in pool.values()):
        raise RuntimeError("scenario overdraws the 108 physical tiles")

    # Keep all preregistered robber tiles reserved before filling other seats.
    for seat in range(4):
        target_size=11 if seat==owner else 13-3*len(melds[seat])
        current=hands.setdefault(seat,[])
        for tile in TILES:
            while pool[tile]>0 and len(current)<target_size:
                current.append(tile)
                pool[tile]-=1
        if len(current)!=target_size:
            raise RuntimeError("could not fill fixed legal hand")
    game._hands=[hands[s] for s in range(4)]
    game._melds=melds
    game._wall=[tile for tile in TILES for _ in range(pool[tile])]
    game.missing_suits=["p"]*4
    for s in range(4):
        if s!=owner:
            game.missing_suits[s]=cfg["missing"] if s in robbers else "m"
    game.phase="dealer_discard"
    game.turn=owner
    if cfg["wall"]=="critical":
        # This is an intentionally synthetic *public* river history, not a
        # natural-play sample. Moving tiles wall->river preserves 108 exactly.
        while len(game._wall)>11:
            tile=game._wall.pop(0)
            game._discards.append({"seat":(owner+2)%4,"tile":tile,
                                    "index":len(game._discards)+1})
    game._assert_physical_tiles()
    if {"type":"bu_gang","tile":TILE} not in game.kong_options(owner):
        raise RuntimeError("constructed owner lacks authorized bu-gang")
    if game.debug_tile_counts()["total"]!=108:
        raise RuntimeError("scenario lost tiles")
    return game,owner,robbers


def verify_constructed_scenario(name:str)->dict[str,Any]:
    game,owner,designated=build_physical_scenario(name)
    initial=game.public_state()
    feat=public_bugang_features(initial,owner,TILE)
    before=_sealed_potential_robbers(game,owner,TILE)
    if before>feat["dingque_eligible_opponents"]:
        raise RuntimeError("hidden legal rob set exceeds public eligibility")
    initial_balance=initial["settled_balances"]
    # Actually enter the official rob-kong response window and ask the very
    # SAME rule engine each opponent's real legal options.
    game.declare_kong(owner,"bu_gang",TILE)
    eligible=[s for s in range(4) if s!=owner
              and not game._won[s] and "hu" in game.rob_options(s)]
    if before!=len(eligible):
        raise RuntimeError("sealed preaction labels disagree with actual rob_options")
    behavior=SCENARIOS[name]["behavior"]
    for s in range(4):
        if s==owner or game._won[s]:
            continue
        choices=game.rob_options(s)
        game.respond_rob_kong(s,"hu" if behavior=="hu" and "hu" in choices
                              else "pass")
    board=game.public_state()
    settled=_audited_public_bugang({
        "public_events":board["events"],
        "winners":board["winners"],
    },owner)
    chosen=len(eligible) if behavior=="hu" else 0
    if (settled["attempted_bu_gang"]!=1 or
        settled["robbed_bu_gang"]!=int(chosen>0) or
        settled["successful_bu_gang"]!=int(chosen==0) or
        settled["rob_kong_winners"]!=chosen):
        raise RuntimeError("real bu-gang/rob outcome mismatches official Hu responses")
    if game.debug_tile_counts()["total"]!=108:
        raise RuntimeError("physical tiles lost after robber choice")
    if (not board["win_ledger"]["zero_sum"] or
        not board["kong_ledger"]["zero_sum"] or
        sum(board["settled_balances"])!=0 or
        any(initial_balance)):
        raise RuntimeError("official public settlement not zero-sum")
    if chosen:
        if (game._melds[owner]!=[{"type":"peng","tile":TILE}] or
            len(board["winners"])!=chosen):
            raise RuntimeError("robbed bu-gang incorrectly upgraded source peng")
    else:
        if game._melds[owner]!=[{"type":"bu_gang","tile":TILE}]:
            raise RuntimeError("unrobbed bu-gang failed to upgrade peng")
    # Expose only a known synthetic scenario's named outcome and public
    # coarse feature band, not any other's concealed hand.
    return {
        "scenario":name,
        "physical_tiles":108,
        "public_band":feat["band"],
        "wall_band":feat["wall_band"],
        "active_opponents":feat["active_opponents"],
        "public_dingque_eligible":feat["dingque_eligible_opponents"],
        "designated_ready_roles":len(designated),
        "sealed_eligible_robbers":before,
        "official_legal_robbers":len(eligible),
        "actually_chose_rob_hu":chosen,
        "attempted":settled["attempted_bu_gang"],
        "successful":settled["successful_bu_gang"],
        "robbed":settled["robbed_bu_gang"],
        "rob_hu_winners":settled["rob_kong_winners"],
        "terminal_phase_after_response":board["phase"],
        "official_zero_sum":True,
        "origin":"constructed_fixture_not_natural_sample",
    }


def stress_report()->dict[str,Any]:
    cases=[verify_constructed_scenario(name) for name in SCENARIOS]
    assert len(cases)==8
    return {
        "protocol":PROTOCOL,"live_policy_modified":False,
        "scenario_count":len(cases),
        "constructed_cases":cases,
        "calibrated_rob_probability":None,
        "limitations":[
            "All fixtures are intentionally constructed from 108 physical tiles, not independent shuffled matches.",
            "Case counts are NEVER a prevalence estimate or probability calibration sample.",
            "A hidden Hu eligibility label is retrospective-only; online AI does not access it.",
            "A positive label can decline Hu, so potential rob is not realized rob.",
            "A public same-suit focus signal is NOT a proof of legal opponent Hu.",
            "Full zero-sum settlement and physical conservation use the real official rule engine.",
        ],
    }
