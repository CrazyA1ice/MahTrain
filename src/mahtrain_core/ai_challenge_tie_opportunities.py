"""M4.42: new-shuffle Challenge baseline safe tie-opportunity audit.

No trained policy changes, no candidate rollouts. Inspect ONLY the choices
already calculated by the live Challenge agent from its own normal view.
The full game is genuinely settled by the unmodified rules engine. No
opponent hand, actual future wall, or acting hand is ever persisted.
"""
from __future__ import annotations

from collections import defaultdict
from math import isfinite
from pathlib import Path
from statistics import mean
from typing import Any

from .ai import MahjongAgent
from .ai_selfplay_counterfactual import KONG_BASE, MAX_ACTIONS, _ledger, _opening
from .ai_selfplay_local_batch import _get_json, _private_location
from .ai_shadow_action_diagnostics import (
    MANIFEST as M439_MANIFEST, PROTOCOL as M439_PROTOCOL, _verify_prior_m437,
)
from .ai_shadow_guarded_trial import PLAN as M441_PLAN, PROTOCOL as M441_PROTOCOL
from .ai_shadow_headtohead import (
    MAX_EVAL_SEEDS, _paired_digest, _write_atomic, load_frozen_local_model,
)
from .ai_tournament import _take_action
from .four_player import FourPlayerOpening

PROTOCOL="m442_fresh_original_shuffle_challenge_safe_tie_opportunities_v1"
SHARD_PROTOCOL="m442_one_authoritative_baseline_per_shuffle_v1"
PLAN="PRIVATE_challenge_tie_probe_plan.json"
SHARDS="PRIVATE_challenge_tie_seed_clusters"
SUMMARY="safe_challenge_tie_opportunities.json"
METRICS=(
    "discard_decisions",
    "single_policy_choice_decisions",
    "multichoice_minimum_shanten_decisions",
    "decisions_with_equal_ukeire_alternative",
    "decisions_with_higher_ukeire_alternative",
    "baseline_max_ukeire_decisions",
    "equal_ukeire_alternative_cuts",
    "higher_ukeire_alternative_cuts",
    "equal_ukeire_alternatives_different_score",
    "equal_ukeire_alternatives_different_fan_value",
    "equal_ukeire_alternatives_different_public_pressure",
    "equal_ukeire_alternatives_different_public_risk_index",
)
PER_DECISION_MAX=27  # 27 unique tile kinds; no extra advantage from duplicates.


class ChallengeTieProbe(MahjongAgent):
    """Capture already evaluated legal options without changing choices/RNG."""

    def __init__(self, *,seed:int,seat:int):
        super().__init__("challenge",seed=seed,seat=seat)
        self.totals={key:0 for key in METRICS}

    def discard(self,view):
        baseline=super().discard(view)
        stats=self.totals
        stats["discard_decisions"]+=1
        ranked=self._last_discard_scores
        # Challenge does not rank anything when exactly ONE eligible
        # minimum-shanten cut exists (including forced missing-suit cuts).
        if ranked is None:
            stats["single_policy_choice_decisions"]+=1
            stats["baseline_max_ukeire_decisions"]+=1
            return baseline
        if not isinstance(ranked,list) or len(ranked)<2:
            raise RuntimeError("unexpected Challenge legal scoring candidate set")
        if len({row["discard"] for row in ranked})!=len(ranked):
            raise RuntimeError("repeated candidate tile in Challenge ranking")
        base=next((r for r in ranked if r["discard"]==baseline),None)
        if base is None:
            raise RuntimeError("baseline cut missing from Challenge own-view scores")
        stats["multichoice_minimum_shanten_decisions"]+=1
        value=base["effective_tile_count"]
        better=[r for r in ranked if r["discard"]!=baseline and
                r["effective_tile_count"]>value]
        tied=[r for r in ranked if r["discard"]!=baseline and
              r["effective_tile_count"]==value]
        if not isinstance(value,int) or value<0:
            raise RuntimeError("bad Challenge actor-view effective tile count")
        stats["decisions_with_equal_ukeire_alternative"]+=int(bool(tied))
        stats["decisions_with_higher_ukeire_alternative"]+=int(bool(better))
        stats["baseline_max_ukeire_decisions"]+=int(not better)
        stats["equal_ukeire_alternative_cuts"]+=len(tied)
        stats["higher_ukeire_alternative_cuts"]+=len(better)
        stats["equal_ukeire_alternatives_different_score"]+=sum(
            r["score"]!=base["score"] for r in tied)
        stats["equal_ukeire_alternatives_different_fan_value"]+=sum(
            r["expected_fan_weighted_copies"]!=
            base["expected_fan_weighted_copies"] for r in tied)
        stats["equal_ukeire_alternatives_different_public_pressure"]+=sum(
            r["public_pressure"]!=base["public_pressure"] for r in tied)
        stats["equal_ukeire_alternatives_different_public_risk_index"]+=sum(
            r["table_threat_index"]!=base["table_threat_index"] for r in tied)
        return baseline


