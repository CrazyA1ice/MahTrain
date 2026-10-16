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

from mahtrain_core import SoloTrainingSession  # noqa: E402
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


def _process(action: str, payload: dict) -> dict:
    with _LOCK:
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
