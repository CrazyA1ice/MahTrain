"""M4.44: independent original shuffle CHALLENGE claim/rob/kong choice audit.

Purely observe the legally offered actions of each actor's standard own
private_view. Reuse original Challenge implementations; no policy changes,
new trained model, hidden opponent hand, wall peek or off-policy payout claim.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .ai import MahjongAgent
from .ai_selfplay_counterfactual import KONG_BASE, MAX_ACTIONS, _ledger, _opening
from .ai_selfplay_local_batch import _get_json, _private_location
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
from .ai_tournament import _take_action
from .four_player import FourPlayerOpening

PROTOCOL="m444_new_seed_challenge_claim_kong_action_frontier_v1"
SHARD_PROTOCOL="m444_private_original_shuffle_claim_frontier_v1"
MANIFEST="PRIVATE_call_frontier_plan.json"
SHARDS="PRIVATE_claim_frontier_seed_clusters"
SUMMARY="safe_challenge_call_frontier.json"

KEYS=(
    "response_windows_seen","response_pass_only_windows",
    "claim_windows_with_peng","claim_windows_with_ming_gang",
    "claim_windows_with_both_peng_and_ming_gang",
    "claim_legal_hu_windows","rob_kong_response_windows",
    "rob_kong_legal_hu_windows",
    "claim_chose_pass_with_claim_available","claim_chose_peng",
    "claim_chose_ming_gang","claim_chose_hu","rob_chose_hu",
    "rob_chose_pass","claim_action_choice_windows",
    "own_discard_stage_visits","own_self_win_opportunities",
    "own_kong_checks","own_kong_checks_with_options",
    "own_kong_checks_with_multiple_options",
    "own_kong_options_an_gang","own_kong_options_bu_gang",
    "own_kong_chose_none_with_options",
    "own_kong_chose_an_gang","own_kong_chose_bu_gang",
)
ACTION_TYPES=("an_gang","bu_gang")


class ChallengeCallFrontierProbe(MahjongAgent):
    def __init__(self,*,seed:int,seat:int):
        super().__init__("challenge",seed=seed,seat=seat)
        self.counts={k:0 for k in KEYS}

    def response(self,view,*,rob:bool=False)->str:
        options=view["rob_options"] if rob else view["claim_options"]
        if (not isinstance(options,list) or
                len(options)!=len(set(options)) or
                not set(options).issubset({"pass","hu","peng","ming_gang"}) or
                not options):
            raise ValueError("illegal actor-visible response option schema")
        choice=super().response(view,rob=rob)
        if choice not in options:
            raise RuntimeError("observed Challenge response not offered")
        c=self.counts
        c["response_windows_seen"]+=1
        if len(options)==1 and options[0]=="pass":
            c["response_pass_only_windows"]+=1
        if rob:
            c["rob_kong_response_windows"]+=1
            c["rob_kong_legal_hu_windows"]+=int("hu" in options)
            c["rob_chose_hu"]+=int(choice=="hu")
            c["rob_chose_pass"]+=int(choice=="pass")
        else:
            peng="peng" in options
            gang="ming_gang" in options
            c["claim_windows_with_peng"]+=int(peng)
            c["claim_windows_with_ming_gang"]+=int(gang)
            c["claim_windows_with_both_peng_and_ming_gang"]+=int(peng and gang)
            c["claim_legal_hu_windows"]+=int("hu" in options)
            c["claim_action_choice_windows"]+=int(peng or gang)
            c["claim_chose_pass_with_claim_available"]+=int(
                choice=="pass" and (peng or gang))
            for label,key in (("peng","claim_chose_peng"),
                              ("ming_gang","claim_chose_ming_gang"),
                              ("hu","claim_chose_hu")):
                c[key]+=int(choice==label)
        return choice

    def kong(self,view)->dict[str,str]|None:
        options=view["kong_options"]
        if not isinstance(options,list):
            raise ValueError("invalid actor-visible kong choices")
        allowed=tuple(
            (item.get("type"),item.get("tile"))
            for item in options if isinstance(item,dict))
        if (len(allowed)!=len(options) or
                any(kind not in ACTION_TYPES or not isinstance(tile,str)
                    for kind,tile in allowed) or len(set(allowed))!=len(allowed)):
            raise ValueError("invalid or duplicate own-kong option")
        outcome=super().kong(view)
        if outcome is not None and (outcome["type"],outcome["tile"]) not in allowed:
            raise RuntimeError("observed Challenge kong action not offered")
        c=self.counts
        c["own_kong_checks"]+=1
        c["own_kong_checks_with_options"]+=int(bool(options))
        c["own_kong_checks_with_multiple_options"]+=int(len(options)>1)
        c["own_kong_options_an_gang"]+=sum(kind=="an_gang" for kind,_ in allowed)
        c["own_kong_options_bu_gang"]+=sum(kind=="bu_gang" for kind,_ in allowed)
        c["own_kong_chose_none_with_options"]+=int(bool(options) and outcome is None)
        if outcome is not None:
            c["own_kong_chose_"+outcome["type"]]+=1
        return outcome


def play_challenge_call_frontier_seed(seed:int)->dict[str,Any]:
    if type(seed) is not int or not 0<=seed<2**32:
        raise ValueError("invalid original shuffle seed")
    game=FourPlayerOpening(seed,kong_base=KONG_BASE,legacy_bugang_cash=False)
    agents={seat:ChallengeCallFrontierProbe(seed=seed,seat=seat)
            for seat in range(4)}
    _opening(game,agents,[])
    trace=[]
    duration=defaultdict(list)
    visit_counts=[0]*4
    win_counts=[0]*4
    for _ in range(MAX_ACTIONS):
        if game.phase in ("finished","wall_exhausted"):
            break
        if game.phase in ("dealer_discard","await_discard"):
            seat=game.turn
            visit_counts[seat]+=1
            win_counts[seat]+=int(game.private_view(seat)["can_self_draw_win"])
        _take_action(game,agents,trace,duration)
        if len(trace)>4:
            trace.clear()
    else:
        raise RuntimeError("full Challenge call frontier game did not settle")
    ledgers=[_ledger(game,s) for s in range(4)]
    if any(sum(item[key] for item in ledgers)!=0
           for key in ("official_net","win_points","kong_points","exhaustive_points")):
        raise RuntimeError("authoritative full game claim/kong ledger not zero sum")
    counts=[]
    for s in range(4):
        c=dict(agents[s].counts)
        c["own_discard_stage_visits"]=visit_counts[s]
        c["own_self_win_opportunities"]=win_counts[s]
        counts.append(c)
    case={
        "private_original_shuffle_seed":seed,
        "actual_completed_challenge_games":1,
        "terminal_phase":game.phase,
        "official_net_by_seat":[r["official_net"] for r in ledgers],
        "per_seat_actor_action_counts":counts,
        "live_challenge_action_identity_preserved":True,
        "no_hidden_wall_or_opponent_hands_recorded":True,
    }
    _validate_case(case,seed)
    return case


def _validate_case(case:dict[str,Any],seed:int)->None:
    if (type(case) is not dict or
            type(case.get("private_original_shuffle_seed")) is not int or
            case["private_original_shuffle_seed"]!=seed or
            case.get("actual_completed_challenge_games")!=1 or
            case.get("terminal_phase") not in ("finished","wall_exhausted") or
            case.get("live_challenge_action_identity_preserved") is not True or
            case.get("no_hidden_wall_or_opponent_hands_recorded") is not True):
        raise ValueError("incomplete or inconsistent true Challenge frontier game")
    scores=case.get("official_net_by_seat")
    seats=case.get("per_seat_actor_action_counts")
    if (type(scores) is not list or len(scores)!=4 or
            any(type(v) is not int for v in scores) or
            sum(scores)!=0 or type(seats) is not list or len(seats)!=4):
        raise ValueError("invalid four-seat net ledger or aggregate observations")
    for c in seats:
        if (type(c) is not dict or set(c)!=set(KEYS) or
                any(type(n) is not int or n<0 for n in c.values())):
            raise ValueError("invalid actor-only claim and kong count keys")
        claim=c["response_windows_seen"]-c["rob_kong_response_windows"]
        if (not 0<=c["response_pass_only_windows"]<=c["response_windows_seen"] or
            not 0<=c["claim_windows_with_both_peng_and_ming_gang"]<=
              min(c["claim_windows_with_peng"],c["claim_windows_with_ming_gang"]) or
            c["claim_action_choice_windows"]!=
              c["claim_windows_with_peng"]+c["claim_windows_with_ming_gang"]-
              c["claim_windows_with_both_peng_and_ming_gang"] or
            c["claim_chose_peng"]+c["claim_chose_ming_gang"]+
              c["claim_chose_pass_with_claim_available"]>
              c["claim_action_choice_windows"] or
            c["claim_chose_hu"]>c["claim_legal_hu_windows"] or
            c["claim_legal_hu_windows"]>claim or
            c["rob_kong_legal_hu_windows"]>c["rob_kong_response_windows"] or
            c["rob_chose_hu"]+c["rob_chose_pass"]!=c["rob_kong_response_windows"] or
            c["own_kong_checks"]>c["own_discard_stage_visits"] or
            c["own_self_win_opportunities"]+c["own_kong_checks"]!=
              c["own_discard_stage_visits"] or
            c["own_kong_checks_with_multiple_options"]>
              c["own_kong_checks_with_options"] or
            c["own_kong_chose_an_gang"]+c["own_kong_chose_bu_gang"]+
              c["own_kong_chose_none_with_options"]!=
              c["own_kong_checks_with_options"] or
            c["own_kong_checks_with_options"]>c["own_kong_checks"]):
            raise ValueError("impossible actor-only claim/kong observation accounting")


def _shard(root:Path,index:int)->Path:
    return root/SHARDS/f"index-{index:08d}.json"


def _read_saved(root:Path,start:int,n:int,digest:str)->dict[int,dict[str,Any]]:
    folder=root/SHARDS
    if not folder.exists():
        return {}
    if not folder.is_dir():
        raise ValueError("wrong private frontier checkpoint directory type")
    result={}
    for f in folder.iterdir():
        if f.is_file() and ".tmp-" in f.name:
            continue
        if (not f.is_file() or not f.name.startswith("index-") or
            not f.name.endswith(".json") or len(f.name)!=19 or
            not f.name[6:14].isdigit()):
            raise ValueError("unexpected private frontier seed checkpoint")
        i=int(f.name[6:14])
        if i>=n or i in result:
            raise ValueError("extra or repeated original shuffle checkpoint")
        env=_get_json(f)
        if (type(env) is not dict or set(env)!={
                "protocol","model_sha256","index","checksum","private_case"} or
                env["protocol"]!=SHARD_PROTOCOL or
                type(env["index"]) is not int or env["index"]!=i or
                env["model_sha256"]!=digest or
                type(env["private_case"]) is not dict):
            raise ValueError("tampered frontier original shuffle envelope")
        case=env["private_case"]
        _validate_case(case,start+i)
        if env["checksum"]!=_paired_digest(case):
            raise ValueError("frontier private checkpoint checksum mismatch")
        result[i]=case
    return result


def _summary(cases:list[dict[str,Any]])->dict[str,Any]:
    totals={k:0 for k in KEYS}
    seeds_with_alternative=0
    for case in cases:
        seed_totals={k:sum(row[k] for row in
            case["per_seat_actor_action_counts"]) for k in KEYS}
        for k,n in seed_totals.items():
            totals[k]+=n
        seeds_with_alternative+=int(
            seed_totals["claim_action_choice_windows"]>0 or
            seed_totals["own_kong_checks_with_options"]>0)
    return {
        "protocol":PROTOCOL,
        "independent_original_shuffle_clusters":len(cases),
        "real_finished_four_player_challenge_games":len(cases),
        "counts":totals,
        "original_shuffles_with_at_least_one_peng_or_kong_alternative":
            seeds_with_alternative,
        "unchanged_challenge_policy":True,
        "same_actual_behavior_as_uninstrumented_challenge":True,
        "no_off_policy_claim_altered":True,
        "no_model_fitted_or_parameters_tuned":True,
        "no_true_futures_or_opponent_hidden_hands_collected":True,
        "no_real_seed_or_tile_name_in_safe_summary":True,
        "old_m437_m439_m441_m442_m443_seed_intervals_excluded":True,
        "candidate_choice_not_terminal_action_value":True,
        "insufficient_seeds_for_strength_claim":len(cases)<20,
        "no_significance_or_online_promotion_claim":True,
    }


def run_new_seed_claim_frontier(
    *,training_dir:Path,prior_m442_dir:Path,prior_m443_dir:Path,
    seed_start:int,seeds:int,out_dir:Path,resume:bool=False,
)->dict[str,Any]:
    if (type(seed_start) is not int or type(seeds) is not int or
            type(resume) is not bool or not 0<=seed_start<2**32 or
            not 1<=seeds<=MAX_EVAL_SEEDS or seed_start+seeds>2**32):
        raise ValueError("invalid new original shuffle frontier plan")
    train=_private_location(Path(training_dir))
    old442=_private_location(Path(prior_m442_dir))
    old443=_private_location(Path(prior_m443_dir))
    output=_private_location(Path(out_dir))
    if len({train,old442,old443,output})!=4 or any(
        x in output.parents or output in x.parents for x in (train,old442,old443)
    ):
        raise ValueError("frontier output must be separate from private inputs")
    _,meta=load_frozen_local_model(train)
    t0=meta["source_m434_train_seed_start"]
    t1=meta["source_m434_seed_end_exclusive"]
    if not (seed_start+seeds<=t0 or seed_start>=t1):
        raise ValueError("new frontier shuffle overlaps original train/holdout")
    oldp442=_get_json(old442/M442_PLAN)
    oldp443=_get_json(old443/M443_PLAN)
    model=meta["model_sha256"]
    if (oldp442.get("protocol")!=M442_PROTOCOL or
        oldp442.get("private_train_dir")!=str(train) or
        oldp442.get("model_sha256")!=model or
        oldp442.get("challenge_behavior_unchanged") is not True or
        oldp443.get("protocol")!=M443_PROTOCOL or
        oldp443.get("private_training_dir")!=str(train) or
        oldp443.get("private_prior_m442_dir")!=str(old442) or
        oldp443.get("model_sha256_provenance_only")!=model or
        oldp443.get("live_policy_untouched") is not True):
        raise ValueError("M4.42/M4.43 original source provenance does not match")
    # Read all legacy plans rather than blindly trusting copied seed numbers.
    paths={
        "m437":Path(oldp442["private_prior_m437_dir"]),
        "m439":Path(oldp442["private_prior_m439_dir"]),
        "m441":Path(oldp442["private_prior_m441_dir"]),
    }
    oldp437=_get_json(paths["m437"]/"PRIVATE_frozen_benchmark_plan.json")
    oldp439=_get_json(paths["m439"]/M439_PLAN)
    oldp441=_get_json(paths["m441"]/M441_PLAN)
    if (oldp437.get("protocol")!=M437_PROTOCOL or
        oldp437.get("resumable_shards_protocol")!=M437_SHARD_PROTOCOL or
        oldp437.get("private_frozen_model_sha256")!=model or
        oldp437.get("private_source_training_directory")!=str(train) or
        oldp439.get("protocol")!=M439_PROTOCOL or
        oldp439.get("private_frozen_model_sha256")!=model or
        oldp439.get("private_source_training_directory")!=str(train) or
        oldp441.get("protocol")!=M441_PROTOCOL or
        oldp441.get("frozen_model_sha256")!=model or
        oldp441.get("private_training_dir")!=str(train) or
        oldp443.get("private_prior_m437_dir")!=str(paths["m437"]) or
        oldp443.get("private_prior_m439_dir")!=str(paths["m439"]) or
        oldp443.get("private_prior_m441_dir")!=str(paths["m441"])):
        raise ValueError("historical real shuffle evidence/model does not reconcile")
    periods=(
        (oldp437,"private_evaluation_seed_start","private_eval_original_shuffle_count"),
        (oldp439,"private_eval_seed_start","private_eval_seed_count"),
        (oldp441,"private_seed_start","original_shuffle_clusters"),
        (oldp442,"private_original_seed_start","independent_seed_clusters"),
        (oldp443,"private_new_shuffle_start","private_independent_shuffle_count"),
    )
    for plan,a,b in periods:
        s=plan.get(a)
        n=plan.get(b)
        if (type(s) is not int or type(n) is not int or
                not 0<=s<2**32 or not 1<=n<=MAX_EVAL_SEEDS or s+n>2**32):
            raise ValueError("invalid immutable previous evaluation seed range")
        if not (seed_start+seeds<=s or seed_start>=s+n):
            raise ValueError("new original shuffle overlaps prior benchmark")
    manifest={
        "protocol":PROTOCOL,
        "private_model_source":str(train),
        "private_m442_source":str(old442),
        "private_m443_source":str(old443),
        "model_sha256_provenance_only":model,
        "private_original_shuffle_start":seed_start,
        "private_original_shuffle_count":seeds,
        "challenge_unmodified":True,
        "no_candidate_policy_test":True,
    }
    if resume:
        if not output.is_dir() or not (output/MANIFEST).is_file():
            raise ValueError("resume requires original saved frontier plan")
        if _get_json(output/MANIFEST)!=manifest:
            raise ValueError("resume parameters or source model changed")
        if any(p.name not in (MANIFEST,SHARDS,SUMMARY) and
               ".tmp-" not in p.name for p in output.iterdir()):
            raise ValueError("unexpected private frontier resume file")
        saved=_read_saved(output,seed_start,seeds,model)
        if (output/SUMMARY).exists() and len(saved)!=seeds:
            raise ValueError("summary claims complete but original seed shards missing")
    else:
        if output.exists() and any(output.iterdir()):
            raise ValueError("frontier audit requires new empty results folder")
        output.mkdir(parents=True,exist_ok=True)
        _write_atomic(output/MANIFEST,manifest)
        saved={}
    (output/SHARDS).mkdir(exist_ok=True)
    cases=[]
    for i in range(seeds):
        case=saved.get(i)
        if case is None:
            case=play_challenge_call_frontier_seed(seed_start+i)
            _validate_case(case,seed_start+i)
            _write_atomic(_shard(output,i),{
                "protocol":SHARD_PROTOCOL,
                "index":i,
                "model_sha256":model,
                "checksum":_paired_digest(case),
                "private_case":case,
            })
        cases.append(case)
    public=_summary(cases)
    public["reused_verified_original_shuffles"]=len(saved)
    _write_atomic(output/SUMMARY,public)
    return public
