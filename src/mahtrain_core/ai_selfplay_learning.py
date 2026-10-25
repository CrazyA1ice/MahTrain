"""M4.30 offline AI self-play: public replays, actor-only training examples,
tiny RESEARCH policy, independent-seed holdout against frozen challenge.

Important: trajectory returns are noisy labels, NOT counterfactual quality of
any single discard. No access to opponent hands/future wall; never promote
the learned pilot to the live AI automatically.
"""
from __future__ import annotations

from copy import deepcopy
from math import isfinite
from statistics import mean
from typing import Any, Mapping

from .ai import MahjongAgent
from .ai_tournament import simulate_match

PROTOCOL = "m430_actor_observation_selfplay_replay_offline_v1"
MODEL_PROTOCOL = "m430_trajectory_weighted_tiebreak_pilot_v1"
LEVELS = ("challenge", "basic", "advanced", "baseline")
FEATURES = (
    "effective_copies", "old_score", "public_pressure",
    "table_threat", "survival", "fan_proxy",
)
FORBIDDEN_PUBLIC_FIELDS = frozenset((
    "hand", "own_hand", "opponent_hands", "drawn_tile",
    "future_wall", "_wall", "_hands", "seed", "kong_options",
    "claim_options", "rob_options", "private_view", "tian_ting",
))
SEED_LIMIT = 2**32
KONG_BASE = 20


def _lineup(rotation: int) -> tuple[list[str], int]:
    if type(rotation) is not int or rotation not in range(4):
        raise ValueError("rotation must be 0..3")
    lineup = [LEVELS[(seat + rotation) % 4] for seat in range(4)]
    return lineup, lineup.index("challenge")


def _features(candidate: Mapping[str, Any]) -> list[float]:
    """Pure, immutable actor-authorized discard ranking features."""
    return [
        min(2.0, candidate["effective_tile_count"] / 40),
        min(4.0, max(0.0, candidate["score"]) / 120),
        min(2.0, candidate["public_pressure"] / 4),
        min(2.0, candidate["table_threat_index"] / 8),
        max(0.0, min(1.0, candidate["survival_factor"])),
        min(2.0, candidate["value_multiplier"] / 5),
    ]


def _snapshot(view: Mapping[str, Any]) -> dict[str, Any]:
    """Whitelisted observation from ONLY the acting AI's private_view."""
    seat = view["seat"]
    return {
        "phase": view["phase"], "seat": seat,
        "own_hand": list(view["hand"]),
        "own_melds": deepcopy(view["own_melds"]),
        "missing_suit": view["missing_suits"][seat]
            if view["missing_suits"] is not None else None,
        "wall_count": view["wall_count"],
        "public_discards": [
            {"seat": entry["seat"], "tile": entry["tile"]}
            for entry in view["discards"]
            if "tile" in entry
        ],
        "public_melds": deepcopy(view["melds"]),
    }


class RecordingChallengeAgent(MahjongAgent):
    """Captures ALL challenge decisions from own authorized view only."""

    def __init__(self, *, seed: int, seat: int) -> None:
        super().__init__("challenge", seed=seed, seat=seat)
        self.actor_decisions: list[dict[str, Any]] = []

    def _record(self, view: Mapping[str, Any], kind: str,
                action: Any, *, options: Any = None,
                ranked: Any = None) -> None:
        row = _snapshot(view)
        row.update({
            "kind":kind, "chosen_action":deepcopy(action),
            "legal_options":deepcopy(options),
        })
        if ranked:
            row["discard_ranked"] = [
                {
                    "discard": item["discard"],
                    "shanten":item["shanten"],
                    "effective_tile_count":item["effective_tile_count"],
                    "score":item["score"],
                    "public_pressure":item["public_pressure"],
                    "table_threat_index":item["table_threat_index"],
                    "survival_factor":item["survival_factor"],
                    "value_multiplier":item["value_multiplier"],
                    "features":_features(item),
                }
                for item in ranked
            ]
        self.actor_decisions.append(row)

    def exchange(self, view: Mapping[str, Any]) -> list[str]:
        action = super().exchange(view)
        self._record(view, "exchange", action)
        return action

    def missing(self, view: Mapping[str, Any]) -> str:
        action = super().missing(view)
        self._record(view, "missing", action)
        return action

    def response(self, view: Mapping[str, Any], *, rob: bool = False) -> str:
        action=super().response(view,rob=rob)
        self._record(
            view,"rob_response" if rob else "claim_response",action,
            options=view["rob_options"] if rob else view["claim_options"],
        )
        return action

    def kong(self, view: Mapping[str, Any]) -> dict[str, str] | None:
        action=super().kong(view)
        if view["kong_options"]:
            self._record(view,"kong",action,options=view["kong_options"])
        return action

    def discard(self, view: Mapping[str, Any]) -> str:
        action=super().discard(view)
        self._record(
            view,"discard",action,ranked=self._last_discard_scores
        )
        return action


