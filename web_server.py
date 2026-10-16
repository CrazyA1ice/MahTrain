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

_SESSIONS: dict[str, SoloTrainingSession] = {}
_LOCK = threading.RLock()
_MAX_SESSIONS = 32
_STATIC = {
    "/": ROOT / "web" / "index.html",
    "/app.css": ROOT / "web" / "app.css",
    "/app.js": ROOT / "web" / "app.js",
}
_SUITS = ("万", "条", "筒")


def _asset_path(url_path: str) -> Path | None:
    if url_path in _STATIC:
        return _STATIC[url_path]
    prefix = "/assets/tiles/"
    if not url_path.startswith(prefix):
        return None
    filename = unquote(url_path[len(prefix):])
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
        if action == "new":
            seed = payload.get("seed", 17)
            if type(seed) is not int or seed < 0 or seed > 2**32 - 1:
                raise ValueError("种子必须是0至2^32-1的整数")
            missing = payload.get("missing_suit")
            if missing == "":
                missing = None
            game = SoloTrainingSession(seed, missing_suit=missing,
                                       rounds=payload.get("rounds", 14))
            token = secrets.token_urlsafe(24)
            if len(_SESSIONS) >= _MAX_SESSIONS:
                _SESSIONS.pop(next(iter(_SESSIONS)))
            _SESSIONS[token] = game
            return {"token": token, "state": game.public_state()}
        token = payload.get("token")
        if not isinstance(token, str) or token not in _SESSIONS:
            raise ValueError("训练会话不存在，请重新开始")
        game = _SESSIONS[token]
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
        # Only completed actions expose answer feedback.
        reveal = action == "discard" or (action == "win" and payload.get("accept"))
        return {
            "state": game.public_state(),
            "feedback": feedback if reveal else None,
            "report": game.report() if game.finished else None,
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
        if path == "/api/state":
            token = parse_qs(url.query).get("token", [None])[0]
            with _LOCK:
                game = _SESSIONS.get(token)
                if not game:
                    self._json(404, {"error": "训练会话不存在"})
                else:
                    self._json(200, {
                        "state": game.public_state(),
                        "report": game.report() if game.finished else None,
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
