"""M3.99: same-tile repeated own-kong offers, attempted/successful/robbed bu-gang.

ALL experiments are OFFLINE and seeded before observing any winner. Private
(kind,tile) identity is held only in the trusted per-seat observer, to avoid
counting the same repeatedly offered bu-gang as independent decisions.
Returned diagnostics contain counts and authoritative PUBLIC settlement only.
The online server, actual challenge policy and legitimate Hu choices are intact.
"""
from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Mapping

from .ai_action_extended_study import NaturalOpportunityAgent, _fixed_lineup
from .ai_challenge_action_counterfactual import METRICS, POLICIES, _one
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_tournament import simulate_match

PROTOCOL = "m399_same_tile_bugang_repeat_rob_audit_v1"
KONG_TYPES = ("an_gang", "bu_gang")
STUDY_ARMS = POLICIES[1:]


class SameTileAuditAgent(NaturalOpportunityAgent):
    """Respect the live challenge action, count repeat private tiles locally."""

    def __init__(self, *, seed: int, seat: int) -> None:
        super().__init__(seed=seed, seat=seat)
        self._ever: set[tuple[str,str]] = set()
        self._previous: set[tuple[str,str]] = set()

    def kong(self, view: Mapping[str, Any]) -> dict[str, str] | None:
        original = super().kong(view)
        if view.get("can_self_draw_win"):
            self._previous.clear()
            return original
        offers = view.get("kong_options") or []
        current: set[tuple[str,str]] = set()
        for option in offers:
            kind = option["type"]
            if kind not in KONG_TYPES:
                raise RuntimeError("unrecognized authoritative kong kind")
            tile = option["tile"]
            key = (kind,tile)
            if key in current:
                raise RuntimeError("duplicate current own-kong offer")
            current.add(key)
            if key not in self._ever:
                self.counts["distinct_"+kind+"_tiles"] += 1
                self._ever.add(key)
            else:
                self.counts["repeat_"+kind+"_candidate_windows"] += 1
                if key not in self._previous:
                    self.counts["returned_after_gap_"+kind] += 1
        self._previous = current
        return original

    def response(self, view: Mapping[str, Any], *, rob: bool = False) -> str:
        choice = super().response(view,rob=rob)
        if rob and "hu" in (view.get("rob_options") or []):
            self.counts["opponent_bugang_rob_hu_available"] += 1
            self.counts["opponent_bugang_rob_hu_taken"] += int(choice == "hu")
        return choice


def _audited_public_bugang(game: Mapping[str,Any], seat: int) -> dict[str,int]:
    """A declared upgrade either resolves successfully or is robbed.

    Do NOT count a bu_gang_declared event as paid/realized. The event 'bu_gang'
    is emitted only after all legal opponents pass rob-kong; 'rob_kong'
    cancels the upgrade and can have multiple Hu winners.
    """
    events=game["public_events"]
    if type(events) is not list:
        raise RuntimeError("public rule events were absent")
    declared=sum(e["type"]=="bu_gang_declared" and e.get("seat")==seat
                 for e in events)
    realized=sum(e["type"]=="bu_gang" and e.get("seat")==seat for e in events)
    robbed=sum(e["type"]=="rob_kong" and e.get("seat")==seat for e in events)
    victims=sum(w["kind"]=="rob_kong" and w["source"]==seat
                for w in game["winners"])
    if declared!=realized+robbed:
        raise RuntimeError("declared bu-gang must settle or be robbed exactly once")
    if robbed>victims or (robbed==0 and victims!=0):
        raise RuntimeError("rob-kong event does not reconcile with winners")
    return {"attempted_bu_gang":declared,"successful_bu_gang":realized,
            "robbed_bu_gang":robbed,"rob_kong_winners":victims}


