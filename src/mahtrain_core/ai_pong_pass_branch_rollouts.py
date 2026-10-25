"""M4.47: authentic matched-state pass/peng branches, actor-only checkpoint.

At MOST the first naturally reached Challenge PASS with legally offered PENG
per original shuffle is studied. Two future-wall permutations, same checkpoint
and agent RNG state within each pass/peng pair. Counterfactual rollouts MAY
use the full local engine internally but never give hidden state to a policy,
train on the held-out outcomes, or export it. Not a population causal EV.
"""
from __future__ import annotations

from collections import defaultdict
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


