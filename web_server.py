"""Local-only stdlib web interface for MahTrain 14-round solo training.

Run: python web_server.py
Open http://127.0.0.1:8765

This is an intentionally local development server, not a production/multiplayer
service. All session state and the shuffled wall stay in Python server memory.
"""
from __future__ import annotations

import json
import mimetypes
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from mahtrain_core import SoloTrainingSession, FourPlayerOpening  # noqa: E402
from mahtrain_core.training import MODES, generate_question, grade_answer
from mahtrain_core.training_levels import DIFFICULTIES
from mahtrain_core.error_focus import (
    ERROR_LABELS, supports_focus, select_focused_question, diagnose_quiz,
)
from mahtrain_core.history import HistoryStore  # noqa: E402

# Override MAHTRAIN_HISTORY_DB to relocate the local, single-user SQLite file.
import os
_HISTORY = HistoryStore(Path(os.environ.get("MAHTRAIN_HISTORY_DB",
                                     str(ROOT / "data" / "mahtrain_history.sqlite3"))))

_SESSIONS: dict[str, SoloTrainingSession] = {}
_QUIZZES: dict[str, dict] = {}
_TABLE_DEMOS: dict[str, FourPlayerOpening] = {}
_MATCH_SESSIONS: dict[str, FourPlayerOpening] = {}
_LOCK = threading.RLock()
_MAX_SESSIONS = 32
_STATIC = {
    "/": ROOT / "web" / "index.html",
    "/app.css": ROOT / "web" / "app.css",
    "/app.js": ROOT / "web" / "app.js",
    "/review.js": ROOT / "web" / "review.js",
    "/retry.js": ROOT / "web" / "retry.js",
    "/history.js": ROOT / "web" / "history.js",
    "/quiz.js": ROOT / "web" / "quiz.js",
    "/quiz_history.js": ROOT / "web" / "quiz_history.js",
    "/four_player.js": ROOT / "web" / "four_player.js",
    "/match.js": ROOT / "web" / "match.js",
    "/tile_art.js": ROOT / "web" / "tile_art.js",
    "/sound.js": ROOT / "web" / "sound.js",
}
_SUITS = ("万", "条", "筒")


def _asset_path(url_path: str) -> Path | None:
    if url_path in _STATIC:
        return _STATIC[url_path]
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


def _match_script_until_human(game: FourPlayerOpening) -> None:
    """Three transparently scripted seats. Human is seat 0 only.

    Script responds with legal HU > gang > peng. It never reads hidden data
    to decide the human's response; only own private state is inspected.
    The human's optional HU/peng/ming_gang/rob response is never skipped.
    """
    for _ in range(512):
        phase=game.phase
        if phase in ("exchange_select", "missing_select",
                     "finished", "wall_exhausted"):
            return
        if phase in ("claim_window", "rob_kong_window"):
            for seat in range(4):
                if game._won[seat]:
                    continue
                if phase=="claim_window":
                    if game._pending_discard["seat"]==seat:
                        continue
                    if seat in game._responses:
                        continue
                    available=game.claim_options(seat)
                else:
                    if game._pending_kong["seat"]==seat:
                        continue
                    if seat in game._responses:
                        continue
                    available=game.rob_options(seat)
                if seat==0 and len(available)>1:
                    return  # show human an actual yes/no response prompt
                if seat==0:
                    pick="pass"
                else:
                    pick=next((x for x in ("hu","ming_gang","peng")
                               if x in available),"pass")
                if phase=="claim_window":
                    game.respond_discard(seat,pick)
                else:
                    game.respond_rob_kong(seat,pick)
                if game.phase!=phase:
                    break
            else:
                # Window still open (e.g. no eligible human) cannot spin.
                if game.phase==phase:
                    raise RuntimeError("scripted responses did not settle")
            continue
        if phase=="await_draw":
            game.draw(game.turn)
            continue
        if phase in ("await_discard","dealer_discard"):
            if game.turn==0:
                return
            seat=game.turn
            if game.private_view(seat)["can_self_draw_win"]:
                game.declare_self_win(seat)
                continue
            kongs=game.kong_options(seat)
            if kongs:
                choice=kongs[0]
                game.declare_kong(seat,choice["type"],choice["tile"])
                continue
            hand=game.private_view(seat)["hand"]
            missing=game.missing_suits[seat]
            tile=next((t for t in hand if t.startswith(missing)),hand[0])
            game.discard(seat,tile)
            continue
        raise RuntimeError("unexpected M3.1 match phase: "+str(phase))
    raise RuntimeError("M3.1 script exceeded 512 transitions")