def play_one_challenge_baseline(seed:int)->dict[str,Any]:
    if type(seed) is not int or not 0<=seed<2**32:
        raise ValueError("invalid original shuffle seed")
    game=FourPlayerOpening(seed,kong_base=KONG_BASE,legacy_bugang_cash=False)
    agents={s:ChallengeTieProbe(seed=seed,seat=s) for s in range(4)}
    public_frames=[]
    _opening(game,agents,public_frames)
    trace=[]
    durations=defaultdict(list)
    for _ in range(MAX_ACTIONS):
        if game.phase in ("finished","wall_exhausted"):
            break
        _take_action(game,agents,trace,durations)
        if len(trace)>4:
            trace.clear()
    else:
        raise RuntimeError("unsettled challenge baseline exceeded action budget")
    ledger=[_ledger(game,seat) for seat in range(4)]
    if (sum(s["official_net"] for s in ledger)!=0 or
            any(sum(s[key] for s in ledger)!=0
                for key in ("win_points","kong_points","exhaustive_points"))):
        raise RuntimeError("true official benchmark ledger not zero sum")
    return {
        "private_original_shuffle_seed":seed,
        "official_complete_baseline_games":1,
        "terminal_phase":game.phase,
        "official_net_by_seat":[s["official_net"] for s in ledger],
        "per_seat_actor_choice_counts":[dict(agents[s].totals) for s in range(4)],
        "unchanged_live_challenge_choices":True,
        "no_hidden_opponent_hand_or_future_wall_collected":True,
    }


def _verify_case(case:dict[str,Any],seed:int)->None:
    if (type(case) is not dict or
            type(case.get("private_original_shuffle_seed")) is not int or
            case["private_original_shuffle_seed"]!=seed or
            case.get("official_complete_baseline_games")!=1 or
            case.get("terminal_phase") not in ("finished","wall_exhausted") or
            case.get("unchanged_live_challenge_choices") is not True or
            case.get("no_hidden_opponent_hand_or_future_wall_collected") is not True):
        raise ValueError("not a completed unchanged Challenge baseline")
    nets=case.get("official_net_by_seat")
    seats=case.get("per_seat_actor_choice_counts")
    if (type(nets) is not list or len(nets)!=4 or
            any(type(v) is not int for v in nets) or sum(nets)!=0 or
            type(seats) is not list or len(seats)!=4):
        raise ValueError("incomplete four-seat authoritative Challenge results")
    for row in seats:
        if (type(row) is not dict or set(row)!=set(METRICS) or
                any(type(v) is not int or v<0 for v in row.values())):
            raise ValueError("invalid own-view discard metric schema")
        total=row["discard_decisions"]
        multi=row["multichoice_minimum_shanten_decisions"]
        one=row["single_policy_choice_decisions"]
        tie=row["decisions_with_equal_ukeire_alternative"]
        higher=row["decisions_with_higher_ukeire_alternative"]
        if (total!=one+multi or
                not 0<=tie<=multi or not 0<=higher<=multi or
                not one<=row["baseline_max_ukeire_decisions"]<=total or
                row["baseline_max_ukeire_decisions"]!=total-higher or
                not tie<=row["equal_ukeire_alternative_cuts"]<=
                         multi*(PER_DECISION_MAX-1) or
                not higher<=row["higher_ukeire_alternative_cuts"]<=
                           multi*(PER_DECISION_MAX-1) or
                any(row[field]>row["equal_ukeire_alternative_cuts"]
                    for field in (
                        "equal_ukeire_alternatives_different_score",
                        "equal_ukeire_alternatives_different_fan_value",
                        "equal_ukeire_alternatives_different_public_pressure",
                        "equal_ukeire_alternatives_different_public_risk_index",
                    ))):
            raise ValueError("inconsistent or impossible safe tie opportunities")


