"""Local-only stdlib web interface for MahTrain 14-round solo training.

Run: python web_server.py
Open http://127.0.0.1:8765

This is an intentionally local development server, not a production/multiplayer
service. All session state and the shuffled wall stay in Python server memory.
"""
from __future__ import annotations

import errno
import json
import mimetypes
import secrets
import sys
import threading
from time import perf_counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from mahtrain_core import SoloTrainingSession, FourPlayerOpening  # noqa: E402
from mahtrain_core.ai import MahjongAgent, AI_LEVELS  # noqa: E402
from mahtrain_core.rules import winning_tiles  # noqa: E402
from mahtrain_core.classic_hint import classic_hand_hint  # noqa: E402
from mahtrain_core.ai_tournament import tournament  # noqa: E402
from mahtrain_core.ai_independent_benchmark import independent_benchmark  # noqa: E402
from mahtrain_core.training import MODES, generate_question, grade_answer
from mahtrain_core.training_levels import DIFFICULTIES
from mahtrain_core.error_focus import (
    ERROR_LABELS, supports_focus, select_focused_question, diagnose_quiz,
)
from mahtrain_core.history import HistoryStore  # noqa: E402
from mahtrain_core.match_archive import MatchArchive  # noqa: E402
from mahtrain_core.next_dealer import next_dealer  # noqa: E402
from mahtrain_core.post_round_review import record_transition  # noqa: E402

# Override MAHTRAIN_HISTORY_DB to relocate the local, single-user SQLite file.
import os
_HISTORY_DB = Path(os.environ.get("MAHTRAIN_HISTORY_DB",
                                     str(ROOT / "data" / "mahtrain_history.sqlite3")))
_HISTORY = HistoryStore(_HISTORY_DB)
_MATCH_ARCHIVE = MatchArchive(Path(os.environ.get("MAHTRAIN_MATCH_DB",
                                               str(_HISTORY_DB))))

_SESSIONS: dict[str, SoloTrainingSession] = {}
_QUIZZES: dict[str, dict] = {}
_TABLE_DEMOS: dict[str, FourPlayerOpening] = {}
_MATCH_SESSIONS: dict[str, FourPlayerOpening] = {}
_MATCH_AGENTS: dict[str, dict[int, MahjongAgent]] = {}
_MATCH_HISTORY: dict[str, list[dict]] = {}
_MATCH_OPENING: dict[str, dict] = {}
_MATCH_ARCHIVE_IDS: dict[str, str] = {}
_MATCH_SUCCESSORS: dict[str, str] = {}  # idempotent new round per completed token
# Never reuse an automatically generated match seed during this server process.
# Experimental fixed seeds remain opt-in for reproducible rule tests.
_MATCH_USED_SEEDS: set[int] = set()


def _automatic_match_seed() -> int:
    if len(_MATCH_USED_SEEDS) >= 2**32:
        raise RuntimeError("no unused match seeds remain")
    seed = secrets.randbelow(2**32)
    while seed in _MATCH_USED_SEEDS:
        seed = secrets.randbelow(2**32)
    return seed

_AI_REPLAY_JOBS: dict[str, dict] = {}
_MAX_REPLAY_JOBS = 4
_MAX_ACTIVE_REPLAY_JOBS = 1
_LOCK = threading.RLock()
_MAX_SESSIONS = 32
_STATIC = {
    "/": ROOT / "web" / "index.html",
    "/app.css": ROOT / "web" / "app.css",
    "/match_table_v2.css": ROOT / "web" / "match_table_v2.css",
    "/app.js": ROOT / "web" / "app.js",
    "/review.js": ROOT / "web" / "review.js",
    "/retry.js": ROOT / "web" / "retry.js",
    "/history.js": ROOT / "web" / "history.js",
    "/quiz.js": ROOT / "web" / "quiz.js",
    "/quiz_history.js": ROOT / "web" / "quiz_history.js",
    "/four_player.js": ROOT / "web" / "four_player.js",
    "/match.js": ROOT / "web" / "match.js",
    "/match_playback.js": ROOT / "web" / "match_playback.js",
    "/match_voice.js": ROOT / "web" / "match_voice.js",
    "/match_archives.js": ROOT / "web" / "match_archives.js",
    "/match_stats.js": ROOT / "web" / "match_stats.js",
    "/navigation.js": ROOT / "web" / "navigation.js",
    "/ai_replay.js": ROOT / "web" / "ai_replay.js",
    "/ai_baseline.js": ROOT / "web" / "ai_baseline.js",
    "/tile_art.js": ROOT / "web" / "tile_art.js",
    "/sound.js": ROOT / "web" / "sound.js",
}
_SUITS = ("万", "条", "筒")


def _asset_path(url_path: str) -> Path | None:
    if url_path in _STATIC:
        return _STATIC[url_path]
    # Genuine kobalab/Majiang 2D client is compiled by Vite.
    # A strict filename whitelist prevents arbitrary source exposure.
    if url_path in ("/classic", "/classic/", "/classic/game.html"):
        return ROOT / "frontend_2d" / "dist" / "game.html"
    for prefix in ("/classic/assets/", "/classic/img/"):
        if url_path.startswith(prefix):
            name=url_path[len(prefix):]
            if (name and len(name)<160
                    and all(ch.isascii() and (ch.isalnum() or ch in "._-")
                            for ch in name)
                    and name not in (".","..")):
                group="assets" if prefix.endswith("assets/") else "img"
                return ROOT / "frontend_2d" / "dist" / group / name
            return None

    # The entire Queju 3D front end is built independently by Vite.
    # Serve ONLY its compiled entry/assets; never serve TypeScript source,
    # private game state, node_modules or path traversal outside dist.
    if url_path in ("/3d", "/3d/", "/3d/game.html"):
        return ROOT / "frontend_3d" / "dist" / "game.html"
    if url_path.startswith("/3d/assets/"):
        name = url_path[len("/3d/assets/"):]
        if (name and len(name) < 200 and
            all(ch.isascii() and (ch.isalnum() or ch in "._-") for ch in name)
            and name not in (".", "..")):
            return ROOT / "frontend_3d" / "dist" / "assets" / name
        return None
    prefix = "/assets/tiles/"
    if not url_path.startswith(prefix):
        return None
    filename = unquote(url_path[len(prefix):])
    if filename == "640x420.jpeg":
        return ROOT / "assets" / "tiles" / filename
    if (
        len(filename) == len("万1.png")
        and filename[0] in _SUITS
        and filename[1] in "123456789"
        and filename.endswith(".png")
    ):
        return ROOT / "assets" / "tiles" / filename
    return None


