"""M4.06 offline-only guard for OPTIONAL opponent-discard ming-gang ranking.

Ledger payment is an explicit, reversible official rule amount; a tail draw
has public-only remaining-copy proxies. Neither is an oracle expected point
value or a realized payout guarantee. The original online challenge AI is
unchanged. Only strict shanten improvement may override an already chosen
ming-gang; otherwise retain its unpriced tail/credit opportunity.
"""
from __future__ import annotations

from collections import Counter
from statistics import mean
from time import perf_counter_ns
from typing import Any, Mapping

from .ai import MahjongAgent, visible_tiles
from .ai_challenge_action_counterfactual import _public_label
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_action_extended_study import _fixed_lineup
from .ai_dual_claim_fastpath_paired import _dual_optional_options
from .ai_joint_optional_action_slate import optional_claim_slate, preferred_from_slate
from .ai_tournament import simulate_match
from .rules import TILES

PROTOCOL="m406_minggang_reversible_payment_tail_draw_guard_v1"
ARMS=("baseline","credit_tail_guard")
METRICS=("official_net","win_points","kong_points","exhaustive_points",
         "win_events","deal_in_events","realized_kongs")


def authorized_public_minggang_evidence(
    view:Mapping[str,Any],slate:list[dict[str,Any]],
)->dict[str,Any]:
    """No hidden opponent hands or future wall, never fake priced kong EV.

    This is deliberately only available when both 'peng' and 'ming_gang'
    were authorized by the SAME rule engine in the current claim window.
    """
    if not _dual_optional_options(view,rob=False):
        raise ValueError("no actual dual-optional claim window")
    by={row["action"]:row for row in slate}
    if any(a not in by for a in ("pass","peng","ming_gang")):
        raise ValueError("incomplete optional action slate")
    meld=by["ming_gang"]
    public=view.get("kong_ledger") or {}
    base=public.get("base")
    if base is not None and (type(base) is not int or not 1<=base<=10**6):
        raise ValueError("unknown invalid kong ledger base")
    wall=view.get("wall_count")
    if type(wall) is not int or not 1<=wall<=108:
        raise ValueError("no authorized physical tail supplement")
    seat=view.get("seat")
    source=(view.get("pending_discard") or {}).get("seat")
    if (type(seat) is not int or seat not in range(4) or
        type(source) is not int or source not in range(4)
        or source==seat):
        raise ValueError("invalid public ming-gang payer/source identity")
    known=Counter(visible_tiles(view))
    known.update(view["hand"])
    unknown=0
    for tile in TILES:
        rest=4-known[tile]
        if rest<0:
            raise RuntimeError("physically impossible public + own tile count")
        unknown+=rest
    if not 0<unknown<=108:
        raise RuntimeError("no unknown physical tiles left for the tail")
    return {
        "payment_if_posted":2*base if base is not None else None,
        "payment_payer_count":1,
        "payment_is_reversible_on_kong_discard_ron":True,
        "tail_draw_exists":True,
        "remaining_wall_count":wall,
        "unknown_physical_copies":unknown,
        "tail_next_draw_effective_copy_ratio":round(
            min(meld["ukeire"],unknown)/unknown,6),
        "fan_weighted_next_draw_proxy":float(meld["value"]),
        "post_minggang_shanten":int(meld["shanten"]),
        "source_is_exposed_opponent_discard":True,
        "expected_official_net_from_kong":None,
    }


def cash_preserving_optional_choice(
    view:Mapping[str,Any],baseline:str,
    slate:list[dict[str,Any]],
)->tuple[str,str,dict[str,Any]]:
    """Compare shape evidence without treating official pay as comparable to ukeire.

    A prior accepted ming-gang is protected against same-shanten speculative
    pass/peng: a complete licensed official payment and tail event is a
    material missing component of M4.04's next-draw proxy. However a strict
    shanten improvement by a LICENSED alternative is still considered.
    """
    if baseline not in view.get("claim_options",[]):
        raise ValueError("original challenge action was illegal")
    evidence=authorized_public_minggang_evidence(view,slate)
    by={x["action"]:x for x in slate}
    suggested=preferred_from_slate(slate)
    if suggested not in view["claim_options"]:
        raise RuntimeError("not an authorized suggestion")
    baseline_row=by[baseline]
    if baseline=="ming_gang" and suggested!="ming_gang":
        # Preserve the value of guaranteed legal supplement, reversible
        # official payment, and progress uncertainty at equal shanten.
        if (not by[suggested]["admissible"] or
            by[suggested]["shanten"]>=baseline_row["shanten"]):
            return baseline,"retain_official_minggang",evidence
        return suggested,"strict_shanten_improves_over_minggang",evidence
    if suggested=="ming_gang" and baseline!="ming_gang":
        # Cannot make a new monetary promise if the room is unpriced. Even
        # when priced, require EXACT, strictly improved shanten, never tie
        # break based on guessed cash/unknown robbed Hu probabilities.
        if (evidence["payment_if_posted"] is None or
            by[suggested]["shanten"]>=baseline_row["shanten"]):
            return baseline,"no_strict_profitable_minggang_proof",evidence
        return suggested,"strict_shanten_and_priced_minggang",evidence
    if suggested!=baseline:
        if (by[suggested]["admissible"] and
            by[suggested]["shanten"]<baseline_row["shanten"]):
            return suggested,"strict_shanten_improvement",evidence
        return baseline,"retain_original_non_minggang",evidence
    return baseline,"unchanged_original_choice",evidence


