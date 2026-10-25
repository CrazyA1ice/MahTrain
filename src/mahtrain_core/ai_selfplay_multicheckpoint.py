"""M4.32: multiple NATURAL four-challenge choice checkpoints per game.

Learner may see only the acting seat's own authorized observation. The
researcher clones a full physical state solely to obtain terminal outcomes
under both actions in two fixed unseen-wall orders. A single original
shuffle seed always counts as ONE correlated training/holdout cluster,
regardless of its number of checkpoints, wall worlds or rollout games.

Learning is gated on SAME-SIGN nonzero outcomes in both worlds. Even
consistent conditional worlds do not estimate the true hidden-world
expectation. No new live policy is installed.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from math import isfinite
from statistics import mean
from typing import Any

from .ai_selfplay_learning import _assert_public
from .ai_selfplay_counterfactual import (
    PROTOCOL as PARENT_PROTOCOL, FEATURE_NAMES, MAX_ACTIONS, SEED_LIMIT,
    WALL_WORLDS, KONG_BASE, _agents, _opening, _find_checkpoint, _ledger,
    _wall_variant, _force_and_finish,
)
from .ai_tournament import _take_action, public_replay_frame
from .four_player import FourPlayerOpening

PROTOCOL = "m432_natural_multicheckpoint_seed_cluster_action_labels_v1"
MODEL_PROTOCOL = "m432_consensus_guarded_seed_weighted_offline_diagnostic_v1"
MAX_CHECKPOINTS = 2
MAX_TRAIN_SEEDS = 4
CASH_RULE = "current_m423"
LEDGER_COMPONENTS = ("win_points", "kong_points", "exhaustive_points")


def _validate(seed_start: int, train_seeds: int, holdout_seeds: int,
              max_checkpoints: int = MAX_CHECKPOINTS) -> None:
    if (type(seed_start) is not int or not 0 <= seed_start < SEED_LIMIT or
            type(train_seeds) is not int or
            not 1 <= train_seeds <= MAX_TRAIN_SEEDS or
            type(holdout_seeds) is not int or
            not 1 <= holdout_seeds <= MAX_TRAIN_SEEDS or
            seed_start + train_seeds + holdout_seeds > SEED_LIMIT or
            type(max_checkpoints) is not int or
            not 1 <= max_checkpoints <= MAX_CHECKPOINTS):
        raise ValueError("invalid disjoint seed clusters or checkpoint quota")


def natural_multi_checkpoint_game(seed: int, *,
                                  max_checkpoints: int = MAX_CHECKPOINTS):
    """A genuine full natural game, up to 2 snapshots, each from a unique seat.

    The snapshot's actual unseen state exists ONLY as an in-process deepcopy.
    The serialized actor example contains just the authorized seat view.
    Selection is the first naturally encountered eligible opportunity per
    distinct seat, until the quota is reached; it is not a random sample of
    all action decisions during a hand.
    """
    _validate(seed, 1, 1, max_checkpoints)
    game = FourPlayerOpening(
        seed, kong_base=KONG_BASE, legacy_bugang_cash=False,
    )
    agents = _agents(seed)
    frames: list[dict[str, Any]] = []
    _opening(game, agents, frames)
    checkpoints = []
    used_seats: set[int] = set()
    trace: list[dict[str, Any]] = []
    durations: dict[str, list[float]] = defaultdict(list)
    for _ in range(MAX_ACTIONS):
        if game.phase in ("finished", "wall_exhausted"):
            break
        if (len(checkpoints) < max_checkpoints and
                game.phase in ("await_discard","dealer_discard") and
                game.turn not in used_seats):
            candidate = _find_checkpoint(game, seed)
            if candidate is not None:
                candidate = deepcopy(candidate)
                used_seats.add(candidate["seat"])
                checkpoints.append((deepcopy(game), candidate))
        _take_action(game, agents, trace, durations)
        frames.append(public_replay_frame(game, trace[-1]))
        if len(trace) > 4:
            trace.clear()
    else:
        raise RuntimeError("natural four challenge agents exceeded action cap")
    board = game.public_state()
    for seat in range(4):
        _ledger(game, seat)  # All seats, fully paid and zero sum.
    public = {
        "protocol":PROTOCOL,
        "game_id":"assigned-by-nonseed-export-index",
        "players":["challenge"]*4,
        "rule_set":CASH_RULE,
        "terminal_phase":game.phase,
        "public_frames":frames,
        "official_final_balances":board["settled_balances"],
    }
    _assert_public(public)
    return public, checkpoints


def _signed_consensus(deltas: list[int]) -> str:
    if len(deltas) != len(WALL_WORLDS) or any(type(x) is not int for x in deltas):
        raise ValueError("need all actual physical world score deltas")
    if all(v > 0 for v in deltas):
        return "alternative_better_in_all_test_worlds"
    if all(v < 0 for v in deltas):
        return "original_better_in_all_test_worlds"
    return "mixed_or_tied_world_outcomes"


def _evaluate_checkpoint(full_game, selection: dict[str, Any],
                         *, seed: int, index: int) -> dict[str, Any]:
    seat=selection["seat"]
    prior=deepcopy(full_game.private_view(seat))
    results=[]
    for world_id in WALL_WORLDS:
        common = _wall_variant(full_game, seed, world_id, selection)
        original = _force_and_finish(
            common, seed, seat, selection["baseline"],
        )
        alternative = _force_and_finish(
            common, seed, seat, selection["alternative"],
        )
        delta={
            k:alternative[k]-original[k]
            for k in ("official_net", *LEDGER_COMPONENTS)
        }
        if delta["official_net"]!=sum(delta[k] for k in LEDGER_COMPONENTS):
            raise RuntimeError("invalid real net difference")
        results.append({
            "world_index":world_id,
            "first_action_challenge":original,
            "first_action_alternative":alternative,
            "alternative_minus_original":delta,
            "same_actor_authorized_view":True,
        })
    if full_game.private_view(seat)!=prior:
        raise RuntimeError("physical rollouts mutated the research source")
    diffs=[r["alternative_minus_original"]["official_net"] for r in results]
    return {
        "checkpoint_index":index,
        "seat":seat,
        "actor_observation":selection,
        "physical_worlds":results,
        "paired_real_terminal_games":len(results)*2,
        "mean_conditional_net_delta":round(mean(diffs),5),
        "two_world_sign_consensus":_signed_consensus(diffs),
        "eligible_as_exploratory_training_label":
            _signed_consensus(diffs)!="mixed_or_tied_world_outcomes",
        "not_unbiased_action_EV":True,
    }


def run_natural_seed(seed: int, *,
                     max_checkpoints: int = MAX_CHECKPOINTS
                     ) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate(seed, 1, 1, max_checkpoints)
    public, checkpoints=natural_multi_checkpoint_game(
        seed, max_checkpoints=max_checkpoints,
    )
    rows=[
        _evaluate_checkpoint(game, observation, seed=seed, index=index)
        for index,(game,observation) in enumerate(checkpoints)
    ]
    if (len(rows)>max_checkpoints or
            len({r["seat"] for r in rows})!=len(rows) or
            any(r["paired_real_terminal_games"]!=4 for r in rows)):
        raise RuntimeError("natural checkpoint quota/seat guarantee failed")
    private={
        "protocol":PROTOCOL,"private_shuffle_seed":seed,
        "actor_only_observations":True,
        "checkpoints":rows,
        "captured_decisions":len(rows),
        "conditional_rollout_games":len(rows)*4,
        "original_natural_games":1,
    }
    return public,private


def _safe_seed_labels(cluster: dict[str, Any]) -> list[tuple[list[float],float]]:
    if (cluster.get("protocol")!=PROTOCOL or
            cluster.get("actor_only_observations") is not True or
            type(cluster.get("private_shuffle_seed")) is not int or
            type(cluster.get("checkpoints")) is not list or
            cluster.get("captured_decisions")!=len(cluster["checkpoints"]) or
            len(cluster["checkpoints"])>MAX_CHECKPOINTS):
        raise ValueError("nonconforming self-play seed cluster")
    labels=[]
    seats=set()
    for item in cluster["checkpoints"]:
        if (type(item) is not dict or
                type(item.get("checkpoint_index")) is not int or
                item["checkpoint_index"]!=len(seats) or
                type(item.get("seat")) is not int or
                item["seat"] not in range(4) or item["seat"] in seats or
                item.get("not_unbiased_action_EV") is not True or
                type(item.get("physical_worlds")) is not list or
                len(item["physical_worlds"])!=len(WALL_WORLDS) or
                item.get("paired_real_terminal_games")!=len(WALL_WORLDS)*2):
            raise ValueError("bad paired case structure")
        seats.add(item["seat"])
        d=[]
        for i,w in enumerate(item["physical_worlds"]):
            if (type(w) is not dict or w.get("world_index")!=WALL_WORLDS[i] or
                    w.get("same_actor_authorized_view") is not True):
                raise ValueError("bad paired wall agreement")
            a=w.get("first_action_challenge")
            b=w.get("first_action_alternative")
            delta=w.get("alternative_minus_original")
            if any(type(x) is not dict for x in (a,b,delta)):
                raise ValueError("missing real finished games")
            for arm in (a,b):
                if (arm.get("terminal_phase") not in ("finished","wall_exhausted")
                        or arm.get("physical_tiles")!=108 or
                        any(type(arm.get(k)) is not int
                            for k in ("official_net",*LEDGER_COMPONENTS)) or
                        arm["official_net"]!=sum(
                            arm[k] for k in LEDGER_COMPONENTS)):
                    raise ValueError("invented or unbalanced authoritative ledger")
            if (set(delta)!={"official_net",*LEDGER_COMPONENTS}
                    or any(type(delta[k]) is not int or
                           delta[k]!=b[k]-a[k] for k in delta)):
                raise ValueError("tampered true paired terminal net points")
            d.append(delta["official_net"])
        consensus=_signed_consensus(d)
        if (item.get("two_world_sign_consensus")!=consensus or
                item.get("eligible_as_exploratory_training_label") is not
                (consensus!="mixed_or_tied_world_outcomes") or
                type(item.get("mean_conditional_net_delta")) not in (float,int) or
                abs(item["mean_conditional_net_delta"]-mean(d))>1e-4):
            raise ValueError("inconsistent training label")
        view=item.get("actor_observation")
        if (type(view) is not dict or view.get("seat")!=item["seat"] or
                type(view.get("features")) is not dict or
                set(view["features"])!={view.get("baseline"),view.get("alternative")} or
                len(view["features"])!=2 or
                type(view.get("minimum_shanten")) is not int):
            raise ValueError("invalid actor-only action features")
        features=[view["features"][view["alternative"]][i]-
                  view["features"][view["baseline"]][i]
                  for i in range(len(FEATURE_NAMES))]
        if (any(type(x) not in (float,int) or not isfinite(x)
                for x in features) or
                any(type(view["features"][tile]) is not list or
                    len(view["features"][tile])!=len(FEATURE_NAMES)
                    for tile in view["features"])):
            raise ValueError("missing finite, bounded research features")
        if consensus!="mixed_or_tied_world_outcomes":
            reward=max(-1.0,min(1.0,mean(d)/1000))
            labels.append((features,reward))
    return labels


def fit_seed_weighted_model(clusters: list[dict[str,Any]]) -> dict[str,Any]:
    """Aggregate WITHIN each seed first, so 2 checkpoints != 2 samples."""
    if type(clusters) is not list or not clusters:
        raise ValueError("requires complete, independent natural seed clusters")
    seed_groups=[]
    ids=set()
    eligible_decisions=0
    for row in clusters:
        seed=row.get("private_shuffle_seed")
        if seed in ids:
            raise ValueError("repeated shuffle seed cannot count independently")
        ids.add(seed)
        examples=_safe_seed_labels(row)
        eligible_decisions+=len(examples)
        if examples:
            seed_groups.append([
                mean(x[i]*reward for x,reward in examples)
                for i in range(len(FEATURE_NAMES))
            ])
    if not seed_groups:
        return {
            "protocol":MODEL_PROTOCOL,
            "status":"no_consistent_action_labels",
            "features":list(FEATURE_NAMES),
            "seed_clusters_seen":len(clusters),
            "independent_seed_clusters_with_labels":0,
            "total_action_labels":0,
            "weights":None,
            "online_promotion_allowed":False,
        }
    weights=[
        round(max(-.2,min(.2,mean(x[i] for x in seed_groups))),7)
        for i in range(len(FEATURE_NAMES))
    ]
    return {
        "protocol":MODEL_PROTOCOL,
        "status":"offline_consensus_weighted_diagnostic",
        "features":list(FEATURE_NAMES),
        "seed_clusters_seen":len(clusters),
        "independent_seed_clusters_with_labels":len(seed_groups),
        "total_action_labels":eligible_decisions,
        "weights":weights,
        "online_promotion_allowed":False,
        "not_calibrated_action_q":True,
    }


def evaluate_unseen_seed_clusters(clusters: list[dict[str,Any]],
                                  model: dict[str,Any]) -> dict[str,Any]:
    if (type(model) is not dict or model.get("protocol")!=MODEL_PROTOCOL or
            model.get("features")!=list(FEATURE_NAMES) or
            model.get("online_promotion_allowed") is not False):
        raise ValueError("unfrozen/unsupported pilot model")
    weights=model.get("weights")
    if (weights is not None and (
            type(weights) is not list or len(weights)!=len(FEATURE_NAMES) or
            any(type(v) not in (int,float) or not isfinite(v) or abs(v)>.2
                for v in weights))):
        raise ValueError("invalid offline parameters")
    seed_reports=[]
    seen=set()
    for row in clusters:
        seed=row.get("private_shuffle_seed")
        if seed in seen:
            raise ValueError("duplicate independent holdout cluster")
        seen.add(seed)
        _safe_seed_labels(row)  # Full outcome integrity checks even if no model.
        decisions=[]
        for item in row["checkpoints"]:
            features=item["actor_observation"]["features"]
            a=features[item["actor_observation"]["alternative"]]
            b=features[item["actor_observation"]["baseline"]]
            margin=(sum((x-y)*w for x,y,w in zip(a,b,weights))
                    if weights is not None else 0.0)
            truth=item["mean_conditional_net_delta"]
            signed=item["two_world_sign_consensus"]
            eligible=(signed!="mixed_or_tied_world_outcomes")
            decisive=(weights is not None and margin!=0 and eligible)
            decisions.append({
                "checkpoint_index":item["checkpoint_index"],
                "sign_consensus":signed,
                "model_abstained":not decisive,
                "model_and_conditional_label_agree":
                    ((margin>0 and truth>0) or (margin<0 and truth<0))
                    if decisive else None,
            })
        seed_reports.append({
            "private_shuffle_seed":seed,
            "natural_decisions":len(decisions),
            "consensus_decisions":sum(
                d["sign_consensus"]!="mixed_or_tied_world_outcomes"
                for d in decisions),
            "decisive_evaluations":sum(not d["model_abstained"] for d in decisions),
            "correct_decisive_labels":sum(
                d["model_and_conditional_label_agree"] is True
                for d in decisions),
            "decisions":decisions,
        })
    return {
        "protocol":MODEL_PROTOCOL,
        "untouched_shuffle_seed_clusters":len(seed_reports),
        "total_natural_checkpoints":sum(x["natural_decisions"] for x in seed_reports),
        "consensus_action_checkpoints":sum(x["consensus_decisions"] for x in seed_reports),
        "scored_decisions":sum(x["decisive_evaluations"] for x in seed_reports),
        "correct_conditional_directions":sum(
            x["correct_decisive_labels"] for x in seed_reports),
        "seed_report":seed_reports,
        "offline_model_only":True,
        "evidence_of_population_strength":False,
    }


def run_study(seed_start: int, train_seeds: int, holdout_seeds: int,
              *, max_checkpoints: int = MAX_CHECKPOINTS) -> dict[str,Any]:
    _validate(seed_start,train_seeds,holdout_seeds,max_checkpoints)
    public=[]
    train=[]
    holdout=[]
    for offset in range(train_seeds+holdout_seeds):
        replay,private=run_natural_seed(
            seed_start+offset,max_checkpoints=max_checkpoints,
        )
        replay["game_id"]=f"game-{offset:04d}"  # not derived from seed
        _assert_public(replay)
        public.append(replay)
        (train if offset<train_seeds else holdout).append(private)
    model=fit_seed_weighted_model(train)
    test=evaluate_unseen_seed_clusters(holdout,model)
    return {
        "protocol":PROTOCOL,
        "train_seed_start":seed_start,
        "test_seed_start":seed_start+train_seeds,
        "train_seed_clusters":train_seeds,
        "test_seed_clusters":holdout_seeds,
        "natural_full_games":len(public),
        "counterfactual_full_games":sum(
            x["conditional_rollout_games"] for x in train+holdout),
        "public_replays":public,
        "private_train":train,
        "private_holdout":holdout,
        "model":model,
        "heldout":test,
        "no_online_ai_change":True,
        "no_validated_improvement_claim":True,
        "cluster_independence_unit":"original_natural_shuffle_seed",
    }