def _demo_exchange_choice(hand: list[str]) -> list[str]:
    """Deterministic scripted selection; NOT strategic AI."""
    for suit in ("m", "s", "p"):
        owned = [t for t in hand if t.startswith(suit)]
        if len(owned) >= 3:
            return owned[:3]
    raise RuntimeError("invalid demo hand without a three-card suit")


def _demo_auto_until_human(game: FourPlayerOpening) -> None:
    """Demo-only all-pass and scripted opponent cuts; never claim as real play."""
    for _ in range(32):
        if game.phase == "claim_window":
            game.pass_all_claims_demo()
        if game.phase in ("wall_exhausted", "exchange_select", "missing_select"):
            return
        if game.turn == 0 and game.phase in ("dealer_discard", "await_discard"):
            return
        if game.phase == "await_draw":
            # Seat zero's draw is included in the scripted round transition.
            game.draw(game.turn)
        elif game.phase in ("dealer_discard", "await_discard"):
            current = game.turn
            hand = game.private_view(current)["hand"]
            # Toy heuristic: cut missing-suit tiles first, otherwise first tile.
            missing = game.missing_suits[current]
            tile = next((t for t in hand if t.startswith(missing)), hand[0])
            game.discard(current, tile)
        else:
            raise RuntimeError("unexpected four-player demo phase")
    raise RuntimeError("demo autoplay failed to reach human turn")


def _match_private_view(game: FourPlayerOpening,
                        agents: dict[int, MahjongAgent]) -> dict:
    """Send seat 0 ONLY: published AI level/strategy, never AI hidden cards."""
    view = game.private_view(0)
    view["ready_waits"] = []
    view["ready_after_discards"] = []
    # This is a strictly seat-zero-only presentation hint, not an AI input.
    # waiting_tiles returns STRUCTURAL wait kinds, not unknown-wall odds.
    missing = game.missing_suits[0]
    hand = view["hand"]
    melds = view["own_melds"]
    effective = len(hand) + 3*len(melds)
    # During AI-only transitions, skip expensive 27-tile wait scans;
    # they are rebuilt when seat zero actually gets its turn.
    if (game.turn == 0 and game.phase in
            ("dealer_discard","await_discard")
            and missing in ("m", "s", "p") and not game._won[0]
            and not any(tile[0] == missing for tile in hand)):
        if effective == 13:
            view["ready_waits"] = winning_tiles(hand, melds, missing)
        elif effective == 14 and game.turn == 0 and (
                game.phase in ("dealer_discard","await_discard")):
            for cut in sorted(set(hand)):
                remaining = list(hand)
                remaining.remove(cut)
                waits = winning_tiles(remaining, melds, missing)
                if waits:
                    view["ready_after_discards"].append({
                        "discard": cut, "waits": waits,
                    })
    view["series_round"] = getattr(game, "series_round", 1)
    view["dealer_origin"] = getattr(game, "dealer_origin", "首局随机庄")
    # Next-dealer derivation is disclosed only after the authoritative
    # round has finished, so no future action or private inference leaks.
    if game.phase in ("finished", "wall_exhausted"):
        view["next_dealer"] = next_dealer(game.public_state())
    view["ai_opponents"] = [
        {"seat": seat, "difficulty": agents[seat].level,
         "description": agents[seat].policy_description()}
        for seat in (1, 2, 3)
    ]
    return view


_MATCH_PUBLIC_BOARD_FIELDS = (
    "phase", "turn", "wall_count", "hand_counts", "melds",
    "discards", "won",
)
_MAX_MATCH_PUBLIC_STEPS = 96
# These public moves are visible or narrated; cross at most one per HTTP
# continuation. Silent draws, claim passes and arbitration may be combined.
# The browser no longer waits for audio completion before continuing.
_MATCH_TURN_BEATS = frozenset((
    "discard", "peng", "ming_gang", "an_gang", "bu_gang_declared",
    "bu_gang", "ron", "multi_ron", "rob_kong", "self_draw_win",
))
_MAX_SILENT_CONTINUATIONS = 8


def _match_public_board(game: FourPlayerOpening) -> dict:
    """Only public, stable board facts. No wall, concealed hands or draws."""
    published = game.public_state()
    return {key: published[key] for key in _MATCH_PUBLIC_BOARD_FIELDS}


def _match_public_step(game: FourPlayerOpening, before_events: int,
                       output: list[dict]) -> None:
    """Record one completed rules transition, not fictitious event substeps."""
    board = game.public_state()
    events = board["events"][before_events:]
    if not events:
        return
    # Each snapshot is captured after the actual rules action finished.
    # One action can emit several bookkeeping/public events: keep those
    # grouped instead of claiming a non-existent intermediate board.
    output.append({
        "events": events,
        "board": {key: board[key] for key in _MATCH_PUBLIC_BOARD_FIELDS},
    })
    if len(output) > _MAX_MATCH_PUBLIC_STEPS:
        del output[:len(output)-_MAX_MATCH_PUBLIC_STEPS]


def _match_record(game: FourPlayerOpening, output: list[dict],
                  action) -> None:
    before = len(game._events)
    prior = len(output)
    hands_before = [list(h) for h in game._hands]
    # Only obtain the authorized, actual deciding seat BEFORE a discard.
    # These private captures never enter public_steps or live HTTP views.
    seats = {}
    if game.phase in ("await_discard", "dealer_discard") and game.turn is not None:
        seats[game.turn] = game.private_view(game.turn)
    action()
    _match_public_step(game, before, output)
    if len(output)>prior:
        review=getattr(game,"_sealed_review",None)
        if review is not None:
            review.append(record_transition(
                game,game._events[before:],hands_before,seats))


