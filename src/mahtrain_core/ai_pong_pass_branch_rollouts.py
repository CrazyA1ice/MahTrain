"""M4.47: authentic matched-state pass/peng branches, actor-only checkpoint.

At MOST the first naturally reached Challenge PASS with legally offered PENG
per original shuffle is studied. Two future-wall permutations, same checkpoint
and agent RNG state within each pass/peng pair. Counterfactual rollouts MAY
use the full local engine internally but never give hidden state to a policy,
train on the held-out outcomes, or export it. Not a population causal EV.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from copy import deepcopy
from pathlib import Path
from random import Random
from statistics import mean
from typing import Any

from .ai_selfplay_counterfactual import (
    KONG_BASE, MAX_ACTIONS, _agents, _ledger, _opening,
)
from .ai_tournament import _take_action
from .four_player import FourPlayerOpening
from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_shadow_headtohead import (
    MAX_EVAL_SEEDS, _paired_digest, _write_atomic, load_frozen_local_model,
)
from .ai_pong_threshold_trial import (
    _load_saved as _m445_saved, _summary as _m445_summary,
)
from .ai_pong_independent_expansion import (
    PROTOCOL as M446_PROTOCOL, PLAN as M446_PLAN, SUMMARY as M446_SUMMARY,
    PRIVATE_BATCH as M446_BATCH, _cluster_metrics,
    _original_evidence as _m445_evidence,
    _policy_digest as _m445_policy_digest,
)

PROTOCOL="m447_first_natural_challenge_pass_peng_matched_branch_v1"
SHARD_PROTOCOL="m447_one_first_claim_two_fixed_worlds_four_paid_branches_v1"
PLAN="PRIVATE_m447_pass_peng_branch_plan.json"
SHARD_DIR="PRIVATE_m447_original_shuffle_branches"
SUMMARY="safe_pong_pass_branch_rollouts.json"
WORLDS=(0,1)
PARTS=("win_points","kong_points","exhaustive_points")
SEED_COUNT=8
CHECKPOINTS_PER_SHUFFLE=1


def _find_candidate(game:FourPlayerOpening,agents:dict[int,Any]):
    """Observe next actor using the exact order of the live engine.

    For branches we must snapshot BEFORE the response mutates the game/RNG.
    The only pre-query is normal own-view + original Challenge.response;
    no privately leaked rival tiles can affect checkpoint selection.
    """
    if game.phase!="claim_window":
        return None
    source=game._pending_discard["seat"]
    seat=next((s for s in range(4)
               if s!=source and not game._won[s] and s not in game._responses),None)
    if seat is None:
        raise RuntimeError("unresolved discard claim responder missing")
    view=game.private_view(seat)
    if "peng" not in view["claim_options"]:
        return None
    # The ordinary Challenge response at this checkpoint is deterministic.
    # Snapshot agents so any future stochastic change would be detected.
    state=agents[seat]._rng.getstate()
    response=agents[seat].response(view)
    if agents[seat]._rng.getstate()!=state:
        raise RuntimeError("Challenge claim prefetched choice consumed RNG")
    if response=="pass":
        return seat
    return None


def _finish(game:FourPlayerOpening,agents:dict[int,Any])->dict[str,Any]:
    trace=[]
    durations=defaultdict(list)
    for _ in range(MAX_ACTIONS):
        if game.phase in ("finished","wall_exhausted"):
            break
        _take_action(game,agents,trace,durations)
        if len(trace)>4:
            trace.clear()
    else:
        raise RuntimeError("true engine branch exhausted action limit")
    settled=[_ledger(game,s) for s in range(4)]
    for key in ("official_net","win_points","kong_points","exhaustive_points"):
        if sum(x[key] for x in settled)!=0:
            raise RuntimeError("nonzero authoritative paired-branch four-seat ledger")
    return {
        "phase":game.phase,
        "official_net":[r["official_net"] for r in settled],
        **{key:[r[key] for r in settled] for key in PARTS},
    }


def _force_one(snapshot:FourPlayerOpening,original_agents:dict[int,Any],
               seat:int,action:str,world:int,seed:int)->dict[str,Any]:
    if (action not in ("pass","peng") or world not in WORLDS or
            snapshot.phase!="claim_window" or
            action not in snapshot.private_view(seat)["claim_options"]):
        raise ValueError("illegal paired pass/peng intervention")
    g=deepcopy(snapshot)
    agents=deepcopy(original_agents)  # maintain ALL per-seat RNG histories
    if world:
        rng=Random(seed*9973+world*101+17)
        rng.shuffle(g._wall)
    g._assert_physical_tiles()
    if (g.private_view(seat)!=snapshot.private_view(seat) or
            g.public_state()!=snapshot.public_state()):
        raise RuntimeError("future wall variant altered pre-intervention actor view")
    pending_index=len(g._discards)-1
    if pending_index<0:
        raise RuntimeError("pending claim not linked to a discard")
    g.respond_discard(seat,action)
    # Resolve remaining opponents' genuine claims (including hu priority)
    # BEFORE attributing whether peng was accepted or beaten by another call.
    trace=[]
    durations=defaultdict(list)
    for _ in range(4):
        if g.phase!="claim_window":
            break
        _take_action(g,agents,trace,durations)
    if g.phase=="claim_window":
        raise RuntimeError("unresolved claim arbitration in branch")
    actual_peng=(
        g._discards[pending_index].get("claimed_by")==seat
        and action=="peng"
    )
    result=_finish(g,agents)
    result["intervention_action"]=action
    result["peng_actually_claimed"]=actual_peng
    return result


def one_natural_shuffle(seed:int)->dict[str,Any]:
    if type(seed) is not int or not 0<=seed<2**32:
        raise ValueError("invalid new original shuffle seed")
    game=FourPlayerOpening(seed,kong_base=KONG_BASE,legacy_bugang_cash=False)
    agents=_agents(seed)
    _opening(game,agents,[])
    trace=[]
    durations=defaultdict(list)
    snapshot=None
    snapshot_agents=None
    actor=None
    for _ in range(MAX_ACTIONS):
        if game.phase in ("finished","wall_exhausted"):
            break
        if snapshot is None:
            observed=_find_candidate(game,agents)
            if observed is not None:
                actor=observed
                snapshot=deepcopy(game)
                snapshot_agents=deepcopy(agents)
        _take_action(game,agents,trace,durations)
        if len(trace)>4:
            trace.clear()
    else:
        raise RuntimeError("natural Challenge baseline did not fully finish")
    real=_finish(game,agents)
    outcome={
        "private_original_shuffle_seed":seed,
        "natural_complete_challenge_games":1,
        "natural_terminal_baseline":real,
        "first_natural_challenge_pass_with_peng_found":snapshot is not None,
        "private_first_actor_seat":actor,
        "private_matched_branches":[],
        "checkpoints_selected_by_first_opportunity_only":True,
        "no_hidden_actor_input_or_online_policy_change":True,
    }
    if snapshot is not None:
        for world in WORLDS:
            past=_force_one(snapshot,snapshot_agents,actor,"pass",world,seed)
            alternative=_force_one(snapshot,snapshot_agents,actor,"peng",world,seed)
            if world==0:
                for key in ("official_net",*PARTS):
                    if past[key]!=real[key]:
                        raise RuntimeError(
                            "original-wall paired pass branch failed exact natural game replay"
                        )
            delta={
                key:alternative[key][actor]-past[key][actor]
                for key in ("official_net",*PARTS)
            }
            if delta["official_net"]!=sum(delta[x] for x in PARTS):
                raise RuntimeError("counterfactual paid component breakdown mismatch")
            outcome["private_matched_branches"].append({
                "world":world,
                "forced_pass_terminal_actor_net":past["official_net"][actor],
                "forced_peng_terminal_actor_net":alternative["official_net"][actor],
                "peng_claim_actually_accepted":alternative["peng_actually_claimed"],
                "official_actor_net_delta":delta["official_net"],
                "win_actor_delta":delta["win_points"],
                "kong_actor_delta":delta["kong_points"],
                "exhaustive_actor_delta":delta["exhaustive_points"],
                "both_arms_genuine_terminal_ledgers":True,
                "no_opponent_hidden_hand_given_to_actors":True,
            })
    _validate_case(outcome,seed)
    return outcome


def _validate_case(case:dict[str,Any],seed:int)->None:
    if (type(case) is not dict or
            type(case.get("private_original_shuffle_seed")) is not int or
            case["private_original_shuffle_seed"]!=seed or
            case.get("natural_complete_challenge_games")!=1 or
            case.get("checkpoints_selected_by_first_opportunity_only") is not True or
            case.get("no_hidden_actor_input_or_online_policy_change") is not True):
        raise ValueError("not a complete natural first-checkpoint trial")
    natural=case.get("natural_terminal_baseline")
    if (type(natural) is not dict or
            natural.get("phase") not in ("finished","wall_exhausted") or
            type(natural.get("official_net")) is not list or
            len(natural["official_net"])!=4 or
            any(type(x) is not int for x in natural["official_net"]) or
            sum(natural["official_net"])!=0 or
            any(type(natural.get(p)) is not list or len(natural[p])!=4 or
                any(type(x) is not int for x in natural[p]) or
                sum(natural[p])!=0 for p in PARTS) or
            any(natural["official_net"][s]!=sum(natural[p][s] for p in PARTS)
                for s in range(4))):
        raise ValueError("real original Challenge payout did not reconcile")
    found=case.get("first_natural_challenge_pass_with_peng_found")
    if type(found) is not bool:
        raise ValueError("checkpoint detection must be boolean")
    seat=case.get("private_first_actor_seat")
    if (seat is not None and (type(seat) is not int or seat not in range(4))) or (
        found!=(seat is not None)
    ):
        raise ValueError("first actor seat not associated with checkpoint")
    branches=case.get("private_matched_branches")
    if (type(branches) is not list or
            len(branches)!=(len(WORLDS) if found else 0)):
        raise ValueError("wrong number of real matched future-world rollouts")
    for world,row in enumerate(branches):
        if (type(row) is not dict or row.get("world")!=world or
                row.get("both_arms_genuine_terminal_ledgers") is not True or
                row.get("no_opponent_hidden_hand_given_to_actors") is not True or
                type(row.get("peng_claim_actually_accepted")) is not bool or
                any(type(row.get(key)) is not int for key in (
                    "forced_pass_terminal_actor_net",
                    "forced_peng_terminal_actor_net",
                    "official_actor_net_delta","win_actor_delta",
                    "kong_actor_delta","exhaustive_actor_delta"
                )) or row["forced_peng_terminal_actor_net"]-
                row["forced_pass_terminal_actor_net"]!=
                row["official_actor_net_delta"] or
                row["official_actor_net_delta"]!=sum(row[x] for x in (
                    "win_actor_delta","kong_actor_delta",
                    "exhaustive_actor_delta",
                ))):
            raise ValueError("not a reconciled true branch pair")
        if (not row["peng_claim_actually_accepted"] and
                row["official_actor_net_delta"]!=0):
            raise ValueError("an unaccepted peng must not alter the real score")


def _private_shard(root:Path,index:int)->Path:
    return root/SHARD_DIR/f"index-{index:08d}.json"


def _read_verified(root:Path,start:int,n:int,model_digest:str)->dict[int,dict[str,Any]]:
    directory=root/SHARD_DIR
    if not directory.exists():
        return {}
    if not directory.is_dir():
        raise ValueError("M4.47 per-shuffle private shard directory invalid")
    stored={}
    for f in directory.iterdir():
        if f.is_file() and ".tmp-" in f.name:
            continue
        if (not f.is_file() or len(f.name)!=19 or
                not f.name.startswith("index-") or
                not f.name.endswith(".json") or
                not f.name[6:14].isdigit()):
            raise ValueError("unexpected M4.47 private checkpoint filename")
        i=int(f.name[6:14])
        if i>=n or i in stored:
            raise ValueError("duplicate/out-of-range original shuffle shard")
        env=_get_json(f)
        if (type(env) is not dict or
                set(env)!={"protocol","index","model_sha256","case_sha256","private_case"} or
                env["protocol"]!=SHARD_PROTOCOL or
                type(env["index"]) is not int or env["index"]!=i or
                env["model_sha256"]!=model_digest or
                type(env["private_case"]) is not dict):
            raise ValueError("M4.47 private checkpoint header invalid")
        case=env["private_case"]
        _validate_case(case,start+i)
        if env["case_sha256"]!=_paired_digest(case):
            raise ValueError("M4.47 private checkpoint SHA-256 mismatch")
        stored[i]=case
    return stored


def _aggregate(cases:list[dict[str,Any]])->dict[str,Any]:
    counts={
        "actual_natural_original_challenge_games":len(cases),
        "original_shuffles_with_legal_peng_after_challenge_pass":0,
        "original_shuffles_without_such_a_checkpoint":0,
        "paired_future_wall_worlds":0,
        "genuine_full_terminal_branch_games":0,
        "branch_pairs_where_peng_was_actually_claimed":0,
        "branch_pairs_where_other_calls_preempted_peng":0,
    }
    per_seed_delta=[]
    per_seed_win=[]
    per_seed_kong=[]
    per_seed_exhaustive=[]
    positive=negative=zero=0
    covered=[]
    for case in cases:
        matched=case["private_matched_branches"]
        found=bool(matched)
        counts["original_shuffles_with_legal_peng_after_challenge_pass"]+=int(found)
        counts["original_shuffles_without_such_a_checkpoint"]+=int(not found)
        counts["paired_future_wall_worlds"]+=len(matched)
        counts["genuine_full_terminal_branch_games"]+=2*len(matched)
        counts["branch_pairs_where_peng_was_actually_claimed"]+=sum(
            row["peng_claim_actually_accepted"] for row in matched)
        counts["branch_pairs_where_other_calls_preempted_peng"]+=sum(
            not row["peng_claim_actually_accepted"] for row in matched)
        cluster_delta=mean(x["official_actor_net_delta"] for x in matched) if found else 0
        per_seed_delta.append(cluster_delta)
        per_seed_win.append(mean(x["win_actor_delta"] for x in matched) if found else 0)
        per_seed_kong.append(mean(x["kong_actor_delta"] for x in matched) if found else 0)
        per_seed_exhaustive.append(mean(
            x["exhaustive_actor_delta"] for x in matched) if found else 0)
        positive+=int(cluster_delta>0)
        negative+=int(cluster_delta<0)
        zero+=int(cluster_delta==0)
        if found:
            covered.append(cluster_delta)
    mean_delta=round(mean(per_seed_delta),5)
    components={
        "win":round(mean(per_seed_win),5),
        "kong":round(mean(per_seed_kong),5),
        "exhaustive":round(mean(per_seed_exhaustive),5),
    }
    if abs(sum(components.values())-mean_delta)>0.00002:
        raise RuntimeError("conditional paired full-ledger components inconsistent")
    return {
        "protocol":PROTOCOL,
        "independent_original_shuffle_clusters":len(cases),
        **counts,
        "real_completed_full_games_baseline_plus_branches":
            len(cases)+counts["genuine_full_terminal_branch_games"],
        "mean_forced_peng_minus_pass_all_seed_clusters":mean_delta,
        "mean_official_component_delta_all_seed_clusters":components,
        "mean_forced_peng_minus_pass_only_covered_seed_clusters_descriptive":
            round(mean(covered),5) if covered else None,
        "seed_level_positive_delta":positive,
        "seed_level_negative_delta":negative,
        "seed_level_zero_delta":zero,
        "first_checkpoint_only_without_payout_cherry_picking":True,
        "matched_full_state_and_rng_for_both_actions_in_each_world":True,
        "same_original_shuffle_future_worlds_not_independent_samples":True,
        "rollouts_may_react_differently_to_public_action_changes":True,
        "counterfactual_engine_hidden_state_not_available_to_any_policy":True,
        "no_old_m445_or_m446_holdout_outcomes_used_for_training":True,
        "new_candidate_policy_not_fitted_or_promoted":True,
        "no_specific_hand_tiles_future_wall_shuffle_seed_or_weights_exported":True,
        "conditional_on_true_seed_and_first_checkpoint_not_population_ev":True,
        "no_claim_of_stronger_ai_or_action_ev_calibration":True,
    }


def _source_plan_and_exclusion(*,train:Path,prior:Path,model:dict[str,Any],
                               start:int,n:int)->dict[str,Any]:
    old=_get_json(prior/M446_PLAN)
    old_start=old.get("private_original_shuffle_start")
    old_n=old.get("private_new_original_shuffle_clusters")
    sha=model["model_sha256"]
    if (old.get("protocol")!=M446_PROTOCOL or
            old.get("private_training_source")!=str(train) or
            old.get("training_model_sha256_provenance_only")!=sha or
            old.get("unchanged_m445_source_sha256")!=_m445_policy_digest() or
            old.get("challenge_live_policy_untouched") is not True or
            type(old_start) is not int or type(old_n) is not int or
            old_n!=20 or not 0<=old_start<2**32 or old_start+old_n>2**32 or
            not (start+n<=old_start or start>=old_start+old_n)):
        raise ValueError("M4.47 new seed conflicts with completed frozen M4.46 source")
    m445=Path(old["private_previous_m445_source"])
    m444=_m445_evidence(
        prior=_private_location(m445),train=train,model=model,start=start,n=n,
    )
    if old.get("private_previous_m444_source")!=str(m444):
        raise ValueError("M4.46 old evidence source path mismatch")
    batch=prior/M446_BATCH
    verified=_m445_saved(batch,old_start,old_n,sha)
    if len(verified)!=old_n:
        raise ValueError("M4.46 requires all twenty complete original-seed checkpoints")
    expected=_m445_summary(
        [verified[i] for i in range(old_n)],
        model["trained_original_shuffle_clusters"],
    )
    previous_safe=_get_json(prior/M446_SUMMARY)
    if (not isinstance(previous_safe,dict) or
            previous_safe.get("protocol")!=M446_PROTOCOL or
            previous_safe.get("independent_original_shuffle_clusters")!=old_n or
            previous_safe.get("actor_only_response_counts")!=expected["actor_only_response_counts"] or
            previous_safe.get("mean_official_net_delta_points")!=expected["mean_official_net_delta_points"] or
            previous_safe.get("mean_official_component_delta_points")!=expected["mean_official_component_delta_points"] or
            previous_safe.get("actual_peng_overrides")!=_cluster_metrics(
                [verified[i] for i in range(old_n)]
            )["actual_peng_overrides"]):
        raise ValueError("previous M4.46 safe report does not match original paid data")
    # Follow exact registered prior-plan chain for M4.37/39/41/42/43/44.
    private444=_get_json(m444/"PRIVATE_call_frontier_plan.json")
    path442=Path(private444["private_m442_source"])
    path443=Path(private444["private_m443_source"])
    p442=_get_json(path442/"PRIVATE_challenge_tie_probe_plan.json")
    p443=_get_json(path443/"PRIVATE_safe_tie_policy_plan.json")
    p437=_get_json(Path(p442["private_prior_m437_dir"])/"PRIVATE_frozen_benchmark_plan.json")
    p439=_get_json(Path(p442["private_prior_m439_dir"])/"PRIVATE_actor_diagnostic_plan.json")
    p441=_get_json(Path(p442["private_prior_m441_dir"])/"PRIVATE_guard_trial_plan.json")
    for plan,startkey,countkey in (
        (p437,"private_evaluation_seed_start","private_eval_original_shuffle_count"),
        (p439,"private_eval_seed_start","private_eval_seed_count"),
        (p441,"private_seed_start","original_shuffle_clusters"),
        (p442,"private_original_seed_start","independent_seed_clusters"),
        (p443,"private_new_shuffle_start","private_independent_shuffle_count"),
        (private444,"private_original_shuffle_start","private_original_shuffle_count"),
    ):
        a=plan.get(startkey)
        size=plan.get(countkey)
        if (type(a) is not int or type(size) is not int or
                not 0<=a<2**32 or not 1<=size<=MAX_EVAL_SEEDS or
                a+size>2**32 or
                not (start+n<=a or start>=a+size)):
            raise ValueError("new M4.47 shuffle overlaps registered historical plan")
    return {"private_m446_source":str(prior),
            "private_m444_source":str(m444),
            "private_m445_source":str(m445)}


def run_matched_pong_branch_trial(
    *,training_dir:Path,prior_m446_dir:Path,
    seed_start:int,seeds:int,out_dir:Path,resume:bool=False,
)->dict[str,Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
            type(resume) is not bool or
            not 0<=seed_start<2**32 or seed_start+seeds>2**32 or
            seeds!=SEED_COUNT):
        raise ValueError("M4.47 requires the frozen eight-shuffle exploratory seed plan")
    train=_private_location(Path(training_dir))
    prior=_private_location(Path(prior_m446_dir))
    output=_private_location(Path(out_dir))
    if (len({train,prior,output})!=3 or any(
        a in b.parents or b in a.parents
        for a,b in ((train,prior),(train,output),(prior,output))
    )):
        raise ValueError("source and output locations must be completely separate")
    _,model=load_frozen_local_model(train)
    a=model["source_m434_train_seed_start"]
    b=model["source_m434_seed_end_exclusive"]
    if not (seed_start+seeds<=a or seed_start>=b):
        raise ValueError("new M4.47 shuffle overlaps original training/holdout")
    sources=_source_plan_and_exclusion(
        train=train,prior=prior,model=model,start=seed_start,n=seeds,
    )
    manifest={
        "protocol":PROTOCOL,
        "private_model_source":str(train),
        **sources,
        "private_natural_shuffle_start":seed_start,
        "private_independent_shuffle_count":seeds,
        "model_sha256_provenance_only":model["model_sha256"],
        "worlds":list(WORLDS),
        "frozen_m447_protocol_source_sha256":sha256(Path(__file__).read_bytes()).hexdigest(),
        "max_first_checkpoints_per_shuffle":CHECKPOINTS_PER_SHUFFLE,
        "no_new_policy_or_refit":True,
    }
    if resume:
        if not output.is_dir() or not (output/PLAN).is_file():
            raise ValueError("resume requires saved frozen M4.47 experiment plan")
        if _get_json(output/PLAN)!=manifest:
            raise ValueError("M4.47 resume parameters or model source changed")
        if any(p.name not in {PLAN,SHARD_DIR,SUMMARY} and ".tmp-" not in p.name
               for p in output.iterdir()):
            raise ValueError("unrecognized M4.47 private output file")
        cached=_read_verified(output,seed_start,seeds,model["model_sha256"])
        if (output/SUMMARY).exists() and len(cached)!=seeds:
            raise ValueError("finished M4.47 safe report has incomplete shards")
    else:
        if output.exists() and any(output.iterdir()):
            raise ValueError("M4.47 requires a newly empty output directory")
        output.mkdir(parents=True,exist_ok=True)
        _write_atomic(output/PLAN,manifest)
        cached={}
    (output/SHARD_DIR).mkdir(exist_ok=True)
    cases=[]
    for i in range(seeds):
        case=cached.get(i)
        if case is None:
            case=one_natural_shuffle(seed_start+i)
            _validate_case(case,seed_start+i)
            _write_atomic(_private_shard(output,i),{
                "protocol":SHARD_PROTOCOL,
                "index":i,
                "model_sha256":model["model_sha256"],
                "case_sha256":_paired_digest(case),
                "private_case":case,
            })
        cases.append(case)
    safe=_aggregate(cases)
    safe["verified_original_seed_shards_reused_on_resume"]=len(cached)
    _write_atomic(output/SUMMARY,safe)
    return safe