def _shard_file(folder:Path,i:int)->Path:
    return folder/SHARDS/f"index-{i:08d}.json"


def _saved_cases(root:Path,start:int,n:int,digest:str)->dict[int,dict[str,Any]]:
    folder=root/SHARDS
    if not folder.exists():
        return {}
    if not folder.is_dir():
        raise ValueError("completed seed shard location is not a folder")
    saved={}
    for file in folder.iterdir():
        if file.is_file() and ".tmp-" in file.name:
            continue
        if (not file.is_file() or len(file.name)!=19 or
                not file.name.startswith("index-") or
                not file.name.endswith(".json") or
                not file.name[6:14].isdigit()):
            raise ValueError("unexpected private baseline shard")
        i=int(file.name[6:14])
        if i<0 or i>=n or i in saved:
            raise ValueError("repeated or out-of-plan baseline shuffle")
        env=_get_json(file)
        if (type(env) is not dict or
                set(env)!={"protocol","model_sha256","index",
                           "private_case","sha256_case"} or
                env["protocol"]!=SHARD_PROTOCOL or
                type(env["index"]) is not int or env["index"]!=i or
                env["model_sha256"]!=digest or
                type(env["private_case"]) is not dict):
            raise ValueError("invalid original seed baseline audit envelope")
        case=env["private_case"]
        _verify_case(case,start+i)
        if env["sha256_case"]!=_paired_digest(case):
            raise ValueError("bad per-original-seed result checksum")
        saved[i]=case
    return saved


def _aggregate(cases:list[dict[str,Any]],train_clusters:int)->dict[str,Any]:
    totals={k:0 for k in METRICS}
    per_seed=[]
    for case in cases:
        seed_totals={k:sum(seat[k] for seat in case[
            "per_seat_actor_choice_counts"]) for k in METRICS}
        for k in METRICS:
            totals[k]+=seed_totals[k]
        per_seed.append(seed_totals)
    return {
        "protocol":PROTOCOL,
        "independent_original_shuffle_clusters":len(cases),
        "actual_complete_four_challenge_games":len(cases),
        "sampled_actor_discard_opportunities":totals["discard_decisions"],
        "trained_original_shuffle_clusters":train_clusters,
        "counts":totals,
        "independent_shuffles_with_at_least_one_equal_ukeire_alternative":
            sum(x["decisions_with_equal_ukeire_alternative"]>0
                for x in per_seed),
        "independent_shuffles_with_no_safe_equal_ukeire_alternative":
            sum(x["decisions_with_equal_ukeire_alternative"]==0
                for x in per_seed),
        "equal_ukeire_tie_discards_are_opportunities_not_policy_wins":True,
        "higher_ukeire_alternatives_are_not_proven_better_terminal_value":True,
        "no_candidate_policy_trained_or_tested":True,
        "original_challenge_policy_unmodified":True,
        "all_acting_observations_own_view_only":True,
        "old_m437_m439_m441_test_outcomes_not_used_for_new_policy_fitting":True,
        "no_opponent_hidden_tiles_or_true_seed_in_safe_summary":True,
        "small_new_seed_exploratory_probe":len(cases)<20,
        "no_strength_or_significance_claim":True,
    }


