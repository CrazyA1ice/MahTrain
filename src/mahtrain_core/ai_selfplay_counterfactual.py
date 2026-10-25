"""M4.31 four-CHALLENGE natural self-play and offline legal discard rollouts.

Public match tapes are strictly redacted. Privately, a real, naturally reached
decision is cloned into two legal SAME-shanten cuts and two alternate future
wall orders; ALL branches run to terminal authoritative Hu/kong/wall scores.

These paired realized returns are noisy CONDITIONAL action labels, not
calibrated action EV. They never enter the live MahjongAgent.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from random import Random
from statistics import mean
from time import perf_counter_ns
from typing import Any, Mapping

from .ai import MahjongAgent
from .ai_tournament import _take_action, public_replay_frame
from .ai_selfplay_learning import _assert_public, _snapshot
from .efficiency import analyze_discards
from .four_player import FourPlayerOpening
from .rules import TILE_INDEX

PROTOCOL="m431_natural_four_challenge_authorized_pair_rollouts_v1"
CAPTURE_VERSION="challenge_v1_frozen"
WALL_WORLDS=(0,1)
ARMS=("baseline_challenge", "same_shanten_alternative")
MAX_ACTIONS=850
KONG_BASE=20
SEED_LIMIT=2**32
FEATURE_NAMES=("effective_copy_count","effective_next_draw_fraction",
               "effective_tile_types")


def _agents(seed: int) -> dict[int, MahjongAgent]:
    return {s:MahjongAgent("challenge",seed=seed,seat=s) for s in range(4)}


def _opening(game: FourPlayerOpening, agents: Mapping[int, MahjongAgent],
             frames: list[dict[str, Any]]) -> None:
    for seat in range(4):
        game.select_exchange(seat,agents[seat].exchange(game.private_view(seat)))
        frames.append(public_replay_frame(game,{
            "phase":"exchange_select","seat":seat,"action":"exchange_three",
            "level":"challenge","count":3,
        }))
    for seat in range(4):
        game.select_missing(seat,agents[seat].missing(game.private_view(seat)))
        frames.append(public_replay_frame(game,{
            "phase":"missing_select","seat":seat,"action":"declare_missing",
            "level":"challenge",
        }))


def _candidate_features(row: Mapping[str, Any]) -> list[float]:
    return [
        round(row["effective_tile_count"]/40,7),
        round(row["next_draw_probability"],7),
        round(len(row["effective_types"])/27,7),
    ]


def _find_checkpoint(game: FourPlayerOpening,seed: int):
    if game.phase not in ("dealer_discard","await_discard"):
        return None
    seat=game.turn
    view=game.private_view(seat)
    if (view["can_self_draw_win"] or
            MahjongAgent("challenge",seed=seed,seat=seat).kong(view) is not None):
        return None
    info=analyze_discards(
        view["hand"],view["own_melds"],
        missing_suit=view["missing_suits"][seat],
        visible_tiles=__import__("mahtrain_core.ai",fromlist=["visible_tiles"]
                         ).visible_tiles(view),
    )
    if info["status"]!="choose_discard":
        return None
    stage=info["minimum_shanten"]
    same=[row for row in info["candidates"] if row["shanten"]==stage]
    if len(same)<2:
        return None
    baseline=MahjongAgent("challenge",seed=seed,seat=seat).discard(view)
    if baseline not in [r["discard"] for r in same]:
        raise RuntimeError("live challenge did not choose best structural stage")
    second=next(row for row in same if row["discard"]!=baseline)
    chosen=[next(r for r in same if r["discard"]==baseline),second]
    return {
        "seat":seat,"baseline":baseline,"alternative":second["discard"],
        "minimum_shanten":stage,
        "features":{r["discard"]:_candidate_features(r) for r in chosen},
        "observation":_snapshot(view),
    }


def _ledger(game: FourPlayerOpening,seat: int) -> dict[str,Any]:
    if game.phase not in ("finished","wall_exhausted"):
        raise RuntimeError("rollout did not really finish")
    board=game.public_state()
    hu=board["win_ledger"]["balances"]
    kong=board["kong_ledger"]["balances"]
    draw=(board["exhaustive_settlement"]["balances"]
          if board["exhaustive_settlement"] is not None else [0]*4)
    net=board["settled_balances"]
    if (game.debug_tile_counts()["total"]!=108 or
            game._legacy_bugang_cash is not False or
            game.kong_ledger.base!=KONG_BASE or
            any(type(x) is not list or len(x)!=4 or
                any(type(v) is not int for v in x) or sum(x)
                for x in (hu,kong,draw,net)) or
            any(net[s]!=hu[s]+kong[s]+draw[s] for s in range(4)) or
            (game.phase=="wall_exhausted" and (
                board["wall_count"]!=0 or
                board["exhaustive_settlement"] is None)) or
            (game.phase=="finished" and sum(board["won"])!=3)):
        raise RuntimeError("invalid actual official terminal balance")
    return {
        "official_net":net[seat],
        "win_points":hu[seat],
        "kong_points":kong[seat],
        "exhaustive_points":draw[seat],
        "terminal_phase":game.phase,
        "physical_tiles":108,
    }


def natural_selfplay(seed: int):
    """Return public tape, LOCAL-private own-view record and actual checkpoint.

    The optional checkpoint has full hidden game state IN MEMORY only; it must
    NEVER enter the exported public or private learner JSON.
    """
    if type(seed) is not int or not 0<=seed<SEED_LIMIT:
        raise ValueError("invalid registered natural self-play seed")
    game=FourPlayerOpening(seed,kong_base=KONG_BASE,
                           legacy_bugang_cash=False)
    agents=_agents(seed)
    frames=[]
    _opening(game,agents,frames)
    checkpoint=None
    trace=[]
    durations=defaultdict(list)
    for _ in range(MAX_ACTIONS):
        if game.phase in ("finished","wall_exhausted"):
            break
        if checkpoint is None and game.phase in ("await_discard","dealer_discard"):
            selection=_find_checkpoint(game,seed)
            if selection is not None:
                checkpoint=(deepcopy(game),selection)
        _take_action(game,agents,trace,durations)
        frames.append(public_replay_frame(game,trace[-1]))
        if len(trace)>4:
            trace.clear()
    else:
        raise RuntimeError("natural four-challenge game hit action limit")
    final=_ledger(game,0)
    public={
        "protocol":PROTOCOL, "game_id":f"match-{seed%10000000:07d}",
        "policies":["challenge"]*4,
        "phase":game.phase,"public_frames":frames,
        "official_final_balances":game.public_state()["settled_balances"],
        "rule_set":"current_m423",
    }
    _assert_public(public)
    private={
        "protocol":PROTOCOL,"private_seed":seed,
        "natural_terminal_actor_zero":final,
        "decision_found":checkpoint is not None,
        "actor_observation_only":True,
        "checkpoint_actor":(checkpoint[1] if checkpoint else None),
    }
    return public,private,checkpoint


def _wall_variant(game: FourPlayerOpening,seed: int,world: int,
                  observer: Mapping[str, Any]) -> FourPlayerOpening:
    if type(world) is not int or world not in WALL_WORLDS:
        raise ValueError("unregistered wall permutation")
    g=deepcopy(game)
    if world:
        rng=Random(seed*9973+world*101+17)
        rng.shuffle(g._wall)
    g._assert_physical_tiles()
    if (g.private_view(observer["seat"])!=
            game.private_view(observer["seat"]) or
            g.public_state()!=game.public_state()):
        raise RuntimeError("offline future permutation contaminated actor view")
    return g


def _force_and_finish(game: FourPlayerOpening,seed: int,seat: int,
                      discard: str) -> dict[str,Any]:
    game=deepcopy(game)
    view=game.private_view(seat)
    if (seat!=game.turn or view["can_self_draw_win"] or
            discard not in view["hand"]):
        raise RuntimeError("illegal override at natural decision")
    game.discard(seat,discard)
    agents=_agents(seed)
    trace=[]
    durations=defaultdict(list)
    for i in range(MAX_ACTIONS):
        if game.phase in ("finished","wall_exhausted"):
            result=_ledger(game,seat)
            result["actions_after_forced_discard"]=i
            return result
        _take_action(game,agents,trace,durations)
        if len(trace)>4:
            trace.clear()
    raise RuntimeError("counterfactual did not finish")


def paired_natural_seed(seed: int) -> tuple[dict[str,Any],dict[str,Any]]:
    public,private,checkpoint=natural_selfplay(seed)
    if checkpoint is None:
        private["paired"]={"status":"no_two_same_stage_legal_discards",
                           "worlds":[]}
        return public,private
    snapshot,selected=checkpoint
    before=snapshot.private_view(selected["seat"])
    worlds=[]
    for world in WALL_WORLDS:
        g=_wall_variant(snapshot,seed,world,selected)
        a=_force_and_finish(g,seed,selected["seat"],selected["baseline"])
        b=_force_and_finish(g,seed,selected["seat"],selected["alternative"])
        delta={k:b[k]-a[k] for k in (
            "official_net","win_points","kong_points","exhaustive_points",
        )}
        if delta["official_net"] != (delta["win_points"]+
            delta["kong_points"]+delta["exhaustive_points"]):
            raise RuntimeError("unreconciled actual terminal payoff delta")
        worlds.append({
            "world":world,"baseline":a,"alternative":b,
            "alternative_minus_baseline":delta,
            "same_actor_observation":True,
        })
    if snapshot.private_view(selected["seat"])!=before:
        raise RuntimeError("rollout mutated natural checkpoint")
    private["paired"]={
        "status":"two_real_terminal_actions",
        "worlds":worlds,"world_count":len(worlds),
        "average_alternative_minus_baseline_official_net":round(
            mean(w["alternative_minus_baseline"]["official_net"]
                 for w in worlds),5),
        "not_calibrated_action_EV":True,
    }
    return public,private


def _train_from_rows(rows: list[dict[str,Any]]) -> dict[str,Any]:
    # Small linear preference diagnostic trained from action-level paired
    # outcomes. It can only make OFFLINE suggestions; no policy deployment.
    examples=[]
    for row in rows:
        record=row["checkpoint_actor"]
        paired=row["paired"]
        if record is None or paired["status"]!="two_real_terminal_actions":
            continue
        x=record["features"][record["alternative"]]
        y=record["features"][record["baseline"]]
        difference=[a-b for a,b in zip(x,y)]
        signal=max(-1.0,min(1.0,
            paired["average_alternative_minus_baseline_official_net"]/1000))
        examples.append((difference,signal))
    if not examples:
        return {
            "status":"insufficient_natural_choice_coverage",
            "trained_samples":0,"feature_names":list(FEATURE_NAMES),
            "online_policy_changed":False,
        }
    weights=[
        round(max(-0.2,min(0.2,mean(x[i]*y for x,y in examples))),7)
        for i in range(len(FEATURE_NAMES))
    ]
    return {
        "status":"bounded_offline_action_preference_fitted",
        "trained_samples":len(examples),
        "feature_names":list(FEATURE_NAMES),"weights":weights,
        "online_policy_changed":False,
        "not_causal_general_population_EV":True,
    }


def _holdout_analysis(rows: list[dict[str,Any]],
                      model: Mapping[str,Any]) -> dict[str,Any]:
    available=[
        row for row in rows if row["paired"]["status"]=="two_real_terminal_actions"
    ]
    reports=[]
    for row in available:
        choice=row["checkpoint_actor"]
        differences=[
            choice["features"][choice["alternative"]][i]-
            choice["features"][choice["baseline"]][i]
            for i in range(len(FEATURE_NAMES))
        ]
        weights=model.get("weights",[])
        projected=sum(a*b for a,b in zip(differences,weights))
        observed=row["paired"]["average_alternative_minus_baseline_official_net"]
        reports.append({
            "private_seed":row["private_seed"],
            "offline_policy_prefers_alternative":projected>0,
            "observed_alternative_minus_baseline":observed,
            "agreement_with_conditional_outcome":
                ((projected>0 and observed>0) or
                 (projected<=0 and observed<=0)),
        })
    return {
        "natural_holdout_seed_clusters":len(rows),
        "natural_covered_decisions":len(available),
        "fully_terminal_counterfactual_games":len(available)*len(WALL_WORLDS)*2,
        "offline_prefers_alternative":sum(
            r["offline_policy_prefers_alternative"] for r in reports),
        "direction_agreement_count":sum(
            r["agreement_with_conditional_outcome"] for r in reports),
        "evaluated_choices":reports,
        "confirmed_stronger":False,
        "online_model_promoted":False,
    }


def run_experiment(seed_start: int,train_seeds: int,
                   holdout_seeds: int) -> dict[str,Any]:
    if (type(seed_start) is not int or not 0<=seed_start<SEED_LIMIT or
            type(train_seeds) is not int or not 1<=train_seeds<=4 or
            type(holdout_seeds) is not int or not 1<=holdout_seeds<=4 or
            seed_start+train_seeds+holdout_seeds>SEED_LIMIT):
        raise ValueError("train/holdout must be independent natural seed ranges")
    public=[]
    train=[]
    held=[]
    for i in range(train_seeds+holdout_seeds):
        seed=seed_start+i
        pub,private=paired_natural_seed(seed)
        public.append(pub)
        (train if i<train_seeds else held).append(private)
    model=_train_from_rows(train)
    evaluation=_holdout_analysis(held,model)
    return {
        "protocol":PROTOCOL,
        "training_seed_start":seed_start,
        "holdout_seed_start":seed_start+train_seeds,
        "public_replays":public,
        "private_training":train,"private_holdout":held,
        "offline_model":model,"holdout":evaluation,
        "natural_games":len(public),
        "full_counterfactual_terminal_games":sum(
            len(row["paired"]["worlds"])*2 for row in train+held),
        "four_challenge_ais":True,
        "online_policy_changed":False,
        "causal_EV_or_strength_proven":False,
    }
