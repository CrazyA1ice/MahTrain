"""M4.43: precommitted safe-tie variants, nine REAL games per new shuffle.

Challenge stays unchanged. Only legal own-view, already-scored minimum-shanten
alternatives having EXACTLY the same effective tile-copy count are eligible.
Two policy arms: risk-first within 5% expected-fan floor, fan-first subject to
small bounded extra public risk. These are descriptive controlled whole-game
comparisons, NOT off-policy/individual-action causal estimates.
"""
from __future__ import annotations

from collections import defaultdict
from math import isfinite
from pathlib import Path
from statistics import mean
from typing import Any

from .ai import MahjongAgent
from .ai_selfplay_counterfactual import KONG_BASE, MAX_ACTIONS, _agents, _ledger, _opening
from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_tournament import _take_action
from .four_player import FourPlayerOpening
from .ai_shadow_action_diagnostics import (
    MANIFEST as M439_MANIFEST, PROTOCOL as M439_PROTOCOL, _verify_prior_m437,
)
from .ai_shadow_guarded_trial import (
    PLAN as M441_PLAN, PROTOCOL as M441_PROTOCOL,
)
from .ai_challenge_tie_opportunities import (
    PLAN as M442_PLAN, PROTOCOL as M442_PROTOCOL,
)
from .ai_shadow_headtohead import (
    MAX_EVAL_SEEDS, _paired_digest, _write_atomic, load_frozen_local_model,
)

PROTOCOL="m443_independent_shuffle_safe_tie_risk_fan_policy_v1"
SHARD_PROTOCOL="m443_paid_nine_game_safe_tie_shard_v1"
PLAN="PRIVATE_safe_tie_policy_plan.json"
SHARDS="PRIVATE_safe_tie_policy_seed_clusters"
SUMMARY="safe_tie_risk_fan_trial.json"
POLICIES=("risk_first","fan_first")
COMPONENTS=("win","kong","exhaustive")
# Fixed before new games: do not change using their actual payout results.
RISK_MIN_DROP=0.03
FAN_ALLOW_FRACTION=0.95
FAN_MIN_GAIN_RATIO=1.02
FAN_MAX_RISK_INCREASE=0.05


def _ranked_peer_cuts(ranked:list[dict[str,Any]],base:dict[str,Any])->list[dict[str,Any]]:
    keys=("shanten","effective_tile_count",
          "expected_fan_weighted_copies","table_threat_index")
    for r in ranked:
        if (not isinstance(r,dict) or any(k not in r for k in keys) or
                any(type(r[k]) not in (int,float) or not isfinite(r[k]) for k in keys) or
                r["effective_tile_count"]<0 or
                not 0<=r["table_threat_index"]<=1):
            raise ValueError("invalid acting-agent public legal cut ranking")
    return [
        r for r in ranked
        if r["discard"]!=base["discard"] and
           r["shanten"]==base["shanten"] and
           r["effective_tile_count"]==base["effective_tile_count"]
    ]


class SafeTiePolicyAgent(MahjongAgent):
    """Only discard differs; opening, claims, kong and RNG match Challenge."""

    def __init__(self,mode:str,*,seed:int,seat:int):
        if mode not in POLICIES:
            raise ValueError("unknown precommitted research tie policy")
        super().__init__("challenge",seed=seed,seat=seat)
        self.mode=mode
        self._offline_reference_cut=True  # skip Challenge-specific tie probe
        self.discard_opportunities=0
        self.safe_tie_opportunities=0
        self.applied_overrides=0
        self.blocked_by_preregistered_criteria=0

    def discard(self,view)->str:
        original=super().discard(view)
        self.discard_opportunities+=1
        ranked=getattr(self,"_last_discard_scores",None)
        if ranked is None:
            return original
        if len(ranked)<2 or len({r["discard"] for r in ranked})!=len(ranked):
            raise RuntimeError("expected unique eligible Challenge cuts")
        base=next((r for r in ranked if r["discard"]==original),None)
        if base is None:
            raise RuntimeError("Challenge discard not present in own legal ranking")
        peers=_ranked_peer_cuts(ranked,base)
        if not peers:
            return original
        self.safe_tie_opportunities+=1
        fan0=base["expected_fan_weighted_copies"]
        risk0=base["table_threat_index"]
        if self.mode=="risk_first":
            eligible=[
                r for r in peers
                if (r["table_threat_index"]<=risk0-RISK_MIN_DROP and
                    r["expected_fan_weighted_copies"]>=
                      FAN_ALLOW_FRACTION*fan0)
            ]
            eligible.sort(key=lambda r:(
                r["table_threat_index"],-r["expected_fan_weighted_copies"],
                r["discard"],
            ))
        else:
            eligible=[
                r for r in peers
                if (r["expected_fan_weighted_copies"]>
                      FAN_MIN_GAIN_RATIO*fan0 and
                    r["table_threat_index"]<=risk0+FAN_MAX_RISK_INCREASE)
            ]
            eligible.sort(key=lambda r:(
                -r["expected_fan_weighted_copies"],
                r["table_threat_index"],r["discard"],
            ))
        if not eligible:
            self.blocked_by_preregistered_criteria+=1
            return original
        chosen=eligible[0]
        if (chosen["shanten"]!=base["shanten"] or
                chosen["effective_tile_count"]!=base["effective_tile_count"]):
            raise RuntimeError("no-retreat safe-tie invariant violated")
        self.applied_overrides+=1
        return chosen["discard"]


