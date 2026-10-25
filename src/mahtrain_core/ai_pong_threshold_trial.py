"""M4.45: preregistered off-line peng/pass threshold pilot on NEW original seeds.

Only acting player's authorized private_view and original Challenge methods.
No change to live Challenge. One true all-Challenge baseline plus four rotated
candidate games per natural shuffle, five fully settled games per seed.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from .ai import (
    MahjongAgent, _call_outlook, _call_settings, _cut_shanten,
    _own_view,
)
from .ai_selfplay_counterfactual import KONG_BASE, MAX_ACTIONS, _agents, _ledger, _opening
from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_tournament import _take_action
from .four_player import FourPlayerOpening
from .rules import TILE_INDEX
from .ai_shadow_headtohead import (
    MAX_EVAL_SEEDS, _paired_digest, _write_atomic, load_frozen_local_model,
    PROTOCOL as M437_PROTOCOL, SHARD_PROTOCOL as M437_SHARD_PROTOCOL,
)
from .ai_shadow_action_diagnostics import (
    PROTOCOL as M439_PROTOCOL, MANIFEST as M439_PLAN,
)
from .ai_shadow_guarded_trial import (
    PROTOCOL as M441_PROTOCOL, PLAN as M441_PLAN,
)
from .ai_challenge_tie_opportunities import (
    PROTOCOL as M442_PROTOCOL, PLAN as M442_PLAN,
)
from .ai_safe_tie_policy_trial import (
    PROTOCOL as M443_PROTOCOL, PLAN as M443_PLAN,
)
from .ai_challenge_call_frontier import (
    PROTOCOL as M444_PROTOCOL, MANIFEST as M444_PLAN,
)

PROTOCOL="m445_new_shuffle_equal_shanten_plus1or2_peng_pilot_v1"
SHARD_PROTOCOL="m445_five_real_paid_games_original_shuffle_v1"
PLAN="PRIVATE_pong_threshold_plan.json"
SHARDS="PRIVATE_pong_trial_seed_clusters"
SUMMARY="safe_pong_threshold_trial.json"
COMPONENTS=("win","kong","exhaustive")
METRICS=(
    "response_windows",
    "legal_peng_windows",
    "baseline_challenge_pass_with_peng",
    "pass_with_ming_gang_offered_excluded",
    "pass_with_tian_ting_excluded",
    "pass_in_tenpai_or_regressing_shanten_excluded",
    "pass_with_no_one_or_two_extra_effective_copies",
    "eligible_equal_shanten_plus1or2_peng",
    "actual_peng_overrides",
)
# Locked BEFORE any new terminal results: Challenge normally demands at
# least +3 effective physical copies for equal-stage peng. Test +1/+2 only,
# never allowing lower shanten progress, fewer copies, lost Tian Ting or hu.
LOWER_EXTRA_COPIES=1
UPPER_EXTRA_COPIES=2


class FrozenPengThresholdAgent(MahjongAgent):
    """Challenge unchanged except precisely one conservative pass->peng arm."""

    def __init__(self,*,seed:int,seat:int):
        super().__init__("challenge",seed=seed,seat=seat)
        self._offline_reference_cut=True
        self.counts={key:0 for key in METRICS}

    def response(self,view,*,rob:bool=False)->str:
        action=super().response(view,rob=rob)
        c=self.counts
        c["response_windows"]+=1
        if rob or "peng" not in view["claim_options"]:
            return action
        c["legal_peng_windows"]+=1
        if action!="pass":
            return action
        c["baseline_challenge_pass_with_peng"]+=1
        if "ming_gang" in view["claim_options"]:
            c["pass_with_ming_gang_offered_excluded"]+=1
            return action
        if (view.get("tian_ting") or {}).get("eligible") is True:
            c["pass_with_tian_ting_excluded"]+=1
            return action

        hand,melds,missing=_own_view(view)
        visible,cap,tian=_call_settings(view)
        target=view["pending_discard"]["tile"]
        baseline=_call_outlook(hand,melds,missing,visible,cap,tian)
        leftover=list(hand)
        for _ in range(2):
            leftover.remove(target)
        groups=[*melds,{"type":"peng","tile":target}]
        forced=sorted(set(leftover),key=TILE_INDEX.__getitem__)
        missing_cuts=[cut for cut in forced if cut[0]==missing]
        if missing_cuts:
            forced=missing_cuts
        ranked=[(cut,_cut_shanten(leftover,groups,missing,cut))
                for cut in forced]
        best=min(stage for _,stage in ranked)
        if best!=baseline["shanten"] or best<=0:
            c["pass_in_tenpai_or_regressing_shanten_excluded"]+=1
            return action

        exposed=list(visible)
        exposed.remove(target)  # real claimed river tile now belongs to peng
        qualifies=False
        for cut,stage in ranked:
            if stage!=best:
                continue
            after=list(leftover)
            after.remove(cut)
            outlook=_call_outlook(
                after,groups,missing,[*exposed,cut],cap,tian
            )
            margin=outlook["ukeire"]-baseline["ukeire"]
            if LOWER_EXTRA_COPIES<=margin<=UPPER_EXTRA_COPIES:
                qualifies=True
                break
        if not qualifies:
            c["pass_with_no_one_or_two_extra_effective_copies"]+=1
            return action
        if "peng" not in view["claim_options"]:
            raise RuntimeError("new experimental peng was not legally available")
        c["eligible_equal_shanten_plus1or2_peng"]+=1
        c["actual_peng_overrides"]+=1
        return "peng"


def _one_game(seed:int,seat:int|None)->dict[str,Any]:
    game=FourPlayerOpening(seed,kong_base=KONG_BASE,legacy_bugang_cash=False)
    agents=_agents(seed)
    candidate=None
    if seat is not None:
        if type(seat) is not int or seat not in range(4):
            raise ValueError("invalid research seat")
        candidate=FrozenPengThresholdAgent(seed=seed,seat=seat)
        agents[seat]=candidate
    _opening(game,agents,[])
    trace=[]
    durations=defaultdict(list)
    for _ in range(MAX_ACTIONS):
        if game.phase in ("finished","wall_exhausted"):
            break
        _take_action(game,agents,trace,durations)
        if len(trace)>4:
            trace.clear()
    else:
        raise RuntimeError("incomplete full paid Mahjong game")
    ledger=[_ledger(game,s) for s in range(4)]
    for field in ("official_net","win_points","kong_points","exhaustive_points"):
        if sum(row[field] for row in ledger)!=0:
            raise RuntimeError("official paid score ledger not zero-sum")
    return {
        "phase":game.phase,
        "official_net_by_seat":[row["official_net"] for row in ledger],
        "win_points_by_seat":[row["win_points"] for row in ledger],
        "kong_points_by_seat":[row["kong_points"] for row in ledger],
        "exhaustive_points_by_seat":[row["exhaustive_points"] for row in ledger],
        "actor_counts":dict(candidate.counts) if candidate else None,
    }


def _one_cluster(seed:int)->dict[str,Any]:
    baseline=_one_game(seed,None)
    if baseline["phase"] not in ("finished","wall_exhausted"):
        raise RuntimeError("baseline not finished")
    rows=[]
    for seat in range(4):
        candidate=_one_game(seed,seat)
        components={
            kind:
                candidate[kind+"_points_by_seat"][seat]-
                baseline[kind+"_points_by_seat"][seat]
            for kind in COMPONENTS
        }
        delta=(candidate["official_net_by_seat"][seat]-
               baseline["official_net_by_seat"][seat])
        if sum(components.values())!=delta:
            raise RuntimeError("unreconciled full terminal paid score")
        rows.append({
            "seat":seat,
            "candidate_terminal_phase":candidate["phase"],
            "challenge_baseline_net":baseline["official_net_by_seat"][seat],
            "experimental_pong_net":candidate["official_net_by_seat"][seat],
            "paired_net_delta":delta,
            "real_component_delta":components,
            "actor_counts":candidate["actor_counts"],
        })
    case={
        "private_original_shuffle_seed":seed,
        "real_complete_official_games":5,
        "challenge_baseline_net_by_seat":baseline["official_net_by_seat"],
        "seat_rotation_results":rows,
        "same_shuffle_rotations_are_correlated":True,
        "challenge_live_policy_unchanged":True,
    }
    _verify_case(case,seed)
    return case


def _verify_case(case:dict[str,Any],seed:int)->None:
    if (type(case) is not dict or type(case.get("private_original_shuffle_seed")) is not int or
            case["private_original_shuffle_seed"]!=seed or
            case.get("real_complete_official_games")!=5 or
            case.get("same_shuffle_rotations_are_correlated") is not True or
            case.get("challenge_live_policy_unchanged") is not True):
        raise ValueError("incomplete or invalid five-real-game original shuffle")
    baseline=case.get("challenge_baseline_net_by_seat")
    rows=case.get("seat_rotation_results")
    if (type(baseline) is not list or len(baseline)!=4 or
            any(type(x) is not int for x in baseline) or sum(baseline)!=0 or
            type(rows) is not list or len(rows)!=4):
        raise ValueError("invalid original four-seat official baseline")
    for s,r in enumerate(rows):
        if (type(r) is not dict or type(r.get("seat")) is not int or
                r["seat"]!=s or r.get("candidate_terminal_phase") not in
                ("finished","wall_exhausted") or
                any(type(r.get(k)) is not int for k in (
                    "challenge_baseline_net","experimental_pong_net",
                    "paired_net_delta")) or
                r["challenge_baseline_net"]!=baseline[s] or
                r["experimental_pong_net"]-baseline[s]!=r["paired_net_delta"] or
                type(r.get("real_component_delta")) is not dict or
                set(r["real_component_delta"])!=set(COMPONENTS) or
                any(type(x) is not int for x in r["real_component_delta"].values()) or
                sum(r["real_component_delta"].values())!=r["paired_net_delta"]):
            raise ValueError("inconsistent authoritative candidate score payments")
        counts=r.get("actor_counts")
        if (type(counts) is not dict or set(counts)!=set(METRICS) or
                any(type(x) is not int or x<0 for x in counts.values())):
            raise ValueError("private response histogram invalid")
        passes=counts["baseline_challenge_pass_with_peng"]
        removed=(counts["pass_with_ming_gang_offered_excluded"]+
            counts["pass_with_tian_ting_excluded"]+
            counts["pass_in_tenpai_or_regressing_shanten_excluded"]+
            counts["pass_with_no_one_or_two_extra_effective_copies"]+
            counts["eligible_equal_shanten_plus1or2_peng"])
        if (removed!=passes or
                counts["actual_peng_overrides"]!=
                counts["eligible_equal_shanten_plus1or2_peng"] or
                passes>counts["legal_peng_windows"] or
                counts["legal_peng_windows"]>counts["response_windows"]):
            raise ValueError("invalid rejected/accepted legal peng action accounting")
        if counts["actual_peng_overrides"]==0 and r["paired_net_delta"]!=0:
            raise ValueError("unchanged Challenge must have unchanged paid score")


def _path(out:Path,i:int)->Path:
    return out/SHARDS/f"index-{i:08d}.json"


def _load_saved(out:Path,start:int,n:int,digest:str)->dict[int,dict[str,Any]]:
    directory=out/SHARDS
    if not directory.exists():
        return {}
    if not directory.is_dir():
        raise ValueError("invalid private shard directory")
    saved={}
    for f in directory.iterdir():
        if f.is_file() and ".tmp-" in f.name:
            continue
        if (not f.is_file() or len(f.name)!=19 or
                not f.name.startswith("index-") or
                not f.name.endswith(".json") or
                not f.name[6:14].isdigit()):
            raise ValueError("unexpected original-shuffle shard filename")
        i=int(f.name[6:14])
        if i>=n or i in saved:
            raise ValueError("shard index out of immutable plan range")
        env=_get_json(f)
        if (type(env) is not dict or
                set(env)!={"protocol","index","model_sha256","sha256_case","private_case"} or
                env["protocol"]!=SHARD_PROTOCOL or
                type(env["index"]) is not int or env["index"]!=i or
                env["model_sha256"]!=digest or
                type(env["private_case"]) is not dict):
            raise ValueError("private checkpoint envelope invalid")
        case=env["private_case"]
        _verify_case(case,start+i)
        if env["sha256_case"]!=_paired_digest(case):
            raise ValueError("private shard SHA-256 mismatch")
        saved[i]=case
    return saved


def _summary(cases:list[dict[str,Any]],train_n:int)->dict[str,Any]:
    totals={k:0 for k in METRICS}
    per_seed=[]
    components={k:[] for k in COMPONENTS}
    seats=[[] for _ in range(4)]
    positive=negative=zero=0
    for case in cases:
        margins=[]
        paid={k:[] for k in COMPONENTS}
        for row in case["seat_rotation_results"]:
            margins.append(row["paired_net_delta"])
            seats[row["seat"]].append(row["paired_net_delta"])
            for k in COMPONENTS:
                paid[k].append(row["real_component_delta"][k])
            for k,v in row["actor_counts"].items():
                totals[k]+=v
        per_seed.append(mean(margins))
        for k in COMPONENTS:
            components[k].append(mean(paid[k]))
    avg=round(mean(per_seed),5)
    mean_components={k:round(mean(v),5) for k,v in components.items()}
    if abs(avg-sum(mean_components.values()))>0.00002:
        raise RuntimeError("paid score breakdown mismatch")
    return {
        "protocol":PROTOCOL,
        "independent_original_shuffle_clusters":len(cases),
        "complete_authoritative_games":len(cases)*5,
        "challenge_baseline_games":len(cases),
        "candidate_four_seat_games":len(cases)*4,
        "training_original_shuffle_clusters":train_n,
        "precommitted_equal_shanten_peng_extra_ukeire_copy_range":[
            LOWER_EXTRA_COPIES,UPPER_EXTRA_COPIES],
        "actor_only_response_counts":totals,
        "mean_official_net_delta_points":avg,
        "mean_official_component_delta_points":mean_components,
        "per_seat_mean_official_net_delta_points":[
            round(mean(x),5) for x in seats],
        "clusters_positive":sum(x>0 for x in per_seed),
        "clusters_negative":sum(x<0 for x in per_seed),
        "clusters_equal":sum(x==0 for x in per_seed),
        "on_test_seeds_not_trained_or_threshold_tuned":True,
        "one_statistical_unit_per_original_shuffle_not_per_seat":True,
        "existing_challenge_claim_kong_hu_untouched":True,
        "experimental_override_only_legal_peng_after_challenge_pass":True,
        "no_regressing_shanten_or_tian_ting_override":True,
        "past_m437_m439_m441_m442_m443_m444_seed_intervals_excluded":True,
        "not_single_action_terminal_causal_attribution":True,
        "small_seed_pilot_not_evidence_of_strength":len(cases)<20,
        "no_hidden_hands_wall_or_specific_tiles_in_public_report":True,
    }


def run_pong_threshold_trial(
    *,training_dir:Path,prior_m444_dir:Path,
    seed_start:int,seeds:int,out_dir:Path,resume:bool=False,
)->dict[str,Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
            type(resume) is not bool or not 0<=seed_start<2**32 or
            not 1<=seeds<=MAX_EVAL_SEEDS or seed_start+seeds>2**32):
        raise ValueError("invalid new original shuffle trial plan")
    train=_private_location(Path(training_dir))
    previous=_private_location(Path(prior_m444_dir))
    output=_private_location(Path(out_dir))
    if (len({train,previous,output})!=3 or
            train in output.parents or previous in output.parents or
            output in train.parents or output in previous.parents):
        raise ValueError("output must not overlap private model/experiment sources")
    _,meta=load_frozen_local_model(train)
    digest=meta["model_sha256"]
    train_start=meta["source_m434_train_seed_start"]
    train_end=meta["source_m434_seed_end_exclusive"]
    if not (seed_start+seeds<=train_start or seed_start>=train_end):
        raise ValueError("M4.45 seed overlaps original training/holdout")
    old444=_get_json(previous/M444_PLAN)
    if (old444.get("protocol")!=M444_PROTOCOL or
            old444.get("private_model_source")!=str(train) or
            old444.get("model_sha256_provenance_only")!=digest or
            old444.get("challenge_unmodified") is not True or
            old444.get("no_candidate_policy_test") is not True):
        raise ValueError("M4.44 source plan/model mismatch")
    old442=_get_json(Path(old444["private_m442_source"])/M442_PLAN)
    old443=_get_json(Path(old444["private_m443_source"])/M443_PLAN)
    path437=Path(old442["private_prior_m437_dir"])
    path439=Path(old442["private_prior_m439_dir"])
    path441=Path(old442["private_prior_m441_dir"])
    old437=_get_json(path437/"PRIVATE_frozen_benchmark_plan.json")
    old439=_get_json(path439/M439_PLAN)
    old441=_get_json(path441/M441_PLAN)
    if (old442.get("protocol")!=M442_PROTOCOL or
            old442.get("private_train_dir")!=str(train) or
            old442.get("model_sha256")!=digest or
            old443.get("protocol")!=M443_PROTOCOL or
            old443.get("private_training_dir")!=str(train) or
            old443.get("private_prior_m442_dir")!=str(Path(old444["private_m442_source"])) or
            old443.get("model_sha256_provenance_only")!=digest or
            old437.get("protocol")!=M437_PROTOCOL or
            old437.get("resumable_shards_protocol")!=M437_SHARD_PROTOCOL or
            old437.get("private_source_training_directory")!=str(train) or
            old437.get("private_frozen_model_sha256")!=digest or
            old439.get("protocol")!=M439_PROTOCOL or
            old439.get("private_source_training_directory")!=str(train) or
            old439.get("private_frozen_model_sha256")!=digest or
            old441.get("protocol")!=M441_PROTOCOL or
            old441.get("private_training_dir")!=str(train) or
            old441.get("frozen_model_sha256")!=digest):
        raise ValueError("inconsistent historical frozen training/evaluation provenance")
    for p,start_key,count_key in (
        (old437,"private_evaluation_seed_start","private_eval_original_shuffle_count"),
        (old439,"private_eval_seed_start","private_eval_seed_count"),
        (old441,"private_seed_start","original_shuffle_clusters"),
        (old442,"private_original_seed_start","independent_seed_clusters"),
        (old443,"private_new_shuffle_start","private_independent_shuffle_count"),
        (old444,"private_original_shuffle_start","private_original_shuffle_count"),
    ):
        start=p.get(start_key);count=p.get(count_key)
        if (type(start) is not int or type(count) is not int or
                not 0<=start<2**32 or not 1<=count<=MAX_EVAL_SEEDS or
                start+count>2**32):
            raise ValueError("corrupt historical shuffle seed plan")
        if not (seed_start+seeds<=start or seed_start>=start+count):
            raise ValueError("new original shuffle overlaps prior evaluation")
    plan={
        "protocol":PROTOCOL,
        "private_model_source":str(train),
        "private_source_m444":str(previous),
        "model_sha256_provenance_only":digest,
        "private_original_shuffle_start":seed_start,
        "private_original_shuffle_count":seeds,
        "precommitted_ukeire_gain_min":LOWER_EXTRA_COPIES,
        "precommitted_ukeire_gain_max":UPPER_EXTRA_COPIES,
        "live_challenge_unchanged":True,
    }
    if resume:
        if not output.is_dir() or not (output/PLAN).is_file():
            raise ValueError("resume needs original precommitted M4.45 plan")
        if _get_json(output/PLAN)!=plan:
            raise ValueError("saved trial plan or model mismatch")
        if any(p.name not in (PLAN,SHARDS,SUMMARY) and ".tmp-" not in p.name
               for p in output.iterdir()):
            raise ValueError("unexpected private M4.45 output file")
        saved=_load_saved(output,seed_start,seeds,digest)
        if (output/SUMMARY).is_file() and len(saved)!=seeds:
            raise ValueError("summary not backed by all frozen shuffle shards")
    else:
        if output.exists() and any(output.iterdir()):
            raise ValueError("need new empty output folder for M4.45")
        output.mkdir(parents=True,exist_ok=True)
        _write_atomic(output/PLAN,plan)
        saved={}
    (output/SHARDS).mkdir(exist_ok=True)
    cases=[]
    for index in range(seeds):
        case=saved.get(index)
        if case is None:
            case=_one_cluster(seed_start+index)
            _verify_case(case,seed_start+index)
            _write_atomic(_path(output,index),{
                "protocol":SHARD_PROTOCOL,"index":index,
                "model_sha256":digest,
                "sha256_case":_paired_digest(case),
                "private_case":case,
            })
        cases.append(case)
    safe=_summary(cases,meta["trained_original_shuffle_clusters"])
    safe["reused_completed_original_shuffle_clusters"]=len(saved)
    _write_atomic(output/SUMMARY,safe)
    return safe