def _match_script_until_human(
    game: FourPlayerOpening, agents: dict[int, MahjongAgent],
    steps: list[dict] | None = None, *, max_actions: int = 512,
) -> None:
    """Run fair-visibility AI actions, bounded for interactive playback.

    Full automation retains the historical default of 512. Web interaction
    requests only one transition and waits for the browser to complete its
    spoken + visible turn before triggering the next request.


    Rule engine alone can adjudicate all legal claims and response priority;
    each bot chooses from its OWN seat-authorized private view and public
    state, never hidden wall, other hands or opponents' secret W0.
    """
    if steps is None:
        steps = []
    for _ in range(max_actions):
        phase = game.phase
        if phase in ("exchange_select", "missing_select",
                     "finished", "wall_exhausted"):
            return
        if phase in ("claim_window", "rob_kong_window"):
            for seat in range(4):
                if game._won[seat]:
                    continue
                source = (game._pending_discard["seat"] if phase=="claim_window"
                          else game._pending_kong["seat"])
                if seat==source or seat in game._responses:
                    continue
                view=game.private_view(seat)
                options = (view["claim_options"] if phase=="claim_window"
                           else view["rob_options"])
                if seat==0 and len(options)>1:
                    return  # Human must decide; no implicit missed HU.
                selection=("pass" if seat==0 else
                           agents[seat].response(view,
                               rob=(phase=="rob_kong_window")))
                if phase=="claim_window":
                    _match_record(game,steps,lambda seat=seat,selection=selection:
                                  game.respond_discard(seat,selection))
                else:
                    _match_record(game,steps,lambda seat=seat,selection=selection:
                                  game.respond_rob_kong(seat,selection))
                if max_actions != 512:
                    return  # One confirmed response at a time.
                if game.phase!=phase:
                    break
            else:
                if game.phase==phase:
                    raise RuntimeError("AI response arbitration did not settle")
            continue
        if phase=="await_draw":
            _match_record(game,steps,lambda: game.draw(game.turn))
            continue
        if phase in ("await_discard","dealer_discard"):
            if game.turn==0:
                return
            seat=game.turn
            view=game.private_view(seat)
            agent=agents[seat]
            if view["can_self_draw_win"]:
                _match_record(game,steps,lambda: game.declare_self_win(seat))
                continue
            chosen_kong=agent.kong(view)
            if chosen_kong is not None:
                _match_record(game,steps,lambda: game.declare_kong(
                    seat,chosen_kong["type"],chosen_kong["tile"]))
                continue
            choice = agent.discard(view)
            _match_record(game,steps,lambda: game.discard(seat,choice))
            continue
        raise RuntimeError("unexpected AI match phase: "+str(phase))
    if max_actions == 512:
        raise RuntimeError("AI script exceeded 512 transitions")


def _match_requires_continue(game: FourPlayerOpening) -> bool:
    """True only when the human has no required decision yet."""
    if game.phase in ("exchange_select","missing_select",
                      "finished","wall_exhausted"):
        return False
    if game.phase in ("dealer_discard","await_discard"):
        return game.turn != 0
    if game.phase == "await_draw":
        return True
    if game.phase in ("claim_window","rob_kong_window"):
        source=(game._pending_discard["seat"]
                if game.phase=="claim_window" else game._pending_kong["seat"])
        if source == 0 or 0 in game._responses:
            return True
        options=(game.claim_options(0) if game.phase=="claim_window"
                 else game.rob_options(0))
        return len(options) <= 1
    return False


def _replay_worker(token: str, seed_start: int, seeds: int) -> None:
    """Slow multi-AI runs live outside the global HTTP session lock."""
    def progress(done: int, total: int) -> None:
        with _LOCK:
            job=_AI_REPLAY_JOBS.get(token)
            if job is not None:
                job["completed_games"]=done

    try:
        result=tournament(seed_start,seeds,on_match=progress)
    except Exception as exc:
        # The development UI receives concise diagnostics, no traceback or
        # inaccessible private wall/hand details.
        with _LOCK:
            if token in _AI_REPLAY_JOBS:
                _AI_REPLAY_JOBS[token].update({
                    "status":"error",
                    "error":"试验计算失败："+str(exc)[:180],
                })
    else:
        with _LOCK:
            if token in _AI_REPLAY_JOBS:
                _AI_REPLAY_JOBS[token].update({
                    "status":"done","result":result,
                    "completed_games":result["games"],
                })


def _independent_worker(token: str, seed_start: int, seeds: int) -> None:
    def progress(done: int, total: int) -> None:
        with _LOCK:
            job=_AI_REPLAY_JOBS.get(token)
            if job is not None:
                job["completed_games"]=done

    try:
        result=independent_benchmark(seed_start,seeds,on_match=progress)
    except Exception as exc:
        with _LOCK:
            if token in _AI_REPLAY_JOBS:
                _AI_REPLAY_JOBS[token].update({
                    "status":"error",
                    "error":"独立基线评测失败："+str(exc)[:180],
                })
    else:
        with _LOCK:
            if token in _AI_REPLAY_JOBS:
                _AI_REPLAY_JOBS[token].update({
                    "status":"done","result":result,
                    "completed_games":result["games"],
                })


def _replay_summary(job: dict) -> dict:
    response={
        "status":job["status"],
        "completed_games":job["completed_games"],
        "total_games":job["seeds"]*(4 if job.get("mode")=="baseline" else 3),
        "seed_start":job["seed_start"],
        "seeds":job["seeds"],
    }
    if job["status"]=="error":
        response["error"]=job["error"]
    if job["status"]=="done" and job.get("mode")=="baseline":
        result=job["result"]
        response["overview"]={
            "protocol":result["protocol"],
            "independent_shuffle_seeds":result["independent_shuffle_seeds"],
            "games":result["games"],
            "opponents":result["opponents"],
            "terminal_phase_counts":result["terminal_phase_counts"],
            "levels":result["levels"],
            "paired_differences_vs_baseline":result[
                "paired_differences_vs_baseline"],
            "official_score_analysis":result["official_score_analysis"],
            "decision_score_diagnostics":result["decision_score_diagnostics"],
            "interval_status":result["interval_status"],
            "intervals":result["intervals"],
            "per_seed":result["per_seed"],
            "limitations":result["limitations"],
        }
    elif job["status"]=="done":
        result=job["result"]
        response["overview"]={
            "games":result["games"],
            "terminal_phase_counts":result["terminal_phase_counts"],
            "levels":result["levels"],
            "seed_analysis":result.get("seed_analysis"),
            "official_score_analysis":result.get("official_score_analysis"),
            "limitations":result["limitations"],
            "matches":[{
                "index":i,"seed":m["seed"],"rotation":m["rotation"],
                "assignment":m["assignment"],"dealer":m["dealer"],
                "terminal_phase":m["terminal_phase"],
                "actions":m["actions"],"winners":m["winners"],
            } for i,m in enumerate(result["matches"])],
        }
    return response