def _finish_real_game(seed:int,seat:int|None,mode:str|None)->dict[str,Any]:
    game=FourPlayerOpening(seed,kong_base=KONG_BASE,legacy_bugang_cash=False)
    agents=_agents(seed)
    actor=None
    if seat is not None:
        if mode not in POLICIES or seat not in range(4):
            raise ValueError("experimental policy must occupy one real seat")
        actor=SafeTiePolicyAgent(mode,seed=seed,seat=seat)
        agents[seat]=actor
    elif mode is not None:
        raise ValueError("baseline must remain all-Challenge")
    frames=[]
    _opening(game,agents,frames)
    trace=[]
    timings=defaultdict(list)
    for _ in range(MAX_ACTIONS):
        if game.phase in ("finished","wall_exhausted"):
            break
        _take_action(game,agents,trace,timings)
        if len(trace)>4:
            trace.clear()
    else:
        raise RuntimeError("fresh safe-tie full real game exceeded action limit")
    ledgers=[_ledger(game,s) for s in range(4)]
    keys=("official_net","win_points","kong_points","exhaustive_points")
    if any(sum(item[key] for item in ledgers)!=0 for key in keys):
        raise RuntimeError("nonzero authoritative four-seat score ledger")
    return {
        "phase":game.phase,
        "official_net_by_seat":[r["official_net"] for r in ledgers],
        "win_points_by_seat":[r["win_points"] for r in ledgers],
        "kong_points_by_seat":[r["kong_points"] for r in ledgers],
        "exhaustive_points_by_seat":[r["exhaustive_points"] for r in ledgers],
        "discard_opportunities":actor.discard_opportunities if actor else 0,
        "safe_tie_opportunities":actor.safe_tie_opportunities if actor else 0,
        "accepted_overrides":actor.applied_overrides if actor else 0,
        "blocked_by_criteria":actor.blocked_by_preregistered_criteria if actor else 0,
    }


def _one_seed(seed:int)->dict[str,Any]:
    baseline=_finish_real_game(seed,None,None)
    if baseline["phase"] not in ("finished","wall_exhausted"):
        raise RuntimeError("Challenge baseline did not settle")
    rotated=[]
    for seat in range(4):
        samples={}
        for mode in POLICIES:
            one=_finish_real_game(seed,seat,mode)
            delta=one["official_net_by_seat"][seat]-baseline["official_net_by_seat"][seat]
            samples[mode]={
                "phase":one["phase"],
                "official_net_delta":delta,
                "baseline_official_net":baseline["official_net_by_seat"][seat],
                "candidate_official_net":one["official_net_by_seat"][seat],
                "real_paid_component_delta":{
                    component:
                       one[component+"_points_by_seat"][seat]-
                       baseline[component+"_points_by_seat"][seat]
                    for component in COMPONENTS
                },
                "discard_opportunities":one["discard_opportunities"],
                "safe_tie_opportunities":one["safe_tie_opportunities"],
                "accepted_overrides":one["accepted_overrides"],
                "blocked_by_criteria":one["blocked_by_criteria"],
            }
        rotated.append({"seat":seat,"policies":samples})
    return {
        "private_original_shuffle_seed":seed,
        "real_completed_games":9,
        "official_baseline_by_seat":baseline["official_net_by_seat"],
        "seat_rotation_results":rotated,
        "common_natural_shuffle_not_nine_independent_seeds":True,
        "online_challenge_unchanged":True,
    }


