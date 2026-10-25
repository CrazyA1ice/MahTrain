"""M4.29 OFFLINE conditional full-game outcome of five known cashless bu-gang disputes.

A deliberately CONSTRUCTED pre-decision physical world is cloned into:
  (a) force this legal cashless delayed bu-gang, or
  (b) forgo THIS kong, choose challenge's normal discard.
Afterwards both branches play to a real terminal state with four seeded AIs.
No real future wall is provided to ANY agent. The original hidden world is
held fixed across both counterfactual actions; paths may diverge afterwards.

This measures conditional realized score in selected worlds; it is not a
natural-game win rate, calibrated counterfactual EV, or policy recommendation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from random import Random
from statistics import mean
from typing import Any, Mapping

from .ai import MahjongAgent
from .ai_baseline import ShapeBaselineAgent
from .ai_tournament import _take_action
from .ai_delayed_bugang_targeted import construct_checkpoint, SPECS

PROTOCOL = "m429_five_preselected_cashless_bugang_full_terminal_pairs_v1"
CASES = (10, 12, 18, 20, 22)  # FROZEN by M4.26/M4.27, not outcome-picked
REPLICAS = (0, 1, 2)
ARMS = ("forced_cashless_bugang", "forced_no_bugang")
METRICS = (
    "official_net", "win_points", "kong_points", "exhaustive_points",
    "wins", "deal_ins", "own_realized_kongs", "own_robbed_kongs",
)
LEDGER_PARTS = ("win_points", "kong_points", "exhaustive_points")
LINEUP = ("challenge", "basic", "advanced", "baseline")
SHARDS = {f"case_{case_id}": case_id for case_id in CASES}
MAX_ACTIONS = 800


def _world(case_id: int, replica: int):
    if (type(case_id) is not int or case_id not in CASES
            or type(replica) is not int or replica not in REPLICAS):
        raise ValueError("unregistered case or future-wall replica")
    game = construct_checkpoint(case_id, delayed=True)
    if game.phase != "await_discard" or game.turn != 0:
        raise RuntimeError("missing legal actor checkpoint")
    target = SPECS[case_id][0]
    view = game.private_view(0)
    if (view["drawn_tile"] == target
            or view["legacy_bugang_cash_rule"] is not False
            or view["can_self_draw_win"] is True
            or {"type": "bu_gang", "tile": target} not in view["kong_options"]):
        raise RuntimeError("pre-selected legal delayed-kong checkpoint changed")

    # Controlled, deterministically prespecified continuation of the unseen
    # wall; NEVER supply this ordering to any AI. Both action arms receive
    # exactly the same 108 real tiles, same opponents and same future wall.
    shuffled = list(game._wall)
    Random(79000 + case_id * 100 + replica).shuffle(shuffled)
    game._wall = shuffled
    game._assert_physical_tiles()
    return game


def _agents(case_id: int, replica: int):
    seed = 79000 + case_id * 100 + replica
    return {
        0: MahjongAgent("challenge", seed=seed, seat=0),
        1: MahjongAgent("basic", seed=seed, seat=1),
        2: MahjongAgent("advanced", seed=seed, seat=2),
        3: ShapeBaselineAgent(seed=seed, seat=3),
    }


def _official_terminal(game, *, initial_force: str, turns: int) -> dict[str, int | str]:
    if game.phase not in ("finished", "wall_exhausted"):
        raise RuntimeError("paired physical continuation did not reach terminal")
    if game.debug_tile_counts()["total"] != 108 or game._legacy_bugang_cash is not False:
        raise RuntimeError("nonphysical game or frozen historical cash rule")
    state=game.public_state()
    win=state["win_ledger"]["balances"]
    kong=state["kong_ledger"]["balances"]
    exhausted=(state["exhaustive_settlement"]["balances"]
               if state["exhaustive_settlement"] is not None
               else [0]*4)
    net=state["settled_balances"]
    pieces=(win,kong,exhausted,net)
    if (not state["win_ledger"]["zero_sum"]
            or not state["kong_ledger"]["zero_sum"]
            or any(type(vals) is not list or len(vals) != 4
                   or any(type(value) is not int for value in vals)
                   or sum(vals) != 0 for vals in pieces)
            or any(net[i] != win[i]+kong[i]+exhausted[i] for i in range(4))
            or (game.phase == "wall_exhausted"
                and (state["wall_count"] != 0
                     or state["exhaustive_settlement"] is None))
            or (game.phase == "finished" and sum(state["won"]) != 3)):
        raise RuntimeError("authoritative Hu + kong + draw settlement is invalid")
    own_kongs=sum(
        e["type"] in ("an_gang", "bu_gang", "ming_gang")
        and e.get("seat")==0
        for e in state["events"]
    )
    robbed=sum(
        e["type"]=="rob_kong" and e.get("seat")==0
        for e in state["events"]
    )
    result={
        "official_net":net[0], "win_points":win[0],
        "kong_points":kong[0], "exhaustive_points":exhausted[0],
        "wins":sum(w["seat"]==0 for w in state["winners"]),
        "deal_ins":sum(
            w["source"]==0 and w["seat"]!=0 for w in state["winners"]),
        "own_realized_kongs":own_kongs, "own_robbed_kongs":robbed,
        "terminal_phase":game.phase,"actions_after_checkpoint":turns,
    }
    if result["official_net"]!=sum(result[x] for x in LEDGER_PARTS):
        raise RuntimeError("actor official final score components do not sum")
    # The already-retained fourth copy cannot be cash-pricable. The branch
    # might win or declare other *later* kongs; only the first declaration
    # has a zero-payment guarantee.
    if initial_force=="forced_cashless_bugang":
        first=next((x for x in state["events"]
                    if x["type"]=="bu_gang_declared" and x["seat"]==0),None)
        if first is None or first["cash_eligible"] is not False:
            raise RuntimeError("forced delayed kong was incorrectly paid")
    return result


def _run_arm(initial_game, *, case_id: int, replica: int, arm: str):
    if arm not in ARMS:
        raise ValueError("invalid frozen intervention")
    game=deepcopy(initial_game)
    agents=_agents(case_id,replica)
    view=game.private_view(0)
    target=SPECS[case_id][0]
    if arm=="forced_cashless_bugang":
        game.declare_kong(0,"bu_gang",target)
        if game.public_state()["pending_rob_kong"]["cash_eligible"] is not False:
            raise RuntimeError("delayed kong unexpectedly payable")
    else:
        choice=agents[0].discard(view)
        if choice not in view["hand"] or choice[0] == "p":
            raise RuntimeError("counterfactual control cut was illegal")
        game.discard(0,choice)
    trace=[]
    durations=defaultdict(list)
    for i in range(MAX_ACTIONS):
        if game.phase in ("wall_exhausted","finished"):
            return _official_terminal(game,initial_force=arm,turns=i)
        _take_action(game,agents,trace,durations)
        # Public replay frames and hidden hands are deliberately NOT
        # exported. They cannot become a user-facing EV estimate.
        if len(trace)>3:
            trace.clear()
    raise RuntimeError("physical paired trial exceeded action limit")


def paired_case(case_id: int, replica: int) -> dict[str, Any]:
    initial=_world(case_id,replica)
    immutable_before=initial.private_view(0)
    arms={
        arm:_run_arm(initial,case_id=case_id,replica=replica,arm=arm)
        for arm in ARMS
    }
    if (initial.private_view(0)!=immutable_before
            or initial.debug_tile_counts()["total"]!=108):
        raise RuntimeError("paired trial mutated the original authorized view")
    diffs={
        k:arms[ARMS[0]][k]-arms[ARMS[1]][k]
        for k in METRICS
    }
    if diffs["official_net"]!=sum(diffs[k] for k in LEDGER_PARTS):
        raise RuntimeError("conditional terminal payoff deltas inconsistent")
    return {
        "case_id":case_id, "replica":replica,
        "exposed_peng":SPECS[case_id][0],
        "cash_rule":"current_m423", "actor_seat":0,
        "interventions":arms,"forced_minus_hold":diffs,
        "same_initial_wall_and_hidden_hands":True,
        "complete_games":2,"natural_random_games":0,
    }


def run_shard(shard: str) -> dict[str, Any]:
    if type(shard) is not str or shard not in SHARDS:
        raise ValueError("unknown frozen conditional paired shard")
    case_id=SHARDS[shard]
    return {
        "protocol":PROTOCOL,"shard":shard,
        "case_id":case_id, "replicas":list(REPLICAS),
        "arms":list(ARMS), "rows":[
            paired_case(case_id,replica) for replica in REPLICAS
        ],"only_constructed_worlds":True, "no_population_EV_claim":True,
    }


def combine_shards(shards: Mapping[str, Any]) -> dict[str, Any]:
    if type(shards) is not dict or set(shards)!=set(SHARDS):
        raise ValueError("missing/extra preregistered M4.29 case shard")
    grouped=[]
    for shard,case_id in SHARDS.items():
        data=shards[shard]
        if (type(data) is not dict or data.get("protocol")!=PROTOCOL
                or data.get("shard")!=shard or data.get("case_id")!=case_id
                or data.get("replicas")!=list(REPLICAS)
                or data.get("arms")!=list(ARMS)
                or data.get("only_constructed_worlds") is not True
                or data.get("no_population_EV_claim") is not True
                or type(data.get("rows")) is not list
                or len(data["rows"])!=len(REPLICAS)):
            raise ValueError("invalid conditional trial envelope")
        checked=[]
        for replica,row in zip(REPLICAS,data["rows"]):
            if (type(row) is not dict or row.get("case_id")!=case_id
                    or type(row.get("replica")) is not int
                    or row["replica"]!=replica
                    or row.get("exposed_peng")!=SPECS[case_id][0]
                    or row.get("cash_rule")!="current_m423"
                    or row.get("actor_seat")!=0
                    or row.get("same_initial_wall_and_hidden_hands") is not True
                    or row.get("complete_games")!=2
                    or row.get("natural_random_games")!=0):
                raise ValueError("missing paired world or physical match")
            arms=row.get("interventions")
            delta=row.get("forced_minus_hold")
            if (type(arms) is not dict or set(arms)!=set(ARMS)
                    or type(delta) is not dict or set(delta)!=set(METRICS)):
                raise ValueError("invalid action arms or official deltas")
            for arm in ARMS:
                a=arms[arm]
                if (type(a) is not dict
                        or a.get("terminal_phase") not in ("finished","wall_exhausted")
                        or type(a.get("actions_after_checkpoint")) is not int
                        or not 0<=a["actions_after_checkpoint"]<MAX_ACTIONS
                        or any(type(a.get(k)) is not int for k in METRICS)
                        or a["official_net"]!=sum(a[k] for k in LEDGER_PARTS)):
                    raise ValueError("nonterminal or invented official payoff")
            if any(delta[k]!=arms[ARMS[0]][k]-arms[ARMS[1]][k]
                   for k in METRICS):
                raise ValueError("changed/invented score deltas")
            if delta["official_net"]!=sum(delta[k] for k in LEDGER_PARTS):
                raise ValueError("score delta components not reconciled")
            checked.append(row)
        grouped.append({"case_id":case_id,
                        "mean_three_conditional_world_net_difference":mean(
                            r["forced_minus_hold"]["official_net"] for r in checked),
                        "conditional_world_net_differences":[
                            r["forced_minus_hold"]["official_net"] for r in checked],
                        "realized_robbed_forced_kongs":sum(
                            r["interventions"][ARMS[0]]["own_robbed_kongs"]
                            for r in checked
                        )})
    rows=[r for data in shards.values() for r in data["rows"]]
    means={k:round(mean(row["forced_minus_hold"][k] for row in rows),5)
           for k in METRICS}
    if abs(means["official_net"]-sum(means[k] for k in LEDGER_PARTS))>1e-4:
        raise RuntimeError("official mean ledger components mismatch")
    return {
        "protocol":PROTOCOL,
        "selected_conditional_case_clusters":len(CASES),
        "tail_permutations_per_case":len(REPLICAS),
        "paired_conditional_worlds":len(rows),
        "complete_terminal_games":len(rows)*len(ARMS),
        "independent_natural_shuffle_seeds":0,
        "weighted_difference_means_for_constructed_cases":means,
        "positive_conditional_world_deltas":sum(
            row["forced_minus_hold"]["official_net"]>0 for row in rows),
        "negative_conditional_world_deltas":sum(
            row["forced_minus_hold"]["official_net"]<0 for row in rows),
        "tied_conditional_world_deltas":sum(
            row["forced_minus_hold"]["official_net"]==0 for row in rows),
        "per_case":grouped,
        "online_policy_changed":False,
        "rob_probability_estimate":None,
        "natural_game_EV_estimate":None,
        "limitations":[
            "All initial hands were physically constructed, conditioned on an exposed peng and a retained fourth tile.",
            "Case IDs were selected because the two guard policies disagreed, never as representative random shuffles.",
            "Three wall permutations within each case are not independent natural-game samples.",
            "An intervention changes subsequent game trajectory and can change who draws a given wall tile.",
            "All other AI decisions remain seeded heuristics, not validated models of real human players.",
            "No calibrated win-rate or population EV claim follows from these conditional payoff differences.",
        ],
    }