def _process(action: str, payload: dict) -> dict:
    with _LOCK:
        if action == "match_new":
            seed=payload.get("seed",42)
            if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
                raise ValueError("M3.1 四人试验局种子须为0至2^32-1")
            game=FourPlayerOpening(seed)
            token=secrets.token_urlsafe(24)
            if len(_MATCH_SESSIONS)>=32:
                _MATCH_SESSIONS.pop(next(iter(_MATCH_SESSIONS)))
            _MATCH_SESSIONS[token]=game
            return {"match_token":token,"match":game.private_view(0)}
        if action in ("match_exchange","match_missing","match_discard",
                      "match_claim","match_kong","match_rob","match_win"):
            token=payload.get("match_token")
            game=(_MATCH_SESSIONS.get(token) if type(token) is str else None)
            if game is None:
                raise ValueError("试验对局不存在，请重新开局")
            if action=="match_exchange":
                game.select_exchange(0,payload.get("tiles"))
                for s in (1,2,3):
                    game.select_exchange(s,_demo_exchange_choice(
                        game.private_view(s)["hand"]))
            elif action=="match_missing":
                game.select_missing(0,payload.get("suit"))
                for s in (1,2,3):
                    cards=game.private_view(s)["hand"]
                    suit=min(("m","s","p"),key=lambda x:(
                        sum(t.startswith(x) for t in cards),
                        ("m","s","p").index(x)
                    ))
                    game.select_missing(s,suit)
                _match_script_until_human(game)
            elif action=="match_discard":
                game.discard(0,payload.get("tile"))
                _match_script_until_human(game)
            elif action=="match_claim":
                game.respond_discard(0,payload.get("choice"))
                _match_script_until_human(game)
            elif action=="match_rob":
                game.respond_rob_kong(0,payload.get("choice"))
                _match_script_until_human(game)
            elif action=="match_kong":
                game.declare_kong(0,payload.get("kind"),payload.get("tile"))
                _match_script_until_human(game)
            elif action=="match_win":
                game.declare_self_win(0)
                _match_script_until_human(game)
            return {"match_token":token,"match":game.private_view(0)}
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
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int, payload: dict) -> None:
        self._respond(status, json.dumps(payload, ensure_ascii=False).encode(),
                      "application/json; charset=utf-8")

    def do_GET(self) -> None:
        url = urlparse(self.path)
        path = unquote(url.path)
        if path == "/api/history":
            query = parse_qs(url.query)
            try:
                with _LOCK:
                    if "archive_id" in query:
                        detail = _HISTORY.detail(query["archive_id"][0])
                        self._json(200, detail)
                    else:
                        limit = int(query.get("limit", ["30"])[0])
                        self._json(200, _HISTORY.list_history(limit))
            except (ValueError, TypeError) as exc:
                self._json(400, {"error": str(exc)})
            return
        if path == "/api/state":
            token = parse_qs(url.query).get("token", [None])[0]
            with _LOCK:
                game = _SESSIONS.get(token)
                if not game:
                    self._json(404, {"error": "训练会话不存在"})
                else:
                    self._json(200, {
                        "state": game.public_state(),
                        "archive_id": getattr(game, "_archive_id", None),
                        "report": game.report() if game.report()["completed_rounds"] else None,
                    })
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
            self._json(200, _process(action, payload))
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
