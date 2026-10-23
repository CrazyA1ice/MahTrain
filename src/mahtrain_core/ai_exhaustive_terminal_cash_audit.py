"""M4.16 retrospective, authoritative Sichuan exhaustive/da-jiao ledger audit.

Replays the already-used M4.14 shuffle seeds and its EXACT frozen policy.
Terminal classifications come only from trusted engine public_state() after
terminal, NEVER from opponent concealed hands or future wall in decision time.
No new policy, no local causal claims, no deployment.
"""
from __future__ import annotations
from collections import Counter
from statistics import mean
from typing import Any, Mapping

from .ai_action_extended_study import _fixed_lineup
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_discard_nearvalue_risk_paired import (
    ARMS, METRICS, NearValueDefenseResearchAgent,
)
from .ai_tournament import simulate_match
from .exhaustive_review import finalize_active_only

PROTOCOL = "m416_authoritative_exhaustive_classes_da_jiao_postgame_v1"
STAGES = ("flower_pig", "da_jiao")
LABELS = ("flower_pig", "listening", "unready")


def audited_terminal(
    board: Mapping[str,Any], *, seat:int, phase:str,
    expected_exhaustive:int,
) -> dict[str,Any]:
    """Validate and summarize ONLY official terminal transfers.

    No per-opponent status, hand, wait tile, wall contents or transcript
    is emitted. The posted one-time authority is reconstructed from the
    rule engine's terminal-only public preview.
    """
    if type(seat) is not int or seat not in range(4):
        raise ValueError("invalid player seat")
    if type(expected_exhaustive) is not int:
        raise ValueError("invalid official expected settlement")
    if phase not in ("wall_exhausted","finished") or board.get("phase")!=phase:
        raise RuntimeError("terminal state mismatch")
    won=board.get("won")
    if type(won) is not list or len(won)!=4 or any(type(x) is not bool for x in won):
        raise RuntimeError("invalid authoritative winner mask")
    settlement=board.get("exhaustive_settlement")
    preview=board.get("exhaustive_review")
    if phase=="finished":
        if settlement is not None or preview is not None or expected_exhaustive!=0:
            raise RuntimeError("finished before wall exhaustion cannot charge da-jiao")
        return {
            "terminal_phase":"finished","active_count":sum(not s for s in won),
            "terminal_class":"already_won" if won[seat] else "not_exhausted",
            "class_counts":{x:0 for x in LABELS},
            "own_wait_count":None,"own_max_effective_fan":None,
            "flower_pig_balance":0,"da_jiao_balance":0,
            "official_exhaustive_balance":0,
            "transfer_counts":{x:0 for x in STAGES},
            "own_stage_payment_counts":{x:0 for x in STAGES},
            "own_stage_receipt_counts":{x:0 for x in STAGES},
        }
    if not isinstance(settlement,dict) or not isinstance(preview,dict):
        raise RuntimeError("wall exhausted but missing official review/posting")
    if settlement.get("posted") is not True:
        raise RuntimeError("unposted or deferred settlement not evidence of cash")
    rules=board.get("win_ledger") or {}
    coefficient=rules.get("room_coefficient")
    cap=rules.get("fan_cap")
    if type(coefficient) is not int or coefficient<=0 or (
            type(cap) is not int or not 0<=cap<=12):
        raise RuntimeError("missing room authority price/cap")
    recomputed=finalize_active_only(preview,won=won,
                                     coefficient=coefficient,fan_cap=cap)
    if settlement != recomputed:
        raise RuntimeError("posted authoritative da-jiao differs from rule review")
    entries=settlement["entries"]
    if (type(entries) is not list or
            type(settlement.get("balances")) is not list or
            len(settlement["balances"])!=4 or
            any(type(v) is not int for v in settlement["balances"]) or
            sum(settlement["balances"])!=0):
        raise RuntimeError("missing or nonzero-sum exhaustive authority")
    classification=preview.get("seats")
    if not isinstance(classification,list):
        raise RuntimeError("absent terminal active classification")
    active=[i for i,flag in enumerate(won) if not flag]
    if preview.get("participating_active_seats")!=active or (
            sorted(x.get("seat") for x in classification)!=active):
        raise RuntimeError("classification does not cover all active players")
    categories=Counter(item.get("classification") for item in classification)
    if any(label not in LABELS for label in categories):
        raise RuntimeError("unresolved or incorrect terminal class")
    own=next((x for x in classification if x["seat"]==seat),None)
    if won[seat] and own is not None or not won[seat] and own is None:
        raise RuntimeError("winner cannot be included in active da-jiao transfer")
    money=Counter()
    count=Counter()
    own_out=Counter()
    own_in=Counter()
    for number,entry in enumerate(entries,1):
        if type(entry) is not dict or entry.get("index")!=number:
            raise RuntimeError("duplicate or out-of-order posted transfer")
        kind=entry.get("stage")
        payer,recipient,amount=(entry.get("payer"),entry.get("recipient"),
                                entry.get("amount"))
        if (kind not in STAGES or
                type(payer) is not int or type(recipient) is not int or
                payer==recipient or payer not in active or recipient not in active or
                type(amount) is not int or amount<=0):
            raise RuntimeError("illegal exhaustive participant or transfer")
        count[kind]+=1
        if payer==seat:
            money[kind]-=amount
            own_out[kind]+=1
        if recipient==seat:
            money[kind]+=amount
            own_in[kind]+=1
        if kind=="flower_pig":
            if amount != 8*coefficient:
                raise RuntimeError("incorrect flower-pig multiplier")
        else:
            fan=entry.get("effective_fan")
            if type(fan) is not int or not 0<=fan<=cap or (
                    amount != coefficient*2**fan):
                raise RuntimeError("incorrect posted maximum ready-hand fan")
    if sum(money[x] for x in STAGES)!=expected_exhaustive or (
            settlement["balances"][seat]!=expected_exhaustive):
        raise RuntimeError("own official exhaustive amount does not reconcile")
    return {
        "terminal_phase":phase,"active_count":len(active),
        "terminal_class":own["classification"] if own else "already_won",
        "class_counts":{x:categories[x] for x in LABELS},
        "own_wait_count":own["wait_count"] if own else None,
        "own_max_effective_fan":(
            own["max_effective_fan"] if own and
            own["classification"]=="listening" else None),
        "flower_pig_balance":money["flower_pig"],
        "da_jiao_balance":money["da_jiao"],
        "official_exhaustive_balance":expected_exhaustive,
        "transfer_counts":{x:count[x] for x in STAGES},
        "own_stage_payment_counts":{x:own_out[x] for x in STAGES},
        "own_stage_receipt_counts":{x:own_in[x] for x in STAGES},
    }


