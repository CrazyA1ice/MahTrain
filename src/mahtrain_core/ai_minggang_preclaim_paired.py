"""M4.11: precommitted, public-only risk-based Ming-Gang -> Peng paired trial.

This is strictly OFFLINE research. The live challenge MahjongAgent remains
untouched. The candidate is tested ONLY at real simultaneously legal Peng
and Ming-Gang responses, and only when the original challenge selected
Ming-Gang. It cannot observe future wall, replacement tile or opponent hands.
The M4.10 POST-tail observation is not available at claim time and MUST NOT
be used to choose an action. A public threat index is NOT a Ron probability.
"""
from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Mapping

from .ai import MahjongAgent
from .ai_action_extended_study import _fixed_lineup
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_dual_claim_fastpath_paired import _dual_optional_options
from .ai_minggang_public_risk_audit import public_minggang_exit_risk
from .ai_tournament import simulate_match

PROTOCOL = "m411_preclaim_public_risk_peng_paired_official_net_v1"
ARMS = ("baseline", "risk_peng")
METRICS = (
    "official_net", "win_points", "kong_points", "exhaustive_points",
    "win_events", "deal_in_events", "realized_kongs",
)
# Freeze this ahead of new seed cohorts. Summed public threat can exceed one.
PUBLIC_THREAT_GATE = 0.25


def proposed_claim(
    view: Mapping[str, Any], original: str,
) -> tuple[str, str]:
    """Offer a conservative policy alternative; return unchanged on all fastpaths.

    The baseline choice comes from real MahjongAgent.response(). The only
    allowed intervention is Ming-Gang -> Peng with a legally authorized
    simultaneous Peng+Ming-Gang offer, no legal Hu, no Tian Ting, and the
    *pre-tail* PUBLIC current-hand minimum threat index >= 0.25.
    """
    options = (view.get("rob_options") if view.get("phase")=="rob_kong_window"
               else view.get("claim_options")) or []
    if original not in options:
        raise ValueError("original challenge response is not authorized")
    if "hu" in options:
        if original!="hu":
            raise RuntimeError("challenge must accept authorized Hu")
        return original, "mandatory_hu"
    if not _dual_optional_options(view,rob=False):
        return original, "not_legal_dual"
    if original != "ming_gang":
        return original, "baseline_not_minggang"
    if (view.get("tian_ting") or {}).get("eligible") is True:
        return original, "protected_tian_ting"
    risk = public_minggang_exit_risk(view)
    if risk["risk_index_is_probability"] is not False or risk[
            "supplement_tile_known"] is not False:
        raise RuntimeError("preclaim analysis illicitly claimed oracle knowledge")
    index = risk["min_existing_cut_threat_index"]
    if type(index) not in (float, int) or index < 0:
        raise RuntimeError("invalid public pre-tail threat index")
    if index < PUBLIC_THREAT_GATE:
        return original, "below_public_threat_gate"
    if "peng" not in options:
        raise RuntimeError("refusal to select unauthorized alternative")
    return "peng", "public_threat_gate"


class PreclaimRiskPengResearchAgent(MahjongAgent):
    """Public-only independent paired candidate; unchanged all other actions."""

    def __init__(self, *, seed: int, seat: int, arm: str) -> None:
        if arm not in ARMS:
            raise ValueError("unknown frozen research arm")
        super().__init__("challenge",seed=seed,seat=seat)
        self.arm=arm
        self.counts:Counter[str]=Counter()

    def response(self, view: Mapping[str, Any], *, rob: bool=False)->str:
        original=super().response(view,rob=rob)
        options=view.get("rob_options") if rob else view.get("claim_options")
        if original not in (options or []):
            raise RuntimeError("illegal challenge baseline response")
        if not _dual_optional_options(view,rob=rob):
            self.counts["fastpath_responses"]+=1
            if "hu" in (options or []):
                if original!="hu":
                    raise RuntimeError("authorized Hu was incorrectly declined")
                self.counts["mandatory_hu_preserved"]+=1
            return original
        self.counts["legal_dual_windows"]+=1
        self.counts["original_"+original]+=1
        proposed, reason=proposed_claim(view,original)
        self.counts["reason_"+reason]+=1
        self.counts["proposed_differences"]+=int(proposed!=original)
        choice=proposed if self.arm=="risk_peng" else original
        self.counts["actual_changes"]+=int(choice!=original)
        if choice not in options:
            raise RuntimeError("candidate returned unauthorized action")
        return choice

    def safe_counts(self)->dict[str,int]:
        if self.counts["legal_dual_windows"]!=sum(
                self.counts["original_"+x] for x in ("pass","peng","ming_gang")):
            raise RuntimeError("dual opportunities do not reconcile")
        if self.counts["actual_changes"]>self.counts["proposed_differences"]:
            raise RuntimeError("unexpected policy change outside candidate")
        if self.arm=="baseline" and self.counts["actual_changes"]:
            raise RuntimeError("baseline was altered")
        return dict(self.counts)


