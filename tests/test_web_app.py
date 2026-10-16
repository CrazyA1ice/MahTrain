"""Local website API, static asset and server-owned session smoke tests."""
from __future__ import annotations

import json
import tempfile
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
from mahtrain_core.history import HistoryStore  # noqa: E402


class WebUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_store = web_server._HISTORY
        cls._temp = tempfile.TemporaryDirectory()
        cls._history_path = Path(cls._temp.name) / "http-archive.sqlite3"
        web_server._HISTORY = HistoryStore(cls._history_path)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), web_server.Handler)
        cls.base = "http://127.0.0.1:" + str(cls.httpd.server_address[1])
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)
        web_server._HISTORY = cls._old_store
        cls._temp.cleanup()

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


    def test_sqlite_history_after_restart_and_archived_retry_http(self):
        created=self.post({"action":"new","seed":17,"rounds":1,"missing_suit":"p"})
        token=created["token"]
        step=self.post({"action":"draw","token":token})
        while step["state"]["phase"] in ("offer_win","offer_kong"):
            mode=step["state"]["phase"]
            step=self.post({"action":"win" if mode=="offer_win" else "kong",
                "token":token,**({"accept":False} if mode=="offer_win"
                else {"tile":None})})
        state=step["state"]
        ranked=analyze_discards(state["hand"],missing_suit="p",
                                visible_tiles=state["discard_history"])
        wrong=next(tile for tile in state["choices"]
                   if tile not in ranked["best_discards"])
        result=self.post({"action":"discard","token":token,"tile":wrong})
        self.assertTrue(result["report"]["finished"])
        archive_id=result["archive_id"]
        self.assertTrue(archive_id)
        history=json.loads(self.get("/api/history")[0])
        self.assertTrue(any(row["archive_id"]==archive_id
                            for row in history["sessions"]))
        # Simulate closing the Python HTTP server and starting a new process:
        # discard live tokens; reopen the sqlite3 file from disk.
        web_server._SESSIONS.pop(token)
        web_server._HISTORY=HistoryStore(self._history_path)
        stored=json.loads(self.get("/api/history?archive_id="+
                      urlencode({"id":archive_id}).split("=",1)[1])[0])
        self.assertEqual(stored["report"],result["report"])
        self.assertNotIn("wall",stored)
        question=self.post({"action":"history_retry_question",
                            "archive_id":archive_id,"round":1})["question"]
        self.assertNotIn("best_actions",question)
        self.assertNotIn("analysis",question)
        right=result["feedback"]["best_actions"][0]
        replay=self.post({"action":"history_retry_submit",
                          "archive_id":archive_id,"round":1,"tile":right})
        self.assertTrue(replay["result"]["correct"])
        self.assertTrue(replay["retry"]["corrected_count"])
        self.assertEqual(json.loads(self.get(
            "/api/history?archive_id="+archive_id
        )[0])["retry"]["corrected_count"],1)
        delete=self.post({"action":"history_delete","archive_id":archive_id})
        self.assertTrue(delete["deleted"])
        with self.assertRaises(HTTPError) as err:
            self.get("/api/history?archive_id="+archive_id)
        self.assertEqual(err.exception.code,400)

    def test_history_page_scripts_and_controls(self):
        html,_=self.get("/")
        self.assertIn(b"/history.js",html)
        self.assertIn(b"id=\"history-panel\"",html)
        js,kind=self.get("/history.js")
        self.assertIn("javascript",kind)
        self.assertIn(b"history_retry_submit",js)
        self.assertIn(b"MahTrainHistory",js)
        css,_=self.get("/app.css")
        self.assertIn(b".history-panel",css)

    def test_quiz_modes_levels_and_trusted_grading(self):
        for mode in ("one_shanten", "tenpai_discard",
                     "pure_suit_waits", "pure_suit_discard"):
            for difficulty in ("basic", "intermediate", "challenge"):
                with self.subTest(mode=mode,difficulty=difficulty):
                    data=self.post({"action":"quiz_new","mode":mode,
                                    "difficulty":difficulty})
                    question=data["question"]
                    self.assertEqual(question["mode"],mode)
                    self.assertEqual(question["difficulty"],difficulty)
                    self.assertNotIn("seed",question)
                    self.assertNotIn("best_actions",question)
                    self.assertNotIn("correct_tiles",question)
                    self.assertGreater(len(data["quiz_token"]),20)
                    answer=([] if question["answer_type"]=="tile_set"
                            else question["choices"][0])
                    response=self.post({"action":"quiz_answer",
                        "quiz_token":data["quiz_token"],"selection":answer})
                    self.assertIn("correct",response["result"])
                    with self.assertRaises(HTTPError) as err:
                        self.post({"action":"quiz_answer",
                            "quiz_token":data["quiz_token"],"selection":answer})
                    self.assertEqual(err.exception.code,400)

    def test_quiz_rejects_bad_levels_and_invalid_answer_without_consuming(self):
        for difficulty in ("invalid", "", None):
            with self.assertRaises(HTTPError) as err:
                self.post({"action":"quiz_new","mode":"one_shanten",
                           "difficulty":difficulty})
            self.assertEqual(err.exception.code,400)
        data=self.post({"action":"quiz_new","mode":"tenpai_discard",
                        "difficulty":"intermediate"})
        with self.assertRaises(HTTPError):
            self.post({"action":"quiz_answer","quiz_token":data["quiz_token"],
                       "selection":"p100"})
        self.assertIn("correct",self.post({"action":"quiz_answer",
            "quiz_token":data["quiz_token"],"selection":
                data["question"]["choices"][0]})["result"])

    def test_quiz_page_has_picture_tile_and_level_controls(self):
        html,_=self.get("/")
        js,kind=self.get("/quiz.js")
        self.assertIn(b'id="quiz-mode"',html)
        self.assertIn(b'id="quiz-level"',html)
        self.assertIn(b'src="/quiz.js"',html)
        self.assertIn("javascript",kind)
        self.assertIn(b"tileElement",js)
        self.assertIn(b"quiz_answer",js)
        css,_=self.get("/app.css")
        self.assertIn(b".quiz-center",css)

    def test_quiz_scores_are_saved_and_recommended_from_sqlite(self):
        # The old solo SQLite store used by these HTTP tests is reused.
        question=self.post({"action":"quiz_new",
            "mode":"pure_suit_discard","difficulty":"basic"})
        token=question["quiz_token"]
        before=self.post({"action":"quiz_progress",
            "mode":"pure_suit_discard","difficulty":"basic"})["progress"]
        count=before["level_totals"]["basic"]["total"]
        with self.assertRaises(HTTPError) as exc:
            self.post({"action":"quiz_answer","quiz_token":token,
                "selection":"invalid"})
        self.assertEqual(exc.exception.code,400)
        after_invalid=self.post({"action":"quiz_progress",
            "mode":"pure_suit_discard","difficulty":"basic"})["progress"]
        self.assertEqual(after_invalid["level_totals"]["basic"]["total"],count)
        selection=question["question"]["choices"][0]
        submitted=self.post({"action":"quiz_answer",
            "quiz_token":token,"selection":selection})
        self.assertIn("answer_id",submitted)
        self.assertEqual(
            submitted["progress"]["level_totals"]["basic"]["total"],count+1)
        key=submitted["answer_id"]
        self.assertNotIn("seed",submitted)
        self.assertNotIn("seed",submitted["progress"])
        original=self.post({"action":"quiz_detail","answer_id":key})["detail"]
        self.assertEqual(original["question"],question["question"])
        self.assertNotIn("seed",original["question"])
        self.assertEqual(original["selection"],selection)
        web_server._HISTORY=HistoryStore(self._history_path)
        stored=self.post({"action":"quiz_detail","answer_id":key})["detail"]
        self.assertEqual(stored["result"],submitted["result"])
        with self.assertRaises(HTTPError) as exc:
            self.post({"action":"quiz_answer","quiz_token":token,
                "selection":selection})
        self.assertEqual(exc.exception.code,400)
        self.assertEqual(
            self.post({"action":"quiz_progress",
              "mode":"pure_suit_discard","difficulty":"basic"}
            )["progress"]["level_totals"]["basic"]["total"],count+1)
        if not submitted["result"]["correct"]:
            safe=self.post({"action":"quiz_retry_question","answer_id":key})["question"]
            self.assertNotIn("best_actions",safe)
            self.assertNotIn("correct_tiles",safe)
            right=submitted["result"]["best_actions"][0]
            retried=self.post({"action":"quiz_retry_answer",
                "answer_id":key,"selection":right})
            self.assertTrue(retried["result"]["correct"])
            self.assertEqual(retried["retry"]["attempts"],1)
        deleted=self.post({"action":"quiz_delete","answer_id":key})
        self.assertTrue(deleted["deleted"])

    def test_quiz_history_js_is_exposed_and_has_manual_recommendation_button(self):
        page,_=self.get("/")
        code,mime=self.get("/quiz_history.js")
        self.assertIn("javascript",mime)
        self.assertIn(b"quiz-history-stats",page)
        self.assertIn(b"quiz-recommendation",page)
        self.assertIn(b"quiz-attempt-list",page)
        self.assertIn(b"quiz_retry_answer",code)
        self.assertIn("采用推荐".encode(),code)
        self.assertIn(b"MahTrainQuizHistory",code)

    def test_fake_token_cannot_grab_other_session(self):
        with self.assertRaises(HTTPError) as err:
            self.post({"action": "draw", "token": "fabricated"})
        self.assertEqual(err.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
