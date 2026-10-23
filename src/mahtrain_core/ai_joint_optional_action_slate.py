"""M4.04: research-only joint ranking of pass / peng / ming-gang.

On-line MahjongAgent is deliberately NOT changed. This evaluates the public,
owner-authorized prechoice outlook for every *legal* option in one table,
including the forced next discard after a peng. It is a cheap next-draw proxy
rather than a full-game EV; actual win/kong/wall net is measured separately.
"""
from __future__ import annotations

from collections import Counter
from statistics import mean
from time import perf_counter_ns
from typing import Any, Mapping

from .ai import (
    MahjongAgent, _own_view, _call_settings, _call_outlook, _cut_shanten,
    _outlook_better_than_baseline,
)
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_action_extended_study import _fixed_lineup
from .ai_tournament import simulate_match
from .rules import TILE_INDEX

PROTOCOL="m404_joint_optional_claim_action_slate_paired_v1"
ARMS=("baseline","joint_slate")
METRICS=("official_net","win_points","kong_points","exhaustive_points",
         "win_events","deal_in_events","realized_kongs")
ACTIONS=("pass","peng","ming_gang")


def _rank_key(candidate:Mapping[str,Any])->tuple:
    """Lexicographic: exact postaction shanten, normalized shape value, copies.

    Validity comes from the SAME authorization and guardrails as the baseline
    (verified tian-ting, peng shanten/ukeire gain, kong >=75% retention).
    A bonus for immediate Kong money is deliberately NOT invented as EV.
    """
    return (-candidate["shanten"],candidate["relative_value"],
            candidate["relative_ukeire"],
            {"pass":2,"peng":1,"ming_gang":0}[candidate["action"]])


def optional_claim_slate(view:Mapping[str,Any])->list[dict[str,Any]]:
    options=view.get("claim_options") or []
    if (view.get("phase")!="claim_window" or
        not options or "pass" not in options):
        raise ValueError("claim evaluator requires an authorized decision window")
    if "hu" in options:
        return [{"action":"hu","admissible":True,"mandatory_win":True}]
    if not any(x in options for x in ("peng","ming_gang")):
        return [{"action":"pass","admissible":True,
                 "mandatory_win":False,"relative_value":1.0,
                 "relative_ukeire":1.0}]
    hand,melds,missing=_own_view(view)
    public,cap,tian=_call_settings(view)
    target=view["pending_discard"]["tile"]
    if target not in TILE_INDEX or public.count(target)<1:
        raise ValueError("claim target is not present in public known copies")
    baseline=_call_outlook(hand,melds,missing,public,cap,tian)
    if baseline["shanten"]<0:
        raise RuntimeError("cannot score call from impossible baseline")
    result=[]
    def append(action:str,outlook:Mapping[str,Any],valid:bool,
               *,best_cut:str|None=None):
        value=float(outlook["value"])
        ukeire=int(outlook["ukeire"])
        result.append({
            "action":action,"admissible":bool(valid),
            "mandatory_win":False,
            "shanten":int(outlook["shanten"]),
            "ukeire":ukeire,"value":value,
            "relative_value":round(
                value/max(1.,float(baseline["value"])),6),
            "relative_ukeire":round(
                ukeire/max(1.,float(baseline["ukeire"])),6),
            # The actual discard identity is *not* exported to research JSON.
            "best_cut":best_cut,
        })
    append("pass",baseline,True)
    # The public river contains the offered tile once; after a meld it is
    # visibly EXPOSED and must not be counted a second time in remaining-copy
    # estimates. Both peng and ming-gang use exactly the same corrected base.
    visible_after=list(public)
    visible_after.remove(target)
    if "ming_gang" in options:
        remainder=list(hand)
        for _ in range(3):remainder.remove(target)
        after=_call_outlook(
            remainder,[*melds,{"type":"ming_gang","tile":target}],
            missing,visible_after,cap,tian)
        allowed=(not tian.get("eligible") or after["tian_kept"]) and (
            _outlook_better_than_baseline(after,baseline,fraction=.75))
        append("ming_gang",after,allowed)
    if "peng" in options:
        remainder=list(hand)
        for _ in range(2):remainder.remove(target)
        groups=[*melds,{"type":"peng","tile":target}]
        unique=sorted(set(remainder),key=TILE_INDEX.__getitem__)
        missing_cuts=[cut for cut in unique if cut[0]==missing]
        if missing_cuts:unique=missing_cuts
        if not unique:
            raise RuntimeError("peng did not leave a legal discard")
        stages=[(cut,_cut_shanten(remainder,groups,missing,cut))
                for cut in unique]
        best=min(stage for _,stage in stages)
        # Avoid expensive full-ply scoring for objectively losing shanten,
        # but for equal/better stages check EACH best cut and retain the one
        # with greatest public-copy next-draw shape (including fan).
        finalists=[]
        if best<=baseline["shanten"] and not tian.get("eligible"):
            for cut,stage in stages:
                if stage!=best:continue
                after=list(remainder);after.remove(cut)
                outlook=_call_outlook(
                    after,groups,missing,[*visible_after,cut],cap,tian)
                finalists.append((outlook,cut))
        if finalists:
            best_outlook,cut=max(
                finalists,key=lambda x:(
                    x[0]["value"],x[0]["ukeire"],-TILE_INDEX[x[1]]))
        else:
            best_outlook={"shanten":best,"ukeire":0,"value":0}
            cut=None
        legal=(not tian.get("eligible") and (
            best<baseline["shanten"] or
            (best==baseline["shanten"] and best>0 and
             best_outlook["ukeire"]>=baseline["ukeire"]+3)))
        append("peng",best_outlook,legal,best_cut=cut)
    # Always keep the actual authorized option in the table, but rank all
    # admissible options simultaneously instead of giving ming-gang priority
    # merely because it is evaluated first. Deterministic, no hidden access.
    return sorted(result,key=lambda x:(
        not x["admissible"],tuple(-v for v in _rank_key(x)))
        )


