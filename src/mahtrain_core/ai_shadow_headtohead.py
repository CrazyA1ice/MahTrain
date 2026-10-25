"""M4.36: frozen OFFLINE model versus unchanged four-challenge real games.

No new public difficulty tier: the candidate is a local shadow adapter. It
receives only the acting player's private_view and changes only legal
minimum-shanten discard tie breaks. All other behavior stays challenge.

Evaluation has four seat rotations per untouched shuffle plus a common
baseline. The original shuffle SEED, not five correlated games, is the
statistical unit. This does not prove strength from small cohorts.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from statistics import mean
from time import perf_counter_ns
from typing import Any, Mapping

from .ai import MahjongAgent, visible_tiles
from .ai_selfplay_counterfactual import (
    FEATURE_NAMES, KONG_BASE, MAX_ACTIONS, _agents, _candidate_features,
    _ledger, _opening,
)
from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_selfplay_uncertainty import (
    PROTOCOL as M435_PROTOCOL, _records, _validate_plan,
    fit_all_conditional_actions,
)
from .ai_tournament import _take_action
from .efficiency import analyze_discards
from .four_player import FourPlayerOpening

PROTOCOL="m436_frozen_shadow_four_seat_real_net_benchmark_v1"
MAX_EVAL_SEEDS=100
MIN_INDEPENDENT_SEEDS_FOR_EXPLORATORY_MEAN=20
MAX_EVAL_ACTION_MS_TO_REPORT=0  # no unsupported latency claim
SHADOW_LEVEL="offline_shadow_candidate"


def _bounded_weights(model: Mapping[str,Any]) -> tuple[float,...] | None:
    if (type(model) is not dict or model.get("protocol")!=M435_PROTOCOL or
            model.get("features")!=list(FEATURE_NAMES) or
            model.get("online_policy_promotion_allowed") is not False or
            model.get("no_test_labels_used_for_training") is not True or
            model.get("estimated_population_action_ev") is not False):
        raise ValueError("unsupported or potentially online-promoted M4.35 model")
    w=model.get("weights")
    if w is None:
        if model.get("status")!="no_legal_training_action_points":
            raise ValueError("unexpected absent research weights")
        return None
    if (model.get("status")!="conditional_two_world_offline_diagnostic" or
            type(w) is not list or len(w)!=len(FEATURE_NAMES) or
            any(type(v) not in (float,int) or not isfinite(v)
                or abs(v)>0.2 for v in w)):
        raise ValueError("nonfinite/out of bounds or malformed frozen weights")
    return tuple(float(v) for v in w)


def load_frozen_local_model(training_directory: Path
                            ) -> tuple[tuple[float,...]|None,dict[str,Any]]:
    """Refit ONLY training shards and verify the frozen local model exactly.

    Train vs holdout was fixed in the M4.34 manifest. Nothing in the
    original M4.34 holdout is touched while constructing candidate weights.
    """
    root=_private_location(Path(training_directory))
    plan=_validate_plan(root)
    target=root/"PRIVATE_uncertainty_offline_model.json"
    if not target.is_file():
        raise ValueError(
            "missing M4.35 frozen local model; first run "
            "python examples/run_local_uncertainty_analysis.py --out-dir <batch>"
        )
    stored=_get_json(target)
    fresh=fit_all_conditional_actions(
        _records(plan,root,0,plan.train_seeds),
        plan.train_seeds,
    )
    if stored!=fresh:
        raise ValueError("frozen model does not match audited TRAIN seed shards")
    w=_bounded_weights(stored)
    digest=sha256(json.dumps(
        fresh,sort_keys=True,separators=(",",":"),
        allow_nan=False
    ).encode("utf8")).hexdigest()
    return w,{
        "source_m434_train_seed_start":plan.seed_start,
        "source_m434_train_seed_count":plan.train_seeds,
        "source_m434_holdout_seed_count":plan.holdout_seeds,
        "source_m434_seed_end_exclusive":plan.seed_start+plan.total,
        "model_sha256":digest,
        "train_legal_action_points":fresh["all_legal_train_action_points"],
        "trained_original_shuffle_clusters":
            fresh["train_seed_clusters_with_legal_checkpoints"],
        "online_promotion_allowed":False,
    }


class FrozenShadowAgent:
    """Same as challenge except own-view minimum-shanten discard selection.

    No game/other hands/future wall API can be supplied to this wrapper.
    The intentionally unique experimental level prevents existing score
    attribution from claiming this is the live challenge policy.
    """

    def __init__(self, *, seed: int, seat: int,
                 weights: tuple[float,...]|None,
                  capture_diagnostics:bool=False,
                 minimum_ukeire_guard:bool=False) -> None:
        if type(seed) is not int or not 0<=seed<2**32 or (
            type(seat) is not int or seat not in range(4)
        ):
            raise ValueError("invalid shadow agent seat/seed")
        if weights is not None and (
            type(weights) is not tuple or
            len(weights)!=len(FEATURE_NAMES) or
            any(type(v) not in (int,float) or not isfinite(v) or
                abs(v)>0.2 for v in weights)
        ):
            raise ValueError("invalid bounded frozen shadow weights")
        self.level=SHADOW_LEVEL
        self.seat=seat
        self.weights=weights
        self._delegate=MahjongAgent("challenge",seed=seed,seat=seat)
        self.considered_discards=0
        self.override_count=0
        if type(capture_diagnostics) is not bool:
            raise ValueError("capture_diagnostics must be boolean")
        self.capture_diagnostics=capture_diagnostics
        if type(minimum_ukeire_guard) is not bool:
            raise ValueError("minimum_ukeire_guard must be boolean")
        self.minimum_ukeire_guard=minimum_ukeire_guard
        self.rejected_ukeire_regressions=0
        self.private_actor_discard_trace:list[dict[str,Any]]=[]
        self.last_choice:dict[str,Any]|None=None

    def exchange(self,view:Mapping[str,Any])->list[str]:
        return self._delegate.exchange(view)

    def missing(self,view:Mapping[str,Any])->str:
        return self._delegate.missing(view)

    def response(self,view:Mapping[str,Any],*,rob:bool=False)->str:
        return self._delegate.response(view,rob=rob)

    def kong(self,view:Mapping[str,Any])->dict[str,str]|None:
        return self._delegate.kong(view)

    def discard(self,view:Mapping[str,Any])->str:
        chosen=self._choose_discard(view)
        if self.capture_diagnostics:
            if self.last_choice is None:
                raise RuntimeError("discard analysis unexpectedly missing")
            self.private_actor_discard_trace.append({
                "decision_ordinal":self.considered_discards,
                **self.last_choice,
                "chosen_discard":chosen,
            })
        return chosen

    def _choose_discard(self,view:Mapping[str,Any])->str:
        # Authoritative delegate first, preserving all established
        # deterministic ties/forced missing-suit policy as baseline.
        original=self._delegate.discard(view)
        self.considered_discards+=1
        self.last_choice={
            "overrode":False,"kept_minimum_shanten":True,
            "baseline_discard":original,
            "reason":"no_better_frozen_margin",
            "model_margin":0.,
        }
        if self.weights is None or not any(self.weights):
            self.last_choice["reason"]="no_frozen_weights"
            return original
        oracle=analyze_discards(
            view["hand"],view["own_melds"],
            missing_suit=view["missing_suits"][view["seat"]],
            visible_tiles=visible_tiles(view)
        )
        if oracle["status"]!="choose_discard":
            self.last_choice["reason"]="no_eligible_discard_oracle"
            return original
        minimum=oracle["minimum_shanten"]
        candidates=[
            c for c in oracle["candidates"] if c["shanten"]==minimum
        ]
        if original not in {c["discard"] for c in candidates}:
            raise RuntimeError("live challenge cut outside minimum shanten")
        if len(candidates)<2:
            self.last_choice["reason"]="only_one_minimum_shanten_cut"
            return original
        base=next(c for c in candidates if c["discard"]==original)
        base_x=_candidate_features(base)
        self.last_choice.update({
            "minimum_shanten":minimum,
            "baseline_effective_tile_count":base["effective_tile_count"],
            "baseline_next_draw_probability":base["next_draw_probability"],
            "baseline_effective_types_count":len(base["effective_types"]),
            "eligible_minimum_shanten_cut_count":len(candidates),
        })
        scored=[]
        for option in candidates:
            tile=option["discard"]
            if tile==original:
                continue
            x=_candidate_features(option)
            margin=sum(
                weight*(a-b) for a,b,weight
                in zip(x,base_x,self.weights)
            )
            # Bound against machine-epsilon-only changes; all candidate cuts
            # are legal and retain exactly the original structural shanten.
            if margin>1e-9:
                scored.append((margin,tile))
        if not scored:
            return original
        scored.sort(key=lambda r:(-r[0],r[1]))
        selected=scored[0][1]
        selected_row=next(c for c in candidates if c["discard"]==selected)
        if selected not in view["hand"]:
            raise RuntimeError("experimental shadow tried to cut unseen tile")
        if (self.minimum_ukeire_guard and
                selected_row["effective_tile_count"]<base["effective_tile_count"]):
            self.rejected_ukeire_regressions+=1
            self.last_choice["reason"]="blocked_lower_effective_tiles"
            return original
        self.override_count+=1
        self.last_choice.update({
            "overrode":True,
            "reason":"positive_frozen_margin",
            "model_margin":scored[0][0],
            "chosen_effective_tile_count":selected_row["effective_tile_count"],
            "chosen_next_draw_probability":selected_row["next_draw_probability"],
            "chosen_effective_types_count":len(selected_row["effective_types"]),
        })
        return selected


def _finish_real_full_game(seed:int, candidate_seat:int|None,
                           weights:tuple[float,...]|None,
                           *,capture_diagnostics:bool=False,
                           minimum_ukeire_guard:bool=False) -> dict[str,Any]:
    if (type(seed) is not int or not 0<=seed<2**32 or
            (candidate_seat is not None and (
                type(candidate_seat) is not int or candidate_seat not in range(4)
            ))):
        raise ValueError("bad frozen comparison seed or seat")
    game=FourPlayerOpening(
        seed,kong_base=KONG_BASE,legacy_bugang_cash=False
    )
    agents=_agents(seed)
    shadow=None
    if candidate_seat is not None:
        shadow=FrozenShadowAgent(
            seed=seed,seat=candidate_seat,weights=weights,
            capture_diagnostics=capture_diagnostics,
            minimum_ukeire_guard=minimum_ukeire_guard,
        )
        agents[candidate_seat]=shadow
    frames=[]
    _opening(game,agents,frames)
    trace=[]
    durations=defaultdict(list)
    for _ in range(MAX_ACTIONS):
        if game.phase in ("finished","wall_exhausted"):
            break
        _take_action(game,agents,trace,durations)
        if len(trace)>4:
            trace.clear()
    else:
        raise RuntimeError("shadow real match exceeded complete action budget")
    payouts=[_ledger(game,s) for s in range(4)]
    vals=[x["official_net"] for x in payouts]
    if (sum(vals)!=0 or
            sum(x["win_points"] for x in payouts)!=0 or
            sum(x["kong_points"] for x in payouts)!=0 or
            sum(x["exhaustive_points"] for x in payouts)!=0):
        raise RuntimeError("shadow terminal authoritative balances not zero-sum")
    return {
        "phase":game.phase,
        "official_net_by_seat":vals,
        "win_points_by_seat":[x["win_points"] for x in payouts],
        "kong_points_by_seat":[x["kong_points"] for x in payouts],
        "exhaustive_points_by_seat":[x["exhaustive_points"] for x in payouts],
        "physical_tiles":108,
        "shadow_discard_decisions":(
            shadow.considered_discards if shadow else 0),
        "shadow_override_count":(
            shadow.override_count if shadow else 0),
        **({"private_actor_discard_trace":shadow.private_actor_discard_trace}
           if shadow is not None and capture_diagnostics else {}),
        **({"shadow_guard_blocked_count":shadow.rejected_ukeire_regressions}
           if shadow is not None and minimum_ukeire_guard else {}),
    }


def evaluate_one_seed(seed:int,
                      weights:tuple[float,...]|None,
                      *,capture_diagnostics:bool=False) -> dict[str,Any]:
    """Five real complete games share ONE natural shuffle, NOT five samples."""
    baseline=_finish_real_full_game(seed,None,weights)
    comparison=[]
    for seat in range(4):
        live=_finish_real_full_game(
            seed,seat,weights,capture_diagnostics=capture_diagnostics
        )
        original=baseline["official_net_by_seat"][seat]
        after=live["official_net_by_seat"][seat]
        comparison.append({
            "seat":seat,
            "challenge_baseline_official_net":original,
            "shadow_official_net":after,
            "delta_shadow_minus_challenge":after-original,
            "shadow_discard_decisions":live["shadow_discard_decisions"],
            "shadow_override_count":live["shadow_override_count"],
            **({"private_actor_discard_trace":live["private_actor_discard_trace"]}
               if capture_diagnostics else {}),
            "challenge_baseline_game_phase":baseline["phase"],
            "shadow_game_phase":live["phase"],
            "real_win_delta":(
                live["win_points_by_seat"][seat]-
                baseline["win_points_by_seat"][seat]),
            "real_kong_delta":(
                live["kong_points_by_seat"][seat]-
                baseline["kong_points_by_seat"][seat]),
            "real_exhaustive_delta":(
                live["exhaustive_points_by_seat"][seat]-
                baseline["exhaustive_points_by_seat"][seat]),
        })
        if (comparison[-1]["delta_shadow_minus_challenge"]!=
                sum(comparison[-1][k] for k in (
                    "real_win_delta","real_kong_delta",
                    "real_exhaustive_delta"
                ))):
            raise RuntimeError("unreconciled candidate true terminal score")
    return {
        "private_evaluation_shuffle_seed":seed,
        "seat_rotation_results":comparison,
        "original_natural_shuffle_seed_is_one_statistical_cluster":True,
        "complete_authoritative_games":5,
        "same_opening_seed_per_comparison":True,
        "no_real_skill_claim":True,
    }



# M4.37: interruption-safe immutable per-original-shuffle result shards.
# The SHA below catches accidental truncation and inconsistent edits; it is
# NOT a cryptographic signature against an adversary who controls this folder.
SHARD_PROTOCOL="m437_frozen_shadow_resumable_seed_v1"
SHARD_DIR="PRIVATE_eval_seed_clusters"


def _paired_digest(case:dict[str,Any]) -> str:
    raw=json.dumps(case,sort_keys=True,separators=(",",":"),
                   ensure_ascii=False,allow_nan=False)
    return sha256(raw.encode("utf8")).hexdigest()


def _audit_paired_case(case:dict[str,Any],seed:int) -> None:
    """Reject a partial, wrong-seed or non-reconciled finished comparison."""
    if (type(case) is not dict or
            type(case.get("private_evaluation_shuffle_seed")) is not int or
            case["private_evaluation_shuffle_seed"]!=seed or
            case.get("complete_authoritative_games")!=5 or
            case.get("original_natural_shuffle_seed_is_one_statistical_cluster") is not True or
            case.get("same_opening_seed_per_comparison") is not True or
            case.get("no_real_skill_claim") is not True):
        raise ValueError("incomplete or mismatched paired shuffle result")
    rows=case.get("seat_rotation_results")
    if type(rows) is not list or len(rows)!=4:
        raise ValueError("paired result must contain all four rotated seats")
    for seat,row in enumerate(rows):
        if type(row) is not dict or type(row.get("seat")) is not int or row["seat"]!=seat:
            raise ValueError("wrong or repeated paired evaluation seat")
        names=("challenge_baseline_official_net","shadow_official_net",
               "delta_shadow_minus_challenge","shadow_discard_decisions",
               "shadow_override_count","real_win_delta","real_kong_delta",
               "real_exhaustive_delta")
        if any(type(row.get(k)) is not int for k in names):
            raise ValueError("invalid true official comparison ledger fields")
        if (row["shadow_discard_decisions"]<0 or
                not 0<=row["shadow_override_count"]<=row["shadow_discard_decisions"] or
                row["shadow_official_net"]-row["challenge_baseline_official_net"]!=
                    row["delta_shadow_minus_challenge"] or
                row["delta_shadow_minus_challenge"]!=
                    sum(row[k] for k in ("real_win_delta","real_kong_delta",
                                         "real_exhaustive_delta")) or
                row.get("challenge_baseline_game_phase") not in ("finished","wall_exhausted") or
                row.get("shadow_game_phase") not in ("finished","wall_exhausted")):
            raise ValueError("unbalanced, unfinished or impossible saved paired game")
        if row["shadow_override_count"]==0 and row["delta_shadow_minus_challenge"]!=0:
            raise ValueError("unchanged candidate must exactly match live baseline")


def _cluster_path(output:Path,index:int) -> Path:
    return output/SHARD_DIR/f"index-{index:08d}.json"


def _resume_cases(output:Path,seeds:int,seed_start:int,
                  model_hash:str) -> dict[int,dict[str,Any]]:
    """Read every completed shard BEFORE launching any new CPU-heavy game."""
    folder=output/SHARD_DIR
    if not folder.exists():
        return {}
    if not folder.is_dir():
        raise ValueError("private resume shard path is not a directory")
    loaded={}
    for path in folder.iterdir():
        # A crash can leave an incomplete atomic temp. Never load it.
        if ".tmp-" in path.name and path.is_file():
            continue
        if (not path.is_file() or len(path.name)!=19 or
                not path.name.startswith("index-") or
                not path.name.endswith(".json") or
                not path.name[6:14].isdigit()):
            raise ValueError("unexpected file in private resume cluster folder")
        index=int(path.name[6:14])
        if not 0<=index<seeds or index in loaded:
            raise ValueError("out-of-plan or duplicate evaluation seed shard")
        envelope=_get_json(path)
        if (set(envelope)!={"protocol","index","model_sha256",
                            "sha256_paired_seed","private_case"} or
                envelope["protocol"]!=SHARD_PROTOCOL or
                type(envelope["index"]) is not int or envelope["index"]!=index or
                envelope["model_sha256"]!=model_hash or
                type(envelope["private_case"]) is not dict):
            raise ValueError("resume shard comes from another benchmark plan/model")
        case=envelope["private_case"]
        _audit_paired_case(case,seed_start+index)
        if envelope["sha256_paired_seed"]!=_paired_digest(case):
            raise ValueError("private paired seed shard checksum mismatch")
        loaded[index]=case
    return loaded


def _save_cluster(output:Path,index:int,case:dict[str,Any],
                  model_hash:str) -> None:
    _audit_paired_case(case,case["private_evaluation_shuffle_seed"])
    _write_atomic(_cluster_path(output,index),{
        "protocol":SHARD_PROTOCOL,
        "index":index,
        "model_sha256":model_hash,
        "sha256_paired_seed":_paired_digest(case),
        "private_case":case,
    })


def evaluate_frozen_shadow(
    *,training_dir:Path,seed_start:int,seeds:int,
    out_dir:Path,resume:bool=False
) -> dict[str,Any]:
    if type(resume) is not bool:
        raise ValueError("resume must be a boolean")
    if (type(seed_start) is not int or type(seeds) is not int or
            not 0<=seed_start<2**32 or
            not 1<=seeds<=MAX_EVAL_SEEDS or
            seed_start+seeds>2**32):
        raise ValueError("evaluation seeds must be bounded positive uint32")
    output=_private_location(Path(out_dir))
    training=_private_location(Path(training_dir))
    if output==training:
        raise ValueError("evaluation output must differ from private training dir")
    weights,provenance=load_frozen_local_model(training)
    prior_start=provenance["source_m434_train_seed_start"]
    prior_end=provenance["source_m434_seed_end_exclusive"]
    if not (seed_start+seeds<=prior_start or seed_start>=prior_end):
        raise ValueError("evaluation shuffles overlap original TRAIN or holdout")
    if not resume and output.exists() and any(output.iterdir()):
        raise ValueError("evaluation output must be new/empty: no silent overwrite")
    if resume and (not output.is_dir() or not
                   (output/"PRIVATE_frozen_benchmark_plan.json").is_file()):
        raise ValueError("resume requires an existing M4.37 private benchmark plan")
    if not resume:
        output.mkdir(parents=True,exist_ok=True)
    source={
        "protocol":PROTOCOL,
        "resumable_shards_protocol":SHARD_PROTOCOL,
        "private_source_training_directory":str(training),
        "private_frozen_model_sha256":provenance["model_sha256"],
        "private_evaluation_seed_start":seed_start,
        "private_eval_original_shuffle_count":seeds,
        "training_from_original_only":True,
        "online_policy_unchanged":True,
    }
    plan_path=output/"PRIVATE_frozen_benchmark_plan.json"
    if resume:
        if _get_json(plan_path)!=source:
            raise ValueError("resume plan differs: model, seeds or training folder changed")
        allowed={plan_path.name,SHARD_DIR,
                 "PRIVATE_four_seat_paired_matches.jsonl.gz",
                 "safe_four_seat_shadow_summary.json"}
        if any(p.name not in allowed and ".tmp-" not in p.name
               for p in output.iterdir()):
            raise ValueError("unexpected files in evaluation resume directory")
        completed=_resume_cases(
            output,seeds,seed_start,provenance["model_sha256"]
        )
        # Final reports mean a previous run had reached the aggregation
        # phase. Missing saved clusters in that state are corruption, not
        # unfinished work: never silently recompute/overwrite past outcomes.
        has_final=(output/"PRIVATE_four_seat_paired_matches.jsonl.gz").exists() or (
            output/"safe_four_seat_shadow_summary.json").exists()
        if has_final and len(completed)!=seeds:
            raise ValueError("final report present but complete seed shards missing")
    else:
        _write_atomic(plan_path,source)
        completed={}
    (output/SHARD_DIR).mkdir(exist_ok=True)
    values=[]
    wins=[0]*4
    deltas_by_seat=[[] for _ in range(4)]
    overrides=0
    considered=0
    for offset in range(seeds):
        game=completed.get(offset)
        if game is None:
            game=evaluate_one_seed(seed_start+offset,weights)
            _audit_paired_case(game,seed_start+offset)
            _save_cluster(output,offset,game,provenance["model_sha256"])
        values.append(game)
        for row in game["seat_rotation_results"]:
            seat=row["seat"]
            delta=row["delta_shadow_minus_challenge"]
            deltas_by_seat[seat].append(delta)
            wins[seat]+=int(delta>0)
            overrides+=row["shadow_override_count"]
            considered+=row["shadow_discard_decisions"]
    _write_private_jsonl(
        output/"PRIVATE_four_seat_paired_matches.jsonl.gz",values
    )
    seed_cluster_means=[
        mean(x["delta_shadow_minus_challenge"]
             for x in g["seat_rotation_results"]) for g in values
    ]
    summary={
        "protocol":PROTOCOL,
        "actual_real_complete_games":5*seeds,
        "independent_initial_shuffle_seed_clusters":seeds,
        "seat_rotations_per_original_seed":4,
        "baseline_games":seeds,
        "experimental_shadow_games":4*seeds,
        "interruption_safe_completed_seed_shards":seeds,
        "reused_prior_completed_seed_shards":len(completed),
        "partial_or_corrupt_shards_never_trusted":True,
        "official_score_ledger_reconciled":True,
        "candidate_discard_opportunities":considered,
        "candidate_legal_minimum_shanten_overrides":overrides,
        "candidate_no_change_to_live_challenge_agent":True,
        "trained_original_shuffle_clusters":
            provenance["trained_original_shuffle_clusters"],
        "trained_on_only_original_training_split":True,
        "evaluation_shuffles_disjoint_from_train_and_original_holdout":True,
        "candidate_model_had_frozen_weights":weights is not None,
        "per_seat_conditional_net_delta_means":[
            round(mean(x),5) for x in deltas_by_seat
        ],
        "seat_rotated_seed_cluster_mean_delta_points":
            round(mean(seed_cluster_means),5),
        "seed_clusters_with_positive_rotated_mean":
            sum(v>0 for v in seed_cluster_means),
        "seed_clusters_with_negative_rotated_mean":
            sum(v<0 for v in seed_cluster_means),
        "seed_clusters_with_zero_rotated_mean":
            sum(v==0 for v in seed_cluster_means),
        "per_seat_positive_delta_counts":wins,
        "enough_independent_seeds_for_exploratory_comparison":
            seeds>=MIN_INDEPENDENT_SEEDS_FOR_EXPLORATORY_MEAN,
        "no_statistical_significance_claim":True,
        "no_generalization_or_strength_proven":True,
        "no_change_to_online_ai":True,
        "no_hidden_tiles_or_true_seed_in_public_summary":True,
        "two_wall_training_method_not_calibrated_ev":True,
    }
    _write_atomic(output/"safe_four_seat_shadow_summary.json",summary)
    return summary


def _write_atomic(path:Path,data:dict[str,Any])->None:
    from .ai_selfplay_local_batch import _atomic_json
    _atomic_json(path,data)


def _write_private_jsonl(path:Path,records:list[dict[str,Any]])->None:
    import gzip
    import os
    import uuid
    tmp=path.with_name(path.name+".tmp-"+uuid.uuid4().hex)
    try:
        with gzip.open(tmp,"wt",encoding="utf8") as output:
            for row in records:
                output.write(json.dumps(row,ensure_ascii=False,
                                        allow_nan=False)+"\n")
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)