def natural_position(seed: int, rotation: int) -> dict[str,Any]:
    if type(seed) is not int or not 0<=seed<2**32:
        raise ValueError("invalid natural shuffle seed")
    lineup,seat=_fixed_lineup(rotation)
    agent=SameTileAuditAgent(seed=seed,seat=seat)
    outcome=simulate_match(
        seed,rotation=rotation%3,lineup=lineup,
        offline_kong_base=1,offline_agent_overrides={seat:agent})
    official=_official_outcome(outcome,seat,lineup)
    counts=Counter(agent.counts)
    for kind in KONG_TYPES:
        if (counts["own_kong_offer_"+kind] !=
                counts["distinct_"+kind+"_tiles"]+
                counts["repeat_"+kind+"_candidate_windows"]):
            raise RuntimeError("consecutive candidate vs distinct tile audit failed")
        if counts["returned_after_gap_"+kind] > counts[
                "repeat_"+kind+"_candidate_windows"]:
            raise RuntimeError("returned-after-gap exceeds repeat windows")
    bu=_audited_public_bugang(outcome,seat)
    if counts["own_kong_original_bu_gang"]!=bu["attempted_bu_gang"]:
        raise RuntimeError("challenge decided bu-gang but rule event not declared")
    if (official["realized_kongs"] <
            bu["successful_bu_gang"]):
        raise RuntimeError("official physical kong count excludes successful bu-gang")
    counts.update(bu)
    return {
        "seed":seed,"rotation":rotation,"challenge_seat":seat,
        "counts":dict(counts),"official_score":official,
        "terminal_phase":outcome["terminal_phase"],
    }


def natural_cohort(seed_start: int, seeds: int) -> dict[str,Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
            seed_start<0 or seeds<1 or seeds>16 or
            seed_start+seeds>2**32):
        raise ValueError("invalid seed range for natural observation")
    positions=[
        natural_position(seed,rotation)
        for seed in range(seed_start,seed_start+seeds)
        for rotation in range(4)
    ]
    total=Counter()
    per_seed=[]
    for seed in range(seed_start,seed_start+seeds):
        four=[p for p in positions if p["seed"]==seed]
        if sorted(p["challenge_seat"] for p in four)!=[0,1,2,3]:
            raise RuntimeError("natural cohort missing a challenge seat")
        sub=Counter()
        for pos in four:sub.update(pos["counts"])
        total.update(sub)
        per_seed.append({
            "seed":seed,"counts":dict(sub),
            "positions_with_bugang":sum(
                p["counts"].get("own_kong_window_with_bu_gang",0)>0
                for p in four),
            "positions_with_any_own_kong":sum(
                p["counts"].get("own_kong_windows",0)>0 for p in four),
        })
    return {
        "seed_start":seed_start,"independent_seeds":seeds,
        "four_seat_positions":len(positions),
        "total_counts":dict(total),"per_seed":per_seed,"positions":positions,
        "comparison_warning":(
            "Repeated offers of the same tile across turns are correlated; "
            "one initial seed, not a window or tile, is the independent unit."),
    }