def preferred_optional_claim(view:Mapping[str,Any])->str:
    ordered=optional_claim_slate(view)
    if ordered[0].get("mandatory_win"):
        return "hu"
    return max((x for x in ordered if x["admissible"]),key=_rank_key)["action"]


class JointSlateResearchAgent(MahjongAgent):
    def __init__(self,*,seed:int,seat:int,arm:str)->None:
        if arm not in ARMS:
            raise ValueError("unknown offline optional-call policy")
        super().__init__("challenge",seed=seed,seat=seat)
        self.arm=arm
        self.counts:Counter[str]=Counter()
        self.elapsed_ns=0

    def response(self,view:Mapping[str,Any],*,rob:bool=False)->str:
        start=perf_counter_ns()
        baseline=super().response(view,rob=rob)
        choices=view["rob_options"] if rob else view["claim_options"]
        if rob or "hu" in choices:
            self.counts["verified_hu_offered"]+=int("hu" in choices)
            self.counts["verified_hu_taken"]+=int(baseline=="hu")
            self.elapsed_ns+=perf_counter_ns()-start
            return baseline
        if not any(x in choices for x in ("peng","ming_gang")):
            self.elapsed_ns+=perf_counter_ns()-start
            return baseline
        self.counts["optional_claim_windows"]+=1
        self.counts["multiple_active_options"]+=int(
            "peng" in choices and "ming_gang" in choices)
        slate=optional_claim_slate(view)
        choice=preferred_from_slate(slate)
        if choice not in choices:
            raise RuntimeError("slate generated an illegal claim")
        self.counts["action_disagreements"]+=int(choice!=baseline)
        self.counts["baseline_"+baseline]+=1
        self.counts["slate_"+choice]+=1
        self.counts["selected_changed"]+=int(
            self.arm=="joint_slate" and choice!=baseline)
        self.elapsed_ns+=perf_counter_ns()-start
        return choice if self.arm=="joint_slate" else baseline

    def kong(self,view:Mapping[str,Any])->dict[str,str]|None:
        # The online challenge evaluator already scores EVERY authorized
        # an-gang/bu-gang option and can choose to skip. Retain it in both arms.
        result=super().kong(view)
        self.counts["own_kong_windows"]+=int(bool(view["kong_options"]))
        self.counts["own_kong_candidates"]+=len(view["kong_options"])
        self.counts["own_kong_taken"]+=int(result is not None)
        return result

    def safe_counts(self)->dict[str,int]:
        return dict(self.counts)


def preferred_from_slate(slate:list[dict[str,Any]])->str:
    if any(x.get("mandatory_win") for x in slate):
        return "hu"
    legal=[x for x in slate if x["admissible"]]
    if not legal:
        raise RuntimeError("slate excluded mandatory pass")
    return max(legal,key=_rank_key)["action"]