def _assert_public(obj: Any) -> None:
    """Recurse over replay field names, not just top-level metadata."""
    if isinstance(obj, dict):
        secrets=FORBIDDEN_PUBLIC_FIELDS.intersection(obj)
        if secrets:
            raise RuntimeError("public replay contains a private field")
        for val in obj.values():
            _assert_public(val)
    elif isinstance(obj, list):
        for val in obj:
            _assert_public(val)


def _settlement(sample: dict[str, Any], seat: int) -> dict[str, int]:
    parts=(
        sample["partial_win_balances"],
        sample["official_kong_balances"],
        sample["official_exhaustive_balances"],
        sample["official_settled_balances"],
    )
    if (sample["terminal_phase"] not in ("finished","wall_exhausted") or
            sample["physical_count"] != 108 or
            sample["scoring_rules"]["kong_base"] != KONG_BASE or
            any(type(p) is not list or len(p)!=4 or
                any(type(v) is not int for v in p) or sum(p)
                for p in parts) or
            any(parts[3][i]!=parts[0][i]+parts[1][i]+parts[2][i]
                for i in range(4))):
        raise RuntimeError("unsettled or invalid current-rule self-play ledger")
    return {
        "official_net":parts[3][seat],
        "win_points":parts[0][seat],
        "kong_points":parts[1][seat],
        "exhaustive_points":parts[2][seat],
    }


