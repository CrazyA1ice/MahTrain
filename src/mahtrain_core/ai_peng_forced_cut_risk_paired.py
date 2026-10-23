"""M4.13 offline-only Peng->Pass risk gate under legal public forced-cut evidence.

The original challenge AI remains unchanged. Only an actually offered,
challenge-selected Peng with unchanged exact shanten is considered.
Compare the minimum PUBLIC threat index of all best-shanten immediate cuts
after that Peng; keep original Peng on any lower-risk, better-shanten, Tian
Ting or mandatory-Hu case. This is NOT P(Ron), an oracle, or live policy.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
from statistics import mean
from typing import Any, Mapping

from .ai import MahjongAgent, _own_view, _cut_shanten
from .ai_action_extended_study import _fixed_lineup
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_table_read import read_discard_threat
from .ai_tournament import simulate_match
from .rules import TILE_INDEX
from .efficiency import shanten_13

PROTOCOL = "m413_equal_shanten_peng_forced_cut_public_threat_paired_v1"
ARMS = ("baseline", "peng_guard")
GATE = 0.30                 # frozen before development/holdout games
METRICS = ("official_net","win_points","kong_points","exhaustive_points",
           "win_events","deal_in_events","realized_kongs")


def licensed_peng_guard(
    view: Mapping[str, Any], baseline: str, *, rob: bool=False,
) -> tuple[str, str]:
    """Return original or legally licensed Pass using only current owner view."""
    opts = view.get("rob_options") if rob else view.get("claim_options")
    if not isinstance(opts,(list,tuple)) or baseline not in opts:
        raise ValueError("original response not authorized")
    if "hu" in opts:
        if baseline != "hu":
            raise RuntimeError("an available verified Hu must be taken")
        return baseline,"mandatory_hu"
    if rob or view.get("phase")!="claim_window" or baseline!="peng":
        return baseline,"not_selected_peng"
    if "pass" not in opts or "peng" not in opts:
        raise RuntimeError("Peng intervention lacks legal Pass and Peng")
    if (view.get("tian_ting") or {}).get("eligible") is True:
        return baseline,"tian_ting_preserved"
    hand,melds,missing=_own_view(view)
    claimed=(view.get("pending_discard") or {}).get("tile")
    if claimed not in TILE_INDEX or hand.count(claimed)<2:
        raise ValueError("no true authorized physical pair")
    before=shanten_13(hand,melds,missing)
    remaining=list(hand)
    remaining.remove(claimed)
    remaining.remove(claimed)
    after_melds=[*melds,{"type":"peng","tile":claimed}]
    legal=sorted(set(remaining),key=TILE_INDEX.__getitem__)
    forced=[tile for tile in legal if tile[0]==missing]
    if forced: legal=forced
    if not legal:
        raise RuntimeError("Peng must leave at least one lawful cut")
    cuts=[(tile,_cut_shanten(remaining,after_melds,missing,tile))
          for tile in legal]
    stage=min(s for _,s in cuts)
    if stage<before:
        return baseline,"strict_shanten_improvement"
    if stage>before:
        # Defensive fallback for a malformed or changed upstream policy.
        return baseline,"no_equal_shanten_study"
    if stage<=0:
        return baseline,"existing_tenpai_preserved"
    minimum=min(read_discard_threat(tile,view)["risk_index"]
                for tile,s in cuts if s==stage)
    if (type(minimum) not in (float,int) or
            not isfinite(minimum) or minimum<0):
        raise RuntimeError("invalid additive public threat index")
    if minimum<GATE:
        return baseline,"at_least_one_lower_risk_cut"
    return "pass","high_threat_all_best_shanten_cuts"


class PengForcedCutResearchAgent(MahjongAgent):
    def __init__(self,*,seed:int,seat:int,arm:str)->None:
        if arm not in ARMS:
            raise ValueError("invalid research arm")
        super().__init__("challenge",seed=seed,seat=seat)
        self.arm=arm
        self.counts:Counter[str]=Counter()

    def response(self,view:Mapping[str,Any],*,rob:bool=False)->str:
        original=super().response(view,rob=rob)
        opts=view.get("rob_options") if rob else view.get("claim_options")
        if original not in (opts or ()):
            raise RuntimeError("baseline did not return authorized response")
        if rob or "hu" in (opts or ()) or original!="peng":
            self.counts["fastpath"]+=1
            if "hu" in (opts or ()) and original!="hu":
                raise RuntimeError("Hu priority lost")
            return original
        self.counts["selected_peng_windows"]+=1
        proposed,reason=licensed_peng_guard(view,original,rob=rob)
        self.counts["reason_"+reason]+=1
        self.counts["proposed_changes"]+=int(proposed!=original)
        chosen=proposed if self.arm=="peng_guard" else original
        self.counts["actual_changes"]+=int(chosen!=original)
        if chosen not in opts:
            raise RuntimeError("chosen response not allowed")
        return chosen

    def safe_counts(self)->dict[str,int]:
        if self.counts["selected_peng_windows"]!=sum(
                value for key,value in self.counts.items()
                if key.startswith("reason_")):
            raise RuntimeError("not all selected Peng windows reviewed")
        if self.counts["actual_changes"]>self.counts["proposed_changes"]:
            raise RuntimeError("intervention outside suggestion")
        if self.arm=="baseline" and self.counts["actual_changes"]:
            raise RuntimeError("baseline changed")
        return dict(self.counts)


def paired_position(seed:int,rotation:int)->dict[str,Any]:
    if type(seed) is not int or not 0<=seed<2**32 or (
        type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid independent seed or seat rotation")
    lineup,seat=_fixed_lineup(rotation)
    arms={}
    for arm in ARMS:
        observer=PengForcedCutResearchAgent(seed=seed,seat=seat,arm=arm)
        game=simulate_match(seed,rotation=rotation%3,lineup=lineup,
                            offline_kong_base=1,
                            offline_agent_overrides={seat:observer})
        official=_official_outcome(game,seat,lineup)
        arms[arm]={"official":official,"counts":observer.safe_counts(),
                   "phase":game["terminal_phase"],"_trace":game["trace"],
                   "_events":game["public_events"]}
    b,c=arms["baseline"],arms["peng_guard"]
    changed=c["counts"].get("actual_changes",0)
    if changed==0 and (b["official"]!=c["official"] or b["phase"]!=c["phase"]
                       or b["_trace"]!=c["_trace"] or
                       b["_events"]!=c["_events"]):
        raise RuntimeError("baseline and untouched candidate diverged")
    diff={k:c["official"][k]-b["official"][k] for k in METRICS}
    if diff["official_net"]!=sum(diff[k] for k in (
        "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("real official balance differences disagree")
    for arm in ARMS:
        del arms[arm]["_trace"]
        del arms[arm]["_events"]
    return {"seed":seed,"rotation":rotation,"challenge_seat":seat,
            "arms":arms,"official_deltas":diff,
            "actual_interventions":changed,
            "identical_if_untouched":changed==0}


def cohort(start:int,seeds:int)->dict[str,Any]:
    if (type(start) is not int or type(seeds) is not int or
        not 0<=start<2**32 or not 1<=seeds<=8 or start+seeds>2**32):
        raise ValueError("valid 1..8 independent shuffled seeds needed")
    trials=[paired_position(s,r) for s in range(start,start+seeds)
            for r in range(4)]
    tally=Counter(); counts={arm:Counter() for arm in ARMS};groups=[]
    for s in range(start,start+seeds):
        rows=[x for x in trials if x["seed"]==s]
        if sorted(x["challenge_seat"] for x in rows)!=list(range(4)):
            raise RuntimeError("missing challenge seat rotation")
        d=Counter()
        changes=0
        for row in rows:
            d.update(row["official_deltas"])
            tally.update(row["official_deltas"])
            changes+=row["actual_interventions"]
            for arm in ARMS:
                counts[arm].update(row["arms"][arm]["counts"])
        groups.append({"seed":s,"interventions":changes,
                       "four_seat_mean_net_delta":round(d["official_net"]/4,4)})
    if tally["official_net"]!=sum(tally[k] for k in (
        "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("aggregate net mismatch")
    actual=counts["peng_guard"]["actual_changes"]
    if actual!=sum(x["interventions"] for x in groups):
        raise RuntimeError("lost a real intervention")
    if actual==0 and any(tally[k] for k in METRICS):
        raise RuntimeError("nonzero scores without any intervention")
    signs=[x["four_seat_mean_net_delta"] for x in groups]
    return {"independent_shuffles":seeds,"paired_seat_positions":len(trials),
            "complete_official_games":len(trials)*2,"frozen_risk_gate":GATE,
            "candidate_policy_interventions":actual,
            "selected_peng_windows":counts["peng_guard"]["selected_peng_windows"],
            "positive_seeds":sum(x>0 for x in signs),
            "negative_seeds":sum(x<0 for x in signs),
            "unchanged_seeds":sum(x==0 for x in signs),
            "mean_four_seat_net_delta":round(mean(signs),4),
            "component_deltas":dict(tally),
            "counts_by_arm":{a:dict(counts[a]) for a in ARMS},
            "per_seed":groups,"positions":trials,
            "candidate_is_live":False,"calibrated_ron_probability":None,
            "confidence_interval":None}


def study(*,development:int=50000,holdout:int=51000,seeds:int=4)->dict[str,Any]:
    if (type(development) is not int or type(holdout) is not int or
        type(seeds) is not int or not 1<=seeds<=8 or
        not 0<=development<2**32 or not 0<=holdout<2**32 or
        max(development,holdout)+seeds>2**32 or
        (development<holdout+seeds and holdout<development+seeds)):
        raise ValueError("nonoverlapping independent seed ranges required")
    return {"protocol":PROTOCOL,"online_policy_modified":False,
            "claim_guard_scope":"baseline_selected_peng_equal_shanten_only",
            "frozen_risk_gate":GATE,
            "development_seed_range":[development,development+seeds],
            "holdout_seed_range":[holdout,holdout+seeds],
            "development":cohort(development,seeds),
            "holdout":cohort(holdout,seeds),
            "limitations":[
              "Public threat is an additive descriptive index, not a Ron probability.",
              "Equal-shanten Peng risk considers actual authorized public view but no future wall.",
              "The actual cut after the claim could differ from the best shanten hypothetical candidates.",
              "This candidate is OFFLINE, not a validated improvement to live challenge AI.",
              "Treatment changes the whole path: official net differences are not a point-action causal EV.",
              "Four seat rotations share the same shuffle seed and are not independent observations.",
              "Do not promote without replicated meaningful net results on unseen shuffle blocks.",
            ]}