class CashGuardResearchAgent(MahjongAgent):
    def __init__(self,*,seed:int,seat:int,arm:str)->None:
        if arm not in ARMS:
            raise ValueError("invalid research arm")
        super().__init__("challenge",seed=seed,seat=seat)
        self.arm=arm
        self.counts:Counter[str]=Counter()
        self.slate_ns=0
        self.peak_slate_ns=0

    def response(self,view:Mapping[str,Any],*,rob:bool=False)->str:
        baseline=super().response(view,rob=rob)
        options=view["rob_options"] if rob else view["claim_options"]
        if "hu" in options:
            if baseline!="hu":
                raise RuntimeError("legal Hu not taken by challenge")
            self.counts["legal_hu_unchanged"]+=1
            return baseline
        if not _dual_optional_options(view,rob=rob):
            self.counts["no_extra_slate"]+=int(
                not rob and ("peng" in options or "ming_gang" in options))
            return baseline
        self.counts["dual_legal_windows"]+=1
        start=perf_counter_ns()
        slate=optional_claim_slate(view)
        proposed,reason,evidence=cash_preserving_optional_choice(
            view,baseline,slate)
        elapsed=perf_counter_ns()-start
        self.slate_ns+=elapsed
        self.peak_slate_ns=max(self.peak_slate_ns,elapsed)
        self.counts["joint_slate_evaluations"]+=1
        self.counts["baseline_"+baseline]+=1
        self.counts["proposal_"+proposed]+=1
        self.counts["reason_"+reason]+=1
        self.counts["proposed_differences"]+=int(proposed!=baseline)
        self.counts["priced_minggang_windows"]+=int(
            evidence["payment_if_posted"] is not None)
        self.counts["unpriced_minggang_windows"]+=int(
            evidence["payment_if_posted"] is None)
        choice=proposed if self.arm=="credit_tail_guard" else baseline
        self.counts["actual_changes"]+=int(choice!=baseline)
        if choice not in options:
            raise RuntimeError("invalid selected action")
        return choice

    def kong(self,view:Mapping[str,Any])->dict[str,str]|None:
        return super().kong(view)

    def safe_counts(self)->dict[str,int]:
        if self.counts["joint_slate_evaluations"]!=self.counts["dual_legal_windows"]:
            raise RuntimeError("wrong slate invocation count")
        if self.counts["actual_changes"]>self.counts["proposed_differences"]:
            raise RuntimeError("illegal forced decision divergence")
        return dict(self.counts)

    def safe_latency(self)->dict[str,Any]:
        return {
            "additional_slate_ms":round(self.slate_ns/1e6,4),
            "peak_additional_slate_ms":round(self.peak_slate_ns/1e6,4),
            "actual_slate_evaluations":self.counts["joint_slate_evaluations"],
            "hardware_dependent":True,
        }


