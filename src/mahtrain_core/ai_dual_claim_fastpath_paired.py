"""M4.05 offline-only dual-option fastpath: no extra slate work on single calls.

The official challenge policy is untouched. We only experiment when peng and
ming_gang are simultaneously *actually legal*, and measure candidate work
per complete paired game. Runtime numbers are observational, never grounds
for a hard platform-independent wall-time claim.
"""
from __future__ import annotations

from collections import Counter
from statistics import mean
from time import perf_counter_ns
from typing import Any, Mapping

from .ai import MahjongAgent
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_action_extended_study import _fixed_lineup
from .ai_joint_optional_action_slate import (
    optional_claim_slate, preferred_from_slate,
)
from .ai_tournament import simulate_match

PROTOCOL="m405_dual_option_public_fastpath_seed_cluster_paired_v1"
ARMS=("baseline","dual_fastpath")
METRICS=("official_net","win_points","kong_points",
         "exhaustive_points","win_events","deal_in_events","realized_kongs")


def _dual_optional_options(view:Mapping[str,Any],*,rob:bool)->bool:
    """Cheap authorization-only check; no private hand or oracle access."""
    if rob or view.get("phase")!="claim_window":
        return False
    offered=view.get("claim_options") or ()
    return ("hu" not in offered and
            "peng" in offered and "ming_gang" in offered)


def choose_dual_claim(view:Mapping[str,Any], baseline:str)->str:
    """Select among *actually legal* dual options; else EXACT baseline.

    No joint evaluation at all if only one kind of voluntary claim exists.
    Never suppress a legal Hu or inspect fields that are not authorized.
    """
    if not _dual_optional_options(view,rob=False):
        return baseline
    offered=view["claim_options"]
    if baseline not in offered:
        raise ValueError("baseline decision is not an authorized legal action")
    # Only one evaluation. M4.04 used optional_claim_slate then called a
    # second function that fully re-enumerated the same candidate space.
    choice=preferred_from_slate(optional_claim_slate(view))
    if choice not in offered:
        raise RuntimeError("dual fastpath produced an illegal action")
    return choice


class DualFastpathResearchAgent(MahjongAgent):
    def __init__(self,*,seed:int,seat:int,arm:str)->None:
        if arm not in ARMS:
            raise ValueError("unknown preregistered dual-claim experiment arm")
        super().__init__("challenge",seed=seed,seat=seat)
        self.arm=arm
        self.counts:Counter[str]=Counter()
        self.base_response_ns=0
        self.additional_slate_ns=0
        self.peak_additional_slate_ns=0

    def response(self,view:Mapping[str,Any],*,rob:bool=False)->str:
        start=perf_counter_ns()
        baseline=super().response(view,rob=rob)
        self.base_response_ns+=perf_counter_ns()-start
        offered=view["rob_options"] if rob else view["claim_options"]
        if "hu" in offered:
            if baseline!="hu":
                raise RuntimeError("verified legal Hu was not accepted")
            self.counts["authorized_hu_taken"]+=1
            return baseline
        if rob:
            if baseline!="pass":
                raise RuntimeError("rob-Hu pass-only guard failed")
            return baseline
        if "peng" in offered or "ming_gang" in offered:
            self.counts["optional_claim_windows"]+=1
        else:
            return baseline
        if not _dual_optional_options(view,rob=rob):
            self.counts["single_kind_fastpath"]+=1
            return baseline
        self.counts["dual_active_windows"]+=1
        start_slate=perf_counter_ns()
        choice=choose_dual_claim(view,baseline)
        elapsed=perf_counter_ns()-start_slate
        self.additional_slate_ns+=elapsed
        self.peak_additional_slate_ns=max(self.peak_additional_slate_ns,elapsed)
        self.counts["joint_slate_evaluations"]+=1
        if choice!=baseline:
            self.counts["dual_action_disagreements"]+=1
            self.counts[f"baseline_{baseline}_to_{choice}"]+=1
        selected=(choice if self.arm=="dual_fastpath" else baseline)
        self.counts["actual_policy_changes"]+=int(selected!=baseline)
        if selected not in offered:
            raise RuntimeError("illegal dual action")
        return selected

    def kong(self,view:Mapping[str,Any])->dict[str,str]|None:
        original=super().kong(view)
        self.counts["self_kong_windows"]+=int(bool(view["kong_options"]))
        self.counts["self_kong_choices"]+=len(view["kong_options"])
        self.counts["self_kong_taken"]+=int(original is not None)
        return original

    def safe_counters(self)->dict[str,int]:
        if self.counts["joint_slate_evaluations"]!=self.counts["dual_active_windows"]:
            raise RuntimeError("joint scorer called outside authorized dual windows")
        if self.counts["dual_action_disagreements"]<self.counts["actual_policy_changes"]:
            raise RuntimeError("intervention without a legitimate baseline difference")
        return dict(self.counts)

    def safe_latency(self)->dict[str,Any]:
        return {
            "baseline_response_ms":round(self.base_response_ns/1e6,4),
            "additional_joint_slate_ms":round(self.additional_slate_ns/1e6,4),
            "maximum_single_extra_slate_ms":round(
                self.peak_additional_slate_ns/1e6,4),
            "extra_slate_evaluations":self.counts["joint_slate_evaluations"],
            "latency_is_environment_dependent":True,
        }


