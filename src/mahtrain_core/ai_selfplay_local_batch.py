"""M4.34 local CPU-parallel, crash-resumable REAL four-challenge self-play.

One immutable original shuffle seed == ONE statistical cluster. A worker runs
the unchanged M4.32 true natural game and its physically legal paired
terminal rollouts. This module only improves LOCAL scheduling/persistence,
dataset coverage and transparent disagreement diagnostics.

Never install an offline learner as online MahjongAgent. All records stay
under an ignored private directory or OUTSIDE this repository. CI publishes
only aggregate summaries. No GPU, PyTorch, cloud service or pip dependency.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import ExitStack
from dataclasses import dataclass
import gzip
import hashlib
import json
from math import isfinite
import os
from pathlib import Path
from statistics import mean
import uuid
from typing import Any, Callable, Iterator

from .ai_selfplay_cohort_audit import _check_private_cluster
from .ai_selfplay_learning import _assert_public
from .ai_selfplay_multicheckpoint import (
    PROTOCOL as SOURCE_PROTOCOL, MODEL_PROTOCOL, FEATURE_NAMES,
    _safe_seed_labels, evaluate_unseen_seed_clusters, run_natural_seed,
)

PROTOCOL = "m434_local_resumable_independent_seed_clusters_v1"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path("data/selfplay/m434-local")
MAX_TOTAL_SEEDS = 100000
MAX_WORKERS = 16
MAX_CHECKPOINTS = 2


@dataclass(frozen=True)
class BatchPlan:
    seed_start: int
    train_seeds: int
    holdout_seeds: int
    max_checkpoints: int = 2

    def __post_init__(self) -> None:
        values = (self.seed_start, self.train_seeds, self.holdout_seeds,
                  self.max_checkpoints)
        if any(type(v) is not int for v in values):
            raise ValueError("seed plan must use integers, never bool or floats")
        if (not 0 <= self.seed_start < 2**32 or
                not 1 <= self.train_seeds or not 1 <= self.holdout_seeds or
                not 1 <= self.train_seeds+self.holdout_seeds <= MAX_TOTAL_SEEDS
                or self.seed_start+self.train_seeds+self.holdout_seeds > 2**32
                or not 1 <= self.max_checkpoints <= MAX_CHECKPOINTS):
            raise ValueError("invalid bounded, independent natural shuffle plan")

    @property
    def total(self) -> int:
        return self.train_seeds+self.holdout_seeds

    def split(self, index: int) -> str:
        if type(index) is not int or not 0 <= index < self.total:
            raise ValueError("outside planned independent shuffle cohort")
        return "train" if index < self.train_seeds else "holdout"

    def as_dict(self) -> dict[str,Any]:
        return {
            "protocol":PROTOCOL,
            "source_protocol":SOURCE_PROTOCOL,
            "seed_start":self.seed_start,
            "train_seeds":self.train_seeds,
            "holdout_seeds":self.holdout_seeds,
            "max_checkpoints":self.max_checkpoints,
            "independence_unit":"original_natural_shuffle_seed",
            "online_policy_changed":False,
        }


def _private_location(outdir: Path) -> Path:
    out = Path(outdir).expanduser().resolve()
    if out==ROOT or ROOT in out.parents:
        protected=ROOT/"data"/"selfplay"
        if out!=protected and protected not in out.parents:
            raise ValueError(
                "private self-play output inside repository MUST be in "
                "gitignored data/selfplay; otherwise choose a path outside repo"
            )
    return out


def _manifest(plan: BatchPlan) -> dict[str,Any]:
    values=plan.as_dict()
    raw=json.dumps(values,sort_keys=True,separators=(",",":"))
    return {
        "private_reproduction_plan":values,
        "sha256_plan":hashlib.sha256(raw.encode("utf8")).hexdigest(),
        "version":1,
    }


def _atomic_json(path: Path, value: dict[str,Any]) -> None:
    if not path.parent.is_dir():
        raise ValueError("output directory not initialized")
    tmp=path.with_name(path.name+f".tmp-{os.getpid()}-{uuid.uuid4().hex}")
    try:
        with tmp.open("w",encoding="utf-8",newline="\n") as handle:
            json.dump(value,handle,ensure_ascii=False,allow_nan=False,
                      sort_keys=True,separators=(",",":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)


def _get_json(path: Path) -> dict[str,Any]:
    with path.open("r",encoding="utf8") as f:
        value=json.load(f)
    if type(value) is not dict:
        raise ValueError("invalid JSON dict in saved private shard")
    return value


def _worker(index: int, seed: int, split: str, quota: int) -> dict[str,Any]:
    # This top-level pure dispatch is Windows spawn picklable. Each child
    # independently owns ONLY its current game's true hidden tile state.
    public, private=run_natural_seed(seed,max_checkpoints=quota)
    public["game_id"]=f"game-{index:08d}"  # never leak shuffle seed in ID
    _assert_public(public)
    return {
        "protocol":PROTOCOL, "index":index,"split":split,
        "source_protocol":SOURCE_PROTOCOL, "private_shuffle_seed":seed,
        "public":public,"actor_private":private,
    }


def _audit_record(record: dict[str,Any], plan: BatchPlan,
                  index: int) -> dict[str,Any]:
    expected=plan.seed_start+index
    split=plan.split(index)
    if (type(record) is not dict or record.get("protocol")!=PROTOCOL or
            record.get("source_protocol")!=SOURCE_PROTOCOL or
            type(record.get("index")) is not int or record["index"]!=index or
            record.get("split")!=split or
            type(record.get("private_shuffle_seed")) is not int or
            record["private_shuffle_seed"]!=expected):
        raise ValueError("wrong, duplicate or corrupted private seed shard")
    pub=record.get("public")
    actor=record.get("actor_private")
    if type(pub) is not dict or type(actor) is not dict:
        raise ValueError("missing authorized actor view / redacted public tape")
    _assert_public(pub)
    balances=pub.get("official_final_balances")
    if (pub.get("protocol")!=SOURCE_PROTOCOL or
            pub.get("game_id")!=f"game-{index:08d}" or
            pub.get("players")!=["challenge"]*4 or
            pub.get("rule_set")!="current_m423" or
            pub.get("terminal_phase") not in ("finished","wall_exhausted") or
            type(balances) is not list or len(balances)!=4 or
            any(type(v) is not int for v in balances) or sum(balances)!=0 or
            type(pub.get("public_frames")) is not list or
            not pub["public_frames"] or
            pub["public_frames"][-1]["board"]["phase"]!=pub["terminal_phase"]):
        raise ValueError("invalid official complete natural four-challenge game")
    return _check_private_cluster(actor,expected,quota=plan.max_checkpoints)


def _shard(outdir: Path,index: int) -> Path:
    return outdir/"PRIVATE_seed_shards"/f"index-{index:08d}.json"


def _prepare(plan: BatchPlan,outdir: Path,resume: bool) -> None:
    if type(resume) is not bool:
        raise ValueError("resume must be true or false")
    expected=_manifest(plan)
    manifest=outdir/"PRIVATE_plan.json"
    if manifest.exists():
        if not resume:
            raise ValueError(
                "private plan exists: use --resume only for EXACT SAME plan"
            )
        if _get_json(manifest)!=expected:
            raise ValueError(
                "existing private plan differs: refusing cross-plan mixing"
            )
    else:
        if resume and outdir.exists() and any(outdir.iterdir()):
            raise ValueError("missing private manifest; cannot safely resume")
        if outdir.exists() and any(outdir.iterdir()):
            raise ValueError("output directory not empty, choose new directory")
        outdir.mkdir(parents=True,exist_ok=True)
        _atomic_json(manifest,expected)
    (outdir/"PRIVATE_seed_shards").mkdir(exist_ok=True)


def _existing_or_missing(plan: BatchPlan,outdir: Path) -> Iterator[int]:
    # Existing shards must pass FULL official terminal/private audit. Do not
    # silently overwrite missing/garbled cases or shuffle split identity.
    for i in range(plan.total):
        p=_shard(outdir,i)
        if p.exists():
            _audit_record(_get_json(p),plan,i)
        else:
            yield i


def _run_parallel(plan: BatchPlan,outdir: Path,workers: int,
                  indices: Iterator[int],
                  progress: Callable[[int,int],None] | None) -> int:
    total_done=0
    if workers==1:
        for i in indices:
            record=_worker(i,plan.seed_start+i,plan.split(i),
                           plan.max_checkpoints)
            _audit_record(record,plan,i)
            _atomic_json(_shard(outdir,i),record)
            total_done+=1
            if progress is not None:
                progress(total_done,plan.total)
        return total_done
    # Bound in-flight futures to <= 2*workers; never enqueue 100000 copies
    # of full-game work at once. Shards are saved by main parent process only.
    with ProcessPoolExecutor(max_workers=workers) as executor:
        active={}
        def top_up() -> None:
            while len(active)<2*workers:
                try:
                    i=next(indices)
                except StopIteration:
                    return
                future=executor.submit(
                    _worker,i,plan.seed_start+i,plan.split(i),
                    plan.max_checkpoints,
                )
                active[future]=i
        top_up()
        while active:
            completed,_=wait(tuple(active),return_when=FIRST_COMPLETED)
            for future in completed:
                i=active.pop(future)
                record=future.result()
                _audit_record(record,plan,i)
                _atomic_json(_shard(outdir,i),record)
                total_done+=1
                if progress is not None:
                    progress(total_done,plan.total)
            top_up()
    return total_done


def _limited_model(clusters: Iterator[dict[str,Any]],
                   count: int) -> dict[str,Any]:
    # Exactly the M4.32 seed-first weighting, implemented with constant
    # accumulator space to support thousands of original shuffled seeds.
    sums=[0.0 for _ in FEATURE_NAMES]
    groups=0
    labels=0
    for actor in clusters:
        examples=_safe_seed_labels(actor)
        labels+=len(examples)
        if examples:
            for i in range(len(sums)):
                sums[i]+=mean(x[i]*r for x,r in examples)
            groups+=1
    common={
        "protocol":MODEL_PROTOCOL,"features":list(FEATURE_NAMES),
        "seed_clusters_seen":count,
        "independent_seed_clusters_with_labels":groups,
        "total_action_labels":labels,
        "online_promotion_allowed":False,
    }
    if not groups:
        return {**common,"status":"no_consistent_action_labels","weights":None}
    return {
        **common,"status":"offline_consensus_weighted_diagnostic",
        "weights":[round(max(-.2,min(.2,s/groups)),7) for s in sums],
        "not_calibrated_action_q":True,
    }


def _atomic_stream_outputs(
    plan: BatchPlan,outdir: Path,model: dict[str,Any]
) -> dict[str,Any]:
    # Full outputs are generated only when ALL natural seed shards validated.
    # Stream in index order, never materialize every public replay in RAM.
    paths={
        "public":outdir/"public_four_challenge_replays.jsonl.gz",
        "train":outdir/"PRIVATE_actor_train.jsonl.gz",
        "holdout":outdir/"PRIVATE_actor_holdout.jsonl.gz",
        "diagnostics":outdir/"PRIVATE_holdout_diagnostics.jsonl.gz",
    }
    temporary={
        k:v.with_name(v.name+".incomplete-"+uuid.uuid4().hex)
        for k,v in paths.items()
    }
    summary={
        "protocol":PROTOCOL,
        "natural_original_seed_clusters":plan.total,
        "natural_full_games":plan.total,
        "train_independent_seed_clusters":plan.train_seeds,
        "holdout_independent_seed_clusters":plan.holdout_seeds,
        "terminal_paired_branch_games":0,
        "total_true_completed_games":0,
        "natural_legal_decision_points":0,
        "training_legal_decision_points":0,
        "holdout_legal_decision_points":0,
        "training_consensus_labels":0,
        "holdout_consensus_labels":0,
        "training_seed_clusters_with_labels":0,
        "holdout_seed_clusters_with_labels":0,
        "two_wall_mixed_or_tied_points":0,
        "paired_world_abs_difference_sum":0,
        "paired_world_abs_difference_max":0,
        "paired_world_delta_count":0,
        "holdout_scored_directions":0,
        "holdout_correct_directions":0,
        "holdout_accuracy_if_at_least_five":None,
        "heldout_accuracy_status":"insufficient_scored_consensus_decisions",
        "model_status":model["status"],
        "model_training_action_labels":model["total_action_labels"],
        "model_training_independent_clusters":
            model["independent_seed_clusters_with_labels"],
        "online_policy_promoted":False,
        "proof_of_increased_ai_strength":False,
        "uncertainty_estimate_valid_for_population":False,
        "private_shuffle_seed_exported":False,
        "independence_unit":"original_natural_shuffle_seed",
    }
    try:
        with ExitStack() as stack:
            outputs={
                k:stack.enter_context(gzip.open(
                    path,"wt",encoding="utf8"
                )) for k,path in temporary.items()
            }
            for i in range(plan.total):
                record=_get_json(_shard(outdir,i))
                audited=_audit_record(record,plan,i)
                split=plan.split(i)
                actor=record["actor_private"]
                output=outputs[split]
                outputs["public"].write(json.dumps(
                    record["public"],ensure_ascii=False,allow_nan=False
                )+"\n")
                output.write(json.dumps(
                    actor,ensure_ascii=False,allow_nan=False
                )+"\n")
                summary["terminal_paired_branch_games"]+=audited[
                    "terminal_counterfactual_games"
                ]
                decisions=audited["natural_decisions"]
                labels=audited["strict_consensus_labels"]
                summary["natural_legal_decision_points"]+=decisions
                summary[f"{split if split=='train' else 'holdout'}ing_legal_decision_points" if split=="train" else "holdout_legal_decision_points"]+=decisions
                summary["training_consensus_labels" if split=="train"
                        else "holdout_consensus_labels"]+=labels
                if labels:
                    summary["training_seed_clusters_with_labels" if split=="train"
                            else "holdout_seed_clusters_with_labels"]+=1
                summary["two_wall_mixed_or_tied_points"]+=audited[
                    "direction_counts"]["mixed_or_tied_world_outcomes"]
                for item in actor["checkpoints"]:
                    worlds=item["physical_worlds"]
                    if len(worlds)!=2:
                        raise ValueError("expected two physical unknown wall orders")
                    d0=worlds[0]["alternative_minus_original"]["official_net"]
                    d1=worlds[1]["alternative_minus_original"]["official_net"]
                    abs_gap=abs(d0-d1)
                    summary["paired_world_abs_difference_sum"]+=abs_gap
                    summary["paired_world_abs_difference_max"]=max(
                        summary["paired_world_abs_difference_max"],abs_gap
                    )
                    summary["paired_world_delta_count"]+=1
                if split=="holdout":
                    diagnostic=evaluate_unseen_seed_clusters([actor],model)
                    data=diagnostic["seed_report"][0]
                    outputs["diagnostics"].write(json.dumps(
                        data,ensure_ascii=False,allow_nan=False
                    )+"\n")
                    summary["holdout_scored_directions"]+=data[
                        "decisive_evaluations"]
                    summary["holdout_correct_directions"]+=data[
                        "correct_decisive_labels"]
        for k,p in paths.items():
            os.replace(temporary[k],p)
    finally:
        for path in temporary.values():
            path.unlink(missing_ok=True)
    summary["total_true_completed_games"]=plan.total+summary[
        "terminal_paired_branch_games"]
    n=summary["paired_world_delta_count"]
    summary["paired_world_mean_abs_gap_points"]=(
        round(summary["paired_world_abs_difference_sum"]/n,5)
        if n else None
    )
    scored=summary["holdout_scored_directions"]
    if scored>=5:
        summary["holdout_accuracy_if_at_least_five"]=round(
            summary["holdout_correct_directions"]/scored,5
        )
        summary["heldout_accuracy_status"]=(
            "exploratory_only_not_strength_proof"
        )
    return summary


def run_local_batch(
    plan: BatchPlan,
    outdir: Path = DEFAULT_OUTPUT,
    *,
    workers: int = 1,
    resume: bool = False,
    progress: Callable[[int,int],None] | None = None,
) -> dict[str,Any]:
    if type(plan) is not BatchPlan:
        raise ValueError("requires a validated immutable batch plan")
    if type(workers) is not int or not 1 <= workers <= MAX_WORKERS:
        raise ValueError("workers must be an integer from 1 to 16")
    destination=_private_location(Path(outdir))
    _prepare(plan,destination,resume)

    _run_parallel(plan,destination,workers,
                  _existing_or_missing(plan,destination),progress)

    def training() -> Iterator[dict[str,Any]]:
        for i in range(plan.train_seeds):
            record=_get_json(_shard(destination,i))
            _audit_record(record,plan,i)
            yield record["actor_private"]

    model=_limited_model(training(),plan.train_seeds)
    summary=_atomic_stream_outputs(plan,destination,model)

    _atomic_json(destination/"PRIVATE_offline_model.json",model)
    _atomic_json(destination/"safe_aggregate_summary.json",summary)
    return summary
