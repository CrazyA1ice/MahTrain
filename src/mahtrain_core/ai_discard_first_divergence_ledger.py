"""M4.15: audit the FIRST actual M4.14 discard divergence and official cash.

This is descriptive post-game forensic REPLAY of the *unchanged* frozen
M4.14 public-risk candidate. No new policy search and no live-AI edits.
Only the acting seat's legitimately authorized view is consulted when the
agent actually cuts; exact tile identities / hands and full game traces
remain ephemeral and NEVER leave this module in returned report objects.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
from statistics import mean
from typing import Any, Mapping

from .ai_action_extended_study import _fixed_lineup
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_discard_nearvalue_risk_paired import (
    ARMS, METRICS, MIN_PUBLIC_THREAT_REDUCTION,
    MIN_UKEIRE_RETENTION, MIN_VALUE_RETENTION,
    NearValueDefenseResearchAgent,
)
from .ai_tournament import simulate_match

PROTOCOL = "m415_frozen_m414_first_discard_divergence_cash_audit_v1"
COMPONENTS = ("win_points", "kong_points", "exhaustive_points")


def _wall_stage(remaining: Any) -> str:
    if type(remaining) is not int or remaining < 0:
        return "unknown"
    return "critical" if remaining <= 12 else (
        "late" if remaining <= 24 else "early")


class FirstDivergenceAuditAgent(NearValueDefenseResearchAgent):
    """Observe after the unchanged M4.14 policy has chosen a legal cut."""

    def __init__(self, *, seed: int, seat: int, arm: str) -> None:
        super().__init__(seed=seed, seat=seat, arm=arm)
        self._anonymous_changes: list[dict[str, Any]] = []

    def discard(self, view: Mapping[str, Any]) -> str:
        chosen = super().discard(view)
        if self.arm != "nearvalue_defense":
            return chosen
        ranked = getattr(self, "_last_discard_scores", None)
        if not ranked or chosen == ranked[0]["discard"]:
            return chosen
        first = ranked[0]
        revised = next((r for r in ranked if r["discard"] == chosen), None)
        if revised is None:
            raise RuntimeError("actual cut is not in frozen min-shanten ranking")
        base_value, new_value = (first["expected_fan_weighted_copies"],
                                 revised["expected_fan_weighted_copies"])
        base_copies, new_copies = (first["effective_tile_count"],
                                   revised["effective_tile_count"])
        risk_drop = first["table_threat_index"] - revised["table_threat_index"]
        if (not all(isfinite(v) for v in (
                base_value, new_value, risk_drop)) or
                base_value <= 0 or base_copies <= 0 or
                first["shanten"] != revised["shanten"] or
                risk_drop + 1e-9 < MIN_PUBLIC_THREAT_REDUCTION or
                new_value+1e-9 < MIN_VALUE_RETENTION*base_value or
                new_copies+1e-9 < MIN_UKEIRE_RETENTION*base_copies):
            raise RuntimeError("actual candidate cut violates frozen guard")
        self._anonymous_changes.append({
            "own_discard_ordinal":self.counts["discard_decisions"],
            "minimum_shanten":first["shanten"],
            "wall_stage":_wall_stage(view.get("wall_count")),
            "public_risk_index_drop_milli":round(risk_drop*1000),
            "retained_fan_weighted_value_pct":round(100*new_value/base_value,2),
            "retained_effective_copies_pct":round(
                100*new_copies/base_copies,2),
        })
        return chosen


def first_real_discard_divergence(
    base: list[Mapping[str, Any]],
    trial: list[Mapping[str, Any]],
    *, seat: int, changes: list[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Inspect transient trusted traces; never export tile or hand details."""
    if type(seat) is not int or seat not in range(4):
        raise ValueError("invalid audited seat")
    first_difference = next(
        (i for i in range(min(len(base),len(trial)))
         if base[i] != trial[i]), None)
    if not changes:
        if first_difference is not None or len(base) != len(trial):
            raise RuntimeError("no policy change but complete trace differs")
        return None
    if first_difference is None:
        raise RuntimeError("candidate claims change but first divergence absent")
    a,b=base[first_difference],trial[first_difference]
    if not all(
        x.get("action") == "discard" and x.get("seat") == seat
        for x in (a,b)
    ) or a.get("tile")==b.get("tile"):
        raise RuntimeError("first split did not originate in an own legal cut")
    if (a.get("minimum_shanten") != b.get("minimum_shanten") or
            a.get("shanten_regret") != 0 or
            b.get("shanten_regret") != 0 or
            a.get("shanten_after") != b.get("shanten_after")):
        raise RuntimeError("first revision regressed exact minimum shanten")
    trial_ordinal=sum(x.get("action") == "discard" and x.get("seat")==seat
                      for x in trial[:first_difference+1])
    if (changes[0].get("own_discard_ordinal") != trial_ordinal or
            any(type(x.get("own_discard_ordinal")) is not int
                for x in changes) or
            any(x["own_discard_ordinal"] >= y["own_discard_ordinal"]
                for x,y in zip(changes,changes[1:]))):
        raise RuntimeError("first real policy action is not the trace divergence")
    return {
        "event_ordinal":first_difference+1,
        "own_discard_ordinal":trial_ordinal,
        "baseline_effective_copies":a["effective_copies"],
        "candidate_effective_copies":b["effective_copies"],
        "exact_minimum_shanten":a["minimum_shanten"],
        "first_policy_change":dict(changes[0]),
    }


def _dominant_component(delta:Mapping[str,int]) -> str:
    if not delta["official_net"]:
        return "zero_net_delta"
    values=sorted(
        ((abs(delta[k]),k) for k in COMPONENTS),reverse=True)
    if values[0][0]==values[1][0]:
        return "mixed_components"
    return values[0][1]