def paired_position(seed:int,rotation:int)->dict[str,Any]:
    if (type(seed) is not int or not 0<=seed<2**32 or
        type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid seed or rotation")
    lineup,seat=_fixed_lineup(rotation)
    arms={}
    for arm in ARMS:
        agent=DualFastpathResearchAgent(seed=seed,seat=seat,arm=arm)
        match=simulate_match(seed,rotation=rotation%3,lineup=lineup,
                             offline_kong_base=1,
                             offline_agent_overrides={seat:agent})
        arms[arm]={
            "official":_official_outcome(match,seat,lineup),
            "counts":agent.safe_counters(),
            "latency":agent.safe_latency(),
            "terminal_phase":match["terminal_phase"],
        }
    return {"seed":seed,"rotation":rotation,
            "challenge_seat":seat,"arms":arms}


def cohort(start:int,seeds:int)->dict[str,Any]:
    if (type(start) is not int or type(seeds) is not int or
        not 0<=start<2**32 or not 1<=seeds<=8 or
        start+seeds>2**32):
        raise ValueError("invalid predeclared independent-seed cohort")
    trials=[paired_position(seed,r)
            for seed in range(start,start+seeds) for r in range(4)]
    count={arm:Counter() for arm in ARMS}
    per_seed=[]
    total_metric=Counter()
    for seed in range(start,start+seeds):
        group=[trial for trial in trials if trial["seed"]==seed]
        if sorted(row["challenge_seat"] for row in group)!=[0,1,2,3]:
            raise RuntimeError("four seat rotations per seed not all present")
        seed_delta=0
        for row in group:
            for arm in ARMS:
                count[arm].update(row["arms"][arm]["counts"])
                data=row["arms"][arm]["official"]
                if data["official_net"]!=sum(data[k] for k in (
                    "win_points","kong_points","exhaustive_points")):
                    raise RuntimeError("official per-seat score mismatch")
            for k in METRICS:
                total_metric[k]+=(
                    row["arms"]["dual_fastpath"]["official"][k]-
                    row["arms"]["baseline"]["official"][k])
            seed_delta+=(
                row["arms"]["dual_fastpath"]["official"]["official_net"]-
                row["arms"]["baseline"]["official"]["official_net"])
        per_seed.append({"seed":seed,
                         "mean_four_seat_net_delta":round(seed_delta/4,4),
                         "real_policy_changes_in_four_fastpath_arms":sum(
                             row["arms"]["dual_fastpath"]["counts"].get(
                                 "actual_policy_changes",0)
                             for row in group)})
    if total_metric["official_net"]!=sum(total_metric[k] for k in (
            "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("aggregate official ledger mismatch")
    # Explicitly report BOTH arms' total CPU timings without comparing
    # absolute performance between different CI runners.
    times={arm:{
        "baseline_response_ms_total":round(sum(
            row["arms"][arm]["latency"]["baseline_response_ms"]
            for row in trials),4),
        "extra_slate_ms_total":round(sum(
            row["arms"][arm]["latency"]["additional_joint_slate_ms"]
            for row in trials),4),
        "max_single_extra_slate_ms":max(
            row["arms"][arm]["latency"]["maximum_single_extra_slate_ms"]
            for row in trials),
    } for arm in ARMS}
    return {
        "independent_shuffle_seeds":seeds,
        "paired_four_seat_positions":len(trials),
        "complete_official_games":len(trials)*len(ARMS),
        "seed_average_official_net_delta":round(mean(
            x["mean_four_seat_net_delta"] for x in per_seed),4),
        "positive_delta_seeds":sum(x["mean_four_seat_net_delta"]>0 for x in per_seed),
        "negative_delta_seeds":sum(x["mean_four_seat_net_delta"]<0 for x in per_seed),
        "unchanged_delta_seeds":sum(x["mean_four_seat_net_delta"]==0 for x in per_seed),
        "official_component_deltas":dict(total_metric),
        "counts_by_arm":{arm:dict(count[arm]) for arm in ARMS},
        "latency_descriptive_only":times,
        "per_seed":per_seed,"positions":trials,
        "confidence_interval":None,
    }


def study(*,development:int=34000,holdout:int=35000,
          seeds:int=8)->dict[str,Any]:
    if (type(development) is not int or type(holdout) is not int or
        type(seeds) is not int or not 1<=seeds<=8 or
        not 0<=development<2**32 or not 0<=holdout<2**32 or
        max(development,holdout)+seeds>2**32 or
        (development<holdout+seeds and holdout<development+seeds)):
        raise ValueError("overlapping or invalid 8+8 independent seed blocks")
    return {
        "protocol":PROTOCOL,"online_challenge_modified":False,
        "seed_statistical_unit":"initial_shuffle_seed",
        "opportunity_target":"peng_and_ming_gang_simultaneously_legal",
        "development_seed_range":[development,development+seeds],
        "holdout_seed_range":[holdout,holdout+seeds],
        "development":cohort(development,seeds),
        "holdout":cohort(holdout,seeds),
        "limitations":[
            "Joint slate only runs on genuinely dual-active decision windows; Hu and rob-Hu remain mandatory.",
            "Extra timing comes from perf_counter_ns during each full game and is hardware dependent.",
            "Reported payoff differences are complete-game trajectories, not a causal value for a single tile.",
            "Two arms start with equal initial shuffle and seating but diverge after different authorized choices.",
            "Independent units are initial seed clusters, not rotations, seats or optional action windows.",
            "No calibrated risk or reward for kong supplemental draw or robbed outcome is invented.",
            "Sparsity may mean zero actual interventions; no online adoption merely because score delta is nonnegative.",
            "Zero, small or uncertain net results are recorded without filtering or cherry-picking seeds.",
        ],
    }
