"""M4.20 bounded OFFLINE one-draw / next-discard / possible-win lookahead.

This is a *two-transition proxy*, not perfect-information expectimax:
  legal own discard -> public-unknown possible next draw -> best legal cut
  -> structurally legal potential winning tiles, scored with official score_win.
Draws are weighted by publicly unobserved physical copies, NOT by an
observed future wall or opponents' concealed hands. Only up to 2 first
candidates, 6 draw types each, and 2 decision windows per match are scanned.
No change to deployed MahjongAgent, Sichuan rules, opponent policy or UI.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
from statistics import mean
from time import perf_counter
from typing import Any, Mapping

from .ai import MahjongAgent, _own_view, visible_tiles
from .ai_action_extended_study import _fixed_lineup
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_discard_nearvalue_risk_paired import METRICS
from .ai_tournament import simulate_match
from .efficiency import effective_draws, shanten_13
from .rules import TILE_INDEX, score_win

PROTOCOL = "m420_frozen_public_bounded_two_transition_lookahead_v1"
ARMS = ("baseline","bounded_two_transition")
MAX_INITIAL_CUTS = 2
MAX_DRAW_TYPES_PER_CUT = 6
MAX_RESEARCH_WINDOWS_PER_MATCH = 2
MIN_PUBLIC_WALL = 12
MIN_EFFECTIVE_COPIES_RETENTION = .70
MAX_PUBLIC_THREAT_INCREASE = .12
MIN_PROJECTED_SCORE_GAIN = 1.12


def next_discard_wait_value(
    after_first_cut: list[str], drawn: str,
    melds: list[dict[str,str]], missing: str,
    publicly_seen_after_first: list[str], fan_cap: int,
)->tuple[float,int]:
    """Best legal postdraw cut's next-win proxy; 0 if not tenpai.

    The second cut is hypothetical, *not* an actual future opponent action.
    The drawn tile is only a branch label from visible-information possibilities.
    """
    fourteen=[*after_first_cut,drawn]
    allowed=sorted(set(fourteen),key=TILE_INDEX.__getitem__)
    forced=[t for t in allowed if t[0]==missing]
    if forced:
        allowed=forced
    best=0.0
    cuts_seen=0
    for second in allowed:
        rest=list(fourteen)
        rest.remove(second)
        cuts_seen+=1
        if shanten_13(rest,melds,missing)!=0:
            continue
        info=effective_draws(
            rest,melds,missing,
            [*publicly_seen_after_first,second],
        )
        potential=0.0
        for item in info["effective_details"]:
            win=score_win([*rest,item["tile"]],melds,missing,cap=fan_cap)
            if win.get("legal") is not True:
                raise RuntimeError("authoritative wait was not a legal win")
            potential+=item["remaining"]*win["multiplier"]
        best=max(best,potential)
    return best,cuts_seen


def projected_branch_score(
    view: Mapping[str,Any], first_cut: str,
)->dict[str,Any]:
    """Conservatively bounded *selected branch* score, with coverage shown."""
    hand,melds,missing=_own_view(view)
    if first_cut not in hand:
        raise ValueError("first cut is not an owned legal tile")
    cap=(view.get("win_ledger") or {}).get("fan_cap",3)
    if type(cap) is not int or not 0<=cap<=12:
        raise ValueError("invalid authoritative room fan cap")
    after=list(hand)
    after.remove(first_cut)
    seen=[*visible_tiles(view),first_cut]
    info=effective_draws(after,melds,missing,seen)
    if info["shanten"]!=1:
        raise ValueError("lookahead requires first cut to leave exact shanten 1")
    candidates=sorted(
        info["effective_details"],
        key=lambda d:(-d["remaining"],TILE_INDEX[d["tile"]]),
    )[:MAX_DRAW_TYPES_PER_CUT]
    weighted_score=0.0
    branches=0
    second_cut_evaluations=0
    covered_copies=0
    for item in candidates:
        draw,remaining=item["tile"],item["remaining"]
        if remaining<=0:
            raise RuntimeError("impossible or negative public draw branch")
        potential,examined=next_discard_wait_value(
            after,draw,melds,missing,seen,cap)
        weighted_score+=remaining*potential
        branches+=1
        covered_copies+=remaining
        second_cut_evaluations+=examined
    if covered_copies>info["effective_tile_count"]:
        raise RuntimeError("branch coverage exceeds public effective counts")
    return {
        "proxy":round(weighted_score,5),
        "draw_types":branches,
        "draw_copy_mass":covered_copies,
        "all_effective_copies":info["effective_tile_count"],
        "second_cuts_checked":second_cut_evaluations,
        "coverage_fraction":round(
            covered_copies/info["effective_tile_count"],5
        ) if info["effective_tile_count"] else 0.0,
    }


def frozen_lookahead_decision(
    view:Mapping[str,Any],ranked:list[dict[str,Any]]|None,
    original:str,
)->tuple[str,str,dict[str,Any]]:
    """Decision and strictly anonymous resource accounting."""
    counts={"evaluated_first_cuts":0,"draw_branches":0,
            "second_cuts":0}
    wall=view.get("wall_count")
    if type(wall) is not int or wall<0:
        raise ValueError("missing current public wall")
    if wall<MIN_PUBLIC_WALL:
        return original,"short_wall",counts
    if (view.get("tian_ting") or {}).get("eligible") is True:
        return original,"verified_tian_ting",counts
    if not ranked or len(ranked)<2:
        return original,"no_multi_minimum_rank",counts
    if ranked[0].get("discard")!=original:
        raise RuntimeError("source rank not aligned with challenge action")
    if ranked[0].get("shanten")!=1:
        return original,"not_one_shanten",counts
    hand=view.get("hand")
    if type(hand) is not list or original not in hand:
        raise RuntimeError("not the current own hand")
    # Check every ranked cut before filtering to ensure illegal tiles cannot
    # lurk just outside the bounded research branch budget.
    seen=set()
    for row in ranked:
        tile=row.get("discard")
        if (tile not in TILE_INDEX or tile not in hand or tile in seen or
                type(row.get("shanten")) is not int or row["shanten"]!=1):
            raise RuntimeError("not a legal equal-minimum-shanten source")
        seen.add(tile)
        for k in ("effective_tile_count","table_threat_index"):
            n=row.get(k)
            if (type(n) not in (int,float) or not isfinite(n) or n<0 or
                    (k=="effective_tile_count" and type(n) is not int)):
                raise RuntimeError("invalid original rank proxy")
    base=ranked[0]
    # Limit the absolute next-step work to exactly two initial cuts. Select
    # the second by official already-evaluated challenge score, not by outcomes
    # or deeper branch results.
    alternatives=[
        r for r in ranked[1:] if
        r["effective_tile_count"]>=(
            base["effective_tile_count"]*MIN_EFFECTIVE_COPIES_RETENTION) and
        r["table_threat_index"]<=(
            base["table_threat_index"]+MAX_PUBLIC_THREAT_INCREASE)
    ]
    if not alternatives:
        return original,"no_publicly_guarded_second_cut",counts
    alternative=alternatives[0]
    first=projected_branch_score(view,original)
    other=projected_branch_score(view,alternative["discard"])
    counts["evaluated_first_cuts"]=2
    counts["draw_branches"]=first["draw_types"]+other["draw_types"]
    counts["second_cuts"]=first["second_cuts_checked"]+other["second_cuts_checked"]
    if (first["proxy"]<=0 or other["proxy"]<=0):
        return original,"zero_projected_wait_value",counts
    if (other["proxy"]+1e-8>=first["proxy"]*MIN_PROJECTED_SCORE_GAIN and
            other["proxy"]>first["proxy"]):
        return alternative["discard"],"better_bounded_next_wait_proxy",counts
    return original,"no_bounded_next_wait_gain",counts


class BoundedLookaheadResearchAgent(MahjongAgent):
    """Official challenge plus optional short, offline-only bounded branch."""
    def __init__(self,*,seed:int,seat:int,arm:str)->None:
        if arm not in ARMS:
            raise ValueError("unknown research arm")
        super().__init__("challenge",seed=seed,seat=seat)
        self._offline_reference_cut=True
        self.arm=arm
        self.counts:Counter[str]=Counter()
        self._wall_ms_total=0.0
        self._wall_ms_peak=0.0

    def discard(self,view:Mapping[str,Any])->str:
        original=super().discard(view)
        self.counts["total_discards"]+=1
        ranked=getattr(self,"_last_discard_scores",None)
        if (not ranked or len(ranked)<2 or ranked[0].get("shanten")!=1):
            self.counts["not_multi_one_shanten"]+=1
            return original
        self.counts["one_shanten_multi_windows"]+=1
        if self.counts["research_windows"]>=MAX_RESEARCH_WINDOWS_PER_MATCH:
            self.counts["budget_skips"]+=1
            return original
        # Both paired arms observe the same diagnostic budget until their
        # first changed cut. No second-draw wall contents ever read.
        self.counts["research_windows"]+=1
        start=perf_counter()
        suggested,why,resources=frozen_lookahead_decision(
            view,ranked,original)
        elapsed=(perf_counter()-start)*1000.0
        self._wall_ms_total+=elapsed
        self._wall_ms_peak=max(self._wall_ms_peak,elapsed)
        self.counts["reason_"+why]+=1
        self.counts["draw_branches"]+=resources["draw_branches"]
        self.counts["second_cuts_checked"]+=resources["second_cuts"]
        self.counts["first_cuts_checked"]+=resources["evaluated_first_cuts"]
        self.counts["suggested_changes"]+=int(suggested!=original)
        selected=suggested if self.arm=="bounded_two_transition" else original
        self.counts["actual_changes"]+=int(selected!=original)
        if selected not in view["hand"]:
            raise RuntimeError("not an authorized candidate cut")
        return selected

    def safe_counts(self)->dict[str,Any]:
        if (self.counts["research_windows"]>
                MAX_RESEARCH_WINDOWS_PER_MATCH or
            self.counts["first_cuts_checked"]>
                MAX_INITIAL_CUTS*MAX_RESEARCH_WINDOWS_PER_MATCH or
            self.counts["draw_branches"]>
                MAX_INITIAL_CUTS*MAX_DRAW_TYPES_PER_CUT*
                MAX_RESEARCH_WINDOWS_PER_MATCH or
            self.counts["actual_changes"]>self.counts["suggested_changes"] or
            (self.arm=="baseline" and self.counts["actual_changes"])):
            raise RuntimeError("bounded research budget or baseline violated")
        return {
            **dict(self.counts),
            "lookahead_elapsed_ms_total":round(self._wall_ms_total,3),
            "lookahead_elapsed_ms_peak":round(self._wall_ms_peak,3),
        }


def paired_position(seed:int,rotation:int)->dict[str,Any]:
    if (type(seed) is not int or not 0<=seed<2**32 or
            type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid initial shuffle or seat")
    lineup,seat=_fixed_lineup(rotation)
    arms={}
    for arm in ARMS:
        agent=BoundedLookaheadResearchAgent(seed=seed,seat=seat,arm=arm)
        match=simulate_match(
            seed,rotation=rotation%3,lineup=lineup,offline_kong_base=1,
            offline_agent_overrides={seat:agent})
        money=_official_outcome(match,seat,lineup)
        if match["physical_count"]!=108 or (
                money["official_net"]!=sum(money[x] for x in
                ("win_points","kong_points","exhaustive_points"))):
            raise RuntimeError("physical conservation or official ledgers failed")
        arms[arm]={
            "official":money,"counts":agent.safe_counts(),
            "terminal_phase":match["terminal_phase"],
            "_trace":match["trace"],"_events":match["public_events"],
        }
    b,c=arms["baseline"],arms["bounded_two_transition"]
    changed=c["counts"].get("actual_changes",0)
    if not changed and (
        b["official"]!=c["official"] or
        b["terminal_phase"]!=c["terminal_phase"] or
        b["_trace"]!=c["_trace"] or b["_events"]!=c["_events"]
    ):
        raise RuntimeError("unaltered candidate cannot change any full-game state")
    delta={k:c["official"][k]-b["official"][k] for k in METRICS}
    if delta["official_net"]!=sum(delta[k] for k in
                                 ("win_points","kong_points","exhaustive_points")):
        raise RuntimeError("official paired money does not reconcile")
    for arm in ARMS:
        del arms[arm]["_trace"]
        del arms[arm]["_events"]
    return {
        "seed":seed,"rotation":rotation,"challenge_seat":seat,
        "arms":arms,"actual_interventions":changed,
        "official_deltas":delta,"candidate_only_offline":True,
    }


def cohort(start:int,seeds:int=3)->dict[str,Any]:
    if (type(start) is not int or type(seeds) is not int or
            not 0<=start<2**32 or not 1<=seeds<=6 or start+seeds>2**32):
        raise ValueError("invalid bounded independent seed block")
    positions=[paired_position(s,r) for s in range(start,start+seeds)
               for r in range(4)]
    sums=Counter()
    counts={arm:Counter() for arm in ARMS}
    per_seed=[]
    for seed in range(start,start+seeds):
        rows=[p for p in positions if p["seed"]==seed]
        if sorted(x["challenge_seat"] for x in rows)!=[0,1,2,3]:
            raise RuntimeError("not four seat rotations per shuffle")
        money=Counter()
        changes=0
        for p in rows:
            sums.update(p["official_deltas"])
            money.update(p["official_deltas"])
            changes+=p["actual_interventions"]
            for arm in ARMS:
                counts[arm].update({
                    k:v for k,v in p["arms"][arm]["counts"].items()
                    if type(v) is int
                })
        per_seed.append({
            "seed":seed,"actual_interventions":changes,
            "mean_seat_net_delta":round(money["official_net"]/4,4),
            "win_delta":money["win_points"],
            "kong_delta":money["kong_points"],
            "exhaustive_delta":money["exhaustive_points"],
        })
    if sums["official_net"]!=sum(sums[x] for x in
                                ("win_points","kong_points","exhaustive_points")):
        raise RuntimeError("cohort authoritative settlement failed")
    total=counts["bounded_two_transition"]["actual_changes"]
    if total!=sum(x["actual_interventions"] for x in per_seed):
        raise RuntimeError("action changes do not match independent clusters")
    return {
        "independent_shuffles":seeds,"complete_official_games":len(positions)*2,
        "candidate_action_changes":total,
        "affected_seed_clusters":sum(p["actual_interventions"]>0 for p in per_seed),
        "positive_seed_clusters":sum(p["mean_seat_net_delta"]>0 for p in per_seed),
        "negative_seed_clusters":sum(p["mean_seat_net_delta"]<0 for p in per_seed),
        "official_component_deltas":{k:sums[k] for k in METRICS},
        "counts_by_arm":{arm:dict(counts[arm]) for arm in ARMS},
        "per_seed":per_seed,"positions":positions,
        "online_ai_modified":False,"local_causal_ev":None,
        "p_ron":None,"p_tenpai":None,
    }


def study()->dict[str,Any]:
    return {
        "protocol":PROTOCOL,
        "preregistered_development_seeds":[60000,60003],
        "preregistered_holdout_seeds":[61000,61003],
        "development":cohort(60000,3),
        "holdout":cohort(61000,3),
        "online_ai_modified":False,
        "limitations":[
            "Draw branches are public unknown-copy hypotheses, NOT hidden wall or probability calibration.",
            "Only top six improving draw TYPES are expanded, so proxy omits branches.",
            "The next cut is a best-case hypothetical policy, not an enforced future action.",
            "Official Hu/Kong/Exhaustive cash differences are whole-game effects, not local causal EV.",
            "Seed clusters are independent shuffles, four seats within each cluster are correlated.",
            "There are at most two research windows per match; not a full-game lookahead AI.",
            "Even positive net deltas in 3+3 seeds cannot alone establish deployment readiness.",
        ],
    }