def paired_position(seed:int,rotation:int)->dict[str,Any]:
    if (type(seed) is not int or not 0<=seed<2**32 or
            type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid fixed shuffle seed or seat rotation")
    lineup,seat=_fixed_lineup(rotation)
    matches={}
    for arm in ARMS:
        agent=PreclaimRiskPengResearchAgent(seed=seed,seat=seat,arm=arm)
        match=simulate_match(
            seed,rotation=rotation%3,lineup=lineup,offline_kong_base=1,
            offline_agent_overrides={seat:agent})
        official=_official_outcome(match,seat,lineup)
        if official["official_net"]!=sum(
                official[k] for k in
                ("win_points","kong_points","exhaustive_points")):
            raise RuntimeError("official Hu/Kong/exhaustive sum differs")
        matches[arm]={
            "official":official,
            "counts":agent.safe_counts(),
            "terminal_phase":match["terminal_phase"],
            # Full public baseline/candidate timeline is transient ONLY for
            # validating no-change identity; NEVER export it.
            "_match":match,
        }
    a,b=matches["baseline"],matches["risk_peng"]
    changed=b["counts"].get("actual_changes",0)
    if changed==0:
        if (a["official"]!=b["official"] or
                a["terminal_phase"]!=b["terminal_phase"] or
                a["_match"]["public_events"]!=b["_match"]["public_events"] or
                a["_match"]["trace"]!=b["_match"]["trace"]):
            raise RuntimeError("unmodified policy diverged in identical seeded arms")
    diff={metric:b["official"][metric]-a["official"][metric]
          for metric in METRICS}
    if diff["official_net"]!=sum(diff[k] for k in (
            "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("paired official point components differ")
    # Purge complete trace/public states. Only aggregate official points,
    # safe counters and seed/rotation remain in JSON.
    for arm in ARMS:
        matches[arm].pop("_match")
    return {
        "seed":seed,"rotation":rotation,"challenge_seat":seat,
        "arms":matches,"paired_deltas":diff,
        "actual_interventions":changed,
        "same_state_when_unchanged":changed==0,
    }


def cohort(start:int,seeds:int)->dict[str,Any]:
    if (type(start) is not int or type(seeds) is not int or
            not 0<=start<2**32 or not 1<=seeds<=8 or start+seeds>2**32):
        raise ValueError("invalid preregistered seed cohort")
    rows=[paired_position(seed,rotation)
          for seed in range(start,start+seeds) for rotation in range(4)]
    total=Counter()
    count_by_arm={a:Counter() for a in ARMS}
    per_seed=[]
    for seed in range(start,start+seeds):
        group=[row for row in rows if row["seed"]==seed]
        if sorted(x["challenge_seat"] for x in group)!=[0,1,2,3]:
            raise RuntimeError("missing fixed challenge seat rotation")
        seed_points=0
        changes=0
        for row in group:
            total.update(row["paired_deltas"])
            seed_points+=row["paired_deltas"]["official_net"]
            changes+=row["actual_interventions"]
            for arm in ARMS:
                count_by_arm[arm].update(row["arms"][arm]["counts"])
        per_seed.append({
            "seed":seed,
            "mean_four_seat_net_delta":round(seed_points/4,4),
            "actual_interventions":changes,
        })
    if total["official_net"]!=sum(total[k] for k in (
            "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("cohort component delta mismatch")
    changes=sum(row["actual_interventions"] for row in rows)
    if changes!=count_by_arm["risk_peng"]["actual_changes"]:
        raise RuntimeError("actual candidate changes not fully counted")
    if changes==0 and any(total[k] for k in METRICS):
        raise RuntimeError("official delta without a policy intervention")
    return {
        "independent_shuffle_seeds":seeds,
        "paired_seat_positions":len(rows),
        "complete_games":len(rows)*2,
        "public_threat_gate":PUBLIC_THREAT_GATE,
        "candidate_real_policy_changes":changes,
        "seed_mean_official_net_delta":round(mean(
            x["mean_four_seat_net_delta"] for x in per_seed),4),
        "positive_delta_seeds":sum(x["mean_four_seat_net_delta"]>0 for x in per_seed),
        "negative_delta_seeds":sum(x["mean_four_seat_net_delta"]<0 for x in per_seed),
        "unchanged_delta_seeds":sum(x["mean_four_seat_net_delta"]==0 for x in per_seed),
        "official_component_deltas":dict(total),
        "counts_by_arm":{a:dict(count_by_arm[a]) for a in ARMS},
        "per_seed":per_seed,"positions":rows,
        "confidence_interval":None,"risk_is_probability":False,
    }


def study(*,development:int=46000,holdout:int=47000,
          seeds:int=4)->dict[str,Any]:
    if (type(development) is not int or type(holdout) is not int or
            type(seeds) is not int or not 1<=seeds<=8 or
            not 0<=development<2**32 or not 0<=holdout<2**32 or
            max(development,holdout)+seeds>2**32 or
            (development<holdout+seeds and holdout<development+seeds)):
        raise ValueError("new fixed independent seed blocks must not overlap")
    return {
        "protocol":PROTOCOL,"online_policy_modified":False,
        "candidate_only_offline":True,
        "development_seed_range":[development,development+seeds],
        "holdout_seed_range":[holdout,holdout+seeds],
        "development":cohort(development,seeds),
        "holdout":cohort(holdout,seeds),
        "limitations":[
            "Risk is an additive publicly inferred index, not calibrated P(Ron).",
            "Threshold 0.25 is fixed before new independent seed cohorts.",
            "This compares full-game paired OFFICIAL net of separate paths, not point EV at the single claim.",
            "An intervention may change later opportunities, wall ordering, opponent actions and game outcome.",
            "Only shuffle seeds are independent; all seat rotations within a seed are correlated.",
            "Sparse changes or mixed-sign seed effects never justify a live AI deployment.",
            "No future-tail, opponent hidden hand, or post-tail observation is available at decision time.",
        ],
    }