def _one(seed:int,rotation:int)->dict[str,Any]:
    if (type(seed) is not int or not 0<=seed<2**32
        or type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid natural paired identity")
    lineup,seat=_fixed_lineup(rotation)
    row={"seed":seed,"rotation":rotation,"challenge_seat":seat,"arms":{}}
    for arm in ARMS:
        agent=JointSlateResearchAgent(seed=seed,seat=seat,arm=arm)
        outcome=simulate_match(seed,rotation=rotation%3,lineup=lineup,
                               offline_kong_base=1,
                               offline_agent_overrides={seat:agent})
        row["arms"][arm]={
            "official":_official_outcome(outcome,seat,lineup),
            "counts":agent.safe_counts(),
            "evaluation_elapsed_ms":round(agent.elapsed_ns/1_000_000,3),
            "terminal_phase":outcome["terminal_phase"],
        }
    return row


def cohort(start:int,seeds:int)->dict[str,Any]:
    if type(start) is not int or type(seeds) is not int or not (
        0<=start<2**32 and 1<=seeds<=8 and start+seeds<=2**32):
        raise ValueError("invalid fixed paired seed cohort")
    rows=[_one(seed,r) for seed in range(start,start+seeds)
          for r in range(4)]
    totals={arm:Counter() for arm in ARMS}
    per_seed=[]
    for seed in range(start,start+seeds):
        choices=[x for x in rows if x["seed"]==seed]
        if sorted(x["challenge_seat"] for x in choices)!=[0,1,2,3]:
            raise RuntimeError("not all four independent seat rotations")
        changes={}
        for arm in ARMS:
            for item in choices:
                totals[arm].update(item["arms"][arm]["counts"])
            changes[arm]=round(sum(
                item["arms"][arm]["official"]["official_net"] for item in choices)/4,4)
        per_seed.append({
            "seed":seed,"net_by_arm":changes,
            "four_seat_net_delta":round(
                changes["joint_slate"]-changes["baseline"],4),
        })
    by_metric={}
    for metric in METRICS:
        deltas=[
            item["arms"]["joint_slate"]["official"][metric]-
            item["arms"]["baseline"]["official"][metric] for item in rows]
        by_metric[metric]=sum(deltas)
    if by_metric["official_net"]!=sum(by_metric[x] for x in (
        "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("official aggregate components failed reconciliation")
    return {
        "independent_shuffle_seeds":seeds,"full_games":len(rows)*2,
        "four_seat_pairs":len(rows),
        "counterfactual_mean_seed_delta":round(mean(
            row["four_seat_net_delta"] for row in per_seed),4),
        "positive_delta_seeds":sum(x["four_seat_net_delta"]>0 for x in per_seed),
        "negative_delta_seeds":sum(x["four_seat_net_delta"]<0 for x in per_seed),
        "ties":sum(x["four_seat_net_delta"]==0 for x in per_seed),
        "sum_official_component_deltas":by_metric,
        "aggregate_counts":{arm:dict(totals[arm]) for arm in ARMS},
        "per_seed":per_seed,"positions":rows,
        "confidence_interval_95pct":None,
    }


def study(*,development:int=32000,holdout:int=33000,
          seeds:int=4)->dict[str,Any]:
    if (type(development) is not int or type(holdout) is not int or
        type(seeds) is not int or not 1<=seeds<=8 or
        not 0<=development<2**32 or not 0<=holdout<2**32 or
        max(development,holdout)+seeds>2**32 or
        (development<holdout+seeds and holdout<development+seeds)):
        raise ValueError("overlapping or invalid preregistered paired seed groups")
    return {
        "protocol":PROTOCOL,
        "live_policy_modified":False,
        "public_only_slate":True,
        "development_seed_range":[development,development+seeds],
        "holdout_seed_range":[holdout,holdout+seeds],
        "development":cohort(development,seeds),
        "holdout":cohort(holdout,seeds),
        "limitations":[
            "Joint slate is a next-draw shanten / fan-weighted public-copy surrogate, not exact multiround expected utility.",
            "Immediate kong points and rob-Hu odds are not given fabricated values inside the slate.",
            "Legal Hu, including rob-Hu, is never overridden; original full own-kong slate stays unchanged.",
            "Paired outcome delta reflects altered trajectories; same initial shuffle is a paired comparison not a same-future counterfactual.",
            "A single seed has four correlated seat rotations, never four independent experiments.",
            "Four seeds per group is too few to report a 95-percent confidence interval.",
            "No real-time MahjongAgent or web server changes until independent terminal payoffs justify adoption.",
        ],
    }
