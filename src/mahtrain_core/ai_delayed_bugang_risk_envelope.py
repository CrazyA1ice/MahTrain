"""M4.28 OFFLINE lawful bu-gang benefit and rob-risk boundary experiments.

Only physically constructed checkpoints; NEVER use hidden opponent hands or
the real tail wall to make an AI decision. A possible rob-kong witness proves
legality in ONE counterfactual unseen world, not its likelihood.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Mapping

from .ai import visible_tiles
from .ai_delayed_bugang_targeted import SPECS, SHARDS, construct_checkpoint
from .efficiency import effective_draws
from .four_player import FourPlayerOpening
from .rules import is_legal_win, score_win

PROTOCOL = "m428_conditional_root_tail_rob_risk_nonprobabilistic_v1"
CURRENT_RULES = "current_m423"
FAMILIES = ("mixed", "concentrated")
ROOT_BASE_FAN = 1
KONG_BASE = 20


def _reference_root_score(target: str, fan_cap: int) -> dict[str, Any]:
    """An explicitly HYPOTHETICAL completed hand, not a fixture outcome.

    Identical eleven concealed tiles make three triplets and a pair in the
    opposite legal suit; switching the exposed peng to bu-gang changes only
    the fourth target copy, which adds one legal root. Cash and rob risk do
    not enter score_win, and the effective fan cap can suppress the gain.
    """
    if (type(target) is not str or target not in {t for t, _ in SPECS}
            or type(fan_cap) is not int or fan_cap < 0):
        raise ValueError("invalid registered tile/cap for conditional reference")
    other = "s" if target[0] == "m" else "m"
    concealed = ([other+"1"]*3 + [other+"3"]*3 +
                 [other+"5"]*3 + [other+"7"]*2)
    before = score_win(concealed,[{"type":"peng","tile":target}],
                       "p",cap=fan_cap)
    after = score_win(concealed,[{"type":"bu_gang","tile":target}],
                      "p",cap=fan_cap)
    if (not before["legal"] or not after["legal"] or
            before["main_pattern"] != after["main_pattern"] or
            before["main_fan"] != after["main_fan"] or
            after["raw_fan"] != before["raw_fan"] + ROOT_BASE_FAN or
            after["bonuses"].get("roots") !=
                    before["bonuses"].get("roots",0)+1 or
            after["multiplier"] < before["multiplier"]):
        raise RuntimeError("the authoritative conditional root scoring changed")
    return {
        "fan_cap":fan_cap,
        "before_raw_fan":before["raw_fan"],
        "after_raw_fan":after["raw_fan"],
        "before_effective_fan":before["effective_fan"],
        "after_effective_fan":after["effective_fan"],
        "before_multiplier":before["multiplier"],
        "after_multiplier":after["multiplier"],
        "capped_multiplier_gain":after["multiplier"]-before["multiplier"],
    }


def _rob_witness(g: FourPlayerOpening, target: str) -> list[str] | None:
    """Build a legal 13-tile robbing hand from the actually unseen tile pool.

    Research-only. The actor view cannot distinguish this completed witness
    from the no-rob world: all reallocation is inside concealed hands/wall.
    """
    if g.phase != "await_discard" or g.turn != 0:
        raise ValueError("witness needs the exact actor checkpoint")
    pool=Counter(g._wall)
    for seat in (1,2,3):
        pool.update(g._hands[seat])
    other="s" if target[0]=="m" else "m"
    number=int(target[1])
    alternatives=[]
    for low in range(max(1,number-2),min(number,7)+1):
        if low <= number <= low+2:
            neighbors=[target[0]+str(k) for k in range(low,low+3)
                       if k!=number]
            if len(neighbors)==2:
                alternatives.append(neighbors)
    for wait in alternatives:
        reserved=Counter(wait)
        if any(pool[t]<c for t,c in reserved.items()):
            continue
        available=pool-reserved
        triples=[t for t in sorted(available)
                 if t[0]==other and available[t]>=3]
        if len(triples)<3:
            continue
        meld_tiles=[]
        for t in triples[:3]:
            meld_tiles.extend([t]*3)
            available[t]-=3
        pair=next((t for t in sorted(available)
                   if t[0] in ("m","s") and t!=target and available[t]>=2),
                  None)
        if pair is None:
            continue
        witness=[*wait,*meld_tiles,pair,pair]
        if len(witness)==13 and is_legal_win([*witness,target],[],"p"):
            return witness
    # Not finding this PARTICULAR witness shape does not prove that no
    # possible opponent hand could rob. Never invent unavailable tiles.
    return None


def _replace_opponents_without_public_change(
    g: FourPlayerOpening, target: str,
) -> FourPlayerOpening | None:
    """Swap ONLY unknown hands and wall for a physically valid robber witness."""
    counterfactual=deepcopy(g)
    prior=g.private_view(0)
    witness=_rob_witness(counterfactual,target)
    if witness is None:
        return None
    pool=Counter(counterfactual._wall)
    for seat in (1,2,3):
        pool.update(counterfactual._hands[seat])
    for t in witness:
        if pool[t]<1:
            raise RuntimeError("illegal fifth tile in counterfactual")
        pool[t]-=1
    remaining=[t for t in sorted(pool) for _ in range(pool[t])]
    if len(remaining) != len(g._wall)+26:
        raise RuntimeError("counterfactual changed tile inventory")
    counterfactual._hands[1]=list(witness)
    counterfactual._hands[2]=remaining[:13]
    counterfactual._hands[3]=remaining[13:26]
    counterfactual._wall=remaining[26:]
    counterfactual._assert_physical_tiles()
    if (counterfactual.private_view(0)!=prior or
            counterfactual.public_state()!=g.public_state() or
            counterfactual.debug_tile_counts()["total"]!=108):
        raise RuntimeError("counterfactual opponent/wall became visible to actor")
    return counterfactual


def _resolve(g: FourPlayerOpening, *, rob: bool) -> dict[str, Any]:
    target=g._melds[0][0]["tile"]
    before_wall=g.public_state()["wall_count"]
    g.declare_kong(0,"bu_gang",target)
    if g.public_state()["pending_rob_kong"]["cash_eligible"]:
        raise RuntimeError("delayed upgrade unexpectedly earns cash")
    legal=g.rob_options(1)
    if rob and "hu" not in legal:
        raise RuntimeError("authoritative engine refused legal rob witness")
    g.respond_rob_kong(1,"hu" if rob else "pass")
    for seat in (2,3):
        g.respond_rob_kong(seat,"pass")
    state=g.public_state()
    if (state["kong_ledger"]["balances"] != [0,0,0,0] or
            not state["kong_ledger"]["zero_sum"] or
            g.debug_tile_counts()["total"] != 108):
        raise RuntimeError("rob branch invented late kong money or physical tiles")
    if rob:
        if (not any(w["seat"]==1 and w["kind"]=="rob_kong"
                    for w in state["winners"]) or
                any(m["type"]=="bu_gang" for m in state["melds"][0]) or
                state["wall_count"]!=before_wall):
            raise RuntimeError("rob did not suppress upgrade/tail draw")
    else:
        if (state["wall_count"]!=before_wall-1 or
                state["melds"][0][0]["type"]!="bu_gang" or
                state["kong_ledger"]["events"][-1]["status"]!="not_payable"):
            raise RuntimeError("ordinary tail supplement/zero-cash outcome changed")
    return {
        "robbed":rob,
        "kong_was_completed":not rob,
        "tail_was_consumed":not rob,
        "cash_from_late_kong":state["kong_ledger"]["balances"][0],
        "actor_official_wins":state["win_ledger"]["balances"][0],
        "physical_count":g.debug_tile_counts()["total"],
        "rob_winner_count":len(state["winners"]) if rob else 0,
    }


def evaluate_case(case_id: int) -> dict[str, Any]:
    if type(case_id) is not int or not 0<=case_id<len(SPECS):
        raise ValueError("invalid registered M4.28 case")
    target,family=SPECS[case_id]
    g=construct_checkpoint(case_id,delayed=True)
    view=g.private_view(0)
    if (view["drawn_tile"]==target or
            {"type":"bu_gang","tile":target} not in view["kong_options"] or
            view["legacy_bugang_cash_rule"] is not False):
        raise RuntimeError("invalid physical cashless case")
    cap=view["win_ledger"]["fan_cap"]
    reference=_reference_root_score(target,cap)
    after=list(view["hand"])
    after.remove(target)
    upgraded=[
        {"type":"bu_gang" if m["type"]=="peng" and m["tile"]==target
         else m["type"],"tile":m["tile"]}
        for m in view["own_melds"]
    ]
    proxy=effective_draws(
        after,upgraded,view["missing_suits"][0],visible_tiles(view),
    )
    if proxy["unknown_tile_count"]<=0:
        raise RuntimeError("no unknown physical tiles remain for proxy")
    before=g.private_view(0)
    safe=_resolve(deepcopy(g),rob=False)
    risk_world=_replace_opponents_without_public_change(g,target)
    if risk_world is not None and risk_world.private_view(0)!=before:
        raise RuntimeError("rob counterfactual changes authorized player view")
    robbed=(_resolve(risk_world,rob=True)
            if risk_world is not None else None)
    if g.private_view(0)!=before or g.debug_tile_counts()["total"]!=108:
        raise RuntimeError("research experiment changed actual game")
    return {
        "case_id":case_id,
        "exposed_peng":target,
        "shape_family":family,
        "conditional_completed_hand_root":reference,
        "tail_proxy_effective_copies":proxy["effective_tile_count"],
        "tail_proxy_unknown_copies":proxy["unknown_tile_count"],
        "tail_proxy_effective_fraction":round(
            proxy["effective_tile_count"]/proxy["unknown_tile_count"],7),
        "constructed_same_view_rob_witness_found":risk_world is not None,
        "no_rob_branch":safe,
        "adversarial_rob_branch":robbed,
        "physical_tiles":g.debug_tile_counts()["total"],
        "not_a_probability_or_EV_estimate":True,
    }


def evaluate_shard(name: str) -> dict[str, Any]:
    if type(name) is not str or name not in SHARDS:
        raise ValueError("unknown M4.28 frozen case shard")
    return {
        "protocol":PROTOCOL,
        "shard":name,
        "case_ids":list(SHARDS[name]),
        "cases":[evaluate_case(i) for i in SHARDS[name]],
        "not_natural_games":True,
        "not_expected_score":True,
    }


def combine(shards: Mapping[str, Any]) -> dict[str, Any]:
    if type(shards) is not dict or set(shards)!=set(SHARDS):
        raise ValueError("all four frozen shards are required")
    cases=[]
    for name,ids in SHARDS.items():
        group=shards[name]
        if (type(group) is not dict or group.get("protocol")!=PROTOCOL
                or group.get("shard")!=name
                or group.get("case_ids")!=list(ids)
                or group.get("not_natural_games") is not True
                or group.get("not_expected_score") is not True
                or type(group.get("cases")) is not list
                or len(group["cases"])!=len(ids)):
            raise ValueError("bad M4.28 shard envelope")
        for id,row in zip(ids,group["cases"]):
            if type(row) is not dict or type(row.get("case_id")) is not int:
                raise ValueError("invalid case record")
            ref=row.get("conditional_completed_hand_root")
            safe=row.get("no_rob_branch")
            risk=row.get("adversarial_rob_branch")
            if (row["case_id"]!=id or
                    row.get("exposed_peng")!=SPECS[id][0] or
                    row.get("shape_family")!=SPECS[id][1] or
                    row.get("physical_tiles")!=108 or
                    row.get("not_a_probability_or_EV_estimate") is not True or
                    type(row.get("constructed_same_view_rob_witness_found")) is not bool or
                    type(ref) is not dict or
                    any(type(ref.get(k)) is not int for k in (
                        "fan_cap","before_raw_fan","after_raw_fan",
                        "before_effective_fan","after_effective_fan",
                        "before_multiplier","after_multiplier",
                        "capped_multiplier_gain")) or
                    ref["after_raw_fan"]!=ref["before_raw_fan"]+1 or
                    ref["capped_multiplier_gain"]!=(
                        ref["after_multiplier"]-ref["before_multiplier"]) or
                    type(row.get("tail_proxy_effective_copies")) is not int or
                    type(row.get("tail_proxy_unknown_copies")) is not int or
                    not 0<=row["tail_proxy_effective_copies"]<=row["tail_proxy_unknown_copies"] or
                    type(row.get("tail_proxy_effective_fraction")) not in (float,int) or
                    abs(row["tail_proxy_effective_fraction"]-
                        row["tail_proxy_effective_copies"]/
                        row["tail_proxy_unknown_copies"])>1e-6 or
                    type(safe) is not dict or
                    (risk is not None and type(risk) is not dict) or
                    (row["constructed_same_view_rob_witness_found"] !=
                        (risk is not None)) or
                    safe.get("cash_from_late_kong")!=0 or
                    (risk is not None and risk.get("cash_from_late_kong")!=0) or
                    safe.get("kong_was_completed") is not True or
                    safe.get("tail_was_consumed") is not True or
                    (risk is not None and (risk.get("robbed") is not True or
                       risk.get("kong_was_completed") is not False or
                       risk.get("tail_was_consumed") is not False or
                       risk.get("rob_winner_count")!=1 or
                       risk.get("physical_count")!=108)) or
                    safe.get("physical_count")!=108):
                raise ValueError("invalid authoritative cashless/rob/tail record")
            cases.append(row)
    return {
        "protocol":PROTOCOL,
        "constructed_checkpoints":len(cases),
        "independent_natural_games":0,
        "conditional_root_multiplier_gain_counts":dict(Counter(
            row["conditional_completed_hand_root"]["capped_multiplier_gain"]
            for row in cases)),
        "legally_robbed_hidden_world_count":sum(
            row["constructed_same_view_rob_witness_found"] for row in cases),
        "rob_probability":None,
        "future_tail_known_to_actor":False,
        "official_EV_estimate":None,
        "online_policy_changed":False,
        "cases":cases,
        "limitations":[
            "Reference completed hands are hypothetical examples, NOT projected outcomes of the actual checkpoint.",
            "Tail effective-copy fraction assumes exchangeable unseen physical copies; the genuine future wall is not exposed.",
            "Rob witnesses use only one selected hand-shape family; no witness found is NOT proof of zero rob risk.",
            "When a witness exists, it is a constructed alternative hidden world with identical actor observations.",
            "No observed rob probability, win rate, realized strategy EV, or long-run AI improvement is established.",
        ],
    }