def _process(action: str, payload: dict) -> dict:
    with _LOCK:
        if action == "ai_baseline_start":
            seed_start=payload.get("seed_start",11)
            seeds=payload.get("seeds",1)
            if (type(seed_start) is not int or
                not 0 <= seed_start < 2**32 or
                type(seeds) is not int or not 1 <= seeds <= 2 or
                seed_start+seeds > 2**32):
                raise ValueError("独立基线：种子需为uint32，网页限1或2个独立种子")
            if any(job["status"]=="running"
                   for job in _AI_REPLAY_JOBS.values()):
                raise ValueError("已有AI试验在运行，等待结束再开始")
            if len(_AI_REPLAY_JOBS)>=_MAX_REPLAY_JOBS:
                done=next((key for key,job in _AI_REPLAY_JOBS.items()
                           if job["status"]!="running"),None)
                if done is None:
                    raise ValueError("复盘任务已满")
                _AI_REPLAY_JOBS.pop(done)
            token=secrets.token_urlsafe(24)
            _AI_REPLAY_JOBS[token]={
                "mode":"baseline","status":"running",
                "completed_games":0,"seed_start":seed_start,"seeds":seeds,
            }
            threading.Thread(
                target=_independent_worker,args=(token,seed_start,seeds),
                daemon=True,
            ).start()
            return {"baseline_token":token,
                    "baseline":_replay_summary(_AI_REPLAY_JOBS[token])}
        if action == "ai_baseline_status":
            token=payload.get("baseline_token")
            job=_AI_REPLAY_JOBS.get(token) if type(token) is str else None
            if job is None or job.get("mode")!="baseline":
                raise ValueError("独立基线评测任务不存在")
            return {"baseline":_replay_summary(job)}
        if action == "ai_replay_start":
            seed_start=payload.get("seed_start",11)
            seeds=payload.get("seeds",1)
            if (type(seed_start) is not int or
                not 0 <= seed_start < 2**32 or
                type(seeds) is not int or not 1 <= seeds <= 5 or
                seed_start+seeds > 2**32):
                raise ValueError("AI复盘种子需在uint32范围、独立种子数1至5")
            active=sum(
                job["status"]=="running" for job in _AI_REPLAY_JOBS.values()
            )
            if active >= _MAX_ACTIVE_REPLAY_JOBS:
                raise ValueError("已有AI对局在运算，请等待它完成后重试")
            if len(_AI_REPLAY_JOBS)>=_MAX_REPLAY_JOBS:
                idle=next((
                    name for name,job in _AI_REPLAY_JOBS.items()
                    if job["status"]!="running"
                ),None)
                if idle is None:
                    raise ValueError("AI复盘会话已满，请稍后再试")
                _AI_REPLAY_JOBS.pop(idle)
            token=secrets.token_urlsafe(24)
            _AI_REPLAY_JOBS[token]={
                "mode":"replay","status":"running","completed_games":0,
                "seed_start":seed_start,"seeds":seeds,
            }
            threading.Thread(
                target=_replay_worker,args=(token,seed_start,seeds),
                daemon=True,
            ).start()
            return {"replay_token":token,
                    "replay":_replay_summary(_AI_REPLAY_JOBS[token])}
        if action in ("ai_replay_status","ai_replay_match"):
            token=payload.get("replay_token")
            job=_AI_REPLAY_JOBS.get(token) if type(token) is str else None
            if job is None or job.get("mode")!="replay":
                raise ValueError("复盘任务不存在，请重新开始")
            if action=="ai_replay_status":
                return {"replay":_replay_summary(job)}
            if job["status"]!="done":
                raise ValueError("复盘尚未计算完成")
            index=payload.get("match_index")
            result=job["result"]
            if (type(index) is not int or
                not 0<=index<len(result["matches"])):
                raise ValueError("复盘对局编号无效")
            match=result["matches"][index]
            return {"match":{
                "seed":match["seed"],"rotation":match["rotation"],
                "dealer":match["dealer"],
                "assignment":match["assignment"],
                "terminal_phase":match["terminal_phase"],
                "winners":match["winners"],
                "wall_remaining":match["wall_remaining"],
                "partial_win_balances":match["partial_win_balances"],
                "steps":match["public_replay"],
                "privacy":"public_board_and_public_action_only",
                "notes":"其他家暗手、未来牌墙、私有合法响应选项及逐家向听不公开",
            }}
        if action in ("match_new", "match_next"):
            # "match_new" begins an independent series with RANDOM dealer.
            # "match_next" requires a terminal authenticated previous match
            # and ignores all client-supplied dealer/seed/AI settings.
            predecessor = None
            inherited = None
            if action == "match_next":
                old_token = payload.get("match_token")
                predecessor = (_MATCH_SESSIONS.get(old_token)
                               if type(old_token) is str else None)
                if predecessor is None:
                    raise ValueError("上一局会话已失效，无法继承庄家")
                if predecessor.phase not in ("finished", "wall_exhausted"):
                    raise ValueError("本局尚未结束，不允许提前继承庄家")
                if any(key in payload for key in (
                        "dealer", "dealer_override", "seed", "ai_levels",
                        "room_coefficient", "kong_base", "fan_cap",
                        "self_draw_mode")):
                    raise ValueError("续局庄家和规则只能由服务器上一局结算决定")
                successor = _MATCH_SUCCESSORS.get(old_token)
                if successor in _MATCH_SESSIONS:
                    next_game = _MATCH_SESSIONS[successor]
                    next_agents = _MATCH_AGENTS[successor]
                    return {"match_token": successor,
                            "match": _match_private_view(next_game, next_agents)}
                inherited = next_dealer(predecessor.public_state())
                levels = [_MATCH_AGENTS[old_token][seat].level
                          for seat in (1, 2, 3)]
                room_coefficient = predecessor.ledger.room_coefficient
                fan_cap = predecessor.ledger.fan_cap
                kong_base = predecessor.kong_ledger.base
                self_draw_mode = predecessor.ledger.self_draw_mode
            # An experimental fixed seed remains available for an
            # independent match only; every continued round uses a new one.
            manual_seed="seed" in payload
            seed=payload["seed"] if manual_seed else _automatic_match_seed()
            if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
                raise ValueError("实验室四人对局种子须为0至2^32-1")
            if action == "match_new":
                levels=payload.get("ai_levels",["challenge","challenge","challenge"])
            if (type(levels) is not list or len(levels)!=3 or
                any(type(level) is not str or level not in AI_LEVELS
                    for level in levels)):
                raise ValueError("三位AI必须分别选择入门、进阶或挑战难度")
            # Existing API callers without a mode retain legacy scoring.
            # Browser games explicitly select one of two house rules.
            if action == "match_new":
                room_coefficient=payload.get("room_coefficient",100)
                fan_cap=payload.get("fan_cap",3)
                kong_base=payload.get("kong_base",room_coefficient)
                self_draw_mode=payload.get("self_draw_mode","legacy")
            if (type(self_draw_mode) is not str or
                    ("self_draw_mode" in payload and self_draw_mode not in
                     ("add_base","add_fan"))):
                raise ValueError("自摸计分仅支持加底或加番模式")
            game=FourPlayerOpening(
                seed,
                room_coefficient=room_coefficient,
                fan_cap=fan_cap,
                kong_base=kong_base,
                self_draw_mode=self_draw_mode,
                dealer_override=(inherited["dealer"] if inherited else None),
            )
            game.series_round=(getattr(predecessor,"series_round",1)+1
                               if predecessor else 1)
            game.dealer_origin=(inherited["label"] if inherited else "首局随机庄")
            agents={
                seat: MahjongAgent(levels[seat-1],seed=seed,seat=seat)
                for seat in (1,2,3)
            }
            token=secrets.token_urlsafe(24)
            _MATCH_USED_SEEDS.add(seed)
            if len(_MATCH_SESSIONS)>=32:
                stale=next(iter(_MATCH_SESSIONS))
                _MATCH_SESSIONS.pop(stale)
                _MATCH_AGENTS.pop(stale,None)
                _MATCH_HISTORY.pop(stale,None)
                _MATCH_OPENING.pop(stale,None)
                _MATCH_ARCHIVE_IDS.pop(stale,None)
                _MATCH_SUCCESSORS.pop(stale,None)
                for previous, child in list(_MATCH_SUCCESSORS.items()):
                    if child == stale:
                        _MATCH_SUCCESSORS.pop(previous,None)
            if predecessor is not None:
                _MATCH_SUCCESSORS[old_token]=token
            # Private training replay exists only in process memory during
            # the game; never put it in game.public_state() or HTTP steps.
            game._sealed_review=[]
            _MATCH_SESSIONS[token]=game
            _MATCH_AGENTS[token]=agents
            _MATCH_HISTORY[token]=[]
            _MATCH_OPENING[token]=_match_public_board(game)
            return {"match_token":token,
                    "match":_match_private_view(game,agents)}
        if action == "match_hint":
            # Deliberately read-only. Do not advance AI, mutate game/RNG,
            # archive a result, or expose other seat private hands/wall.
            token = payload.get("match_token")
            game = (_MATCH_SESSIONS.get(token)
                    if type(token) is str else None)
            agents = (_MATCH_AGENTS.get(token)
                      if game is not None else None)
            if game is None or agents is None:
                raise ValueError("对局会话已失效，请重新开局")
            view = game.private_view(0)
            return {"match_token": token, "hint": classic_hand_hint(view)}
        if action == "match_resume":
            # Read-only recovery of a SAME-TAB bearer session. Never accept
            # a seat id, replay private walls, generate a new game, or move AI.
            token=payload.get("match_token")
            game=(_MATCH_SESSIONS.get(token) if type(token) is str else None)
            agents=(_MATCH_AGENTS.get(token) if game is not None else None)
            if game is None or agents is None:
                raise ValueError("对局会话已失效，请重新开局")
            view=_match_private_view(game,agents)
            view["needs_continue"]=_match_requires_continue(game)
            view["public_steps"]=[]
            view["match_archive_id"]=_MATCH_ARCHIVE_IDS.get(token)
            return {"match_token":token,"match":view}
        if action in ("match_exchange","match_missing","match_discard",
                      "match_claim","match_kong","match_rob","match_win",
                      "match_continue"):
            token=payload.get("match_token")
            game=(_MATCH_SESSIONS.get(token) if type(token) is str else None)
            if game is None:
                raise ValueError("试验对局不存在，请重新开局")
            agents=_MATCH_AGENTS.get(token)
            if agents is None:
                raise ValueError("试验对局AI未初始化，请重新开局")
            steps: list[dict] = []
            if action=="match_continue":
                if not _match_requires_continue(game):
                    raise ValueError("当前需等待玩家操作，无法自动推进")
                # Each rules transition is still recorded separately in the
                # public history. Aggregate only unspoken intermediate work:
                # concealed draws, pending PASS responses and bookkeeping.
                # Stop after the FIRST visible/audible move, or at the
                # human decision boundary; do not speculate past either.
                for _ in range(_MAX_SILENT_CONTINUATIONS):
                    if not _match_requires_continue(game):
                        break
                    before=len(game._events)
                    _match_script_until_human(game,agents,steps,max_actions=1)
                    latest=game._events[before:]
                    if any(event["type"] in _MATCH_TURN_BEATS
                           for event in latest):
                        break
            elif action=="match_exchange":
                _match_record(game,steps,lambda: game.select_exchange(
                    0,payload.get("tiles")))
                for s in (1,2,3):
                    choice=agents[s].exchange(game.private_view(s))
                    _match_record(game,steps,lambda s=s,choice=choice:
                                  game.select_exchange(s,choice))
            elif action=="match_missing":
                _match_record(game,steps,lambda: game.select_missing(
                    0,payload.get("suit")))
                for s in (1,2,3):
                    suit=agents[s].missing(game.private_view(s))
                    _match_record(game,steps,lambda s=s,suit=suit:
                                  game.select_missing(s,suit))
                # AI acts via match_continue after the short visual frame.
            elif action=="match_discard":
                _match_record(game,steps,lambda: game.discard(
                    0,payload.get("tile"),
                    from_draw=payload.get("from_draw")))
                # AI acts via match_continue after the short visual frame.
            elif action=="match_claim":
                _match_record(game,steps,lambda: game.respond_discard(
                    0,payload.get("choice")))
                # AI acts via match_continue after the short visual frame.
            elif action=="match_rob":
                _match_record(game,steps,lambda: game.respond_rob_kong(
                    0,payload.get("choice")))
                # AI acts via match_continue after the short visual frame.
            elif action=="match_kong":
                _match_record(game,steps,lambda: game.declare_kong(
                    0,payload.get("kind"),payload.get("tile")))
                # AI acts via match_continue after the short visual frame.
            elif action=="match_win":
                _match_record(game,steps,lambda: game.declare_self_win(0))
                # AI acts via match_continue after the short visual frame.
            view=_match_private_view(game,agents)
            view["needs_continue"]=_match_requires_continue(game)
            view["public_steps"]=steps
            if token in _MATCH_HISTORY:
                _MATCH_HISTORY[token].extend(steps)
            if (game.phase in ("finished","wall_exhausted")
                    and token not in _MATCH_ARCHIVE_IDS):
                published=game.public_state()
                archive_id=_MATCH_ARCHIVE.save_completed(
                    published,_MATCH_HISTORY[token],_MATCH_OPENING[token],
                    [agents[n].level for n in (1,2,3)],
                    sealed_review=getattr(game,"_sealed_review",None))
                _MATCH_ARCHIVE_IDS[token]=archive_id
            view["match_archive_id"]=_MATCH_ARCHIVE_IDS.get(token)
            return {"match_token":token,"match":view}
        if action == "table_new":
            seed = payload.get("seed", 42)
            if type(seed) is not int or not 0 <= seed <= 2**32-1:
                raise ValueError("四人演示随机种子必须为0至2^32-1")
            table = FourPlayerOpening(seed)
            key = secrets.token_urlsafe(24)
            if len(_TABLE_DEMOS) >= 32:
                _TABLE_DEMOS.pop(next(iter(_TABLE_DEMOS)))
            _TABLE_DEMOS[key] = table
            return {"table_token": key, "table": table.private_view(0)}
        if action in ("table_exchange","table_missing","table_discard"):
            key = payload.get("table_token")
            table = _TABLE_DEMOS.get(key) if type(key) is str else None
            if table is None:
                raise ValueError("四人开局演示会话不存在，请重新发牌")
            if action == "table_exchange":
                table.select_exchange(0, payload.get("tiles"))
                for s in (1, 2, 3):
                    table.select_exchange(
                        s, _demo_exchange_choice(table.private_view(s)["hand"])
                    )
            elif action == "table_missing":
                table.select_missing(0, payload.get("suit"))
                for s in (1, 2, 3):
                    hand = table.private_view(s)["hand"]
                    missing = min(
                        ("m", "s", "p"),
                        key=lambda suit: (
                            sum(t.startswith(suit) for t in hand),
                            ("m", "s", "p").index(suit),
                        )
                    )
                    table.select_missing(s, missing)
                _demo_auto_until_human(table)
            else:
                table.discard(0, payload.get("tile"))
                _demo_auto_until_human(table)
            return {"table_token": key, "table": table.private_view(0)}
        if action in ("preview", "new"):
            seed = payload.get("seed", 17)
            if type(seed) is not int or seed < 0 or seed > 2**32 - 1:
                raise ValueError("种子必须是0至2^32-1的整数")
            if action == "preview":
                # Deal the 13 visible tiles without declaring dingque yet.
                preview = SoloTrainingSession(seed, missing_suit=None,
                                              rounds=payload.get("rounds", 14))
                cards = preview.public_state()["hand"]
                counts = {s: sum(t[0] == s for t in cards) for s in ("m", "s", "p")}
                absent = [s for s, count in counts.items() if count == 0]
                return {
                    "initial_hand": cards,
                    "suit_counts": counts,
                    "tianque": len(absent) == 1,
                    "absent_suits": absent,
                    "stage": "deal_before_declaring_missing_suit",
                    "note": "单人练习暂无换三张；正式四人玩法为换三张后一起定缺",
                }
            missing = payload.get("missing_suit")
            if missing not in ("m", "s", "p"):
                raise ValueError("请先查看发好的牌，并明确选择万/条/筒作为定缺")
            game = SoloTrainingSession(seed, missing_suit=missing,
                                       rounds=payload.get("rounds", 14))
            token = secrets.token_urlsafe(24)
            if len(_SESSIONS) >= _MAX_SESSIONS:
                _SESSIONS.pop(next(iter(_SESSIONS)))
            _SESSIONS[token] = game
            return {"token": token, "state": game.public_state()}
        if action == "quiz_progress":
            # Legacy calls retain their original interface; new history
            # controls explicitly opt into period and offset queries.
            if "period" in payload or "offset" in payload:
                return {"progress": _HISTORY.quiz_progress(
                    payload.get("mode"), payload.get("difficulty"),
                    period=payload.get("period","all"),
                    offset=payload.get("offset",0),
                )}
            return {"progress": _HISTORY.quiz_progress(
                payload.get("mode"), payload.get("difficulty")
            )}
        if action == "quiz_detail":
            return {"detail": _HISTORY.quiz_detail(payload.get("answer_id"))}
        if action == "quiz_retry_question":
            return _HISTORY.quiz_retry_question(payload.get("answer_id"))
        if action == "quiz_retry_answer":
            return _HISTORY.quiz_retry_submit(
                payload.get("answer_id"), payload.get("selection")
            )
        if action == "quiz_delete":
            _HISTORY.delete_quiz_attempt(payload.get("answer_id"))
            return {"deleted": True}
        if action == "quiz_new":
            mode, difficulty = payload.get("mode"), payload.get("difficulty")
            if mode not in MODES or difficulty not in DIFFICULTIES:
                raise ValueError("invalid quiz mode or difficulty")
            focus = payload.get("focus")
            if focus is not None and (focus != "auto" and
                                       not supports_focus(mode,focus)):
                raise ValueError("当前单题模式不支持该错因专项")
            seed = secrets.randbelow(2**32-24)
            applied_focus = None
            if focus == "auto":
                weaknesses = _HISTORY.quiz_progress(mode,difficulty)["weaknesses"]
                counts = weaknesses["counts"]
                # 75% focused questions, 25% ordinary variety, once the
                # learner has mode-specific errors. The ratio and sampled
                # label are disclosed in the UI, not the answer.
                options = [name for name,value in counts.items()
                           for _ in range(value)]
                if options and secrets.randbelow(4) != 0:
                    # Weighted by actual misplay frequency, preferring more
                    # prevalent causes, with graceful verified fallback.
                    candidate = options[secrets.randbelow(len(options))]
                    # Do not disclose win/no-win answers via focus labels.
                    # Mix positive and negative win decisions 50/50.
                    if candidate in ("missed_win","false_win"):
                        candidate=("missed_win" if secrets.randbelow(2)==0
                                   else "false_win")
                    try:
                        seed,question=select_focused_question(
                            mode,difficulty,candidate,seed)
                        applied_focus=candidate
                    except ValueError:
                        question=generate_question(mode,seed,difficulty=difficulty)
                else:
                    question=generate_question(mode,seed,difficulty=difficulty)
            elif focus is not None:
                candidate=focus
                if candidate in ("missed_win","false_win"):
                    candidate=("missed_win" if secrets.randbelow(2)==0
                               else "false_win")
                seed,question=select_focused_question(
                    mode,difficulty,candidate,seed)
                applied_focus=candidate
            else:
                question=generate_question(mode,seed,difficulty=difficulty)
            if applied_focus:
                public_focus=("win_decision" if applied_focus
                              in ("missed_win","false_win") else applied_focus)
                public_label=("胡牌判断（混合可胡和不可胡）"
                              if public_focus=="win_decision"
                              else ERROR_LABELS[applied_focus])
                question={**question, "focus":public_focus,
                          "focus_label":public_label}
            if focus == "auto":
                question={**question,"training_strategy":"adaptive_weakness",
                          "focus_applied":applied_focus is not None}
            quiz_token = secrets.token_urlsafe(24)
            if len(_QUIZZES) >= 128:
                _QUIZZES.pop(next(iter(_QUIZZES)))
            _QUIZZES[quiz_token] = {
                "seed": seed, "mode": mode, "difficulty": difficulty,
                "focus": applied_focus, "strategy": focus,
                "question_id": question["question_id"], "submitted": False,
            }
            return {"quiz_token": quiz_token, "question": question}
        if action == "quiz_answer":
            quiz_token = payload.get("quiz_token")
            record = _QUIZZES.get(quiz_token) if type(quiz_token) is str else None
            if record is None:
                raise ValueError("quiz expired or missing")
            if record["submitted"]:
                raise ValueError("this question has already been answered")
            result = grade_answer(
                record["mode"], record["seed"], payload.get("selection"),
                difficulty=record["difficulty"],
                question_id=record["question_id"],
            )
            result["error_types"] = diagnose_quiz(record["mode"],result)
            result["error_labels"] = [
                ERROR_LABELS[cause] for cause in result["error_types"]
            ]
            # Persist only successfully graded answers, then mark the
            # token consumed. Failed validation/storage must not consume it.
            question = generate_question(
                record["mode"], record["seed"],
                difficulty=record["difficulty"],
            )
            if record["focus"]:
                original_focus=record["focus"]
                public_focus=("win_decision" if original_focus
                              in ("missed_win","false_win") else original_focus)
                label=("胡牌判断（混合可胡和不可胡）"
                       if public_focus=="win_decision"
                       else ERROR_LABELS[original_focus])
                question={**question, "focus":public_focus,
                          "focus_label":label}
            if record["strategy"] == "auto":
                question={**question,"training_strategy":"adaptive_weakness",
                          "focus_applied":record["focus"] is not None}
            answer_id = _HISTORY.save_quiz_answer(
                question, result, payload.get("selection")
            )
            record["submitted"] = True
            return {
                "result": result, "answer_id": answer_id,
                "progress": _HISTORY.quiz_progress(
                    record["mode"], record["difficulty"]
                ),
            }
        if action == "history_retry_question":
            return {"question": _HISTORY.retry_question(
                payload.get("archive_id"), payload.get("round")
            )}
        if action == "history_retry_submit":
            return _HISTORY.retry_submit(
                payload.get("archive_id"), payload.get("round"),
                payload.get("tile"),
            )
        if action == "history_delete":
            _HISTORY.delete_history(payload.get("archive_id"))
            return {"deleted": True}
        token = payload.get("token")
        if not isinstance(token, str) or token not in _SESSIONS:
            raise ValueError("训练会话不存在，请重新开始")
        game = _SESSIONS[token]
        if action == "retry_list":
            if not game.finished:
                raise ValueError("训练尚未结束，暂不能重练")
            return {"retry": _HISTORY.retry_list(game._archive_id)}
        if action == "retry_question":
            if not game.finished:
                raise ValueError("训练尚未结束，暂不能重练")
            return {"question": _HISTORY.retry_question(
                game._archive_id, payload.get("round")
            )}
        if action == "retry_submit":
            if not game.finished:
                raise ValueError("训练尚未结束，暂不能重练")
            return _HISTORY.retry_submit(
                game._archive_id, payload.get("round"), payload.get("tile")
            )
        feedback = None
        if action == "draw":
            game.draw_next()
        elif action == "win":
            feedback = game.decide_win(payload.get("accept"))
        elif action == "kong":
            tile = payload.get("tile")
            feedback = game.decide_kong(tile)
        elif action == "discard":
            feedback = game.submit(payload.get("tile"))
        else:
            raise ValueError("无效操作")
        if game.finished and not hasattr(game, "_archive_id"):
            # Unique per PLAYTHROUGH, even when the user repeats the same seed.
            game._archive_id = _HISTORY.save_finished(game)
        # Only completed actions expose answer feedback.
        reveal = action == "discard" or (action == "win" and payload.get("accept"))
        return {
            "state": game.public_state(),
            "archive_id": getattr(game, "_archive_id", None),
            "feedback": feedback if reveal else None,
            # Historical answers can be shown once submitted; pending answers
            # and wall order are never returned.
            "report": game.report() if game.report()["completed_rounds"] else None,
        }


