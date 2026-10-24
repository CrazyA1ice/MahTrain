"""M3.6 full-turn, four-agent closed-loop trial under draft game rules.

This is NOT a formal win-rate tournament: kong prices and exhausted-wall
settlements are unresolved; the legal prototype can stop at either three wins
or a depleted wall. Identical shuffles and three seat-rotated assignments
balance each heuristic tier's exposure to deal positions.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import mean
from time import perf_counter_ns
from typing import Any, Callable

from .ai import (AI_LEVELS, ABLATION_VARIANTS, MahjongAgent,
                 AblationMahjongAgent, visible_tiles)
from .ai_baseline import ShapeBaselineAgent
from .efficiency import analyze_discards
from .four_player import FourPlayerOpening
from .ai_seed_stats import analyze_seed_clusters
from .ai_controlled_scores import controlled_official_scores
from .ai_pressure_diagnostics import diagnose_pressure_tiebreak


def _validate(seed_start: int, seeds: int) -> None:
    if (type(seed_start) is not int or not 0 <= seed_start < 2**32
            or type(seeds) is not int or not 1 <= seeds <= 100
            or seed_start + seeds > 2**32):
        raise ValueError("seed_start must be uint32 and seeds 1..100")


def seat_assignment(rotation: int) -> list[str]:
    if type(rotation) is not int or rotation not in (0, 1, 2):
        raise ValueError("rotation must be 0, 1 or 2")
    return [AI_LEVELS[(seat + rotation) % 3] for seat in range(4)]


def _take_action(game: FourPlayerOpening, agents: dict[int, Any],
                 trace: list[dict[str, Any]],
                 durations: dict[str, list[float]]) -> None:
    phase = game.phase
    if phase == "await_draw":
        seat = game.turn
        game.draw(seat)
        trace.append({"phase":phase, "seat":seat,"action":"draw"})
        return

    if phase in ("claim_window", "rob_kong_window"):
        rob = phase == "rob_kong_window"
        source = (game._pending_kong["seat"] if rob else
                  game._pending_discard["seat"])
        candidates = [
            s for s in range(4)
            if s != source and not game._won[s] and s not in game._responses
        ]
        if not candidates:
            raise RuntimeError("unresolved response window without responders")
        seat = candidates[0]
        view = game.private_view(seat)
        level = agents[seat].level
        start = perf_counter_ns()
        choice = agents[seat].response(view,rob=rob)
        elapsed = (perf_counter_ns()-start)/1_000_000
        durations[level].append(elapsed)
        options = view["rob_options"] if rob else view["claim_options"]
        if choice not in options:
            raise RuntimeError("AI selected an illegal response")
        trace.append({
            "phase":phase,"seat":seat,"level":level,"action":choice,
            "legal_options":options,
            "source":source,
            "tile":view["pending_rob_kong"]["tile"] if rob
                  else view["pending_discard"]["tile"],
        })
        if rob:
            game.respond_rob_kong(seat,choice)
        else:
            game.respond_discard(seat,choice)
        return

    if phase in ("await_discard", "dealer_discard"):
        seat=game.turn
        view=game.private_view(seat)
        agent=agents[seat]
        level=agent.level
        if view["can_self_draw_win"]:
            game.declare_self_win(seat)
            trace.append({"phase":phase,"seat":seat,"level":level,
                          "action":"self_draw_win"})
            return
        start=perf_counter_ns()
        kong=agent.kong(view)
        elapsed=(perf_counter_ns()-start)/1_000_000
        durations[level].append(elapsed)
        if kong is not None:
            if kong not in view["kong_options"]:
                raise RuntimeError("AI chose an illegal kong")
            game.declare_kong(seat,kong["type"],kong["tile"])
            trace.append({
                "phase":phase,"seat":seat,"level":level,
                "action":kong["type"],
                "tile":None if kong["type"]=="an_gang" else kong["tile"],
            })
            return
        start=perf_counter_ns()
        tile=agent.discard(view)
        elapsed=(perf_counter_ns()-start)/1_000_000
        durations[level].append(elapsed)
        # Benchmark the ACTUAL cut after the choice, using precisely the same
        # public information and own tiles, not any opponents' hidden hands.
        oracle=analyze_discards(
            view["hand"],view["own_melds"],
            missing_suit=view["missing_suits"][seat],
            visible_tiles=visible_tiles(view),
        )
        options={v["discard"]:v for v in oracle["candidates"]}
        if tile not in options:
            raise RuntimeError("AI chose an illegal discard")
        row=options[tile]
        event={
            "phase":phase,"seat":seat,"level":level,
            "action":"discard","tile":tile,
            "shanten_after":row["shanten"],
            "minimum_shanten":oracle["minimum_shanten"],
            "shanten_regret":row["shanten"]-oracle["minimum_shanten"],
            "effective_copies":row["effective_tile_count"],
            "locally_optimal":bool(row["local_optimal"]),
        }
        if (level in ("challenge", "challenge_no_pressure") and not
                getattr(agent, "_offline_reference_cut", False)):
            # Offline reference-cut controls deliberately do NOT make a
            # challenge-policy choice. Its pressure tiebreak probe checks
            # equality to the live challenge decision, so it is inapplicable.
            # The real challenge agent and live game remain unchanged.
            # Private, aggregate-only instrumentation. The unplayed shadow
            # tile never enters the trace, public replay or network result.
            event["pressure_probe"]=diagnose_pressure_tiebreak(
                view, oracle, tile, policy=level,
                ranking=getattr(agent, "_last_discard_scores", None),
            )
        trace.append(event)
        game.discard(seat,tile)
        return
    raise RuntimeError("unexpected phase in multi-agent trial: "+str(phase))



def explain_public_action(action: dict[str, Any],
                          board: dict[str, Any]) -> dict[str, str]:
    """Safe POLICY rationale from public action + already-public board only.

    Never claim a private numerical justification (shanten/ukeire/risk exact
    values); such metrics stay server-side even after the hand is over.
    """
    kind=action["action"]
    seat=action["seat"]
    level=action.get("level")
    if kind=="discard":
        suits=board["missing_suits"]
        missing=suits[seat] if suits is not None else None
        if missing and action["tile"][0]==missing:
            code="discard_missing"
            explanation="本次切掉已公开的定缺花色。当前对照策略都优先处理定缺牌；这一行为不能单独证明切牌为全局最优。"
        elif level=="baseline":
            code="baseline_shape_policy"
            explanation="独立牌形基线按自己的同牌及邻牌数量选择孤立牌；不使用向听数、有效进张评估器或对手暗牌。"
        elif level=="basic":
            code="basic_discard"
            explanation="入门档在可选切牌范围内按种子随机选择；不公开用到的自家暗手和私有牌效数据。"
        elif level=="challenge_no_ukeire":
            code="ablation_no_ukeire_policy"
            explanation="消融版本只按向听与公开副露弱风险规则选切牌；不调用有效进张排序，不公布隐藏牌效。"
        elif level=="challenge_no_pressure":
            code="ablation_no_pressure_policy"
            explanation="消融版本按向听与公开信息有效进张排序；不使用公开副露花色压力平局规则。"
        elif level=="advanced":
            code="advanced_policy"
            explanation="进阶档的切牌策略优先降低切后向听数；此处只说明算法规则，不公布本家隐藏向听数。"
        else:
            code="challenge_policy"
            explanation="挑战档优先向听、再考虑公开信息有效进张；完全并列才参考公开副露的弱风险信号。此处不声称风险已准确预测。"
    elif kind=="response_submitted":
        code="sealed_response"
        explanation="响应仍在密封收集中；此时不能公开选的是胡、碰、杠还是过。"
    elif kind=="response_resolved":
        code="resolved_response"
        explanation="活跃玩家的响应已经经过规则状态机统一裁决；只公开最终牌权结果。"
    elif kind=="declare_missing":
        code="sealed_missing" if board["missing_suits"] is None else "missing_revealed"
        explanation=("每家选缺门仍为密封声明，尚未统一公开。" if
                     board["missing_suits"] is None else
                     "四家完成定缺后才同时揭示全部缺门，未提前暴露单家的选择。")
    elif kind=="exchange_three":
        code="sealed_exchange"
        explanation="仅记录本家已密封提交同花色三张；具体换出牌不进入公开复盘。"
    elif kind=="an_gang":
        code="concealed_kong"
        explanation="暗杠已成立，补牌由规则引擎执行；公开复盘不显示暗杠牌种或补牌内容。"
    elif kind in ("ming_gang","bu_gang"):
        code="kong_claim"
        explanation="公开杠牌操作由状态机核验合法性并处理尾墙补摸及可能的抢杠；不推断隐藏牌。"
    elif kind=="self_draw_win":
        code="verified_self_win"
        explanation="已由服务端合法胡牌判定后执行自摸；不在公开复盘中展开暗手牌型或私有听口。"
    elif kind=="draw":
        code="hidden_draw"
        explanation="按当前牌墙规则摸牌，只更新公开的张数与行动状态；新摸到的牌不公开。"
    else:
        code="public_event"
        explanation="只显示已结算或当时可公开的操作，不展示隐藏决策明细。"
    return {"code":code,"text":explanation,"scope":"public_policy_only"}


def public_replay_frame(game: FourPlayerOpening, action: dict[str, Any]) -> dict[str, Any]:
    """Capture PUBLIC board after this action. No seat-private effective draws.

    The trace still retains post-game metrics for aggregate benchmarking, but
    browser replay explicitly excludes opponent shanten and claim options.
    """
    state=game.public_state()
    visible_action={
        k:v for k,v in action.items()
        if k in ("phase","seat","level","action","tile","source","suit","count")
    }
    # Even when a concealed kong's server-side trace gains a tile later,
    # its public replay may never reveal the tile.
    if action.get("action")=="an_gang":
        visible_action.pop("tile",None)
    # Four sealed dingque selections become public ONLY after all are in;
    # revealing each submission as it happens breaks simultaneous disclosure.
    if action.get("action")=="declare_missing":
        visible_action.pop("suit",None)
    if action.get("phase") in ("claim_window","rob_kong_window"):
        # Claims/rob decisions are private until arbitration. A player's
        # "hu", "peng", or "pass" cannot appear as a live public replay action
        # while other seats have yet to respond.
        settled=state["phase"]!=action["phase"]
        visible_action["action"]=(
            "response_resolved" if settled else "response_submitted"
        )
        if settled:
            public_types={
                "ron","multi_ron","peng","ming_gang","all_pass",
                "rob_kong","bu_gang",
            }
            public_result=next((
                e["type"] for e in reversed(state["events"])
                if e["type"] in public_types
            ),None)
            if public_result:
                visible_action["resolution"]=public_result
    return {
        "action":visible_action,
        "explanation":explain_public_action(visible_action,state),
        "board":{
            "phase":state["phase"],"turn":state["turn"],
            "dealer":state["dealer"],"wall_count":state["wall_count"],
            "hand_counts":state["hand_counts"],"missing_suits":state["missing_suits"],
            "won":state["won"],"melds":state["melds"],
            "discards":state["discards"],
            "winners":[
                {"seat":w["seat"],"source":w["source"],"kind":w["kind"]}
                for w in state["winners"]
            ],
        },
    }


def simulate_match(seed: int, rotation: int = 0,
                   *, max_actions: int = 800,
                   lineup: list[str] | None = None,
                   offline_observer: Callable[[FourPlayerOpening], None] | None = None,
                   offline_agent_overrides: dict[int, Any] | None = None,
                   offline_kong_base: int | None = None,
                   offline_ruleset: str = "frozen_pre_m423"
                   ) -> dict[str, Any]:
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be an unsigned 32-bit integer")
    if type(max_actions) is not int or not 40 <= max_actions <= 5000:
        raise ValueError("max_actions must be 40..5000")
    if lineup is None:
        assignment=seat_assignment(rotation)
    else:
        if (type(lineup) is not list or len(lineup)!=4 or
            any(type(level) is not str or level not in (*AI_LEVELS,"baseline",*ABLATION_VARIANTS)
                for level in lineup) or len(set(lineup))!=4):
            raise ValueError("independent lineup needs 4 distinct AI policies")
        assignment=list(lineup)
    # Defaults preserve public simulation behaviour. Offline research can
    # explicitly enable the official kong ledger so its paired score measures
    # complete current-rule net balances, not Hu-only legacy approximations.
    if offline_kong_base is not None and (type(offline_kong_base) is not int
                                          or offline_kong_base < 0):
        raise ValueError("offline kong base must be a nonnegative integer")
    # All historical M3/M4 experiment seed results were generated with
    # old any-turn bu-gang money. Do not silently rewrite their frozen
    # official ledgers when changing the live rule. New independent
    # studies must explicitly request the current M4.23 ruleset.
    if offline_ruleset not in ("frozen_pre_m423", "current_m423"):
        raise ValueError("unsupported offline rule profile")
    game=FourPlayerOpening(
        seed, kong_base=offline_kong_base,
        legacy_bugang_cash=(offline_ruleset=="frozen_pre_m423"),
    )
    agents={
        seat:(ShapeBaselineAgent(seed=seed,seat=seat)
              if assignment[seat]=="baseline" else
              AblationMahjongAgent(assignment[seat],seed=seed,seat=seat)
              if assignment[seat] in ABLATION_VARIANTS else
              MahjongAgent(assignment[seat],seed=seed,seat=seat))
        for seat in range(4)
    }
    if offline_agent_overrides is not None:
        for seat, agent in offline_agent_overrides.items():
            if (type(seat) is not int or seat not in range(4)
                or assignment[seat] != "challenge"
                or not isinstance(agent, MahjongAgent)
                or agent.level != "challenge" or agent.seat != seat):
                raise ValueError("offline overrides require a matching challenge agent")
            agents[seat] = agent
    trace=[]
    frames=[]
    durations=defaultdict(list)
    for seat in range(4):
        proposed=agents[seat].exchange(game.private_view(seat))
        game.select_exchange(seat,proposed)
        trace.append({"phase":"exchange_select","seat":seat,
                      "level":assignment[seat],"action":"exchange_three",
                      "count":3})
        frames.append(public_replay_frame(game,trace[-1]))
    for seat in range(4):
        suit=agents[seat].missing(game.private_view(seat))
        game.select_missing(seat,suit)
        trace.append({"phase":"missing_select","seat":seat,
                      "level":assignment[seat],"action":"declare_missing",
                      "suit":suit})
        frames.append(public_replay_frame(game,trace[-1]))
    for _ in range(max_actions):
        if game.phase in ("wall_exhausted","finished"):
            break
        # Offline-only research probe, invoked before any agent action.
        # Not used by web_server; deliberately never appended to the public
        # trace, replay, network output or saved match archive.
        if offline_observer is not None and game.phase in (
            "await_discard", "dealer_discard"
        ):
            offline_observer(game)
        _take_action(game,agents,trace,durations)
        frames.append(public_replay_frame(game,trace[-1]))
    else:
        raise RuntimeError(
            f"trial exceeded {max_actions} actions, seed={seed}, rotation={rotation}"
        )
    conservation=game.debug_tile_counts()
    if conservation["total"] != 108:
        raise RuntimeError("trial lost physical tiles")
    board=game.public_state()
    if not board["win_ledger"]["zero_sum"] or not board["kong_ledger"]["zero_sum"]:
        raise RuntimeError("non-zero-sum prototype ledger")
    if game.phase == "finished" and sum(board["won"]) != 3:
        raise RuntimeError("finished before exactly three players won")
    if game.phase=="wall_exhausted" and board["wall_count"]!=0:
        raise RuntimeError("wall exhaustion claimed with remaining tiles")
    # Only PUBLIC state and offered responses go into the downloadable log.
    # An-gang tile is masked and no opponent concealed or wall tiles leak.
    return {
        "seed":seed,"rotation":rotation,"dealer":board["dealer"],
        "assignment":assignment,"terminal_phase":board["phase"],
        "actions":len(trace),"wall_remaining":board["wall_count"],
        "winners":[
            {"seat":w["seat"],"level":assignment[w["seat"]],
             "kind":w["kind"],"source":w["source"]}
            for w in board["winners"]
        ],
        "partial_win_balances":board["win_ledger"]["balances"],
        # This is an AUTHORITATIVE one-shot rule-A score, not the preview.
        # Keep HU-only results separate for legacy statistics.
        "official_settled_balances":board["settled_balances"],
        # Separate AUTHORITATIVE ledger components. They are already public
        # in FourPlayerOpening.public_state(), and let offline policy
        # experiments attribute the exact delta to Hu, priced kongs or
        # exhaustive-wall settlements without reverse-engineering events.
        "official_kong_balances":board["kong_ledger"]["balances"],
        "official_exhaustive_balances":(
            board["exhaustive_settlement"]["balances"]
            if board["exhaustive_settlement"] is not None
            else [0, 0, 0, 0]
        ),
        "official_exhaustive_posted":bool(
            board["exhaustive_settlement"] is not None and
            board["exhaustive_settlement"]["posted"]),
        "scoring_rules":{
            "room_coefficient":game.ledger.room_coefficient,
            "fan_cap":game.ledger.fan_cap,
            "kong_base":game.kong_ledger.base,
        },
        "unpriced_kong_events":len(board["kong_ledger"]["events"]),
        "exhaustive_preview_not_posted":(
            bool(board["exhaustive_review"] is not None)
            and not board["exhaustive_review"]["posted"]
        ),
        "public_events":board["events"],
        "trace":trace,
        "public_replay":frames,
        "timings_ms":{level:round(mean(values),4)
                      for level,values in durations.items() if values},
        "physical_count":conservation["total"],
    }


def tournament(seed_start: int = 0, seeds: int = 2,
               *, include_traces: bool = True,
               on_match: Any = None) -> dict[str, Any]:
    _validate(seed_start,seeds)
    games=[]
    for seed in range(seed_start,seed_start+seeds):
        for rotation in range(3):
            game=simulate_match(seed,rotation)
            games.append(game)
            if on_match is not None:
                on_match(len(games),seeds*3)
    by_level={}
    for level in AI_LEVELS:
        seats=[(game,seat) for game in games
               for seat,assigned in enumerate(game["assignment"])
               if assigned==level]
        winners=[winner for game in games for winner in game["winners"]
                 if winner["level"]==level]
        discards=[event for game in games for event in game["trace"]
                  if event.get("level")==level and event["action"]=="discard"]
        choices=[event for game in games for event in game["trace"]
                 if event.get("level")==level and event["action"] not in
                 ("exchange_three","declare_missing","draw")]
        latencies=[game["timings_ms"][level]
                   for game in games if level in game["timings_ms"]]
        exposed=len(seats)
        if exposed != seeds*4:
            raise RuntimeError("unbalanced AI seat exposure")
        by_level[level]={
            "seat_exposures":exposed,
            "win_events":len(winners),
            "win_event_fraction":round(len(winners)/exposed,4),
            "self_draws":sum(w["kind"]=="self_draw" for w in winners),
            "discard_wins":sum(w["kind"]=="ron" for w in winners),
            "rob_kong_wins":sum(w["kind"]=="rob_kong" for w in winners),
            "deal_in_events":sum(
                w["source"]==seat and w["source"]!=w["seat"]
                for game,seat in seats for w in game["winners"]
            ),
            "partial_hu_points_per_seat_exposure":round(
                sum(game["partial_win_balances"][seat]
                    for game,seat in seats)/exposed,3),
            "discards":len(discards),
            "discard_min_shanten_fraction":(
                round(sum(e["shanten_regret"]==0 for e in discards)/
                      len(discards),4) if discards else None
            ),
            "discard_local_optimal_fraction":(
                round(sum(e["locally_optimal"] for e in discards)/
                      len(discards),4) if discards else None
            ),
            "mean_shanten_regret":(
                round(mean(e["shanten_regret"] for e in discards),4)
                if discards else None
            ),
            "policy_decisions":len(choices),
            "mean_game_level_policy_ms":(
                round(mean(latencies),4) if latencies else None
            ),
        }
    return {
        "protocol":"seat_rotated_closed_loop_v1",
        "seed_start":seed_start,"seeds":seeds,
        "games":len(games),
        "terminal_phase_counts":{
            terminal:sum(g["terminal_phase"]==terminal for g in games)
            for terminal in ("finished","wall_exhausted")
        },
        "seat_balance":"each level occupies every seat equally across 3 rotations",
        "partial_ledger_only":True,
        "limitations":[
            "heuristic AI playing heuristic AI, not independent human match wins",
            "win_event_fraction is not formal fully-settled win rate",
            "exhaustive draw flower-pig/da-jiao payouts unposted",
            "kong prices unconfigured and unposted",
            "decision latency depends on CI hardware/cache",
            "rule preset still draft and disabled",
        ],
        "levels":by_level,
        "seed_analysis":analyze_seed_clusters(games),
        "official_score_analysis":controlled_official_scores(games),
        "matches":games if include_traces else [
            {k:v for k,v in g.items()
             if k not in ("trace","public_events","public_replay")}
            for g in games
        ],
    }
