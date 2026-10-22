"""M3.72: Windows localhost client-abort regression tests.

Reproduce the request failure WITHOUT depending on timing-sensitive sockets.
Only expected peer disconnects may be suppressed; all other I/O errors must
retain their tracebacks. Archive list and state responses must release the
global game mutex BEFORE writing to the client.
"""
from __future__ import annotations

import errno
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import web_server


def response_handler(*, write_error=None, header_error=None):
    """Uninitialized HTTP handler with deterministic transport callbacks."""
    handler = web_server.Handler.__new__(web_server.Handler)
    handler.send_response = Mock()
    handler.send_header = Mock()
    handler.end_headers = Mock(side_effect=header_error)
    handler.wfile = SimpleNamespace(write=Mock(side_effect=write_error))
    handler.close_connection = False
    return handler


def win_socket_error(code: int) -> OSError:
    # Python running on Linux cannot create Windows-specific OSError.winerror
    # directly. Set the attribute to simulate Windows WinError 10053/10054/10058.
    exc = OSError("Windows localhost socket was disconnected")
    exc.winerror = code
    return exc


class LocalHTTPClientDisconnect(unittest.TestCase):
    def test_regular_complete_json_response_keeps_content_and_headers(self):
        h = response_handler()
        h._json(200, {"result": "已完成", "total": 4})
        self.assertFalse(h.close_connection)
        h.send_response.assert_called_once_with(200)
        headers = dict(call.args for call in h.send_header.call_args_list)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Content-Length"], str(
            len('{"result": "已完成", "total": 4}'.encode("utf8"))
        ))
        self.assertEqual(
            h.wfile.write.call_args.args[0],
            '{"result": "已完成", "total": 4}'.encode("utf8"),
        )

    def test_all_standard_peer_disconnects_cancel_only_current_response(self):
        errors = (
            BrokenPipeError(errno.EPIPE, "peer closed the pipe"),
            ConnectionResetError(errno.ECONNRESET, "peer reset"),
            ConnectionAbortedError(errno.ECONNABORTED, "peer aborted"),
        )
        for exc in errors:
            with self.subTest(error=type(exc).__name__):
                h = response_handler(write_error=exc)
                # This is the exact _json -> _respond -> wfile.write path
                # in the user-reported traceback.
                h._json(200, {"archives": []})
                self.assertTrue(h.close_connection)
                h.wfile.write.assert_called_once()

    def test_windows_abort_and_reset_are_quiet_in_both_header_and_body(self):
        for code in (10053, 10054, 10058):
            with self.subTest(code=code):
                response = response_handler(write_error=win_socket_error(code))
                response._json(200, {"archives": []})
                self.assertTrue(response.close_connection)
                headers = response_handler(header_error=win_socket_error(code))
                headers._json(200, {"archives": []})
                self.assertTrue(headers.close_connection)
                headers.wfile.write.assert_not_called()

    def test_unexpected_response_errors_are_not_suppressed(self):
        for error in (
            OSError(errno.EIO, "real disk or IO failure"),
            OSError(errno.ENOSPC, "out of disk"),
            RuntimeError("unexpected runtime failure"),
        ):
            with self.subTest(exc=str(error)):
                h = response_handler(write_error=error)
                with self.assertRaises(type(error)):
                    h._json(200, {"archives": []})
                self.assertFalse(h.close_connection)

    def test_archive_history_and_state_never_write_under_global_game_lock(self):
        # If we hold _LOCK while calling wfile.write, a cancelled history
        # download may stall AI and other active HTTP game actions.
        captured = []

        def json_after_unlock(status, result):
            self.assertFalse(
                web_server._LOCK._is_owned(),
                "HTTP bytes should never be written while holding _LOCK",
            )
            captured.append((status, result))

        fake_archive = SimpleNamespace(
            detail=Mock(return_value={"id": "a"}),
            list_completed=Mock(return_value={"matches": []}),
        )
        fake_history = SimpleNamespace(
            detail=Mock(return_value={"id": "b"}),
            list_history=Mock(return_value={"history": []}),
        )
        with patch.object(web_server, "_MATCH_ARCHIVE", fake_archive), \
             patch.object(web_server, "_HISTORY", fake_history):
            handler = response_handler()
            handler._json = json_after_unlock
            for url in (
                "/api/match_archives?limit=25",
                "/api/match_archives?archive_id=a",
                "/api/history?limit=20",
                "/api/history?archive_id=b",
                "/api/state?token=not-found",
            ):
                with self.subTest(url=url):
                    handler.path = url
                    handler.do_GET()
        self.assertEqual(len(captured), 5)
        self.assertEqual([status for status, _ in captured],
                         [200, 200, 200, 200, 404])
        fake_archive.list_completed.assert_called_once_with(25, period='all')
        fake_archive.detail.assert_called_once_with("a")
        fake_history.list_history.assert_called_once_with(20)
        fake_history.detail.assert_called_once_with("b")


if __name__ == "__main__":
    unittest.main()
