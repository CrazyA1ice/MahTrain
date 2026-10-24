"""M4.21 retrospective forensic ledger for *unchanged* M4.20 paired actions.

This replay uses only the original public-authorized bounded-search agent
and the full-game simulator. Decision-time search never sees future outcomes.
Only after both simulated games terminate do we inspect transient trusted
action traces and posted official settlements, then return anonymized metrics.

Time to tenpai means first observed post-split OWN DISCARD leaving exact
shanten 0. It is right-censored if no such discard occurs, NOT assumed
failure to reach tenpai, nor a controlled local causal action effect.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
from statistics import mean
from typing import Any, Mapping

from .ai_action_extended_study import _fixed_lineup
from .ai_bounded_public_lookahead_paired import (
    ARMS, METRICS, BoundedLookaheadResearchAgent,
    MIN_EFFECTIVE_COPIES_RETENTION, MAX_PUBLIC_THREAT_INCREASE,
    MIN_PROJECTED_SCORE_GAIN, projected_branch_score,
)
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_discard_first_divergence_ledger import first_real_discard_divergence
from .ai_exhaustive_terminal_cash_audit import audited_terminal
from .ai_tournament import simulate_match

PROTOCOL = "m421_m420_original_first_true_split_to_observed_tenpai_ledger_v1"
REPLAY_GROUPS={"development":(60000,3),"holdout":(61000,3)}
COMPONENTS=("win_points","kong_points","exhaustive_points")


class FirstSplitBoundedAuditAgent(BoundedLookaheadResearchAgent):
    """Observe the original M4.20 first altered cut, never select a new one."""
    def __init__(self,*,seed:int,seat:int,arm:str)->None:
        super().__init__(seed=seed,seat=seat,arm=arm)
        self.anonymous_changes:list[dict[str,Any]]=[]

    def discard(self,view:Mapping[str,Any])->str:
        selected=super().discard(view)
        if self.arm!="bounded_two_transition":
            return selected
        ranked=getattr(self,"_last_discard_scores",None)
        if not ranked or selected==ranked[0]["discard"]:
            return selected
        base=ranked[0]
        alt=next((r for r in ranked[1:] if r["discard"]==selected),None)
        if alt is None or base["shanten"]!=1 or alt["shanten"]!=1:
            raise RuntimeError("actual revised cut not a legal one-shanten rank")
        if (alt["effective_tile_count"]+1e-9<
                base["effective_tile_count"]*MIN_EFFECTIVE_COPIES_RETENTION
                or alt["table_threat_index"]>
                base["table_threat_index"]+MAX_PUBLIC_THREAT_INCREASE+1e-9):
            raise RuntimeError("actual candidate violates frozen public guards")

        # Post-choice FORENSIC recalculation of precisely the two same
        # authorized first-cut proxies; outcomes never feed back into agent.
        original=projected_branch_score(view,base["discard"])
        revised=projected_branch_score(view,selected)
        if (original["proxy"]<=0 or revised["proxy"]<=0 or
                revised["proxy"]+1e-8<
                MIN_PROJECTED_SCORE_GAIN*original["proxy"] or
                revised["proxy"]<=original["proxy"]):
            raise RuntimeError("actual policy change not supported by frozen proxy")
        ratio=revised["proxy"]/original["proxy"]
        if not isfinite(ratio):
            raise RuntimeError("nonfinite revised two-step score ratio")
        self.anonymous_changes.append({
            "own_discard_ordinal":self.counts["total_discards"],
            "minimum_shanten":1,
            "wall_remaining_at_choice":view.get("wall_count"),
            "baseline_effective_copies":base["effective_tile_count"],
            "candidate_effective_copies":alt["effective_tile_count"],
            "public_threat_increase_milli":round(
                1000*(alt["table_threat_index"]-
                      base["table_threat_index"])),
            "projected_ratio":round(ratio,5),
            "baseline_draw_types_scanned":original["draw_types"],
            "candidate_draw_types_scanned":revised["draw_types"],
            "baseline_branch_coverage_fraction":original["coverage_fraction"],
            "candidate_branch_coverage_fraction":revised["coverage_fraction"],
        })
        return selected


def observed_tenpai_after_first_split(
    trace:list[Mapping[str,Any]], *,
    seat:int, first_event_index:int,
)->dict[str,Any]:
    """Actual own shanten=0 on a later cut; censored otherwise.

    We deliberately do not equate winning, claimed Peng/Kong, tenpai
    opportunities before the split, or structural forecast with a *later*
    observed zero-shanten cut. Wall state and other hands are not needed.
    """
    if (type(seat) is not int or seat not in range(4) or
            type(first_event_index) is not int or
            not 0<=first_event_index<len(trace)):
        raise ValueError("invalid first split position")
    if (trace[first_event_index].get("action")!="discard" or
            trace[first_event_index].get("seat")!=seat):
        raise RuntimeError("first divergence must be own actual discard")
    timeline=[
        (i,e) for i,e in enumerate(trace[first_event_index+1:],
                                  start=first_event_index+1)
        if e.get("seat")==seat and e.get("action")=="discard"
    ]
    for ordinal,(i,e) in enumerate(timeline,1):
        shanten=e.get("shanten_after")
        if type(shanten) is not int or shanten<0:
            raise RuntimeError("actual later discard lacks exact shanten")
        if shanten==0:
            return {
                "observed_zero_shanten":True,
                "censored":False,
                "events_after_split":i-first_event_index,
                "own_later_discards_until_tenpai":ordinal,
                "own_later_discards_total":len(timeline),
            }
    return {
        "observed_zero_shanten":False,"censored":True,
        "events_after_split":None,
        "own_later_discards_until_tenpai":None,
        "own_later_discards_total":len(timeline),
    }


def paired_audit_position(seed:int,rotation:int)->dict[str,Any]:
    if (type(seed) is not int or not 0<=seed<2**32 or
            type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid frozen replay initial shuffle or seat")
    lineup,seat=_fixed_lineup(rotation)
    arms={}
    ephemeral={}
    for arm in ARMS:
        agent=FirstSplitBoundedAuditAgent(seed=seed,seat=seat,arm=arm)
        capture={}
        def store(game:Any)->None:
            capture["terminal_game"]=game
        match=simulate_match(
            seed,rotation=rotation%3,lineup=lineup,offline_kong_base=1,
            offline_agent_overrides={seat:agent},
            offline_observer=store,
        )
        if match["physical_count"]!=108 or "terminal_game" not in capture:
            raise RuntimeError("no complete real 108-tile state to audit")
        game=capture["terminal_game"]
        if match["terminal_phase"]!=game.phase:
            raise RuntimeError("terminal observer was not same official game")
        money=_official_outcome(match,seat,lineup)
        if money["official_net"]!=sum(money[k] for k in COMPONENTS):
            raise RuntimeError("official full-game net not reconciled")
        term=audited_terminal(game.public_state(),seat=seat,
                              phase=match["terminal_phase"],
                              expected_exhaustive=money["exhaustive_points"])
        arms[arm]={
            "official":money,"counts":agent.safe_counts(),
            "terminal_phase":match["terminal_phase"],
            "own_terminal_class":term["terminal_class"],
            "own_exhaustive_flower_pig":term["flower_pig_balance"],
            "own_exhaustive_da_jiao":term["da_jiao_balance"],
            "own_terminal_wait_count":term["own_wait_count"],
            "own_terminal_max_effective_fan":term["own_max_effective_fan"],
        }
        ephemeral[arm]={
            "trace":match["trace"],"public_events":match["public_events"],
            "changes":agent.anonymous_changes,
        }

    base,candidate=ephemeral["baseline"],ephemeral["bounded_two_transition"]
    changed=arms["bounded_two_transition"]["counts"].get("actual_changes",0)
    if (base["changes"] or len(candidate["changes"])!=changed):
        raise RuntimeError("anonymous actual changes not equal to policy count")
    split=first_real_discard_divergence(
        base["trace"],candidate["trace"],seat=seat,
        changes=candidate["changes"],
    )
    if changed==0 and (
            split is not None or base["public_events"]!=candidate["public_events"]
            or arms["baseline"]["official"]!=
                arms["bounded_two_transition"]["official"]
            or arms["baseline"]["terminal_phase"]!=
                arms["bounded_two_transition"]["terminal_phase"]):
        raise RuntimeError("untouched candidate produced different game")
    if changed>0 and split is None:
        raise RuntimeError("true candidate discard lacks first true trace split")
    deltas={k:arms["bounded_two_transition"]["official"][k]-
                arms["baseline"]["official"][k] for k in METRICS}
    if deltas["official_net"]!=sum(deltas[k] for k in COMPONENTS):
        raise RuntimeError("paired official component deltas mismatch")
    stage_delta={
        "flower_pig":arms["bounded_two_transition"]["own_exhaustive_flower_pig"]-
                     arms["baseline"]["own_exhaustive_flower_pig"],
        "da_jiao":arms["bounded_two_transition"]["own_exhaustive_da_jiao"]-
                 arms["baseline"]["own_exhaustive_da_jiao"],
    }
    if sum(stage_delta.values())!=deltas["exhaustive_points"]:
        raise RuntimeError("terminal official flower-pig/da-jiao balance drift")

    if changed:
        index=split["event_ordinal"]-1
        timeline={
            arm:observed_tenpai_after_first_split(
                ephemeral[arm]["trace"],seat=seat,first_event_index=index,
            ) for arm in ARMS
        }
        both=all(timeline[a]["observed_zero_shanten"] for a in ARMS)
        first={
            **split,
            "observed_tenpai_after_split":timeline,
            "candidate_minus_baseline_own_cuts_to_tenpai":(
                timeline["bounded_two_transition"][
                    "own_later_discards_until_tenpai"]-
                timeline["baseline"]["own_later_discards_until_tenpai"]
                if both else None
            ),
            "both_observed_zero_shanten":both,
            "own_terminal_classes":{
                a:arms[a]["own_terminal_class"] for a in ARMS},
            "terminal_own_wait_counts":{
                a:arms[a]["own_terminal_wait_count"] for a in ARMS},
            "terminal_own_max_effective_fan":{
                a:arms[a]["own_terminal_max_effective_fan"] for a in ARMS},
        }
    else:
        first=None

    return {
        "seed":seed,"rotation":rotation,"challenge_seat":seat,
        "actual_changes":changed,"first_split":first,
        "authoritative_deltas":deltas,
        "terminal_stage_deltas":stage_delta,
        "arms":arms,
        "live_policy_modified":False,"attributed_local_action_ev":None,
    }


def cohort(start:int,seeds:int=3)->dict[str,Any]:
    if (type(start) is not int or type(seeds) is not int or
            not 0<=start<2**32 or not 1<=seeds<=6 or start+seeds>2**32):
        raise ValueError("invalid frozen retrospective seed block")
    rows=[paired_audit_position(seed,rotation)
          for seed in range(start,start+seeds) for rotation in range(4)]
    cash=Counter()
    stage=Counter()
    per_seed=[]
    changed_rows=[]
    for seed in range(start,start+seeds):
        group=[p for p in rows if p["seed"]==seed]
        if sorted(p["challenge_seat"] for p in group)!=[0,1,2,3]:
            raise RuntimeError("missing one of four paired seats")
        local=Counter()
        changes=0
        for row in group:
            cash.update(row["authoritative_deltas"])
            local.update(row["authoritative_deltas"])
            stage.update(row["terminal_stage_deltas"])
            changes+=row["actual_changes"]
            if row["actual_changes"]:
                changed_rows.append(row)
        per_seed.append({
            "seed":seed,"actual_changes":changes,
            "mean_four_seat_net_delta":round(local["official_net"]/4,4),
            "win_delta":local["win_points"],
            "kong_delta":local["kong_points"],
            "exhaustive_delta":local["exhaustive_points"],
        })
    if (cash["official_net"]!=sum(cash[k] for k in COMPONENTS) or
            cash["exhaustive_points"]!=sum(stage.values())):
        raise RuntimeError("official cash and terminal phases not reconciled")
    return {
        "independent_historical_shuffles":seeds,
        "complete_paired_games":len(rows)*2,
        "total_actual_changes":sum(x["actual_changes"] for x in rows),
        "changed_seat_positions":len(changed_rows),
        "official_component_deltas":{k:cash[k] for k in METRICS},
        "flower_pig_and_da_jiao_deltas":dict(stage),
        "per_seed":per_seed,
        "changed_position_forensics":changed_rows,
        "unchanged_position_count":len(rows)-len(changed_rows),
        "retrospective_not_new_validation":True,
        "online_ai_modified":False,
    }


def study()->dict[str,Any]:
    return {
        "protocol":PROTOCOL,"retrospective_not_independent_validation":True,
        "online_ai_modified":False,
        "development":cohort(*REPLAY_GROUPS["development"]),
        "holdout":cohort(*REPLAY_GROUPS["holdout"]),
        "limitations":[
            "Actual cut-to-tenpai measures only later own discards that reach exact shanten 0.",
            "No later zero-shanten discard is RIGHT-CENSORED, not proof that the hand never listened.",
            "Observed paths may diverge in all later draws, other seats' actions, calls, and available wall.",
            "The truncated next-draw proxy is an optimistic structural value, not P(tenpai) or causal EV.",
            "Original M4.20 shuffle seeds are reused; this is descriptive history, NOT new holdout.",
            "No raw tile, concealed hand, future wall, full game trace or opponent hidden wait is exported.",
            "No live AI, official rules, human UI or tournament scoring is changed.",
        ],
    }