def first_own_kong_cohort(seed_start: int, seeds: int) -> dict[str,Any]:
    """Pre-registered first OWN kong (not cherry-picked later bu-gang)."""
    if (type(seed_start) is not int or type(seeds) is not int or
            seed_start<0 or seeds<1 or seeds>16 or
            seed_start+seeds>2**32):
        raise ValueError("invalid first-kong study cohort")
    rows=[_one(seed,rotation,"own_kong")
          for seed in range(seed_start,seed_start+seeds)
          for rotation in range(4)]
    per_seed=[]
    for seed in range(seed_start,seed_start+seeds):
        group=[x for x in rows if x["seed"]==seed]
        if sorted(x["challenge_seat"] for x in group)!=[0,1,2,3]:
            raise RuntimeError("incomplete first-own-kong seat cluster")
        per_seed.append({
            "seed":seed,"offered_positions":sum(r["offered"] for r in group),
            "four_seat_delta":{
                arm:sum(
                    r["alternatives"][arm]["delta"]["official_net"]
                    if r["offered"] else 0 for r in group)/4
                for arm in STUDY_ARMS
            },
        })
    arms={}
    for arm in STUDY_ARMS:
        effects=Counter()
        changed=0
        offers=0
        type_counts=Counter()
        for row in rows:
            if not row["offered"]:
                continue
            offers+=1
            candidate=row["alternatives"][arm]
            effects.update(candidate["delta"])
            changed+=int(candidate["changed"])
            # No identifying tile names; retain only the type of the first
            # offered active action and the original pass/active status.
            before=row["baseline"]["opportunity"]
            kind=before["options"][1].split("#",1)[0]
            type_counts["first_active_offer_"+kind]+=1
            if candidate["changed"]:
                type_counts["changed_first_active_offer_"+kind]+=1
        diffs=[r["four_seat_delta"][arm] for r in per_seed]
        arms[arm]={
            "offered_positions":offers,"changed_positions":changed,
            "mean_seed_cluster_net_delta":round(mean(diffs),4),
            "positive_seeds":sum(x>0 for x in diffs),
            "negative_seeds":sum(x<0 for x in diffs),
            "tied_seeds":sum(x==0 for x in diffs),
            "candidate_types":dict(type_counts),
            "cumulative_official_component_deltas":{
                k:effects[k] for k in METRICS},
            # Eight independent seeds permit interval estimation in
            # principle, but coverage can still be too sparse. We report
            # raw cluster outcomes; do not fabricate CIs from empty seeds.
            "confidence_interval_95pct":None,
            "interval_status":"not_estimated_sparse_action_clusters",
        }
    return {
        "seed_start":seed_start,"independent_seeds":seeds,
        "four_seat_positions":len(rows),"per_seed":per_seed,
        "arms":arms,"positions":rows,
    }


def study(*, natural_development: int = 20000,
          natural_holdout: int = 21000,
          paired_development: int = 22000,
          paired_holdout: int = 23000,
          seeds_per_group: int = 8,
          mode: str = "all") -> dict[str,Any]:
    if (type(mode) is not str or mode not in ("all","natural","paired")
            or type(seeds_per_group) is not int or
            not 1<=seeds_per_group<=16 or
            any(type(v) is not int or not 0<=v<2**32 for v in (
                natural_development,natural_holdout,
                paired_development,paired_holdout))):
        raise ValueError("invalid experiment control")
    ranges=[
        (natural_development,natural_development+seeds_per_group),
        (natural_holdout,natural_holdout+seeds_per_group),
        (paired_development,paired_development+seeds_per_group),
        (paired_holdout,paired_holdout+seeds_per_group),
    ]
    if (any(end>2**32 for _,end in ranges) or
            any(a[0]<b[1] and b[0]<a[1]
                for i,a in enumerate(ranges) for b in ranges[i+1:])):
        raise ValueError("four predeclared independent seed groups overlap")
    result={
        "protocol":PROTOCOL,"mode":mode,
        "natural_seed_ranges":ranges[:2],
        "paired_seed_ranges":ranges[2:],
        "live_ai_modified":False,
        "limitations":[
            "Same-kind same-tile identities stay private to the observer, never in exported JSON.",
            "A bu-gang announcement may be robbed and is not a successful priced kong.",
            "Optional kong may be offered repeatedly across successive turns.",
            "Repeated actions within a shuffle seed are NOT independent samples.",
            "First-kong counterfactual is selected by earliest legal choice, not by later realized gain.",
            "Fixed-wall paired outcome differences are not deployable online EV probabilities.",
            "Hu and rob-kong Hu are never overridden.",
        ],
    }
    if mode in ("all","natural"):
        result["natural"]={
            "development":natural_cohort(natural_development,seeds_per_group),
            "holdout":natural_cohort(natural_holdout,seeds_per_group),
        }
    if mode in ("all","paired"):
        result["paired"]={
            "development":first_own_kong_cohort(
                paired_development,seeds_per_group),
            "holdout":first_own_kong_cohort(
                paired_holdout,seeds_per_group),
        }
    return result
