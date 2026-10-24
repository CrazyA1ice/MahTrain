"""M4.18: first one-shanten UKEIRE improvement, paired official outcomes.

Frozen OFFLINE candidate.  Uses the existing challenge ranking of authorized
minimum-shanten cuts, never an unseen wall or opponents' private hands.
The existing challenge online policy remains unchanged.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
from statistics import mean
from typing import Any, Mapping, Sequence

from .ai import MahjongAgent
from .ai_action_extended_study import _fixed_lineup
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_discard_nearvalue_risk_paired import METRICS
from .ai_tournament import simulate_match
from .rules import TILE_INDEX

PROTOCOL="m418_frozen_one_shanten_effective_copies_offline_paired_v1"
ARMS=("baseline","one_shanten_ukeire")
MIN_ABSOLUTE_EXTRA_COPIES=2
MIN_RELATIVE_COPY_MULTIPLIER=1.10
MIN_WEIGHTED_VALUE_RETENTION=0.90
MAX_PUBLIC_RISK_INCREASE=0.12
MIN_PUBLIC_WALL_REMAINING=9


def suggest_one_shanten_ukeire(
    original:str, ranked:Sequence[Mapping[str,Any]]|None,
    view:Mapping[str,Any],
)->tuple[str,str]:
    """Choose only a legal min-shanten-1 cut with proven public-copy gain.

    No hidden hands, no future wall peek, no fresh effective_draws/score_win
    search; every numerical input comes from the ORIGINAL challenge ranking.
    The copy gain is theoretical publicly unknown physical copies, not P(tenpai).
    """
    wall=view.get("wall_count")
    if type(wall) is not int or wall<0:
        raise ValueError("missing public wall count")
    if wall<MIN_PUBLIC_WALL_REMAINING:
        return original,"too_little_public_wall"
    if (view.get("tian_ting") or {}).get("eligible") is True:
        return original,"verified_tian_ting"
    if not ranked or len(ranked)<2:
        return original,"not_multiple_minimum_cuts"
    if ranked[0].get("discard")!=original:
        raise RuntimeError("original challenge cut and rank zero disagree")
    hand=view.get("hand")
    if type(hand) is not list or original not in hand:
        raise RuntimeError("unauthorized original cut")
    shanten=ranked[0].get("shanten")
    if type(shanten) is not int:
        raise RuntimeError("missing exact minimum shanten")
    if shanten!=1:
        return original,"not_one_shanten"
    seen=set()
    for r in ranked:
        tile=r.get("discard")
        if (tile not in TILE_INDEX or tile not in hand or tile in seen or
                r.get("shanten")!=1):
            raise RuntimeError("illegal, duplicate, or shanten-regressing ranked tile")
        seen.add(tile)
        for name in ("effective_tile_count","expected_fan_weighted_copies",
                     "table_threat_index"):
            val=r.get(name)
            if type(val) not in (int,float) or not isfinite(val) or val<0:
                raise RuntimeError("invalid public effect/value/risk")
    baseline=ranked[0]
    chosen=[
        r for r in ranked[1:]
        if r["effective_tile_count"]>=(
            baseline["effective_tile_count"]+MIN_ABSOLUTE_EXTRA_COPIES)
        and r["effective_tile_count"]>=(
            baseline["effective_tile_count"]*MIN_RELATIVE_COPY_MULTIPLIER)
        and r["expected_fan_weighted_copies"]>=(
            baseline["expected_fan_weighted_copies"]*MIN_WEIGHTED_VALUE_RETENTION)
        and r["table_threat_index"]<=(
            baseline["table_threat_index"]+MAX_PUBLIC_RISK_INCREASE)
    ]
    if not chosen:
        return original,"no_more_ukeire_while_preserving_value"
    best=min(chosen,key=lambda r:(
        -r["effective_tile_count"],
        -r["expected_fan_weighted_copies"],
        r["table_threat_index"],
        TILE_INDEX[r["discard"]],
    ))
    return best["discard"],"more_visible_effective_copies"


class OneShantenUkeireResearchAgent(MahjongAgent):
    def __init__(self,*,seed:int,seat:int,arm:str)->None:
        if arm not in ARMS:
            raise ValueError("unrecognized offline arm")
        super().__init__("challenge",seed=seed,seat=seat)
        self._offline_reference_cut=True
        self.arm=arm
        self.counts:Counter[str]=Counter()

    def discard(self,view:Mapping[str,Any])->str:
        original=super().discard(view)
        self.counts["total_cuts"]+=1
        ranked=getattr(self,"_last_discard_scores",None)
        self.counts["one_shanten_ranked"]+=int(bool(
            ranked and ranked[0]["shanten"]==1))
        self.counts["one_shanten_multi"]+=int(bool(
            ranked and len(ranked)>1 and ranked[0]["shanten"]==1))
        proposed,reason=suggest_one_shanten_ukeire(original,ranked,view)
        self.counts["reason_"+reason]+=1
        self.counts["proposed_changes"]+=int(proposed!=original)
        selected=proposed if self.arm=="one_shanten_ukeire" else original
        self.counts["actual_changes"]+=int(selected!=original)
        if selected not in view["hand"]:
            raise RuntimeError("candidate was never legal")
        return selected

    def safe_counts(self)->dict[str,int]:
        if self.counts["total_cuts"]!=sum(
                n for key,n in self.counts.items() if key.startswith("reason_")):
            raise RuntimeError("not all baseline cuts classified")
        if (self.counts["actual_changes"]>self.counts["proposed_changes"] or
                (self.arm=="baseline" and self.counts["actual_changes"])):
            raise RuntimeError("research agent changed baseline or noncandidate")
        return dict(self.counts)


def paired_position(seed:int,rotation:int)->dict[str,Any]:
    if (type(seed) is not int or not 0<=seed<2**32 or
            type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid seed or seat rotation")
    lineup,seat=_fixed_lineup(rotation)
    arms={}
    for arm in ARMS:
        agent=OneShantenUkeireResearchAgent(seed=seed,seat=seat,arm=arm)
        game=simulate_match(
            seed,rotation=rotation%3,lineup=lineup,offline_kong_base=1,
            offline_agent_overrides={seat:agent},
        )
        arms[arm]={
            "official":_official_outcome(game,seat,lineup),
            "counts":agent.safe_counts(),"terminal_phase":game["terminal_phase"],
            "_trace":game["trace"],"_events":game["public_events"],
        }
    a,b=arms["baseline"],arms["one_shanten_ukeire"]
    changes=b["counts"].get("actual_changes",0)
    if changes==0 and (
            a["official"]!=b["official"] or
            a["terminal_phase"]!=b["terminal_phase"] or
            a["_trace"]!=b["_trace"] or a["_events"]!=b["_events"]):
        raise RuntimeError("unchanged path must have identical full history")
    d={key:b["official"][key]-a["official"][key] for key in METRICS}
    if d["official_net"]!=sum(d[k] for k in (
            "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("authoritative official score components disagree")
    for arm in ARMS:
        del arms[arm]["_trace"]
        del arms[arm]["_events"]
    return {
        "seed":seed,"rotation":rotation,"challenge_seat":seat,
        "arms":arms,"official_deltas":d,"actual_interventions":changes,
        "identical_if_untouched":changes==0,
    }


def cohort(start:int,seeds:int)->dict[str,Any]:
    if (type(start) is not int or type(seeds) is not int or
            not 0<=start<2**32 or not 1<=seeds<=8 or start+seeds>2**32):
        raise ValueError("invalid independent shuffle block")
    positions=[
        paired_position(seed,rotation)
        for seed in range(start,start+seeds) for rotation in range(4)
    ]
    cash=Counter()
    by_arm={arm:Counter() for arm in ARMS}
    per_seed=[]
    for seed in range(start,start+seeds):
        rows=[row for row in positions if row["seed"]==seed]
        if sorted(row["challenge_seat"] for row in rows)!=[0,1,2,3]:
            raise RuntimeError("one shuffle must include all four seats")
        local=Counter()
        interventions=0
        for row in rows:
            local.update(row["official_deltas"])
            cash.update(row["official_deltas"])
            interventions+=row["actual_interventions"]
            for arm in ARMS:
                by_arm[arm].update(row["arms"][arm]["counts"])
        per_seed.append({
            "seed":seed,"real_interventions":interventions,
            "mean_four_seat_net_delta":round(local["official_net"]/4,4),
            "win_delta":local["win_points"],
            "kong_delta":local["kong_points"],
            "exhaustive_delta":local["exhaustive_points"],
        })
    total=by_arm["one_shanten_ukeire"]["actual_changes"]
    if total!=sum(r["real_interventions"] for r in per_seed):
        raise RuntimeError("lost intervention during aggregation")
    if cash["official_net"]!=sum(cash[k] for k in (
            "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("official sum inconsistent")
    if total==0 and any(cash[k] for k in METRICS):
        raise RuntimeError("zero changes cannot change official game score")
    signs=[x["mean_four_seat_net_delta"] for x in per_seed]
    return {
        "independent_shuffle_seeds":seeds,
        "paired_seat_positions":len(positions),
        "complete_official_games":len(positions)*2,
        "frozen_min_absolute_copy_gain":MIN_ABSOLUTE_EXTRA_COPIES,
        "frozen_min_relative_copy_multiplier":MIN_RELATIVE_COPY_MULTIPLIER,
        "frozen_min_weighted_value_retention":MIN_WEIGHTED_VALUE_RETENTION,
        "frozen_max_public_risk_increase":MAX_PUBLIC_RISK_INCREASE,
        "frozen_min_public_wall_remaining":MIN_PUBLIC_WALL_REMAINING,
        "baseline_total_cuts":by_arm["baseline"]["total_cuts"],
        "baseline_one_shanten_ranked":by_arm["baseline"]["one_shanten_ranked"],
        "baseline_one_shanten_multi":by_arm["baseline"]["one_shanten_multi"],
        "actual_discard_interventions":total,
        "independent_seeds_with_interventions":sum(
            r["real_interventions"]>0 for r in per_seed),
        "positive_seed_clusters":sum(s>0 for s in signs),
        "negative_seed_clusters":sum(s<0 for s in signs),
        "neutral_seed_clusters":sum(s==0 for s in signs),
        "mean_four_seat_net_delta":round(mean(signs),4),
        "official_component_deltas":{k:cash[k] for k in METRICS},
        "counts_by_arm":{arm:dict(by_arm[arm]) for arm in ARMS},
        "per_seed":per_seed,"positions":positions,
        "online_ai_modified":False,
        "calibrated_p_tenpai":None,
        "local_causal_action_value":None,
        "confidence_interval":None,
    }


def study(*,development:int=56000,holdout:int=57000,
          seeds:int=4)->dict[str,Any]:
    if (type(development) is not int or type(holdout) is not int or
            type(seeds) is not int or not 1<=seeds<=8 or
            not 0<=development<2**32 or not 0<=holdout<2**32 or
            max(development,holdout)+seeds>2**32 or
            (development<holdout+seeds and holdout<development+seeds)):
        raise ValueError("overlapping or invalid independent seed blocks")
    return {
        "protocol":PROTOCOL,"candidate_only_offline":True,
        "online_ai_modified":False,
        "development_seed_range":[development,development+seeds],
        "holdout_seed_range":[holdout,holdout+seeds],
        "development":cohort(development,seeds),
        "holdout":cohort(holdout,seeds),
        "limitations":[
            "Effective copies are publicly not-yet-seen copies, not wall counts nor P(tenpai).",
            "Higher immediate ukeire does not prove earlier ready hand or higher official income.",
            "After any real cut change both full game paths can diverge.",
            "Seat rotations of one independent shuffle are statistically dependent.",
            "No future wall or opponents' concealed tiles are consulted by candidate actions.",
            "Frozen small blocks cannot justify deployment or a significant performance claim.",
            "Official challenge, all legal game rules and player web UI remain unchanged.",
        ],
    }
