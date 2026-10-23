"""M4.14: frozen near-equal-value, lower public-risk discard paired study.

Offline-only: the unmodified challenge computes its normal ranked candidates
ONCE, then this observer may substitute a *different* authorized minimum-
shanten cut. Both official paths use the same seed and all other challenge
actions. Public threat is an additive descriptive index, not a P(Ron).
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

PROTOCOL="m414_frozen_public_risk_nearvalue_discard_paired_v1"
ARMS=("baseline","nearvalue_defense")
MIN_PUBLIC_THREAT_REDUCTION=0.08
MIN_VALUE_RETENTION=0.80
MIN_UKEIRE_RETENTION=0.85
METRICS=("official_net","win_points","kong_points","exhaustive_points",
         "win_events","deal_in_events","realized_kongs")


def suggest_nearvalue_defense(
    baseline:str,ranked:Sequence[Mapping[str,Any]]|None,view:Mapping[str,Any],
)->tuple[str,str]:
    """Candidate is an EXISTING same-min-shanten baseline-authorized cut.

    No new calls to effective_draws/score_win, no wall/hidden opponents,
    no changing dingque priority and no policy change to existing Tian Ting.
    The policy compares only the already computed authorized rank entries.
    """
    if not ranked or len(ranked)<2:
        return baseline,"single_minimum_cut"
    if (view.get("tian_ting") or {}).get("eligible") is True:
        return baseline,"tian_ting_protected"
    if ranked[0].get("discard")!=baseline:
        raise RuntimeError("shadow rows do not match original challenge choice")
    original=ranked[0]
    hand=view.get("hand")
    if not isinstance(hand,list) or baseline not in hand:
        raise RuntimeError("baseline cut absent from authorized own hand")
    s=original.get("shanten")
    if type(s) is not int:
        raise RuntimeError("missing exact minimum postcut shanten")
    candidates=[]
    seen=set()
    for row in ranked:
        tile=row.get("discard")
        if (tile not in TILE_INDEX or tile not in hand or tile in seen or
                row.get("shanten")!=s):
            raise RuntimeError("shadow ranking contains illegal/repeated/worse cut")
        seen.add(tile)
        for key in ("table_threat_index","expected_fan_weighted_copies",
                    "effective_tile_count"):
            number=row.get(key)
            if (type(number) not in (float,int) or not isfinite(number)
                    or number<0):
                raise RuntimeError("nonfinite or invalid authorized cut evidence")
        if tile != baseline:
            candidates.append(row)
    if (original["expected_fan_weighted_copies"] <= 0 or
            original["effective_tile_count"]<=0):
        return baseline,"no_baseline_draw_value"
    chosen=[
        row for row in candidates
        if row["table_threat_index"] <=
           original["table_threat_index"]-MIN_PUBLIC_THREAT_REDUCTION
        and row["expected_fan_weighted_copies"] >=
            original["expected_fan_weighted_copies"]*MIN_VALUE_RETENTION
        and row["effective_tile_count"] >=
            original["effective_tile_count"]*MIN_UKEIRE_RETENTION
    ]
    if not chosen:
        return baseline,"no_lower_risk_nearvalue_alternative"
    preferred=min(chosen,key=lambda r:(
        r["table_threat_index"],
        -r["expected_fan_weighted_copies"],
        -r["effective_tile_count"],
        TILE_INDEX[r["discard"]],
    ))
    return preferred["discard"],"lower_public_threat_nearvalue"


class NearValueDefenseResearchAgent(MahjongAgent):
    def __init__(self,*,seed:int,seat:int,arm:str)->None:
        if arm not in ARMS:
            raise ValueError("unknown offline research arm")
        super().__init__("challenge",seed=seed,seat=seat)
        # The tournament pressure probe requires EXACT original challenge
        # ranking. Our offline candidate deliberately tests a distinct cut;
        # skip that baseline-only probe on BOTH arms, while retaining the
        # standard legal-cut, full trace and official cash validations.
        self._offline_reference_cut=True
        self.arm=arm
        self.counts:Counter[str]=Counter()

    def discard(self,view:Mapping[str,Any])->str:
        original=super().discard(view)
        self.counts["discard_decisions"]+=1
        ranking=getattr(self,"_last_discard_scores",None)
        if ranking and len(ranking)>1:
            self.counts["multiple_minimum_shanten_cuts"]+=1
        proposed,reason=suggest_nearvalue_defense(original,ranking,view)
        self.counts["reason_"+reason]+=1
        self.counts["suggested_changes"]+=int(proposed!=original)
        chosen=proposed if self.arm=="nearvalue_defense" else original
        self.counts["actual_changes"]+=int(chosen!=original)
        if chosen not in view["hand"]:
            raise RuntimeError("research cut not authorized")
        return chosen

    def safe_counts(self)->dict[str,int]:
        if self.counts["discard_decisions"]!=sum(
                v for k,v in self.counts.items() if k.startswith("reason_")):
            raise RuntimeError("some original discards not evaluated")
        if self.counts["actual_changes"]>self.counts["suggested_changes"]:
            raise RuntimeError("unregistered extra intervention")
        if self.arm=="baseline" and self.counts["actual_changes"]:
            raise RuntimeError("original arm was changed")
        return dict(self.counts)


def paired_position(seed:int,rotation:int)->dict[str,Any]:
    if type(seed) is not int or not 0<=seed<2**32 or (
            type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid fixed independent seed / seating")
    lineup,seat=_fixed_lineup(rotation)
    arms={}
    for arm in ARMS:
        agent=NearValueDefenseResearchAgent(seed=seed,seat=seat,arm=arm)
        match=simulate_match(seed,rotation=rotation%3,lineup=lineup,
                             offline_kong_base=1,
                             offline_agent_overrides={seat:agent})
        official=_official_outcome(match,seat,lineup)
        arms[arm]={
            "official":official,"counts":agent.safe_counts(),
            "terminal_phase":match["terminal_phase"],
            "_trace":match["trace"],"_events":match["public_events"],
        }
    b,c=arms["baseline"],arms["nearvalue_defense"]
    changed=c["counts"].get("actual_changes",0)
    if changed==0 and (
            b["official"]!=c["official"] or
            b["terminal_phase"]!=c["terminal_phase"] or
            b["_trace"]!=c["_trace"] or b["_events"]!=c["_events"]):
        raise RuntimeError("untouched same-seed baseline paths diverged")
    delta={k:c["official"][k]-b["official"][k] for k in METRICS}
    if delta["official_net"]!=sum(delta[k] for k in
              ("win_points","kong_points","exhaustive_points")):
        raise RuntimeError("official paired cash components disagree")
    for arm in ARMS:
        del arms[arm]["_trace"]
        del arms[arm]["_events"]
    return {
        "seed":seed,"rotation":rotation,"challenge_seat":seat,
        "arms":arms,"paired_deltas":delta,
        "actual_interventions":changed,
        "identical_if_untouched":changed==0,
    }


def cohort(start:int,seeds:int=4)->dict[str,Any]:
    if (type(start) is not int or type(seeds) is not int or
            not 0<=start<2**32 or not 1<=seeds<=8 or start+seeds>2**32):
        raise ValueError("invalid independent shuffle block")
    positions=[paired_position(seed,r)
               for seed in range(start,start+seeds) for r in range(4)]
    all_delta=Counter()
    counts={arm:Counter() for arm in ARMS}
    per_seed=[]
    for seed in range(start,start+seeds):
        group=[p for p in positions if p["seed"]==seed]
        if sorted(p["challenge_seat"] for p in group)!=list(range(4)):
            raise RuntimeError("incomplete or repeated four-seat cluster")
        local=Counter()
        interventions=0
        for row in group:
            all_delta.update(row["paired_deltas"])
            local.update(row["paired_deltas"])
            interventions+=row["actual_interventions"]
            for arm in ARMS:
                counts[arm].update(row["arms"][arm]["counts"])
        per_seed.append({
            "seed":seed,"actual_interventions":interventions,
            "mean_four_seat_official_net_delta":round(
                local["official_net"]/4,4),
        })
    total_changes=counts["nearvalue_defense"]["actual_changes"]
    if total_changes!=sum(x["actual_interventions"] for x in per_seed):
        raise RuntimeError("missing real discard interventions")
    if all_delta["official_net"]!=sum(all_delta[k] for k in (
        "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("incompatible official settled balances")
    if total_changes==0 and any(all_delta[k] for k in METRICS):
        raise RuntimeError("unmodified baseline caused scoring change")
    scores=[r["mean_four_seat_official_net_delta"] for r in per_seed]
    return {
        "independent_shuffle_seeds":seeds,
        "paired_positions":len(positions),
        "complete_games":len(positions)*2,
        "frozen_reduction":MIN_PUBLIC_THREAT_REDUCTION,
        "frozen_value_retention":MIN_VALUE_RETENTION,
        "frozen_ukeire_retention":MIN_UKEIRE_RETENTION,
        "total_baseline_discards":counts["baseline"]["discard_decisions"],
        "multiple_minimum_shanten_cuts":
            counts["baseline"]["multiple_minimum_shanten_cuts"],
        "actual_discard_interventions":total_changes,
        "seeds_with_interventions":sum(x["actual_interventions"]>0 for x in per_seed),
        "positive_seed_clusters":sum(v>0 for v in scores),
        "negative_seed_clusters":sum(v<0 for v in scores),
        "neutral_seed_clusters":sum(v==0 for v in scores),
        "mean_four_seat_official_net_delta":round(mean(scores),4),
        "official_component_deltas":dict(all_delta),
        "counts_by_arm":{a:dict(counts[a]) for a in ARMS},
        "per_seed":per_seed,"positions":positions,
        "live_policy_modified":False,"confidence_interval":None,
        "calibrated_ron_probability":None,
    }


def study(*,development:int=52000,holdout:int=53000,seeds:int=4)->dict[str,Any]:
    if (type(development) is not int or type(holdout) is not int or
            type(seeds) is not int or not 1<=seeds<=8 or
            not 0<=development<2**32 or not 0<=holdout<2**32 or
            max(development,holdout)+seeds>2**32 or
            (development<holdout+seeds and holdout<development+seeds)):
        raise ValueError("cohorts overlap or seed ranges are not valid")
    return {
        "protocol":PROTOCOL,"online_policy_modified":False,
        "candidate_only_offline":True,
        "development_seed_range":[development,development+seeds],
        "holdout_seed_range":[holdout,holdout+seeds],
        "development":cohort(development,seeds),
        "holdout":cohort(holdout,seeds),
        "limitations":[
            "Public risk is an additive threat index, never calibrated P(Ron).",
            "Only already-authorized min-shanten cuts from original challenge ranking are used.",
            "The candidate does NOT change existing verified Tian Ting discards.",
            "The entire subsequent game can branch after one revised discard.",
            "Identical initial shuffles are paired but subsequent wall consumption can differ.",
            "Four seat rotations are correlated within a seed, not independent shuffles.",
            "No score difference, rare changes, or conflicting holdout forbids deployment.",
            "The actual real-time benchmark must be separately checked before any rollout.",
        ],
    }