def selfplay_seed(seed: int, rotation: int, *,
                  public_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Full AI-only actual round; public replay and PRIVATE learner dataset."""
    if type(seed) is not int or not 0<=seed<SEED_LIMIT:
        raise ValueError("invalid self-play shuffle seed")
    if type(public_id) is not str or not public_id.startswith("game-"):
        raise ValueError("must supply nonseed public replay ID")
    lineup, seat = _lineup(rotation)
    recorder = RecordingChallengeAgent(seed=seed,seat=seat)
    result=simulate_match(
        seed, lineup=lineup, offline_ruleset="current_m423",
        offline_kong_base=KONG_BASE,
        offline_agent_overrides={seat:recorder},
    )
    payout=_settlement(result,seat)
    # Frames were produced by the simulator's existing public-only redaction.
    # Never serialize seed or actor private observations to this archive.
    public={
        "protocol":PROTOCOL, "game_id":public_id,
        "assignment":lineup,
        "terminal_phase":result["terminal_phase"],
        "public_frames":result["public_replay"],
        "official_final_balances":result["official_settled_balances"],
        "rule_set":"current_m423",
    }
    _assert_public(public)
    private={
        "protocol":PROTOCOL, "game_id":public_id,
        "private_shuffle_seed":seed, "rotation":rotation,
        "seat":seat, "terminal_outcome":payout,
        "decisions":recorder.actor_decisions,
        "rule_set":"current_m423",
        "actor_observations_only":True,
    }
    if not any(d["kind"]=="discard" for d in private["decisions"]):
        raise RuntimeError("self-play produced no training discards")
    return public,private


def _candidate_choice_score(candidate: Mapping[str, Any],
                            weights: list[float],
                            scale: float) -> float:
    original=float(candidate["score"])/scale
    return original+sum(w*f for w,f in zip(
        weights,_features(candidate)))


def fit_trajectory_pilot(games: list[dict[str, Any]]) -> dict[str, Any]:
    """A bounded actor-only outcome-weighted *imitation pilot*.

    Terminal score is shared by MANY actions and proves NO action caused it.
    The only safe use here is an exploratory weight proposal, subject to
    untouched seed-cluster holdout evaluation. No unobserved actions have
    action-value labels and no such labels are fabricated.
    """
    if type(games) is not list or not games:
        raise ValueError("requires real actor-only self-play games")
    seed_clusters: dict[int,list[dict[str,Any]]] = {}
    for g in games:
        seed=g.get("private_shuffle_seed")
        if (g.get("protocol")!=PROTOCOL or
                g.get("actor_observations_only") is not True or
                g.get("rule_set")!="current_m423" or
                type(seed) is not int or
                type(g.get("rotation")) is not int or
                g["rotation"] not in range(4) or
                type(g.get("decisions")) is not list):
            raise ValueError("unsupported/unsafe learner data")
        seed_clusters.setdefault(seed,[]).append(g)
    if any(sorted(g["rotation"] for g in gs)!=[0,1,2,3]
           for gs in seed_clusters.values()):
        raise ValueError("self-play learning requires full four-seat rotations")
    total=[0.0]*len(FEATURES)
    episodes=0
    decisions=0
    for seed in sorted(seed_clusters):
        for g in sorted(seed_clusters[seed],key=lambda row:row["rotation"]):
            reward=g["terminal_outcome"]["official_net"]
            if type(reward) is not int:
                raise ValueError("real official terminal integer reward required")
            # Saturate extreme matched-rule payments. Do not let one
            # 3-fan limit / late all-pay exhaustively dominate a pilot.
            reward=max(-1.0,min(1.0,reward/1000.0))
            episode=[0.0]*len(FEATURES)
            eligible=0
            for decision in g["decisions"]:
                if decision.get("kind")!="discard":
                    continue
                ranked=decision.get("discard_ranked",[])
                if (len(ranked)<2 or
                        not any(x["discard"]==decision["chosen_action"]
                                for x in ranked)):
                    continue
                selected=next(x for x in ranked
                              if x["discard"]==decision["chosen_action"])
                others=[x for x in ranked if x is not selected]
                for i in range(len(FEATURES)):
                    delta=(selected["features"][i]-
                           mean(x["features"][i] for x in others))
                    episode[i]+=delta
                eligible+=1
            if eligible:
                episodes+=1
                decisions+=eligible
                for i in range(len(FEATURES)):
                    total[i]+=reward*episode[i]/eligible
    if not episodes:
        raise ValueError("no genuine multi-option challenge discard decisions")
    # Very small bounded adjustments: preserve original exact minimum
    # shanten policy and restrict eligible candidate score proximity.
    weights=[round(max(-0.20,min(0.20,x/episodes)),7) for x in total]
    return {
        "protocol":MODEL_PROTOCOL,
        "features":list(FEATURES),"weights":weights,
        "training_seed_clusters":len(seed_clusters),
        "training_games":len(games),"eligible_discard_decisions":decisions,
        "online_promotion_allowed":False,
        "training_method":"bounded_trajectory_return_weighted_preference_pilot",
        "limitations":"correlated trajectory outcomes; no per-discard causal value labels",
    }


class OfflineLearnedChallengeAgent(MahjongAgent):
    """Only modifies equal-shanten, close-score discard ties offline."""

    def __init__(self, *, seed: int, seat: int, model: Mapping[str, Any]):
        super().__init__("challenge", seed=seed, seat=seat)
        if (model.get("protocol")!=MODEL_PROTOCOL or
                model.get("features")!=list(FEATURES) or
                model.get("online_promotion_allowed") is not False or
                type(model.get("weights")) is not list or
                len(model["weights"])!=len(FEATURES) or
                any(type(w) not in (float,int) or not isfinite(w) or
                    abs(w)>0.2 for w in model["weights"])):
            raise ValueError("invalid/unsafe unverified offline policy model")
        self._weights=list(model["weights"])
        self.changed_discards=0
        self.scored_decisions=0

    def discard(self, view: Mapping[str, Any]) -> str:
        baseline=super().discard(view)
        ranked=self._last_discard_scores
        if not ranked or len(ranked)<2:
            return baseline
        best=float(ranked[0]["score"])
        scale=max(1.0,abs(best))
        # Respect original exact minimum shanten and only near-tied
        # score candidates. Ordinary large-quality differences never flip.
        eligible=[
            c for c in ranked
            if c["shanten"]==ranked[0]["shanten"] and
            float(c["score"]) >= best-0.10*scale
        ]
        if len(eligible)<2:
            return baseline
        self.scored_decisions+=1
        chosen=max(
            eligible,key=lambda c:(
                _candidate_choice_score(c,self._weights,scale),
                -ranked.index(c)),
        )["discard"]
        if chosen!=baseline:
            self.changed_discards+=1
        return chosen


def heldout_trial(seed_start: int, seed_count: int,
                  model: Mapping[str, Any]) -> dict[str, Any]:
    """Frozen untouched seed clusters, ALL four challenge seat rotations."""
    if (type(seed_start) is not int or not 0<=seed_start<SEED_LIMIT or
            type(seed_count) is not int or not 1<=seed_count<=10 or
            seed_start+seed_count>SEED_LIMIT):
        raise ValueError("invalid frozen holdout seeds")
    pairs=[]
    for seed in range(seed_start,seed_start+seed_count):
        for rotation in range(4):
            lineup,seat=_lineup(rotation)
            baseline=simulate_match(
                seed,lineup=lineup,offline_ruleset="current_m423",
                offline_kong_base=KONG_BASE,
            )
            learned=OfflineLearnedChallengeAgent(
                seed=seed,seat=seat,model=model,
            )
            candidate=simulate_match(
                seed,lineup=lineup,offline_ruleset="current_m423",
                offline_kong_base=KONG_BASE,
                offline_agent_overrides={seat:learned},
            )
            before=_settlement(baseline,seat)
            after=_settlement(candidate,seat)
            pairs.append({
                "seed":seed,"rotation":rotation,"challenge_seat":seat,
                "baseline_official_net":before["official_net"],
                "learned_official_net":after["official_net"],
                "learned_minus_baseline_official_net":
                    after["official_net"]-before["official_net"],
                "learned_changed_discards":learned.changed_discards,
                "learned_scored_decisions":learned.scored_decisions,
            })
    return {
        "protocol":MODEL_PROTOCOL,
        "heldout_independent_seed_clusters":seed_count,
        "heldout_complete_games":len(pairs)*2,
        "seed_start":seed_start,
        "sum_conditional_holdout_delta":sum(
            p["learned_minus_baseline_official_net"] for p in pairs),
        "mean_conditional_holdout_delta":round(mean(
            p["learned_minus_baseline_official_net"] for p in pairs),5),
        "changed_discard_choices":sum(
            p["learned_changed_discards"] for p in pairs),
        "pairs":pairs,
        "promoted_to_live_ai":False,
        "confirmed_stronger":False,
        "limitations":[
            "Policies share initial shuffle seeds but their subsequent paths may diverge.",
            "A few independent seed clusters are insufficient to establish policy strength.",
            "Training only weights historical chosen actions, never supplies counterfactual labels.",
            "The same frozen learned pilot remains offline regardless of holdout score sign.",
        ],
    }


def run_pilot(seed_start: int, training_seed_count: int,
              heldout_seed_count: int) -> dict[str, Any]:
    if (type(seed_start) is not int or not 0<=seed_start<SEED_LIMIT or
            type(training_seed_count) is not int or
            not 1<=training_seed_count<=10 or
            type(heldout_seed_count) is not int or
            not 1<=heldout_seed_count<=10 or
            seed_start+training_seed_count+heldout_seed_count>SEED_LIMIT):
        raise ValueError("invalid disjoint self-play/holdout seed ranges")
    public_archives=[]
    private_games=[]
    for seed in range(seed_start,seed_start+training_seed_count):
        for rotation in range(4):
            public,private=selfplay_seed(
                seed,rotation,
                public_id=f"game-{seed-seed_start:03d}-{rotation}",
            )
            public_archives.append(public)
            private_games.append(private)
    model=fit_trajectory_pilot(private_games)
    evaluation=heldout_trial(
        seed_start+training_seed_count,heldout_seed_count,model,
    )
    return {
        "protocol":PROTOCOL,
        "training_seed_start":seed_start,
        "training_seed_clusters":training_seed_count,
        "holdout_seed_start":seed_start+training_seed_count,
        "holdout_seed_clusters":heldout_seed_count,
        "public_replays":public_archives,
        "private_actor_examples":private_games,
        "offline_model":model,
        "heldout":evaluation,
        "no_auto_promotion":True,
    }