def run_new_seed_tie_audit(
    *,training_dir:Path,prior_m437_dir:Path,prior_m439_dir:Path,
    prior_m441_dir:Path,seed_start:int,seeds:int,out_dir:Path,
    resume:bool=False
)->dict[str,Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
            type(resume) is not bool or not 0<=seed_start<2**32 or
            not 1<=seeds<=MAX_EVAL_SEEDS or seed_start+seeds>2**32):
        raise ValueError("invalid new independent shuffle audit plan")
    training=_private_location(Path(training_dir))
    old437=_private_location(Path(prior_m437_dir))
    old439=_private_location(Path(prior_m439_dir))
    old441=_private_location(Path(prior_m441_dir))
    output=_private_location(Path(out_dir))
    sources=(training,old437,old439,old441)
    if (len(set((*sources,output)))!=5 or any(
        p in output.parents or output in p.parents for p in sources
    )):
        raise ValueError("tie audit output must not overlap private input")
    weights,prov=load_frozen_local_model(training)
    tbegin=prov["source_m434_train_seed_start"]
    tend=prov["source_m434_seed_end_exclusive"]
    if not (seed_start+seeds<=tbegin or seed_start>=tend):
        raise ValueError("new tie audit overlaps original train/holdout seeds")
    _verify_prior_m437(old437,training,prov["model_sha256"],
                       seed_start,seeds)
    plan439=_get_json(old439/M439_MANIFEST)
    m439start=plan439.get("private_eval_seed_start")
    m439n=plan439.get("private_eval_seed_count")
    if (plan439.get("protocol")!=M439_PROTOCOL or
            plan439.get("private_source_training_directory")!=str(training) or
            plan439.get("private_source_m437_directory")!=str(old437) or
            plan439.get("private_frozen_model_sha256")!=prov["model_sha256"] or
            plan439.get("online_policy_changed") is not False or
            type(m439start) is not int or type(m439n) is not int or
            not 0<=m439start<2**32 or not 1<=m439n<=MAX_EVAL_SEEDS or
            m439start+m439n>2**32):
        raise ValueError("M4.39 source plan not auditable")
    if not (seed_start+seeds<=m439start or
            seed_start>=m439start+m439n):
        raise ValueError("M4.42 new shuffle overlaps prior M4.39 evaluation")
    plan441=_get_json(old441/M441_PLAN)
    m441start=plan441.get("private_seed_start")
    m441n=plan441.get("original_shuffle_clusters")
    if (plan441.get("protocol")!=M441_PROTOCOL or
            plan441.get("private_training_dir")!=str(training) or
            plan441.get("private_prior_m437_dir")!=str(old437) or
            plan441.get("private_prior_m439_dir")!=str(old439) or
            plan441.get("frozen_model_sha256")!=prov["model_sha256"] or
            plan441.get("live_online_promotion") is not False or
            type(m441start) is not int or type(m441n) is not int or
            not 0<=m441start<2**32 or not 1<=m441n<=MAX_EVAL_SEEDS or
            m441start+m441n>2**32):
        raise ValueError("M4.41 source guard trial plan not auditable")
    if not (seed_start+seeds<=m441start or
            seed_start>=m441start+m441n):
        raise ValueError("M4.42 new shuffle overlaps prior M4.41 evaluation")
    plan={
        "protocol":PROTOCOL,
        "model_sha256":prov["model_sha256"],
        "private_train_dir":str(training),
        "private_prior_m437_dir":str(old437),
        "private_prior_m439_dir":str(old439),
        "private_prior_m441_dir":str(old441),
        "private_original_seed_start":seed_start,
        "independent_seed_clusters":seeds,
        "audit_only_not_candidate_policy_experiment":True,
        "challenge_behavior_unchanged":True,
    }
    if resume:
        if not output.is_dir() or not (output/PLAN).is_file():
            raise ValueError("resume requires existing M4.42 source plan")
        if _get_json(output/PLAN)!=plan:
            raise ValueError("resume plan or training model changed")
        if any(p.name not in {PLAN,SHARDS,SUMMARY} and ".tmp-" not in p.name
               for p in output.iterdir()):
            raise ValueError("unexpected diagnostic output on resume")
        saved=_saved_cases(output,seed_start,seeds,prov["model_sha256"])
        if (output/SUMMARY).is_file() and len(saved)!=seeds:
            raise ValueError("reported finished result has incomplete seed shards")
    else:
        if output.exists() and any(output.iterdir()):
            raise ValueError("output must be new/empty: never overwrite original trials")
        output.mkdir(parents=True,exist_ok=True)
        _write_atomic(output/PLAN,plan)
        saved={}
    (output/SHARDS).mkdir(exist_ok=True)
    cases=[]
    for i in range(seeds):
        case=saved.get(i)
        if case is None:
            case=play_one_challenge_baseline(seed_start+i)
            _verify_case(case,seed_start+i)
            _write_atomic(_shard_file(output,i),{
                "protocol":SHARD_PROTOCOL,
                "model_sha256":prov["model_sha256"],
                "index":i,
                "sha256_case":_paired_digest(case),
                "private_case":case,
            })
        cases.append(case)
    safe=_aggregate(cases,prov["trained_original_shuffle_clusters"])
    safe["reused_already_finished_original_seed_shards"]=len(saved)
    _write_atomic(output/SUMMARY,safe)
    return safe