def paired_audit_position(seed:int,rotation:int)->dict[str,Any]:
    if (type(seed) is not int or not 0<=seed<2**32 or
            type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid preregistered independent shuffle / seat")
    lineup,seat=_fixed_lineup(rotation)
    arms={}
    hidden={}
    for arm in ARMS:
        agent=FirstDivergenceAuditAgent(seed=seed,seat=seat,arm=arm)
        game=simulate_match(
            seed,rotation=rotation%3,lineup=lineup,offline_kong_base=1,
            offline_agent_overrides={seat:agent},
        )
        arms[arm]={
            "official":_official_outcome(game,seat,lineup),
            "counts":agent.safe_counts(),
            "terminal_phase":game["terminal_phase"],
        }
        hidden[arm]=(game["trace"],game["public_events"],
                     agent._anonymous_changes)
    base,trial=hidden["baseline"],hidden["nearvalue_defense"]
    changed=arms["nearvalue_defense"]["counts"].get("actual_changes",0)
    if len(trial[2])!=changed or base[2]:
        raise RuntimeError("anonymous policy changes and actual count disagree")
    split=first_real_discard_divergence(base[0],trial[0],
                                        seat=seat,changes=trial[2])
    if not changed:
        if (split is not None or base[1]!=trial[1] or
                arms["baseline"]["official"]!=
                    arms["nearvalue_defense"]["official"] or
                arms["baseline"]["terminal_phase"]!=
                    arms["nearvalue_defense"]["terminal_phase"]):
            raise RuntimeError("unmodified two-arm game diverged")
    delta={key:arms["nearvalue_defense"]["official"][key]-
               arms["baseline"]["official"][key] for key in METRICS}
    if delta["official_net"]!=sum(delta[k] for k in COMPONENTS):
        raise RuntimeError("terminal authoritative cash not reconciled")
    return {
        "seed":seed,"rotation":rotation,"challenge_seat":seat,
        "baseline_official":arms["baseline"]["official"],
        "candidate_official":arms["nearvalue_defense"]["official"],
        "delta":delta,"real_interventions":changed,
        "first_divergence":split,
        "dominant_cash_component":_dominant_component(delta),
        "terminations":{
            a:arms[a]["terminal_phase"] for a in ARMS
        },
    }


def cohort(start:int,seeds:int=4)->dict[str,Any]:
    if (type(start) is not int or type(seeds) is not int or
            not 0<=start<2**32 or not 1<=seeds<=8 or
            start+seeds>2**32):
        raise ValueError("invalid frozen diagnostic seed range")
    rows=[paired_audit_position(seed,r)
          for seed in range(start,start+seeds) for r in range(4)]
    per_seed=[]
    cash=Counter()
    observed=[]
    for seed in range(start,start+seeds):
        rotations=[p for p in rows if p["seed"]==seed]
        if sorted(p["challenge_seat"] for p in rotations)!=list(range(4)):
            raise RuntimeError("incomplete independent seed / seat coverage")
        cluster=Counter()
        changed=0
        for p in rotations:
            cash.update(p["delta"])
            cluster.update(p["delta"])
            changed+=p["real_interventions"]
            if p["real_interventions"]:
                observed.append({
                    "seed":p["seed"],"rotation":p["rotation"],
                    "challenge_seat":p["challenge_seat"],
                    "real_interventions":p["real_interventions"],
                    "first_divergence":p["first_divergence"],
                    "official_component_deltas":{
                        k:p["delta"][k] for k in METRICS
                    },
                    "dominant_cash_component":p["dominant_cash_component"],
                })
        per_seed.append({
            "seed":seed,"real_interventions":changed,
            "four_seat_mean_net_delta":round(cluster["official_net"]/4,4),
            "win_delta":cluster["win_points"],
            "kong_delta":cluster["kong_points"],
            "exhaustive_delta":cluster["exhaustive_points"],
        })
    if cash["official_net"]!=sum(cash[x] for x in COMPONENTS):
        raise RuntimeError("all authoritative ledgers do not balance")
    if len(observed)!=sum(p["real_interventions"]>0 for p in rows):
        raise RuntimeError("wrong intervention position count")
    return {
        "independent_shuffle_seeds":seeds,"paired_positions":len(rows),
        "complete_games":2*len(rows),
        "changed_positions":len(observed),
        "actual_policy_changes":sum(x["real_interventions"] for x in rows),
        "official_deltas":{k:cash[k] for k in METRICS},
        "mean_four_seat_net_delta":round(
            mean(p["four_seat_mean_net_delta"] for p in per_seed),4),
        "per_seed":per_seed,
        "changed_position_diagnostics":observed,
        "live_ai_modified":False,
        "local_causal_action_ev":None,
        "p_ron":None,
    }


def study()->dict[str,Any]:
    """Re-examine PREVIOUSLY measured M4.14 seeds, not fresh holdout data."""
    return {
        "protocol":PROTOCOL,"online_policy_modified":False,
        "retrospective_not_independent_validation":True,
        "development":cohort(52000,4),
        "holdout":cohort(53000,4),
        "limitations":[
            "Scores after the first divergence include subsequent action/wall/opponent path effects.",
            "Cash component differences are verified ledger descriptions, not an attribution of blame.",
            "Multiple policy changes in a diverged game are not independent observations.",
            "The 52000 and 53000 blocks already informed M4.14 findings: NOT new prospective data.",
            "Public risk differences are not calibrated P(Ron) or local per-action expected points.",
            "No full trace, specific tile, wall or other seat's hidden hand is exported.",
            "Official challenge AI and web-facing gameplay remain unchanged.",
        ],
    }
