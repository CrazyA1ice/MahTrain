"""M4.19 descriptive Pareto frontier for ACTUAL one-shanten challenge discards.

Offline observation only. Three documented public proxy objectives:
- MAX publicly unknown effective copies
- MAX original fan/shape weighted copies
- MIN original additive public threat index

No altered cut, no fresh expensive hand evaluations, no concealed opponents,
no future wall, and no calibrated P(tenpai)/P(Ron) claims. Pareto dominance of
these proxies is NOT causal evidence of a stronger Mahjong action.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
from statistics import mean
from typing import Any, Mapping, Sequence

from .ai import MahjongAgent
from .ai_action_extended_study import _fixed_lineup
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_tournament import simulate_match
from .rules import TILE_INDEX

PROTOCOL="m419_one_shanten_public_pareto_frontier_observational_v1"
OBJECTIVES={
    "effective_tile_count":"maximize",
    "expected_fan_weighted_copies":"maximize",
    "table_threat_index":"minimize",
}
METRICS=("official_net","win_points","kong_points","exhaustive_points")


def dominates(a:Mapping[str,Any],b:Mapping[str,Any])->bool:
    """Weakly better on all three measured proxies AND strictly on >=1."""
    return (
        a["effective_tile_count"]>=b["effective_tile_count"] and
        a["expected_fan_weighted_copies"]>=b["expected_fan_weighted_copies"] and
        a["table_threat_index"]<=b["table_threat_index"] and
        (
            a["effective_tile_count"]>b["effective_tile_count"] or
            a["expected_fan_weighted_copies"]>b["expected_fan_weighted_copies"] or
            a["table_threat_index"]<b["table_threat_index"]
        )
    )


def one_shanten_pareto(
    original:str,
    ranked:Sequence[Mapping[str,Any]],
    view:Mapping[str,Any],
)->dict[str,Any]:
    """Anonymous current-legal-frontier facts; absolutely no tile labels out."""
    if not ranked or len(ranked)<2:
        raise ValueError("Pareto frontier requires >=2 actual ranked cuts")
    if ranked[0].get("discard")!=original or (
            type(ranked[0].get("shanten")) is not int or
            ranked[0]["shanten"]!=1):
        raise ValueError("requires actual original one-shanten choice")
    hand=view.get("hand")
    if type(hand) is not list or original not in hand:
        raise ValueError("missing authorized own hand/current cut")
    seen=set()
    for r in ranked:
        tile=r.get("discard")
        if (tile not in TILE_INDEX or tile not in hand or tile in seen or
                type(r.get("shanten")) is not int or r["shanten"]!=1):
            raise RuntimeError("rank includes repeated, unavailable, or regressing cut")
        seen.add(tile)
        for name in OBJECTIVES:
            value=r.get(name)
            if (type(value) not in (int,float) or
                    not isfinite(value) or value<0 or
                    (name=="effective_tile_count" and type(value) is not int)):
                raise RuntimeError("missing or invalid original public proxy")
    front=[
        i for i,x in enumerate(ranked)
        if not any(i!=j and dominates(y,x)
                   for j,y in enumerate(ranked))
    ]
    selected=ranked[0]
    dominators=[x for x in ranked[1:] if dominates(x,selected)]
    # A Pareto-optimal choice can still be a poor actual Mahjong choice;
    # this is a strictly descriptive, current-information comparison.
    gains=[{
        "effective_copy_gain":x["effective_tile_count"]-
                              selected["effective_tile_count"],
        "weighted_copy_gain":round(
            x["expected_fan_weighted_copies"]-
            selected["expected_fan_weighted_copies"],5),
        "threat_reduction":round(
            selected["table_threat_index"]-x["table_threat_index"],6),
    } for x in dominators]
    if bool(dominators)==(0 in front):
        raise RuntimeError("selected Pareto membership is inconsistent")
    return {
        "candidate_count":len(ranked),
        "pareto_frontier_count":len(front),
        "selected_nondominated":not dominators,
        "dominating_alternatives":len(dominators),
        "selected_max_effective_copies":(
            selected["effective_tile_count"]==
            max(x["effective_tile_count"] for x in ranked)
        ),
        "selected_max_weighted_copies":(
            selected["expected_fan_weighted_copies"]==
            max(x["expected_fan_weighted_copies"] for x in ranked)
        ),
        "selected_min_public_threat":(
            selected["table_threat_index"]==
            min(x["table_threat_index"] for x in ranked)
        ),
        "any_more_copies":any(
            x["effective_tile_count"]>selected["effective_tile_count"]
            for x in ranked[1:]),
        "any_more_weighted_value":any(
            x["expected_fan_weighted_copies"]>
            selected["expected_fan_weighted_copies"] for x in ranked[1:]),
        "any_lower_threat":any(
            x["table_threat_index"]<selected["table_threat_index"]
            for x in ranked[1:]),
        "maximum_dominator_copy_gain":max(
            (x["effective_copy_gain"] for x in gains),default=0),
        "maximum_dominator_weighted_gain":max(
            (x["weighted_copy_gain"] for x in gains),default=0.0),
        "maximum_dominator_threat_reduction":max(
            (x["threat_reduction"] for x in gains),default=0.0),
    }


class ParetoObservationAgent(MahjongAgent):
    """Strict original challenge behavior with bounded summary-only telemetry."""
    def __init__(self,*,seed:int,seat:int)->None:
        super().__init__("challenge",seed=seed,seat=seat)
        self.counts:Counter[str]=Counter()
        self._max_dominator_copy_gain=0
        self._max_dominator_weighted_gain=0.0
        self._max_dominator_threat_reduction=0.0

    def discard(self,view:Mapping[str,Any])->str:
        chosen=super().discard(view)
        self.counts["total_cuts"]+=1
        ranked=getattr(self,"_last_discard_scores",None)
        if not ranked:
            self.counts["no_challenge_rank"]+=1
            return chosen
        if ranked[0].get("discard")!=chosen:
            raise RuntimeError("original action does not match current rank")
        shanten=ranked[0].get("shanten")
        if type(shanten) is not int:
            raise RuntimeError("original rank lacks exact shanten")
        if shanten!=1:
            self.counts["rank_not_one_shanten"]+=1
            return chosen
        if len(ranked)==1:
            self.counts["one_shanten_single_rank"]+=1
            return chosen
        row=one_shanten_pareto(chosen,ranked,view)
        self.counts["one_shanten_multi"]+=1
        self.counts["nondominated"]+=int(row["selected_nondominated"])
        self.counts["dominated"]+=int(not row["selected_nondominated"])
        self.counts["total_legal_ranked_options"]+=row["candidate_count"]
        self.counts["total_pareto_frontier_options"]+=row["pareto_frontier_count"]
        self.counts["total_dominating_alternatives"]+=row["dominating_alternatives"]
        for indicator in (
            "selected_max_effective_copies",
            "selected_max_weighted_copies",
            "selected_min_public_threat",
            "any_more_copies","any_more_weighted_value","any_lower_threat",
        ):
            self.counts[indicator]+=int(row[indicator])
        self._max_dominator_copy_gain=max(
            self._max_dominator_copy_gain,
            row["maximum_dominator_copy_gain"])
        self._max_dominator_weighted_gain=max(
            self._max_dominator_weighted_gain,
            row["maximum_dominator_weighted_gain"])
        self._max_dominator_threat_reduction=max(
            self._max_dominator_threat_reduction,
            row["maximum_dominator_threat_reduction"])
        return chosen

    def safe_report(self)->dict[str,Any]:
        if self.counts["total_cuts"]!=sum(
            self.counts[k] for k in (
                "no_challenge_rank","rank_not_one_shanten",
                "one_shanten_single_rank","one_shanten_multi")
        ) or self.counts["one_shanten_multi"]!=sum(
            self.counts[k] for k in ("dominated","nondominated")
        ):
            raise RuntimeError("incomplete noninvasive Pareto audit funnel")
        return {
            "counts":dict(self.counts),
            "max_dominator_copy_gain":self._max_dominator_copy_gain,
            "max_dominator_weighted_gain":self._max_dominator_weighted_gain,
            "max_dominator_threat_reduction":self._max_dominator_threat_reduction,
        }


def audited_position(seed:int,rotation:int)->dict[str,Any]:
    if (type(seed) is not int or not 0<=seed<2**32 or
            type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid unsigned shuffle or balanced seat rotation")
    lineup,seat=_fixed_lineup(rotation)
    observer=ParetoObservationAgent(seed=seed,seat=seat)
    match=simulate_match(
        seed,rotation=rotation%3,lineup=lineup,offline_kong_base=1,
        offline_agent_overrides={seat:observer},
    )
    if match["physical_count"]!=108:
        raise RuntimeError("physical deck was not conserved")
    money=_official_outcome(match,seat,lineup)
    if money["official_net"]!=sum(money[k] for k in (
            "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("official one-shot ledger did not reconcile")
    return {
        "seed":seed,"rotation":rotation,"challenge_seat":seat,
        "official":{k:money[k] for k in METRICS},
        "observed":observer.safe_report(),
        "terminal_phase":match["terminal_phase"],
        "candidate_actions_changed":0,
    }


def cohort(start:int,seeds:int=4)->dict[str,Any]:
    if (type(start) is not int or type(seeds) is not int or
            not 0<=start<2**32 or not 1<=seeds<=8 or start+seeds>2**32):
        raise ValueError("invalid 1..8 independent shuffle seeds")
    positions=[audited_position(seed,rotation)
               for seed in range(start,start+seeds) for rotation in range(4)]
    total=Counter()
    per_seed=[]
    maxima=Counter()
    for seed in range(start,start+seeds):
        group=[r for r in positions if r["seed"]==seed]
        if sorted(x["challenge_seat"] for x in group)!=[0,1,2,3]:
            raise RuntimeError("seed lacks exact 4 challenge seat rotations")
        local=Counter()
        for row in group:
            local.update(row["observed"]["counts"])
            total.update(row["observed"]["counts"])
            for k in ("max_dominator_copy_gain","max_dominator_weighted_gain",
                      "max_dominator_threat_reduction"):
                maxima[k]=max(maxima[k],row["observed"][k])
            if row["candidate_actions_changed"]:
                raise RuntimeError("descriptive audit changed a live move")
        per_seed.append({
            "seed":seed,
            "one_shanten_multiple_cut_windows":local["one_shanten_multi"],
            "selected_dominated_windows":local["dominated"],
            "selected_nondominated_windows":local["nondominated"],
        })
    if total["dominated"]+total["nondominated"]!=total["one_shanten_multi"]:
        raise RuntimeError("Pareto choice classification incomplete")
    n=total["one_shanten_multi"]
    return {
        "independent_shuffle_seeds":seeds,
        "audited_real_games":len(positions),
        "candidate_actions_changed":0,
        "baseline_total_cuts":total["total_cuts"],
        "baseline_one_shanten_multiple_cut_windows":n,
        "selected_dominated_windows":total["dominated"],
        "selected_nondominated_windows":total["nondominated"],
        "dominated_window_fraction":(
            round(total["dominated"]/n,5) if n else None),
        "total_legal_ranked_options":total["total_legal_ranked_options"],
        "total_frontier_options":total["total_pareto_frontier_options"],
        "mean_frontier_options_per_window":(
            round(total["total_pareto_frontier_options"]/n,4) if n else None),
        "other_public_proxy_comparisons":{
            k:total[k] for k in (
                "selected_max_effective_copies",
                "selected_max_weighted_copies",
                "selected_min_public_threat",
                "any_more_copies","any_more_weighted_value","any_lower_threat",
                "total_dominating_alternatives",
            )
        },
        "largest_observed_dominator_margins":dict(maxima),
        "counts":dict(total),"per_seed":per_seed,
        "online_ai_modified":False,
        "any_policy_alternative_executed":False,
        "causal_improvement_estimate":None,
        "probability_of_ron":None,
    }


def study(*,historical_development:int=56000,historical_holdout:int=57000,
          fresh_development:int=58000,fresh_holdout:int=59000,
          seeds:int=4)->dict[str,Any]:
    starts=(historical_development,historical_holdout,
            fresh_development,fresh_holdout)
    if (type(seeds) is not int or not 1<=seeds<=8 or
            any(type(x) is not int or not 0<=x<2**32 or x+seeds>2**32
                for x in starts) or
            any(a<b+seeds and b<a+seeds for i,a in enumerate(starts)
                for b in starts[i+1:])):
        raise ValueError("four pairwise disjoint fixed shuffle blocks required")
    return {
        "protocol":PROTOCOL,"observational_only":True,
        "online_ai_modified":False,
        "objectives":OBJECTIVES,
        "historical_development":cohort(historical_development,seeds),
        "historical_holdout":cohort(historical_holdout,seeds),
        "fresh_development":cohort(fresh_development,seeds),
        "fresh_holdout":cohort(fresh_holdout,seeds),
        "limitations":[
            "These three public objectives are proxies; the challenge ranking uses more factors.",
            "A dominated proxy choice is not proven worse in actual game winnings.",
            "Frontier membership is not proof of optimal Mahjong or causal value.",
            "Publicly unknown effective copies do not reveal copies in the future wall.",
            "Historical blocks were used in M4.18; fresh blocks are descriptive replication.",
            "Four seat rotations with one seed are correlated, not independent trials.",
            "No alternative is executed, so no outcome improvement can be inferred.",
        ],
    }