def paired_position(seed:int,rotation:int)->dict[str,Any]:
    if (type(seed) is not int or not 0<=seed<2**32 or
            type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid fixed retrospective shuffle/seat")
    lineup,seat=_fixed_lineup(rotation)
    arms={}
    for arm in ARMS:
        agent=NearValueDefenseResearchAgent(seed=seed,seat=seat,arm=arm)
        authority:dict[str,Any]={}
        def capture(game:Any)->None:
            authority["game"]=game
        match=simulate_match(seed,rotation=rotation%3,lineup=lineup,
                             offline_kong_base=1,
                             offline_agent_overrides={seat:agent},
                             offline_observer=capture)
        if "game" not in authority or (
            authority["game"].phase!=match["terminal_phase"]):
            raise RuntimeError("terminal game reference unavailable")
        board=authority["game"].public_state()
        official=_official_outcome(match,seat,lineup)
        terminal=audited_terminal(board,seat=seat,
                                  phase=match["terminal_phase"],
                                  expected_exhaustive=official["exhaustive_points"])
        arms[arm]={
            "official":official,"terminal":terminal,
            "counts":agent.safe_counts(),
            "_trace":match["trace"],"_events":match["public_events"],
        }
    b,c=arms["baseline"],arms["nearvalue_defense"]
    interventions=c["counts"].get("actual_changes",0)
    if not interventions and (
            b["official"]!=c["official"] or b["terminal"]!=c["terminal"] or
            b["_trace"]!=c["_trace"] or b["_events"]!=c["_events"]):
        raise RuntimeError("no actual altered cut yet paired path diverged")
    delta={k:c["official"][k]-b["official"][k] for k in METRICS}
    if delta["official_net"]!=sum(delta[k] for k in (
            "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("paired official scores do not reconcile")
    if delta["exhaustive_points"]!=sum(
            c["terminal"][x]-b["terminal"][x] for x in
            ("flower_pig_balance","da_jiao_balance")):
        raise RuntimeError("da-jiao vs flower pig partition does not balance")
    for arm in ARMS:
        del arms[arm]["_trace"]
        del arms[arm]["_events"]
    return {
        "seed":seed,"rotation":rotation,"challenge_seat":seat,
        "real_interventions":interventions,
        "arms":{a:{"official":arms[a]["official"],
                   "terminal":arms[a]["terminal"]} for a in ARMS},
        "official_deltas":delta,
        "terminal_stage_deltas":{
            "flower_pig":c["terminal"]["flower_pig_balance"]-
                            b["terminal"]["flower_pig_balance"],
            "da_jiao":c["terminal"]["da_jiao_balance"]-
                        b["terminal"]["da_jiao_balance"],
        },
    }


def cohort(start:int,seeds:int=4)->dict[str,Any]:
    if (type(start) is not int or type(seeds) is not int or
            not 0<=start<2**32 or not 1<=seeds<=8 or
            start+seeds>2**32):
        raise ValueError("invalid historical seed block")
    rows=[paired_position(seed,rotation) for seed in range(start,start+seeds)
          for rotation in range(4)]
    totals=Counter()
    stages=Counter()
    per_seed=[]
    changed=[]
    for seed in range(start,start+seeds):
        group=[r for r in rows if r["seed"]==seed]
        if sorted(r["challenge_seat"] for r in group)!=list(range(4)):
            raise RuntimeError("incomplete seat rotation under shuffle cluster")
        sd=Counter()
        sc=Counter()
        count=0
        for r in group:
            totals.update(r["official_deltas"])
            stages.update(r["terminal_stage_deltas"])
            sd.update(r["official_deltas"])
            sc.update(r["terminal_stage_deltas"])
            count+=r["real_interventions"]
            if r["real_interventions"]:
                changed.append(r)
        per_seed.append({
            "seed":seed,"real_interventions":count,
            "four_seat_mean_net_delta":round(sd["official_net"]/4,4),
            "exhaustive_delta":sd["exhaustive_points"],
            "flower_pig_delta":sc["flower_pig"],
            "da_jiao_delta":sc["da_jiao"],
        })
    if totals["exhaustive_points"] != sum(stages[k] for k in STAGES):
        raise RuntimeError("cohort official transfer components do not reconcile")
    return {
        "independent_shuffles":seeds,"paired_seat_positions":len(rows),
        "complete_games":len(rows)*2,
        "real_interventions":sum(r["real_interventions"] for r in rows),
        "changed_positions":len(changed),
        "official_deltas":{k:totals[k] for k in METRICS},
        "stage_deltas":{k:stages[k] for k in STAGES},
        "per_seed":per_seed,
        "changed_position_terminal_audits":changed,
        "live_policy_modified":False,
        "causal_action_attribution":None,
    }


def study()->dict[str,Any]:
    return {
        "protocol":PROTOCOL,
        "retrospective_not_independent_holdout":True,
        "online_policy_modified":False,
        "development":cohort(52000,4),
        "holdout":cohort(53000,4),
        "limitations":[
            "Terminal status and fan were learned only AFTER final settlement.",
            "Opponent concealed hands, waits, and full trace are not exported.",
            "Final balances describe complete branched game paths, not the local discard EV.",
            "Retrospective M4.14 seeds are not independent new validation.",
            "No deployment of a new wall-stage or da-jiao policy is authorized.",
        ],
    }
