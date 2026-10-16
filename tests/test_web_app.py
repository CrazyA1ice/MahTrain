"""Local website API, static asset and server-owned session smoke tests."""
from __future__ import annotations

import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import web_server  # noqa: E402
from mahtrain_core.efficiency import analyze_discards  # noqa: E402


class WebUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), web_server.Handler)
        cls.base = "http://127.0.0.1:" + str(cls.httpd.server_address[1])
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)

    @classmethod
    def get(cls, route):
        with urlopen(cls.base + route, timeout=10) as response:
            return response.read(), response.getheader("Content-Type")

    @classmethod
    def post(cls, payload, header=True):
        headers = {"Content-Type": "application/json"}
        if header:
            headers["X-MahTrain"] = "1"
        req = Request(
            cls.base + "/api/action",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(req, timeout=10) as response:
            return json.load(response)

    def test_page_and_existing_tile_art_are_served(self):
        html, kind = self.get("/")
        self.assertIn(b"MahTrain", html)
        self.assertIn("text/html", kind)
        self.assertIn("独立杠区".encode(), html)
        code, kind = self.get("/app.js")
        self.assertIn(b"offer_kong", code)
        self.assertIn(b"offer_win", code)
        self.assertIn("javascript", kind)
        css, kind = self.get("/app.css")
        self.assertIn(b".kong-area", css)
        self.assertIn(b".win-diagnosis", css)
        self.assertIn(b".tile-atlas-face", css)
        self.assertIn(b"preview-section", html)
        self.assertIn(b"preview-button", html)
        self.assertIn(b"sound.js", html)
        self.assertIn(b"win-diagnosis", html)
        self.assertIn(b"sound-toggle", html)
        self.assertIn(b"/review.js", html)
        self.assertIn(b"report-title", html)
        review_code, review_kind = self.get("/review.js")
        self.assertIn("javascript", review_kind)
        self.assertIn(b"MahTrainReview", review_code)
        self.assertIn(b"review-round", review_code)
        self.assertIn(b"review-trend", css)
        self.assertIn(b"width:94%;height:94%", css)
        atlas, atlas_kind = self.get("/assets/tiles/640x420.jpeg")
        self.assertEqual(atlas_kind, "image/jpeg")
        self.assertTrue(atlas.startswith(b"\xff\xd8\xff"))
        self.assertIn(b"atlasFace", code)
        self.assertIn(b"backgroundPosition", code)
        self.assertIn(b"showDealtPreview", code)
        sounds, sound_kind = self.get("/sound.js")
        self.assertIn("javascript", sound_kind)
        self.assertIn(b"AudioContext", sounds)
        self.assertIn(b"MahTrainSound", sounds)
        self.assertIn(b"offer_win", code)
        self.assertIn(b"renderWinDiagnosis", code)
        self.assertIn(b"sound-toggle", code)
        art, kind = self.get("/assets/tiles/%E4%B8%871.png")
        # Files in this repository use .png names but JPEG signatures.
        self.assertTrue(art.startswith(b"\xff\xd8\xff"))
        self.assertEqual(kind, "image/jpeg")

    def test_invalid_paths_not_readable(self):
        for route in (
            "/web_server.py",
            "/assets/tiles/../README.md",
            "/assets/tiles/%2e%2e%2fREADME.md",
            "/assets/tiles/%E4%B8%8710.png",
        ):
            with self.subTest(route=route), self.assertRaises(HTTPError) as err:
                self.get(route)
            self.assertEqual(err.exception.code, 404)

    def test_same_origin_json_custom_header_required(self):
        with self.assertRaises(HTTPError) as err:
            self.post({"action": "new", "seed": 0}, header=False)
        self.assertEqual(err.exception.code, 415)

    def test_local_session_api_flow_and_hidden_wall(self):
        preview = self.post({"action": "preview", "seed": 17, "rounds": 2})
        self.assertEqual(len(preview["initial_hand"]), 13)
        self.assertNotIn("token", preview)
        self.assertNotIn("wall", preview)
        response = self.post({"action": "new", "seed": 17, "rounds": 2,
                              "missing_suit": "p"})
        token = response["token"]
        self.assertGreater(len(token), 20)
        state = response["state"]
        self.assertEqual(state["phase"], "ready_to_draw")
        self.assertNotIn("wall", state)
        self.assertNotIn("seed", state)
        self.assertNotIn("analysis", state)
        self.assertEqual(len(state["hand"]), 13)
        self.assertEqual(state["hand"], preview["initial_hand"])
        self.assertIn("win_status", state)
        self.assertIn("missing_suit_tile_count", state["win_status"])
        second = self.post({"action": "draw", "token": token})
        self.assertIn(second["state"]["phase"], (
            "await_discard", "offer_kong", "offer_win"
        ))
        self.assertIsNone(second["feedback"])
        self.assertIn("win_status",second["state"])
        self.assertEqual(second["state"]["win_status"]["legal_win"],second["state"]["phase"]=="offer_win")
        while second["state"]["phase"] in ("offer_win", "offer_kong"):
            action = "win" if second["state"]["phase"] == "offer_win" else "kong"
            option = {"accept": False} if action == "win" else {"tile": None}
            second = self.post({"action": action, "token": token, **option})
            self.assertIsNone(second["feedback"])
        tile = second["state"]["choices"][0]
        graded = self.post({"action": "discard", "token": token, "tile": tile})
        self.assertIn("correct", graded["feedback"])
        self.assertEqual(graded["state"]["completed_rounds"], 1)
        self.assertIsNotNone(graded["report"])
        self.assertEqual(len(graded["report"]["round_review"]), 1)
        self.assertFalse(graded["report"]["finished"])
        self.assertIn("progress_summary", graded["report"])
        self.assertEqual(
            graded["report"]["round_review"][0]["choice"], tile)
        self.assertEqual(
            graded["report"]["round_review"][0]["effective_tile_count"],
            graded["feedback"]["selected_candidate"]["effective_tile_count"])
        state_info, _ = self.get("/api/state?" + urlencode({"token": token}))
        saved = json.loads(state_info)
        self.assertEqual(saved["state"]["completed_rounds"], 1)
        self.assertNotIn("wall", saved["state"])
        self.assertNotIn("analysis", saved["state"])
        self.assertEqual(len(saved["report"]["round_review"]), 1)
        # Following draw is unsubmitted: only historical graded analysis appears.
        next_draw = self.post({"action":"draw","token":token})
        self.assertEqual(len(next_draw["report"]["round_review"]),1)
        self.assertNotIn("analysis",next_draw["state"])
        self.assertNotIn("wall",next_draw["state"])

    def test_must_select_missing_suit_after_preview(self):
        for value in (None, "", "invalid"):
            with self.subTest(value=value), self.assertRaises(HTTPError) as err:
                self.post({"action":"new", "seed":12, "missing_suit":value})
            self.assertEqual(err.exception.code,400)

    def test_preview_reports_suit_counts_and_tianque_without_hidden_wall(self):
        preview = self.post({"action":"preview", "seed":31})
        cards = preview["initial_hand"]
        counts = preview["suit_counts"]
        self.assertEqual(len(cards),13)
        self.assertEqual(sum(counts.values()),13)
        for suit in ("m","s","p"):
            self.assertEqual(counts[suit],sum(t[0]==suit for t in cards))
        absent=[s for s in ("m","s","p") if counts[s]==0]
        self.assertEqual(preview["absent_suits"],absent)
        self.assertEqual(preview["tianque"],len(absent)==1)
        self.assertNotIn("wall",preview)
        self.assertNotIn("correct_answer",preview)

    def test_retry_endpoints_hide_solution_and_keep_original_session(self):
        create=self.post({"action":"new","seed":17,"rounds":1,
                          "missing_suit":"p"})
        token=create["token"]
        with self.assertRaises(HTTPError) as err:
            self.post({"action":"retry_list","token":token})
        self.assertEqual(err.exception.code,400)
        step=self.post({"action":"draw","token":token})
        while step["state"]["phase"] in ("offer_win","offer_kong"):
            action="win" if step["state"]["phase"]=="offer_win" else "kong"
            step=self.post({"action":action,"token":token,**(
                {"accept":False} if action=="win" else {"tile":None}
            )})
        state=step["state"]
        analysis=analyze_discards(
            state["hand"],missing_suit="p",
            visible_tiles=state["discard_history"]
        )
        if analysis["status"]=="already_winning":
            wrong=state["choices"][0]
        else:
            wrong=next(t for t in state["choices"]
                       if t not in analysis["best_discards"])
        completed=self.post({"action":"discard","token":token,"tile":wrong})
        self.assertFalse(completed["feedback"]["correct"])
        original=completed["report"]
        self.assertTrue(original["finished"])
        listing=self.post({"action":"retry_list","token":token})["retry"]
        self.assertEqual(listing["mistake_count"],1)
        question=self.post({"action":"retry_question","token":token,
                            "round":1})["question"]
        self.assertNotIn("best_actions",question)
        self.assertNotIn("correct",question)
        self.assertNotIn("wall",question)
        self.assertEqual(len(question["concealed"]),14)
        with self.assertRaises(HTTPError) as err:
            self.post({"action":"retry_submit","token":token,
                       "round":1,"tile":"invalid"})
        self.assertEqual(err.exception.code,400)
        wrong_retry=self.post({"action":"retry_submit","token":token,
                               "round":1,"tile":wrong})
        self.assertFalse(wrong_retry["result"]["correct"])
        right=completed["feedback"]["best_actions"][0]
        right_retry=self.post({"action":"retry_submit","token":token,
                               "round":1,"tile":right})
        self.assertTrue(right_retry["result"]["correct"])
        self.assertTrue(right_retry["result"]["improved"])
        self.assertEqual(right_retry["retry"]["corrected_count"],1)
        restored=json.loads(self.get(
            "/api/state?"+urlencode({"token":token})
        )[0])
        self.assertEqual(restored["report"],original)
        self.assertEqual(restored["state"],completed["state"])

    def test_fake_token_cannot_grab_other_session(self):
        with self.assertRaises(HTTPError) as err:
            self.post({"action": "draw", "token": "fabricated"})
        self.assertEqual(err.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