def _audit_case(case:dict[str,Any],seed:int)->None:
    if (type(case) is not dict or
            type(case.get("private_original_shuffle_seed")) is not int or
            case["private_original_shuffle_seed"]!=seed or
            case.get("real_completed_games")!=9 or
            case.get("common_natural_shuffle_not_nine_independent_seeds") is not True or
            case.get("online_challenge_unchanged") is not True):
        raise ValueError("not a genuine complete nine-match independent shuffle")
    baseline=case.get("official_baseline_by_seat")
    seats=case.get("seat_rotation_results")
    if (type(baseline) is not list or len(baseline)!=4 or
            any(type(v) is not int for v in baseline) or sum(baseline)!=0 or
            type(seats) is not list or len(seats)!=4):
        raise ValueError("invalid common baseline four-seat official payout")
    for seat,row in enumerate(seats):
        if (type(row) is not dict or type(row.get("seat")) is not int or
                row["seat"]!=seat or type(row.get("policies")) is not dict or
                set(row["policies"])!=set(POLICIES)):
            raise ValueError("missing or duplicate policy seat rotations")
        for mode in POLICIES:
            e=row["policies"][mode]
            if (type(e) is not dict or e.get("phase") not in ("finished","wall_exhausted") or
                    any(type(e.get(k)) is not int for k in (
                        "official_net_delta","baseline_official_net","candidate_official_net",
                        "discard_opportunities","safe_tie_opportunities","accepted_overrides",
                        "blocked_by_criteria",
                    ))):
                raise ValueError("missing complete real game or actor counters")
            if (not 0<=e["accepted_overrides"]<=e["safe_tie_opportunities"]<=e["discard_opportunities"] or
                    not 0<=e["blocked_by_criteria"]<=e["safe_tie_opportunities"] or
                    e["accepted_overrides"]+e["blocked_by_criteria"]!=
                      e["safe_tie_opportunities"] or
                    e["baseline_official_net"]!=baseline[seat] or
                    e["candidate_official_net"]-baseline[seat]!=
                      e["official_net_delta"] or
                    type(e.get("real_paid_component_delta")) is not dict or
                    set(e["real_paid_component_delta"])!=set(COMPONENTS) or
                    any(type(v) is not int for v in e["real_paid_component_delta"].values()) or
                    sum(e["real_paid_component_delta"].values())!=e["official_net_delta"]):
                raise ValueError("unsafe or unreconciled safe-tie game outcome")
            if e["accepted_overrides"]==0 and e["official_net_delta"]!=0:
                raise ValueError("unchanged baseline discard cannot alter official score")


def _shard(root:Path,i:int)->Path:
    return root/SHARDS/f"index-{i:08d}.json"


def _saved(root:Path,start:int,n:int,digest:str)->dict[int,dict[str,Any]]:
    folder=root/SHARDS
    if not folder.exists():
        return {}
    if not folder.is_dir():
        raise ValueError("saved seed folder is not a directory")
    cases={}
    for f in folder.iterdir():
        if f.is_file() and ".tmp-" in f.name:
            continue
        if (not f.is_file() or not f.name.startswith("index-") or
                not f.name.endswith(".json") or len(f.name)!=19 or
                not f.name[6:14].isdigit()):
            raise ValueError("unexpected M4.43 private seed shard")
        index=int(f.name[6:14])
        if index>=n or index in cases:
            raise ValueError("unexpected or duplicate old M4.43 seed shard")
        envelope=_get_json(f)
        if (type(envelope) is not dict or
                set(envelope)!={"protocol","model_sha256","index","sha256_case","private_case"} or
                envelope["protocol"]!=SHARD_PROTOCOL or
                envelope["model_sha256"]!=digest or
                type(envelope["index"]) is not int or envelope["index"]!=index or
                type(envelope["private_case"]) is not dict):
            raise ValueError("invalid immutable M4.43 original seed checkpoint")
        case=envelope["private_case"]
        _audit_case(case,start+index)
        if envelope["sha256_case"]!=_paired_digest(case):
            raise ValueError("tampered original-seed private checkpoint checksum")
        cases[index]=case
    return cases