def paired_position(seed:int,rotation:int)->dict[str,Any]:
    if type(seed) is not int or not 0<=seed<2**32 or (
        type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid initial seed and seat rotation")
    lineup,seat=_fixed_lineup(rotation)
    arms={}
    for arm in ARMS:
        agent=CashGuardResearchAgent(seed=seed,seat=seat,arm=arm)
        result=simulate_match(seed,rotation=rotation%3,lineup=lineup,
                              offline_kong_base=1,
                              offline_agent_overrides={seat:agent})
        arms[arm]={
            "official":_official_outcome(result,seat,lineup),
            "counts":agent.safe_counts(),
            "latency":agent.safe_latency(),
            "terminal_phase":result["terminal_phase"],
        }
    return {"seed":seed,"rotation":rotation,"challenge_seat":seat,"arms":arms}


def cohort(start:int,seeds:int)->dict[str,Any]:
    if (type(start) is not int or type(seeds) is not int or
        not 0<=start<2**32 or not 1<=seeds<=8 or start+seeds>2**32):
        raise ValueError("invalid fixed independent seed group")
    matches=[paired_position(seed,r) for seed in range(start,start+seeds)
             for r in range(4)]
    per_seed=[]
    counts={arm:Counter() for arm in ARMS}
    metric=Counter()
    for seed in range(start,start+seeds):
        fours=[x for x in matches if x["seed"]==seed]
        if sorted(x["challenge_seat"] for x in fours)!=[0,1,2,3]:
            raise RuntimeError("incomplete seed cluster seat rotation")
        net=0
        changed=0
        for row in fours:
            for arm in ARMS:
                counts[arm].update(row["arms"][arm]["counts"])
                official=row["arms"][arm]["official"]
                if official["official_net"]!=sum(official[k] for k in (
                    "win_points","kong_points","exhaustive_points")):
                    raise RuntimeError("official Hu/Kong/exhaustive discrepancy")
            changed+=row["arms"]["credit_tail_guard"]["counts"].get(
                "actual_changes",0)
            for m in METRICS:
                diff=(row["arms"]["credit_tail_guard"]["official"][m]-
                      row["arms"]["baseline"]["official"][m])
                metric[m]+=diff
                if m=="official_net":net+=diff
        per_seed.append({
            "seed":seed,
            "four_seat_average_net_delta":round(net/4,4),
            "actual_changes":changed,
        })
    if metric["official_net"]!=sum(metric[k] for k in (
        "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("paired official component deltas do not sum")
    return {
        "independent_initial_shuffle_seeds":seeds,
        "paired_seat_positions":len(matches),
        "complete_games":len(matches)*2,
        "average_official_net_delta":round(mean(
            x["four_seat_average_net_delta"] for x in per_seed),4),
        "positive_seed_clusters":sum(x["four_seat_average_net_delta"]>0 for x in per_seed),
        "negative_seed_clusters":sum(x["four_seat_average_net_delta"]<0 for x in per_seed),
        "unchanged_seed_clusters":sum(x["four_seat_average_net_delta"]==0 for x in per_seed),
        "components":dict(metric),
        "counts_by_arm":{arm:dict(counts[arm]) for arm in ARMS},
        "latency_by_arm":{arm:{
            "sum_additional_slate_ms":round(sum(
                x["arms"][arm]["latency"]["additional_slate_ms"] for x in matches),4),
            "max_single_extra_ms":max(
                x["arms"][arm]["latency"]["peak_additional_slate_ms"] for x in matches),
        } for arm in ARMS},
        "per_seed":per_seed,"positions":matches,
        "confidence_interval":None,
    }


def study(*,development:int=36000,holdout:int=37000,
          seeds:int=8)->dict[str,Any]:
    if (type(development) is not int or type(holdout) is not int or
        type(seeds) is not int or not 1<=seeds<=8 or
        not 0<=development<2**32 or not 0<=holdout<2**32 or
        max(development,holdout)+seeds>2**32 or
        (development<holdout+seeds and holdout<development+seeds)):
        raise ValueError("new seed groups must be fixed, disjoint and unsigned")
    return {
        "protocol":PROTOCOL,"online_policy_modified":False,
        "claim_scope":"true_dual_peng_minggang_only",
        "development_seed_range":[development,development+seeds],
        "holdout_seed_range":[holdout,holdout+seeds],
        "development":cohort(development,seeds),
        "holdout":cohort(holdout,seeds),
        "limitations":[
            "Official ming-gang payment is reversible on kong-discard ron; posted points are not guaranteed EV.",
            "Supplement comes from tail but is unseen; next draw proxy uses authorized public copies, never future wall.",
            "Cash guard is a deterministic conservative policy, not an unbiased learned optimal-action oracle.",
            "The base response and legal Hu/Tian Ting and all own-kong actions are preserved.",
            "Baseline and candidate complete-game paths diverge after an intervention; held-out net is path-wide.",
            "Only independent initial shuffle seeds count; no artificial scenarios enter natural outcome samples.",
            "Small eight-seed arms with sparse conflicts cannot establish win-rate superiority or calibrated Hu risk.",
            "Do not deploy unless new unseen independently replicated terminal payoff and runtime justify change.",
        ],
    }
