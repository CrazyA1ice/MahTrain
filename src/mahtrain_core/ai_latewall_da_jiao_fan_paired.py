"""M4.17: frozen offline-only late-wall ready-hand max-fan discard study.

Read ONLY the acting player's authorized own hand, declared melds,
dingque, the public wall count and already computed challenge rank.
The same official score_win used by terminal da-jiao supplies hypothetical
maximum effective fan. It is NOT a guarantee the game will exhaust.
Never modifies the live challenge policy, other players, or the rules.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
from statistics import mean
from typing import Any, Mapping, Sequence

from .ai import MahjongAgent, _own_view
from .ai_action_extended_study import _fixed_lineup
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_discard_nearvalue_risk_paired import METRICS
from .ai_tournament import simulate_match
from .rules import TILE_INDEX, score_win, winning_tiles

PROTOCOL = "m417_frozen_late_wall_max_fan_tenpai_paired_v1"
ARMS = ("baseline", "late_wall_fan")
LATE_WALL_TILES = 32
MIN_MAX_FAN_GAIN = 1
MIN_EFFECTIVE_COPIES_RETENTION = 0.60
MIN_WAIT_TYPES_RETENTION = 0.50
MIN_FAN_WEIGHTED_RETENTION = 0.65
MAX_PUBLIC_THREAT_INCREASE = 0.15


def maximum_authorized_da_jiao_fan(
    view: Mapping[str, Any], cut: str,
) -> tuple[int | None, int]:
    """Hypothetical own 13-effective ready hand; never inspect future walls.

    The *same* score_win and wait rules as official exhaustive review are
    called with actual verified Tian Ting information (not guessed).
    Return None for non-listening. These are possible waits, not known tiles
    remaining in the physical wall or opponents' hands.
    """
    hand,melds,missing = _own_view(view)
    if cut not in hand or cut not in TILE_INDEX:
        raise ValueError("cut must exist in actor's legal own hand")
    rest=list(hand)
    rest.remove(cut)
    if len(rest)+3*len(melds)!=13:
        raise ValueError("candidate has no legal 13-effective hand")
    waits=winning_tiles(rest,melds,missing)
    if not waits:
        return None,0
    cap=(view.get("win_ledger") or {}).get("fan_cap")
    if type(cap) is not int or not 0<=cap<=12:
        raise RuntimeError("unverified official room fan cap")
    tian=(view.get("tian_ting") or {})
    verified=(tian.get("eligible") is True and
              set(waits)==set(tian.get("initial_waits",())))
    scores=[score_win([*rest,tile],melds,missing,cap=cap,
                      context={"tian_ting_verified":verified})
            for tile in waits]
    fans=[v["effective_fan"] for v in scores if v.get("legal") is True]
    if not fans:
        raise RuntimeError("verified structural waiting set cannot all fail score")
    return max(fans),len(waits)


def propose_late_wall_fan_cut(
    original: str, ranked: Sequence[Mapping[str,Any]] | None,
    view: Mapping[str,Any],
)->tuple[str,str]:
    """No regression of min shanten or guaranteed forecast from terminal fan."""
    wall=view.get("wall_count")
    if type(wall) is not int or wall<0:
        raise ValueError("missing current public wall size")
    if wall>LATE_WALL_TILES:
        return original,"before_late_wall_window"
    if (view.get("tian_ting") or {}).get("eligible") is True:
        return original,"verified_tian_ting_untouched"
    if not ranked or len(ranked)<2:
        return original,"no_alternative_minimum_shanten"
    if ranked[0].get("discard")!=original:
        raise RuntimeError("original action does not match rank zero")
    hand=view.get("hand")
    if type(hand) is not list or original not in hand:
        raise RuntimeError("acting own hand does not authorize original cut")
    shanten=ranked[0].get("shanten")
    if type(shanten) is not int:
        raise RuntimeError("unknown strict minimum shanten")
    if shanten!=0:
        return original,"not_already_tenpai_after_cut"

    seen=set()
    for entry in ranked:
        tile=entry.get("discard")
        if (tile not in TILE_INDEX or tile not in hand or
                tile in seen or entry.get("shanten")!=shanten):
            raise RuntimeError("unauthorized/nonminimum/duplicate discard rank")
        seen.add(tile)
        for key in ("effective_tile_count","expected_fan_weighted_copies",
                    "table_threat_index"):
            value=entry.get(key)
            if type(value) not in (int,float) or not isfinite(value) or value<0:
                raise RuntimeError("invalid source public rank observation")
    base=ranked[0]
    if (base["effective_tile_count"]<=0 or
            base["expected_fan_weighted_copies"]<=0):
        return original,"no_visible_baseline_waits"
    base_fan,base_types=maximum_authorized_da_jiao_fan(view,original)
    if base_fan is None or base_types<=0:
        raise RuntimeError("zero-shanten candidate cannot have no structural waits")
    choices=[]
    for row in ranked[1:]:
        if row["effective_tile_count"] < (
                base["effective_tile_count"]*MIN_EFFECTIVE_COPIES_RETENTION):
            continue
        if row["expected_fan_weighted_copies"] < (
                base["expected_fan_weighted_copies"]*MIN_FAN_WEIGHTED_RETENTION):
            continue
        if row["table_threat_index"] > (
                base["table_threat_index"]+MAX_PUBLIC_THREAT_INCREASE):
            continue
        fan,types=maximum_authorized_da_jiao_fan(view,row["discard"])
        if fan is None or types<base_types*MIN_WAIT_TYPES_RETENTION:
            continue
        if fan-base_fan<MIN_MAX_FAN_GAIN:
            continue
        choices.append((fan,types,row))
    if not choices:
        return original,"no_guarded_higher_fan_wait"
    # Max official terminal fan first, then legal wait-type count; retain
    # original evaluated fan-weighted efficiency for tie-breaks.
    choice=min(choices,key=lambda x:(
        -x[0],-x[1],
        -x[2]["expected_fan_weighted_copies"],
        -x[2]["effective_tile_count"],
        x[2]["table_threat_index"],TILE_INDEX[x[2]["discard"]]
    ))
    return choice[2]["discard"],"more_possible_max_da_jiao_fan"


class LateWallFanResearchAgent(MahjongAgent):
    def __init__(self,*,seed:int,seat:int,arm:str)->None:
        if arm not in ARMS:
            raise ValueError("invalid frozen arm")
        super().__init__("challenge",seed=seed,seat=seat)
        # Baseline-only pressure diagnostics enforce original rank zero.
        # Both research arms are still subject to game legal action validation.
        self._offline_reference_cut=True
        self.arm=arm
        self.counts: Counter[str]=Counter()

    def discard(self,view:Mapping[str,Any])->str:
        original=super().discard(view)
        self.counts["total_cuts"]+=1
        ranked=getattr(self,"_last_discard_scores",None)
        proposed,why=propose_late_wall_fan_cut(original,ranked,view)
        self.counts["reason_"+why]+=1
        self.counts["late_wall_cuts"]+=int(
            type(view.get("wall_count")) is int and
            view["wall_count"]<=LATE_WALL_TILES)
        self.counts["baseline_min_shanten_tenpai"]+=int(bool(
            ranked and ranked[0]["shanten"]==0))
        self.counts["suggestions"]+=int(proposed!=original)
        result=proposed if self.arm=="late_wall_fan" else original
        self.counts["actual_changes"]+=int(result!=original)
        if result not in view["hand"]:
            raise RuntimeError("cut not in visible own concealed hand")
        return result

    def safe_counts(self)->dict[str,int]:
        if self.counts["total_cuts"]!=sum(
                v for k,v in self.counts.items() if k.startswith("reason_")):
            raise RuntimeError("not all cuts are classified")
        if self.counts["actual_changes"]>self.counts["suggestions"] or (
                self.arm=="baseline" and self.counts["actual_changes"]):
            raise RuntimeError("baseline mutation or unregistered cut")
        return dict(self.counts)


def paired_position(seed:int,rotation:int)->dict[str,Any]:
    if (type(seed) is not int or not 0<=seed<2**32 or
            type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid seed / balanced seating")
    lineup,seat=_fixed_lineup(rotation)
    arms={}
    for arm in ARMS:
        agent=LateWallFanResearchAgent(seed=seed,seat=seat,arm=arm)
        game=simulate_match(seed,rotation=rotation%3,lineup=lineup,
                            offline_kong_base=1,
                            offline_agent_overrides={seat:agent})
        arms[arm]={
            "official":_official_outcome(game,seat,lineup),
            "counts":agent.safe_counts(),
            "phase":game["terminal_phase"],
            "_trace":game["trace"],"_events":game["public_events"],
        }
    b,c=arms["baseline"],arms["late_wall_fan"]
    changes=c["counts"].get("actual_changes",0)
    if changes==0 and (
            b["official"]!=c["official"] or b["phase"]!=c["phase"] or
            b["_trace"]!=c["_trace"] or b["_events"]!=c["_events"]):
        raise RuntimeError("identical cut trajectories diverged")
    delta={k:c["official"][k]-b["official"][k] for k in METRICS}
    if delta["official_net"]!=sum(delta[k] for k in (
            "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("official full-game components do not reconcile")
    for arm in ARMS:
        del arms[arm]["_trace"]
        del arms[arm]["_events"]
    return {
        "seed":seed,"rotation":rotation,"challenge_seat":seat,
        "arms":arms,"official_deltas":delta,
        "actual_interventions":changes,"identical_if_untouched":changes==0,
    }


def cohort(start:int,seeds:int)->dict[str,Any]:
    if (type(start) is not int or type(seeds) is not int or
            not 0<=start<2**32 or not 1<=seeds<=8 or
            start+seeds>2**32):
        raise ValueError("invalid independent initial shuffle cohort")
    positions=[paired_position(s,r) for s in range(start,start+seeds)
               for r in range(4)]
    total=Counter()
    by_arm={a:Counter() for a in ARMS}
    per_seed=[]
    for seed in range(start,start+seeds):
        rows=[p for p in positions if p["seed"]==seed]
        if sorted(p["challenge_seat"] for p in rows)!=list(range(4)):
            raise RuntimeError("unbalanced seed across four seats")
        local=Counter()
        changes=0
        for p in rows:
            local.update(p["official_deltas"])
            total.update(p["official_deltas"])
            changes+=p["actual_interventions"]
            for arm in ARMS:
                by_arm[arm].update(p["arms"][arm]["counts"])
        per_seed.append({
            "seed":seed,"real_interventions":changes,
            "four_seat_mean_net_delta":round(local["official_net"]/4,4),
            "exhaustive_delta":local["exhaustive_points"],
            "win_delta":local["win_points"],
            "kong_delta":local["kong_points"],
        })
    changes=by_arm["late_wall_fan"]["actual_changes"]
    if changes!=sum(p["real_interventions"] for p in per_seed):
        raise RuntimeError("missing real changed cuts")
    if total["official_net"]!=sum(total[k] for k in (
            "win_points","kong_points","exhaustive_points")):
        raise RuntimeError("official cash delta did not balance")
    if changes==0 and any(total[k] for k in METRICS):
        raise RuntimeError("zero intervention generated a score difference")
    signs=[p["four_seat_mean_net_delta"] for p in per_seed]
    return {
        "independent_shuffles":seeds,"paired_seats":len(positions),
        "complete_official_games":2*len(positions),
        "frozen_wall_count_cutoff":LATE_WALL_TILES,
        "frozen_min_max_fan_gain":MIN_MAX_FAN_GAIN,
        "frozen_copies_retention":MIN_EFFECTIVE_COPIES_RETENTION,
        "frozen_wait_types_retention":MIN_WAIT_TYPES_RETENTION,
        "frozen_fan_weighted_retention":MIN_FAN_WEIGHTED_RETENTION,
        "frozen_max_public_risk_increase":MAX_PUBLIC_THREAT_INCREASE,
        "baseline_cuts":by_arm["baseline"]["total_cuts"],
        "baseline_late_cuts":by_arm["baseline"]["late_wall_cuts"],
        "baseline_tenpai_cuts":by_arm["baseline"]["baseline_min_shanten_tenpai"],
        "actual_interventions":changes,
        "seed_clusters_with_interventions":sum(
            p["real_interventions"]>0 for p in per_seed),
        "positive_seed_clusters":sum(v>0 for v in signs),
        "negative_seed_clusters":sum(v<0 for v in signs),
        "neutral_seed_clusters":sum(v==0 for v in signs),
        "mean_four_seat_net_delta":round(mean(signs),4),
        "official_component_deltas":{k:total[k] for k in METRICS},
        "counts_by_arm":{a:dict(by_arm[a]) for a in ARMS},
        "per_seed":per_seed,"positions":positions,
        "online_ai_changed":False,"calibrated_local_action_ev":None,
        "ron_probability":None,"confidence_interval":None,
    }


def study(*,development:int=54000,holdout:int=55000,
          seeds:int=4)->dict[str,Any]:
    if (type(development) is not int or type(holdout) is not int or
            type(seeds) is not int or not 1<=seeds<=8 or
            not 0<=development<2**32 or not 0<=holdout<2**32 or
            max(development,holdout)+seeds>2**32 or
            (development<holdout+seeds and holdout<development+seeds)):
        raise ValueError("development/holdout cannot overlap")
    return {
        "protocol":PROTOCOL,"online_policy_modified":False,
        "candidate_only_offline":True,
        "development_seed_range":[development,development+seeds],
        "holdout_seed_range":[holdout,holdout+seeds],
        "development":cohort(development,seeds),
        "holdout":cohort(holdout,seeds),
        "limitations":[
            "Late wall size is public now but is not a guarantee the game will exhaust.",
            "Official hypothetical max fan is not a per-cut EV or likelihood of wall exhaustion.",
            "Candidate may never trigger in few seeds; absence of policy changes proves no gain.",
            "Paired full games can diverge after a changed cut, so official score is path-wide.",
            "Four seat positions of one initial shuffle are correlated.",
            "No other player's hidden hands, waits, full wall or future outcomes guide cuts.",
            "Frozen parameters are not tuned on development nor holdout outcomes.",
            "Research code has no path to live challenge AI.",
        ],
    }