def _summary(cases:list[dict[str,Any]],trained:int)->dict[str,Any]:
    result={}
    for mode in POLICIES:
        delta_by_cluster=[]
        per_seat=[[] for _ in range(4)]
        components={c:[] for c in COMPONENTS}
        totals={
            "candidate_discard_opportunities":0,
            "eligible_same_shanten_same_ukeire_decisions":0,
            "actual_safe_tie_overrides":0,
            "eligible_tie_decisions_rejected_by_extra_constraints":0,
            "rotations_without_override":0,
        }
        for case in cases:
            rows=case["seat_rotation_results"]
            group=[]
            pieces={k:[] for k in COMPONENTS}
            for s,row in enumerate(rows):
                e=row["policies"][mode]
                group.append(e["official_net_delta"])
                per_seat[s].append(e["official_net_delta"])
                for component in COMPONENTS:
                    pieces[component].append(e["real_paid_component_delta"][component])
                totals["candidate_discard_opportunities"]+=e["discard_opportunities"]
                totals["eligible_same_shanten_same_ukeire_decisions"]+=e["safe_tie_opportunities"]
                totals["actual_safe_tie_overrides"]+=e["accepted_overrides"]
                totals["eligible_tie_decisions_rejected_by_extra_constraints"]+=e[
                    "blocked_by_criteria"]
                totals["rotations_without_override"]+=int(e["accepted_overrides"]==0)
            delta_by_cluster.append(mean(group))
            for component in COMPONENTS:
                components[component].append(mean(pieces[component]))
        mean_delta=round(mean(delta_by_cluster),5)
        component_means={k:round(mean(v),5) for k,v in components.items()}
        if abs(mean_delta-sum(component_means.values()))>0.00002:
            raise RuntimeError("safe-tie official paid component decomposition failed")
        result[mode]={
            **totals,
            "mean_paired_official_net_delta_points":mean_delta,
            "mean_official_component_deltas":component_means,
            "per_seat_mean_official_net_delta_points":[
                round(mean(vals),5) for vals in per_seat
            ],
            "independent_shuffles_positive":sum(x>0 for x in delta_by_cluster),
            "independent_shuffles_negative":sum(x<0 for x in delta_by_cluster),
            "independent_shuffles_equal":sum(x==0 for x in delta_by_cluster),
        }
    return {
        "protocol":PROTOCOL,
        "independent_original_shuffle_seed_clusters":len(cases),
        "true_complete_official_games":9*len(cases),
        "true_original_challenge_baseline_games":len(cases),
        "true_risk_first_four_seat_rotations":4*len(cases),
        "true_fan_first_four_seat_rotations":4*len(cases),
        "source_original_training_clusters":trained,
        "fixed_pretest_experiment_controls":{
            "min_public_risk_index_drop_for_risk_first":RISK_MIN_DROP,
            "min_retained_expected_fan_fraction_for_risk_first":FAN_ALLOW_FRACTION,
            "min_expected_fan_gain_ratio_for_fan_first":FAN_MIN_GAIN_RATIO,
            "max_public_risk_index_increase_for_fan_first":FAN_MAX_RISK_INCREASE,
        },
        "risk_first":result["risk_first"],
        "fan_first":result["fan_first"],
        "same_original_shuffle_not_independent_rotations":True,
        "same_minimum_shanten_and_equal_ukeire_enforced_at_every_override":True,
        "only_actor_view_challenge_original_ranking":True,
        "frozen_old_model_weights_not_used_for_new_policy":True,
        "no_fit_or_tuning_on_prior_test_outcomes":True,
        "no_live_challenge_ai_changes":True,
        "no_specific_private_tiles_or_real_shuffle_ids_in_safe_summary":True,
        "single_cut_not_a_causal_terminal_outcome":True,
        "no_population_strength_or_significance_claim":True,
        "too_few_independent_shuffles_for_inference":len(cases)<20,
    }