# Disconnects during a local HTTP response are normal (page navigation,
# cancelled fetch, browser shutdown). On Windows, security software can also
# abort an established localhost connection with WinError 10053.
# Do not hide unrelated socket/file errors or failed JSON serialization.
_CLIENT_DISCONNECT_ERRNOS = frozenset((
    errno.EPIPE, errno.ECONNRESET, errno.ECONNABORTED,
))
_CLIENT_DISCONNECT_WINERRORS = frozenset((10053, 10054, 10058))


def _is_client_disconnect(exc: OSError) -> bool:
    return (
        isinstance(exc, (BrokenPipeError, ConnectionResetError,
                         ConnectionAbortedError))
        or exc.errno in _CLIENT_DISCONNECT_ERRNOS
        or getattr(exc, "winerror", None) in _CLIENT_DISCONNECT_WINERRORS
    )


class Handler(BaseHTTPRequestHandler):
    def _respond(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "img-src 'self' data:; connect-src 'self'; "
                         "object-src 'none'; frame-ancestors 'none'")
        try:
            self.end_headers()
            self.wfile.write(data)
        except OSError as exc:
            if not _is_client_disconnect(exc):
                raise
            # The browser has gone away; nothing useful can be sent now.
            # Treat this as a cancelled response, not a failed match/archive
            # operation. Suppress only these expected network disconnects.
            self.close_connection = True

    def _json(self, status: int, payload: dict) -> None:
        self._respond(status, json.dumps(payload, ensure_ascii=False).encode(),
                      "application/json; charset=utf-8")

    def do_GET(self) -> None:
        url = urlparse(self.path)
        path = unquote(url.path)
        if path == "/api/match_archives":
            query = parse_qs(url.query)
            try:
                with _LOCK:
                    if "archive_id" in query:
                        result = _MATCH_ARCHIVE.detail(query["archive_id"][0])
                    else:
                        limit = int(query.get("limit", ["50"])[0])
                        offset = int(query.get("offset", ["0"])[0])
                        period = query.get("period", ["all"])[0]
                        result = (_MATCH_ARCHIVE.list_completed(limit)
                                  if period=="all" and offset==0 else
                                  _MATCH_ARCHIVE.list_completed(
                                      limit, period=period, offset=offset))
            except (ValueError, TypeError) as exc:
                self._json(400, {"error": str(exc)})
            else:
                # Don't block active matches while a browser downloads
                # archives or aborts a request halfway through the response.
                self._json(200, result)
            return
        if path == "/api/history":
            query = parse_qs(url.query)
            try:
                with _LOCK:
                    if "archive_id" in query:
                        result = _HISTORY.detail(query["archive_id"][0])
                    else:
                        limit = int(query.get("limit", ["30"])[0])
                        if "period" in query or "offset" in query:
                            result = _HISTORY.list_history(
                                limit,period=query.get("period",["all"])[0],
                                offset=int(query.get("offset",["0"])[0]))
                        else:
                            result = _HISTORY.list_history(limit)
            except (ValueError, TypeError) as exc:
                self._json(400, {"error": str(exc)})
            else:
                self._json(200, result)
            return
        if path == "/api/state":
            token = parse_qs(url.query).get("token", [None])[0]
            with _LOCK:
                game = _SESSIONS.get(token)
                if not game:
                    status, result = 404, {"error": "训练会话不存在"}
                else:
                    status, result = 200, {
                        "state": game.public_state(),
                        "archive_id": getattr(game, "_archive_id", None),
                        "report": game.report() if game.report()["completed_rounds"] else None,
                    }
            self._json(status, result)
            return
        asset = _asset_path(path)
        if asset is None or not asset.is_file():
            self._json(404, {"error": "资源不存在"})
            return
        data = asset.read_bytes()
        kind = mimetypes.guess_type(str(asset))[0] or "application/octet-stream"
        # Existing assets/tiles/*.png include JPEG-encoded images despite
        # their extension. Report actual bytes' MIME without re-encoding.
        if data.startswith(b"\xff\xd8\xff"):
            kind = "image/jpeg"
        elif data.startswith(b"\x89PNG\r\n\x1a\n"):
            kind = "image/png"
        if kind.startswith("text/") or kind == "application/javascript":
            kind += "; charset=utf-8"
        self._respond(200, data, kind)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/action":
            self._json(404, {"error": "无效地址"})
            return
        # JSON and custom same-origin request header prevent cross-site form
        # POSTs; no CORS headers are emitted.
        if (
            self.headers.get_content_type() != "application/json"
            or self.headers.get("X-MahTrain") != "1"
        ):
            self._json(415, {"error": "请求格式不受支持"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4096:
                raise ValueError("请求体尺寸无效")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if type(payload) is not dict:
                raise ValueError("请求必须为JSON对象")
            action = payload.get("action")
            started=perf_counter()
            result=_process(action,payload)
            # Distinguish server compute time from client animation/speech.
            # This does not expose RNG, hands or internal AI decisions.
            result["server_elapsed_ms"]=round((perf_counter()-started)*1000,1)
            self._json(200,result)
        except (ValueError, TypeError, UnicodeError) as exc:
            self._json(400, {"error": str(exc)})

    def log_message(self, fmt: str, *args: object) -> None:
        return  # quiet local dev server


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("Local prototype may bind only to localhost")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"MahTrain 本地训练界面：http://{host}:{port}")
    print("按 Ctrl+C 停止服务。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