def run_safe_tie_trial(
    *,training_dir:Path,prior_m437_dir:Path,prior_m439_dir:Path,
    prior_m441_dir:Path,prior_m442_dir:Path,seed_start:int,seeds:int,
    out_dir:Path,resume:bool=False,
)->dict[str,Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
            type(resume) is not bool or
            not 0<=seed_start<2**32 or not 1<=seeds<=MAX_EVAL_SEEDS or
            seed_start+seeds>2**32):
        raise ValueError("invalid new independent shuffle research plan")
    training=_private_location(Path(training_dir))
    old437=_private_location(Path(prior_m437_dir))
    old439=_private_location(Path(prior_m439_dir))
    old441=_private_location(Path(prior_m441_dir))
    old442=_private_location(Path(prior_m442_dir))
    out=_private_location(Path(out_dir))
    sources=(training,old437,old439,old441,old442)
    if len(set((*sources,out)))!=6 or any(
        source in out.parents or out in source.parents for source in sources
    ):
        raise ValueError("M4.43 output must be separate from private evidence sources")
    _,provenance=load_frozen_local_model(training)
    tstart=provenance["source_m434_train_seed_start"]
    tend=provenance["source_m434_seed_end_exclusive"]
    if not (seed_start+seeds<=tstart or seed_start>=tend):
        raise ValueError("new seed overlaps original train and holdout")
    digest=provenance["model_sha256"]
    _verify_prior_m437(old437,training,digest,seed_start,seeds)
    previous439=_get_json(old439/M439_MANIFEST)
    if (previous439.get("protocol")!=M439_PROTOCOL or
            previous439.get("private_source_training_directory")!=str(training) or
            previous439.get("private_source_m437_directory")!=str(old437) or
            previous439.get("private_frozen_model_sha256")!=digest or
            previous439.get("online_policy_changed") is not False):
        raise ValueError("prior M4.39 source provenance mismatch")
    previous441=_get_json(old441/M441_PLAN)
    if (previous441.get("protocol")!=M441_PROTOCOL or
            previous441.get("private_training_dir")!=str(training) or
            previous441.get("private_prior_m437_dir")!=str(old437) or
            previous441.get("private_prior_m439_dir")!=str(old439) or
            previous441.get("frozen_model_sha256")!=digest or
            previous441.get("live_online_promotion") is not False):
        raise ValueError("prior M4.41 source provenance mismatch")
    previous442=_get_json(old442/M442_PLAN)
    if (previous442.get("protocol")!=M442_PROTOCOL or
            previous442.get("private_train_dir")!=str(training) or
            previous442.get("private_prior_m437_dir")!=str(old437) or
            previous442.get("private_prior_m439_dir")!=str(old439) or
            previous442.get("private_prior_m441_dir")!=str(old441) or
            previous442.get("model_sha256")!=digest or
            previous442.get("challenge_behavior_unchanged") is not True):
        raise ValueError("prior M4.42 source provenance mismatch")
    for previous,label,start_key,size_key in (
        (previous439,"M4.39","private_eval_seed_start","private_eval_seed_count"),
        (previous441,"M4.41","private_seed_start","original_shuffle_clusters"),
        (previous442,"M4.42","private_original_seed_start","independent_seed_clusters"),
    ):
        a=previous.get(start_key)
        n=previous.get(size_key)
        if (type(a) is not int or type(n) is not int or
                not 0<=a<2**32 or not 1<=n<=MAX_EVAL_SEEDS or a+n>2**32):
            raise ValueError("corrupt older private seed plan: "+label)
        if not (seed_start+seeds<=a or seed_start>=a+n):
            raise ValueError("new original shuffles overlap prior "+label)
    plan={
        "protocol":PROTOCOL,
        "model_sha256_provenance_only":digest,
        "private_training_dir":str(training),
        "private_prior_m437_dir":str(old437),
        "private_prior_m439_dir":str(old439),
        "private_prior_m441_dir":str(old441),
        "private_prior_m442_dir":str(old442),
        "private_new_shuffle_start":seed_start,
        "private_independent_shuffle_count":seeds,
        "precommitted_immutable_risk_min_drop":RISK_MIN_DROP,
        "precommitted_immutable_fan_floor":FAN_ALLOW_FRACTION,
        "precommitted_immutable_fan_gain":FAN_MIN_GAIN_RATIO,
        "precommitted_immutable_fan_risk_allowance":FAN_MAX_RISK_INCREASE,
        "live_policy_untouched":True,
    }
    if resume:
        if not out.is_dir() or not (out/PLAN).is_file():
            raise ValueError("resume requires a previously frozen M4.43 plan")
        if _get_json(out/PLAN)!=plan:
            raise ValueError("resume model, old source directories or precommitted plan changed")
        if any(p.name not in (PLAN,SHARDS,SUMMARY) and ".tmp-" not in p.name
               for p in out.iterdir()):
            raise ValueError("unexpected entries in private evaluation output")
        cached=_saved(out,seed_start,seeds,digest)
        if (out/SUMMARY).is_file() and len(cached)!=seeds:
            raise ValueError("finished safe report missing original shuffle shards")
    else:
        if out.exists() and any(out.iterdir()):
            raise ValueError("M4.43 requires a new empty results directory")
        out.mkdir(parents=True,exist_ok=True)
        _write_atomic(out/PLAN,plan)
        cached={}
    (out/SHARDS).mkdir(exist_ok=True)
    games=[]
    for index in range(seeds):
        one=cached.get(index)
        if one is None:
            one=_one_seed(seed_start+index)
            _audit_case(one,seed_start+index)
            _write_atomic(_shard(out,index),{
                "protocol":SHARD_PROTOCOL,
                "model_sha256":digest,
                "index":index,
                "sha256_case":_paired_digest(one),
                "private_case":one,
            })
        games.append(one)
    summary=_summary(games,provenance["trained_original_shuffle_clusters"])
    summary["resumed_completed_original_shuffle_clusters"]=len(cached)
    _write_atomic(out/SUMMARY,summary)
    return summary
