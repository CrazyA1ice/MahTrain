"""Local website API, static asset and server-owned session smoke tests."""
from __future__ import annotations

import json
import tempfile
import sys
import threading
import unittest
from unittest.mock import patch
from time import sleep
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
from mahtrain_core.match_archive import MatchArchive  # noqa: E402


class WebUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_store = web_server._HISTORY
        cls._old_match_archive = web_server._MATCH_ARCHIVE
        cls._temp = tempfile.TemporaryDirectory()
        cls._history_path = Path(cls._temp.name) / "http-archive.sqlite3"
        web_server._HISTORY = HistoryStore(cls._history_path)
        web_server._MATCH_ARCHIVE = MatchArchive(cls._history_path)
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
        web_server._MATCH_ARCHIVE = cls._old_match_archive
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

    def test_m348_read_only_match_resume_and_invalid_capabilities(self):
        created=self.post({"action":"match_new","seed":137})
        token=created["match_token"]
        game=web_server._MATCH_SESSIONS[token]
        before=game.public_state()
        count=len(web_server._MATCH_SESSIONS)
        first=self.post({"action":"match_resume","match_token":token,
                         "seat":3,"action_override":"match_discard"})
        self.assertEqual(first["match_token"],token)
        self.assertEqual(first["match"]["seat"],0)
        self.assertEqual(first["match"]["hand"],created["match"]["hand"])
        self.assertEqual(first["match"]["phase"],created["match"]["phase"])
        self.assertEqual(first["match"]["public_steps"],[])
        self.assertFalse(first["match"]["needs_continue"])
        self.assertEqual(first["match"]["ai_opponents"],
                         created["match"]["ai_opponents"])
        self.assertEqual(len(web_server._MATCH_SESSIONS),count)
        self.assertEqual(game.public_state(),before,
                         "read-only resume must not advance a tile or event")
        for key in ("_hands","_wall","seed","wall_tiles","other_hands"):
            self.assertNotIn(key,first["match"])
        with self.assertRaises(HTTPError) as cm:
            self.post({"action":"match_resume","match_token":"invalid"})
        self.assertEqual(cm.exception.code,400)
        with self.assertRaises(HTTPError):
            self.post({"action":"match_resume"})
        exchange=next([t for t in created["match"]["hand"]
                       if t.startswith(s)][:3] for s in "msp"
                      if sum(t.startswith(s) for t in created["match"]["hand"])>=3)
        self.post({"action":"match_exchange","match_token":token,"tiles":exchange})
        self.post({"action":"match_missing","match_token":token,"suit":"p"})
        current=game.public_state()
        resumed=self.post({"action":"match_resume","match_token":token})
        self.assertEqual(resumed["match"]["phase"],current["phase"])
        self.assertEqual(resumed["match"]["turn"],current["turn"])
        self.assertEqual(resumed["match"]["needs_continue"],
                         web_server._match_requires_continue(game))
        self.assertEqual(game.public_state(),current)
        html,_=self.get("/")
        script,_=self.get("/match.js")
        css,_=self.get("/app.css")
        for element in (b'id="match-resume-tools"',
                        b'id="match-resume-message"',
                        b'id="match-resume-retry"'):
            self.assertIn(element,html)
        for field in (b"sessionStorage",b"match_resume",
                      b"MATCH_SESSION_KEY",b"savedMatchToken",
                      b"clearSavedMatchToken",b"resumeMatch()",
                      b"token===expectedToken"):
            self.assertIn(field,script)
        self.assertIn(b".match-resume-tools[hidden]",css)

    def test_m349_interrupted_action_reconciliation_contract(self):
        page,_=self.get("/")
        client,_=self.get("/match.js")
        self.assertIn(b"fetchMatchSnapshot",client)
        self.assertIn(b"acceptMatchSnapshot",client)
        self.assertIn(b"recoveryRequired",client)
        self.assertIn(b"resyncError.expired",client)
        self.assertIn(b"failure.rejected=",client)
        self.assertIn(b'if(busy||(recoveryRequired',client)
        self.assertIn("本步结果尚未确认".encode(),client)
        self.assertIn("已重新同步服务器牌局".encode(),client)
        self.assertIn("没有重复提交".encode(),client)
        self.assertIn(b'id="match-resume-retry"',page)

    def test_m337_public_speech_controls_are_locally_served(self):
        page, _ = self.get("/")
        voice, kind = self.get("/match_voice.js")
        client, _ = self.get("/match.js")
        css, _ = self.get("/app.css")
        self.assertIn("javascript", kind)
        for element in (b'id="match-voice-speed"', b'id="match-voice-repeat"',
                        b'value="slow"', b'value="normal"', b'value="fast"'):
            self.assertEqual(page.count(element), 1)
        for token in (b"repeatLast", b"canRepeat", b"reset",
                      b"RATES", b"announced"):
            self.assertIn(token, voice)
        for token in (b"syncVoiceControls", b"match-voice-speed",
                      b"match-voice-repeat", b"voice?.reset()"):
            self.assertIn(token, client)
        self.assertIn(b".match-voice-controls", css)

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

    def test_error_diagnosis_and_verified_focus_api(self):
        # No client-provided seed or arbitrary correct-answer claimed.
        for mode,focus in (
            ("pure_suit_waits","missing_wait"),
            ("pure_suit_waits","extra_wait"),
            ("pure_suit_discard","missed_win"),
            ("pure_suit_discard","false_win"),
        ):
            with self.subTest(mode=mode,focus=focus):
                data=self.post({"action":"quiz_new","mode":mode,
                    "difficulty":"basic","focus":focus})
                question=data["question"]
                public=("win_decision" if focus in ("missed_win",
                       "false_win") else focus)
                self.assertEqual(question["focus"],public)
                if public=="win_decision":
                    self.assertNotIn("missed_win",json.dumps(question))
                    self.assertNotIn("false_win",json.dumps(question))
                self.assertNotIn("seed",question)
                self.assertNotIn("best_actions",question)
                self.assertNotIn("correct_tiles",question)
                choice=([] if question["answer_type"]=="tile_set"
                        else question["choices"][0])
                graded=self.post({"action":"quiz_answer",
                    "quiz_token":data["quiz_token"],"selection":choice})
                self.assertIn("error_types",graded["result"])
                self.assertIn("weaknesses",graded["progress"])
                self.assertIn("counts",graded["progress"]["weaknesses"])
        with self.assertRaises(HTTPError) as err:
            self.post({"action":"quiz_new","mode":"pure_suit_waits",
                "difficulty":"basic","focus":"missed_win"})
        self.assertEqual(err.exception.code,400)

    def test_auto_focus_strategy_and_frontend_weakness_controls(self):
        data=self.post({"action":"quiz_new","mode":"pure_suit_waits",
            "difficulty":"basic","focus":"auto"})
        q=data["question"]
        self.assertEqual(q["training_strategy"],"adaptive_weakness")
        self.assertEqual(q["focus_applied"],"focus" in q)
        self.assertNotIn("seed",q)
        page,_=self.get("/")
        code,_=self.get("/quiz_history.js")
        main,_=self.get("/quiz.js")
        self.assertIn(b'id="quiz-weaknesses"',page)
        self.assertIn("开启薄弱项强化".encode(),code)
        self.assertIn(b'activeStrategy',main)
        self.assertIn(b'error_labels',main)

    def test_solo_error_report_and_deep_link_appear_without_future_answer(self):
        created=self.post({"action":"new","seed":17,"rounds":2,
                           "missing_suit":"p"})
        token=created["token"]
        state=self.post({"action":"draw","token":token})
        self.assertIsNone(state["report"],
                          "the pending answer must not be included")
        while state["state"]["phase"] in ("offer_win","offer_kong"):
            mode=state["state"]["phase"]
            state=self.post({"action":"win" if mode=="offer_win" else "kong",
                             "token":token,**({"accept":False}
                             if mode=="offer_win" else {"tile":None})})
        selection=state["state"]["choices"][0]
        result=self.post({"action":"discard","token":token,"tile":selection})
        report=result["report"]
        self.assertIn("error_summary",report)
        self.assertEqual(len(report["round_review"]),1)
        item=report["round_review"][0]
        self.assertIn("error_types",item)
        self.assertIn("error_labels",item)
        self.assertEqual(bool(item["error_types"]),not item["correct"])
        self.assertEqual(report["error_summary"]["error_rounds"],
                         int(not item["correct"]))
        self.assertNotIn("wall",report)
        self.assertNotIn("future_wall",report)
        page,_=self.get("/")
        ui,mime=self.get("/review.js")
        archive_ui,_=self.get("/history.js")
        css,_=self.get("/app.css")
        self.assertIn(b"report-panel",page)
        self.assertIn(b"showErrors",ui)
        self.assertIn(b"startFocus",ui)
        self.assertIn(b"error_labels",ui)
        self.assertIn(b"error_summary",archive_ui)
        self.assertIn(b".solo-error-summary",css)
        self.assertIn("javascript",mime)

    def test_four_seat_opening_browser_demo_and_sealed_phases(self):
        setup=self.post({"action":"table_new","seed":42})
        token=setup["table_token"]
        table=setup["table"]
        self.assertEqual(table["phase"],"exchange_select")
        self.assertEqual(table["wall_count"],55)
        self.assertEqual(sorted(table["hand_counts"]),[13,13,13,14])
        self.assertEqual(table["seat"],0)
        self.assertEqual(len(table["hand"]),
                         14 if table["dealer"]==0 else 13)
        self.assertNotIn("seed",str(table))
        self.assertNotIn("_hands",str(table))
        self.assertNotIn("_wall",str(table))
        self.assertIsNone(table["missing_suits"])
        self.assertEqual(table["exchange_submitted"],[])
        hand=table["hand"]
        pick=next([t for t in hand if t.startswith(s)][:3]
                  for s in "msp"
                  if len([t for t in hand if t.startswith(s)])>=3)
        with self.assertRaises(HTTPError) as exc:
            self.post({"action":"table_exchange",
                "table_token":token,"tiles":pick[:2]})
        self.assertEqual(exc.exception.code,400)
        exchanged=self.post({"action":"table_exchange",
            "table_token":token,"tiles":pick})["table"]
        self.assertEqual(exchanged["phase"],"missing_select")
        self.assertEqual(exchanged["wall_count"],55)
        self.assertEqual(len(exchanged["hand"]),len(hand))
        self.assertTrue(exchanged["tianque"] in (True,False))
        self.assertIsNone(exchanged["missing_suits"])
        with self.assertRaises(HTTPError):
            self.post({"action":"table_exchange",
                "table_token":token,"tiles":pick})
        started=self.post({"action":"table_missing",
            "table_token":token,"suit":"p"})["table"]
        self.assertIn(started["phase"],("dealer_discard","await_discard"))
        self.assertEqual(started["turn"],0)
        self.assertEqual(len(started["missing_suits"]),4)
        self.assertEqual(started["missing_suits"][0],"p")
        self.assertEqual(len(started["hand"]),14)
        self.assertNotIn("opponent_hand",started)
        self.assertGreaterEqual(started["wall_count"],52)
        with self.assertRaises(HTTPError):
            self.post({"action":"table_missing",
                "table_token":token,"suit":"m"})
        cut=started["hand"][0]
        next_turn=self.post({"action":"table_discard",
            "table_token":token,"tile":cut})["table"]
        self.assertEqual(next_turn["discards"][0]["tile"],cut)
        self.assertEqual(next_turn["discards"][0]["seat"],
                         started["dealer"] if started["dealer"]==0 else started["dealer"])
        self.assertGreaterEqual(next_turn["wall_count"],0)
        self.assertEqual(next_turn["turn"],0)
        self.assertEqual(next_turn["phase"],"await_discard")
        self.assertEqual(len(next_turn["hand"]),14)
        self.assertIn("demo_no_claims",[
            e["type"] for e in next_turn["events"]
        ])

    def test_four_seat_demo_static_assets_and_bad_seeds(self):
        html,_=self.get("/")
        script,mime=self.get("/four_player.js")
        self.assertIn("javascript",mime)
        self.assertIn(b'id="four-player-demo"',html)
        self.assertIn(b'id="table-hand"',html)
        self.assertIn(b"table_exchange",script)
        self.assertIn(b"table_missing",script)
        css,_=self.get("/app.css")
        self.assertIn(b".table-demo",css)
        for seed in (-1,2**32,True,"42"):
            with self.subTest(seed=seed),self.assertRaises(HTTPError):
                self.post({"action":"table_new","seed":seed})
        with self.assertRaises(HTTPError):
            self.post({"action":"table_discard",
                       "table_token":"forged","tile":"m1"})

    def test_m31_match_api_scripted_opening_and_claim_windows(self):
        started=self.post({"action":"match_new","seed":42})
        token=started["match_token"]
        state=started["match"]
        self.assertEqual(state["phase"],"exchange_select")
        self.assertEqual(state["wall_count"],55)
        self.assertNotIn("seed",state)
        self.assertNotIn("_wall",state)
        self.assertNotIn("_hands",state)
        self.assertIsNone(state["missing_suits"])
        self.assertEqual(len(state["hand"]),14 if state["dealer"]==0 else 13)
        hand=state["hand"]
        chosen=next([t for t in hand if t.startswith(s)][:3]
                    for s in "msp"
                    if sum(t.startswith(s) for t in hand)>=3)
        with self.assertRaises(HTTPError):
            self.post({"action":"match_exchange","match_token":token,
                       "tiles":chosen[:2]})
        swapped=self.post({"action":"match_exchange","match_token":token,
                           "tiles":chosen})["match"]
        self.assertEqual(swapped["phase"],"missing_select")
        self.assertIsNone(swapped["missing_suits"])
        self.assertEqual(swapped["wall_count"],55)
        with self.assertRaises(HTTPError):
            self.post({"action":"match_exchange","match_token":token,
                       "tiles":chosen})
        started=self.post({"action":"match_missing","match_token":token,
                           "suit":"p"})["match"]
        self.assertEqual(started["missing_suits"][0],"p")
        self.assertNotIn("opponent_hand",started)
        self.assertNotIn("seed",started)
        self.assertNotIn("wall",started)
        current=started
        for index in range(12):
            phase=current["phase"]
            if phase in ("finished","wall_exhausted"):
                break
            if current.get("needs_continue"):
                # Interactive game explicitly advances ONE AI transition per
                # request; old all-AI-at-once assumptions are no longer valid.
                result=self.post({"action":"match_continue",
                                  "match_token":token})
                events=[event for step in result["match"].get("public_steps",[])
                        for event in step["events"]]
                self.assertLessEqual(
                    sum(event["type"] in web_server._MATCH_TURN_BEATS
                        for event in events),1,
                    "a continuation must stop before the second voiced action")
                self.assertLessEqual(
                    len(result["match"].get("public_steps",[])),
                    web_server._MAX_SILENT_CONTINUATIONS)
            elif phase=="claim_window":
                choices=current["claim_options"]
                self.assertGreater(len(choices),1)
                result=self.post({"action":"match_claim","match_token":token,
                                   "choice":"pass"})
            elif phase=="rob_kong_window":
                self.assertGreater(len(current["rob_options"]),1)
                result=self.post({"action":"match_rob","match_token":token,
                                   "choice":"pass"})
            else:
                self.assertIn(phase,("dealer_discard","await_discard"))
                self.assertEqual(current["turn"],0)
                self.assertEqual(len(current["hand"])+
                                 3*len(current["own_melds"]),14)
                result=self.post({"action":"match_discard","match_token":token,
                                   "tile":current["hand"][0]})
            current=result["match"]
            steps=current.get("public_steps",[])
            self.assertIsInstance(steps,list)
            self.assertLessEqual(len(steps),96)
            for step in steps:
                board=step["board"]
                self.assertEqual(set(board),{
                    "phase","turn","wall_count","hand_counts",
                    "melds","discards","won",
                })
                self.assertEqual(len(board["hand_counts"]),4)
                self.assertEqual(len(board["melds"]),4)
                self.assertEqual(len(board["won"]),4)
                self.assertTrue(step["events"])
                self.assertNotIn("hand",board)
                self.assertNotIn("drawn_tile",board)
                self.assertNotIn("future_wall",board)
                for seat_melds in board["melds"]:
                    for meld in seat_melds:
                        if meld["type"]=="an_gang":
                            if meld.get("revealed") is True:
                                self.assertRegex(meld["tile"],r"^[msp][1-9]$")
                            else:
                                self.assertIsNone(meld["tile"])
                for event in step["events"]:
                    if event["type"]=="an_gang":
                        if event.get("revealed") is True:
                            self.assertRegex(event["tile"],r"^[msp][1-9]$")
                        else:
                            self.assertNotIn("tile",event)
            if steps:
                for field in ("phase","turn","wall_count","hand_counts",
                              "melds","discards","won"):
                    self.assertEqual(steps[-1]["board"][field],current[field])
            self.assertTrue(0<=current["wall_count"]<=55)
            self.assertLessEqual(len(current["discards"]),55)
            self.assertNotIn("_wall",current)
        self.assertIn(current["phase"],(
            "finished","wall_exhausted","claim_window","rob_kong_window",
            "dealer_discard","await_discard","await_draw"))
        with self.assertRaises(HTTPError) as exc:
            self.post({"action":"match_discard","match_token":"forged",
                       "seat":1,"tile":"m1"})
        self.assertEqual(exc.exception.code,400)

    def test_m31_match_static_controls_and_validation(self):
        markup,_=self.get("/")
        js,mime=self.get("/match.js")
        css,_=self.get("/app.css")
        self.assertIn(b'id="match-panel"',markup)
        self.assertIn(b'src="/match.js"',markup)
        self.assertIn(b".match-panel",css)
        self.assertIn("javascript",mime)
        self.assertIn(b"match_claim",js)
        self.assertIn(b"match_rob",js)
        self.assertIn(b"match_kong",js)
        self.assertIn(b"match_win",js)
        for bad in (-1,2**32,True,"42"):
            with self.subTest(bad=bad),self.assertRaises(HTTPError):
                self.post({"action":"match_new","seed":bad})

    def test_m324_random_server_seeds_lab_and_voice_assets(self):
        from unittest.mock import patch
        first, second = 4190000041, 4190000042
        web_server._MATCH_USED_SEEDS.discard(first)
        web_server._MATCH_USED_SEEDS.discard(second)
        with patch.object(web_server.secrets, "randbelow",
                          side_effect=[first, first, second]) as rand:
            a = self.post({"action": "match_new"})
            b = self.post({"action": "match_new"})
            self.assertEqual(rand.call_count, 3)
        self.assertNotEqual(a["match_token"], b["match_token"])
        self.assertEqual(a["match"]["phase"], "exchange_select")
        self.assertEqual(b["match"]["phase"], "exchange_select")
        self.assertIn(first, web_server._MATCH_USED_SEEDS)
        self.assertIn(second, web_server._MATCH_USED_SEEDS)
        for response in (a, b):
            self.assertNotIn("seed", response["match"])
            self.assertNotIn("seed", response)
            self.assertNotIn("_wall", response["match"])
        # Explicit old API seed is still accepted for laboratory replay.
        old = self.post({"action": "match_new", "seed": 42})["match"]
        self.assertEqual(old["hand"], self.post({
            "action": "match_new", "seed": 42})["match"]["hand"])
        html, _ = self.get("/")
        script, content_type = self.get("/match_voice.js")
        css, _ = self.get("/app.css")
        self.assertIn("javascript", content_type)
        for ident in ("match-again", "match-lab", "match-lab-enabled",
                      "match-seed", "match-voice-enabled"):
            self.assertEqual(html.count(('id="%s"' % ident).encode()), 1)
        self.assertLess(html.index(b"/match_voice.js"), html.index(b"/match.js"))
        self.assertIn(b"MahTrainMatchVoice", script)
        self.assertIn(b".match-river-cell .tile{width:44px;height:60px}", css)
        self.assertIn(b".match-seat-meld .tile{width:40px;height:54px}", css)

    def test_m330_controlled_ai_score_lab_is_public_and_visible(self):
        html,_=self.get("/")
        js,_=self.get("/ai_replay.js")
        for ident in ("ai-replay-official-scores",
                      "ai-replay-official-caveat",
                      "ai-replay-official-levels",
                      "ai-replay-official-differences",
                      "ai-replay-official-download"):
            self.assertEqual(html.count(('id="%s"' % ident).encode()),1)
        self.assertIn(b"official_score_analysis",js)
        self.assertIn(b"renderOfficialScores()",js)
        self.assertIn(b"downloadOfficialScores",js)
        self.assertNotIn(b"private_view",js)

    def test_m314_live_match_four_sided_table_markup_and_privacy(self):
        page,_=self.get("/")
        css,_=self.get("/app.css")
        js,_=self.get("/match.js")
        for seat in range(4):
            self.assertEqual(page.count(
                ('id="match-seat-%d"' % seat).encode()), 1)
            self.assertEqual(page.count(
                ('id="match-river-%d"' % seat).encode()), 1)
        for landmark in ("match-board", "match-wall",
                         "match-wall-count", "match-self-status",
                         "match-self-melds", "match-controls",
                         "match-public", "match-hand"):
            self.assertEqual(
                page.count(('id="%s"' % landmark).encode()),1)
        self.assertIn(b".match-seat--top",css)
        self.assertIn(b".match-seat--bottom",css)
        self.assertIn(b".match-river--left",css)
        self.assertIn(b".match-river--right",css)
        self.assertIn(b".match-board-scroll",css)
        for ident in ("match-hud-turn","match-hud-wall",
                      "match-hud-missing","match-hud-tip",
                      "match-focus-toggle","match-decision",
                      "match-confirm-discard"):
            self.assertEqual(page.count(('id="%s"' % ident).encode()),1)
        self.assertIn(b"#match-stage.is-immersive #match-public",css)
        self.assertIn(b".match-seat-avatar",css)
        self.assertIn(b".match-hud-chip--turn",css)
        self.assertIn(b".match-pending-discard",css)
        self.assertIn(b"pendingDiscard",js)
        self.assertIn(b"chooseDiscard(",js)
        self.assertIn(b"pointer: coarse",js)
        self.assertIn(b"renderHUD()",js)
        self.assertIn(b"renderBoard()",js)
        for ident in ("match-score-bursts","match-motion-big-action"):
            self.assertEqual(page.count(('id="%s"' % ident).encode()),1)
        self.assertIn(b"renderScoreBursts(",js)
        for ident in ("match-hand-prev","match-hand-next",
                      "match-hand-draw","match-hand-position",
                      "match-table-self-summary","match-skin-toggle"):
            self.assertEqual(page.count(('id="%s"' % ident).encode()),1)
        self.assertIn(b"updateHandNavigation()",js)
        self.assertIn(b'navigateHand("draw")',js)
        self.assertIn(b"previousHandScroll",js)
        self.assertIn(b"match-reaction-actions",js)
        self.assertIn(b".match-hand-navigation",css)
        self.assertIn(b".match-reaction--hu",css)
        self.assertIn(b".match-table-self-summary",css)
        self.assertIn(b"is-midnight-felt",css)
        self.assertIn(b"midnightFelt",js)
        self.assertIn(b"match-motion-big-action",css)
        self.assertIn(b".match-score-burst.is-credit",css)
        self.assertIn(b".match-score-burst.is-debit",css)
        self.assertIn(b"@media(max-width:700px)",css)
        self.assertIn(b".match-board-scroll{overflow-x:hidden",css)
        self.assertIn(b".match-board-center{",css)
        self.assertIn(b"scroll-snap-type:x proximity",css)
        self.assertIn(b"prefers-reduced-motion:reduce",css)
        self.assertIn(b"view.discards.map",js)
        self.assertIn(b"view.hand_counts[seat]",js)
        self.assertIn(b"meld.tile===null",js)
        self.assertIn(b"match_discard",js)
        self.assertIn(b"match_exchange",js)
        self.assertIn(b"match_missing",js)
        self.assertIn(b"match_rob",js)
        self.assertIn(b"match_claim",js)
        self.assertIn(b"match_win",js)
        self.assertIn(b"match_kong",js)

    def test_m317_public_snapshots_are_from_actual_rule_calls(self):
        from test_four_player import to_dealer_turn
        from web_server import _match_record, _match_public_step
        game=to_dealer_turn(17)
        seat=game.dealer
        steps=[]
        # The dealer cuts WITHOUT drawing first.
        tile=game.private_view(seat)["hand"][0]
        _match_record(game,steps,lambda: game.discard(seat,tile))
        self.assertEqual(len(steps),1)
        first=steps[0]["board"]
        self.assertEqual(first["hand_counts"][seat],13)
        self.assertEqual(first["wall_count"],55)
        self.assertEqual(first["discards"][0]["tile"],tile)
        self.assertEqual(steps[0]["events"][-1]["type"],"discard")
        # All pass + next player's REAL front draw gives distinct boards.
        _match_record(game,steps,game.pass_all_claims_demo)
        self.assertEqual(steps[1]["events"][-1]["type"],"demo_no_claims")
        other=game.turn
        _match_record(game,steps,lambda: game.draw(other))
        self.assertEqual(steps[-1]["events"][-1]["type"],"draw")
        self.assertEqual(steps[-1]["board"]["wall_count"],54)
        self.assertEqual(steps[-1]["board"]["hand_counts"][other],14)
        self.assertEqual(game.debug_tile_counts()["total"],108)
        self.assertEqual(set(steps[-1]["board"]),{
            "phase","turn","wall_count","hand_counts",
            "melds","discards","won",
        })
        for step in steps:
            self.assertNotIn("hand",step["board"])
            self.assertNotIn("_wall",step["board"])
            self.assertNotIn("drawn_tile",step["board"])
        empty=len(steps)
        _match_public_step(game,len(game._events),steps)
        self.assertEqual(len(steps),empty)

    def test_m322_completed_match_archive_api_and_static_ui(self):
        page,_=self.get("/")
        js,mime=self.get("/match_archives.js")
        css,_=self.get("/app.css")
        app,_=self.get("/app.js")
        self.assertIn("javascript",mime)
        self.assertIn(b"MahTrainMatchArchives",js)
        self.assertIn(b"MahTrainMatchArchives?.init",app)
        for item in ("match-archives-refresh","match-archives-list",
                     "match-archives-detail","match-archives-compare",
                     "match-archives-export","match-archives-board",
                     "match-archives-seat","match-archives-action"):
            self.assertEqual(page.count(('id="%s"' % item).encode()),1)
        self.assertIn(b".match-archive-four-seats",css)
        self.assertLess(page.index(b'/match_archives.js'),
                        page.index(b'/app.js'))
        before,_=self.get("/api/match_archives")
        count=json.loads(before)["summary"]["games"]
        game=web_server.FourPlayerOpening(47)
        actual=game.public_state()
        terminal={**actual,"phase":"wall_exhausted"}
        archive=web_server._MATCH_ARCHIVE.save_completed(
            terminal,[{"board":actual,
                       "events":[{"type":"draw","seat":1,
                                  "tile":"PRIVATE-MUST-NOT-SAVE"}]}],
            actual,["basic","advanced","challenge"])
        summary,_=self.get("/api/match_archives?limit=10")
        parsed=json.loads(summary)
        self.assertEqual(parsed["summary"]["games"],count+1)
        self.assertIn(archive,[r["archive_id"] for r in parsed["matches"]])
        card=parsed["scorecard"]
        self.assertEqual(len(card["seats"]),4)
        self.assertTrue(card["zero_sum"])
        self.assertGreaterEqual(card["valid_games"],1)
        self.assertEqual(sum(x["settled_total"] for x in card["seats"]),0)
        self.assertIn("groupings",card)
        self.assertIn("ai_lineups",card["groupings"])
        self.assertIn("room_rules",card["groupings"])
        self.assertNotIn("PRIVATE-MUST-NOT-SAVE",json.dumps(card))
        for required in ("match-scorecard-status","match-scorecard-seats",
                         "match-scorecard-trend"):
            self.assertEqual(page.count(('id="%s"' % required).encode()),1)
        self.assertIn(b".match-scorecard-trend-row",css)
        self.assertIn(b".match-history-group-item",css)
        for ident in ("match-history-groups-mode","match-history-groups-status",
                      "match-history-groups-rows"):
            self.assertEqual(page.count(('id="%s"' % ident).encode()),1)
        detail,_=self.get("/api/match_archives?archive_id="+archive)
        data=json.loads(detail)["report"]
        self.assertEqual(data["privacy"],"public_board_only")
        self.assertEqual(data["steps"][0]["events"],[
            {"type":"draw","seat":1}])
        self.assertNotIn("seed",json.dumps(data))
        with self.assertRaises(HTTPError) as exc:
            self.get("/api/match_archives?archive_id=not-found")
        self.assertEqual(exc.exception.code,400)
        with self.assertRaises(HTTPError) as exc:
            self.get("/api/match_archives?limit=500")
        self.assertEqual(exc.exception.code,400)

    def test_m321_filterable_replay_uses_public_historical_frames(self):
        page,_=self.get("/")
        js,_=self.get("/match.js")
        playback,_=self.get("/match_playback.js")
        css,_=self.get("/app.css")
        for name in ("match-review-seat-filter","match-review-type-filter",
                     "match-review-inspector","match-review-selected",
                     "match-review-board-status","match-review-preview-seats",
                     "match-review-prev","match-review-next",
                     "match-review-count"):
            self.assertEqual(page.count(('id="%s"' % name).encode()),1)
        for field in (b"appendReviewFrames",b"renderReviewInspector",
                      b"renderReviewFiltered",b"MAX_REVIEW_STEPS",
                      b"normalizeHistorySteps",b"filterReviewEntries",
                      b"stepReview"):
            self.assertIn(field,js)
        for field in (b"normalizeBoard",b"openingFrame",
                      b"normalizeHistorySteps",b"filterReviewEntries"):
            self.assertIn(field,playback)
        for field in (b".match-review-inspector",
                      b".match-review-preview-seats",
                      b".match-review-action.is-selected"):
            self.assertIn(field,css)

    def test_m320_round_end_report_and_all_win_details(self):
        page,_=self.get("/")
        script,_=self.get("/match.js")
        playback,_=self.get("/match_playback.js")
        css,_=self.get("/app.css")
        for name in ("match-motion-settlements","match-table-history",
                     "match-round-report","match-round-report-title",
                     "match-round-report-status","match-round-report-seats",
                     "match-round-report-wins","match-round-report-events",
                     "match-round-report-note"):
            self.assertEqual(page.count(('id="%s"' % name).encode()),1)
        self.assertIn(b"renderRoundReport",script)
        self.assertIn(b"appendWinRecord",script)
        self.assertIn(b"win_settlement",playback)
        self.assertIn(b"settlements.map",playback)
        self.assertIn(b".match-motion-payment",css)
        self.assertIn(b".match-round-report",css)
        self.assertIn(b".match-win-history",css)

    def test_m319_table_meld_racks_and_settlement_landmarks(self):
        page,_=self.get("/")
        js,_=self.get("/match.js")
        css,_=self.get("/app.css")
        for item in ("match-table-settlement","match-table-scores",
                     "match-table-wins","match-table-score-note",
                     "match-table-settlement-title","match-own-score",
                     "match-table-round-phase"):
            self.assertEqual(page.count(
                ('id="%s"' % item).encode()),1)
        self.assertLess(page.index(b'id="match-seat-0"'),
                        page.index(b'id="match-table-settlement"'))
        self.assertLess(page.index(b'id="match-table-settlement"'),
                        page.index(b'id="match-controls"'))
        for token in (b"renderTableSettlement",b"settlementAvailable",
                      b"match-seat-meld--",b"win_ledger.balances",
                      b"match-table-score-note",b"kong_ledger"):
            self.assertIn(token,js)
        for token in (b".match-table-settlement",
                      b".match-table-scores",
                      b".match-seat--left .match-seat-melds",
                      b".match-seat--right .match-seat-melds",
                      b".match-board .match-seat.is-won::before"):
            self.assertIn(token,css)
        self.assertIn(b"grid-area:summary",css)

    def test_m318_kong_win_playback_controls_always_available(self):
        page,_=self.get("/")
        script,mime=self.get("/match_playback.js")
        match,_=self.get("/match.js")
        css,_=self.get("/app.css")
        self.assertIn("javascript",mime)
        for name in ("match-playback-speed","match-playback-focus",
                     "match-playback-step","match-motion-chain",
                     "match-motion-delta"):
            self.assertEqual(
                page.count(('id="%s"' % name).encode()),1)
        self.assertLess(
            page.index(b'class="match-playback-settings"'),
            page.index(b'id="match-playback"'))
        for token in (b"highlightFrames",b"holdScale",b"tailDraw",
                      b"changes",b"step()",b"normalizeSteps"):
            self.assertIn(token,script)
        for token in (b"match-playback-step",b"match-playback-focus",
                      b"match-motion-chain",b"match-motion-delta"):
            self.assertIn(token,match)
        for token in (b".match-motion.is-kong-motion",
                      b".match-motion.is-peng-motion",
                      b".match-motion.is-winning-motion",
                      b".match-playback-settings"):
            self.assertIn(token,css)

    def test_m316_public_match_action_playback_assets(self):
        page,_=self.get("/")
        script,mime=self.get("/match_playback.js")
        main,_=self.get("/match.js")
        style,_=self.get("/app.css")
        self.assertIn("javascript",mime)
        self.assertLess(page.index(b'src="/match_playback.js"'),
                        page.index(b'src="/match.js"'))
        for item in ("match-playback","match-playback-speed",
                     "match-playback-pause","match-playback-skip",
                     "match-playback-status","match-playback-progress",
                     "match-motion","match-motion-card","match-motion-text"):
            self.assertEqual(page.count(('id="%s"' % item).encode()),1)
        for field in (b"normalize",b"createController",b"pause",b"resume",
                      b"setSpeed",b"VISIBLE_TILE",b"an_gang"):
            self.assertIn(field,script)
        for field in (b"showPublicMotion",b"match-playback-speed",
                      b"match-playback-pause",b"match-playback-skip"):
            self.assertIn(field,main)
        self.assertIn(b".match-motion",style)
        self.assertIn(b"prefers-reduced-motion",style)
        response=self.post({"action":"match_new","seed":42})
        self.assertIn("events",response["match"])
        self.assertNotIn("_hands",response["match"])
        self.assertNotIn("_wall",response["match"])

    def test_m315_match_readiness_and_private_draw_display(self):
        page,_=self.get("/")
        script,_=self.get("/match.js")
        style,_=self.get("/app.css")
        for node in (b'id="match-win-alert"',b'id="match-ready-hint"'):
            self.assertIn(node,page)
        for signal in (b"match-new-draw",b"ready_waits",
                       b"ready_after_discards",b"discard_kind",
                       b"from_draw",b"renderWinAlert",b"renderReadyHint"):
            self.assertIn(signal,script)
        for style_name in (b".match-new-draw",b".match-win-alert",
                           b".match-ready-hint",b".match-discard-kind"):
            self.assertIn(style_name,style)
        created=self.post({"action":"match_new","seed":42})
        state=created["match"]
        self.assertIsNone(state["drawn_tile"])
        self.assertEqual(state["ready_waits"],[])
        self.assertEqual(state["ready_after_discards"],[])
        self.assertNotIn("_drawn_tiles",str(state))
        self.assertNotIn("_wall",str(state))

    def test_m32_hu_ledger_and_tian_ting_visible_only_for_own_seat(self):
        started=self.post({"action":"match_new","seed":42,
                           "room_coefficient":200,"fan_cap":3})
        token=started["match_token"]
        state=started["match"]
        self.assertEqual(state["win_ledger"]["room_coefficient"],200)
        self.assertEqual(state["win_ledger"]["fan_cap"],3)
        self.assertEqual(state["win_ledger"]["balances"],[0,0,0,0])
        self.assertTrue(state["win_ledger"]["zero_sum"])
        self.assertNotIn("opponent_tian_ting",state)
        self.assertEqual(state["tian_ting"]["reason"],"not_initialized")
        hand=state["hand"]
        selected=next([t for t in hand if t[0]==s][:3] for s in "msp"
                      if sum(x[0]==s for x in hand)>=3)
        changed=self.post({"action":"match_exchange",
                           "match_token":token,"tiles":selected})["match"]
        self.assertEqual(changed["tian_ting"]["reason"],"not_initialized")
        live=self.post({"action":"match_missing","match_token":token,
                        "suit":"p"})["match"]
        self.assertNotEqual(live["tian_ting"]["reason"],"not_initialized")
        self.assertIsInstance(live["tian_ting"]["initial_waits"],list)
        self.assertIn("win_ledger",live)
        self.assertIn("pending_kong_payments",live)
        self.assertTrue(live["win_ledger"]["zero_sum"])
        self.assertEqual(sum(live["win_ledger"]["balances"]),0)
        self.assertNotIn("_wall",str(live))
        self.assertNotIn("_hands",str(live))
        # The client cannot submit arbitrary scores or see another seat's
        # secret baseline via any server endpoint.
        with self.assertRaises(HTTPError):
            self.post({"action":"match_pay","match_token":token,
                       "winner":0,"amount":999999})
        with self.assertRaises(HTTPError):
            self.post({"action":"match_detail",
                       "match_token":token,"seat":1})
        page,_=self.get("/")
        js,mime=self.get("/match.js")
        self.assertIn(b'id="match-coefficient"',page)
        self.assertIn(b'id="match-fan-cap"',page)
        self.assertIn(b"match-balances",js)
        self.assertIn(b"tian_ting",js)
        self.assertIn(b"pending_kong_payments",js)
        self.assertIn(b"raw_fan",js)
        self.assertIn("javascript",mime)

    def test_m339_self_draw_quote_is_private_readonly_and_served(self):
        client,_=self.get("/match.js")
        css,_=self.get("/app.css")
        for marker in (b"self_draw_preview",b"match-self-win-preview",
                       b"quote.payers",b"quote.total_received",
                       b"quote.amount_per_payer",b"quote.posted"):
            self.assertIn(marker,client)
        self.assertIn(b".match-self-win-preview",css)
        for mode in ("add_base","add_fan"):
            state=self.post({
                "action":"match_new","seed":901,
                "self_draw_mode":mode,
            })["match"]
            self.assertIn("self_draw_preview",state)
            self.assertIsNone(state["self_draw_preview"],
                "opening sealed hands must never show a win quotation")
            self.assertNotIn("opponent_self_draw_preview",state)
            self.assertNotIn("_hands",state)
            self.assertNotIn("_wall",state)

    def test_m341_silent_draw_and_ai_discard_are_one_server_response(self):
        # A real physically conserved 108-tile setup at an AI draw boundary:
        # the concealed draw can run immediately into an audible discard.
        from test_four_player_claims import staged_game
        from mahtrain_core.ai import MahjongAgent
        dealer=web_server.FourPlayerOpening(19).dealer
        ai_seat=next(seat for seat in (1,2,3) if seat!=dealer)
        # A deliberate missing-suit tile prevents a self-win, and unique
        # kinds prevent any optional kong from interrupting the discard.
        ai_hand=["p1"]+["m"+str(n) for n in range(1,10)]+[
            "s1","s2","s3"]
        game=staged_game({ai_seat:ai_hand},{ai_seat:"p"},seed=19)
        game.phase="await_draw"
        game.turn=ai_seat
        token="m341-private-fixture"
        agents={
            seat:MahjongAgent("basic",seed=19,seat=seat)
            for seat in (1,2,3)
        }
        with patch.dict(web_server._MATCH_SESSIONS,{token:game}), \
             patch.dict(web_server._MATCH_AGENTS,{token:agents}):
            result=self.post({"action":"match_continue",
                              "match_token":token})
        view=result["match"]
        steps=view["public_steps"]
        self.assertEqual([e["type"] for step in steps
                          for e in step["events"]][:1],["draw"])
        self.assertEqual(len(steps),2,
                         "one silent draw and one audible discard per request")
        self.assertEqual(steps[-1]["events"][-1]["type"],"discard")
        self.assertEqual(
            sum(e["type"] in web_server._MATCH_TURN_BEATS
                for step in steps for e in step["events"]),1)
        self.assertEqual(steps[-1]["board"]["discards"],view["discards"])
        self.assertEqual(steps[-1]["board"]["wall_count"],view["wall_count"])
        self.assertNotIn("_wall",view)
        self.assertNotIn("_hands",view)
        for step in steps:
            self.assertNotIn("hand",step["board"])
            self.assertNotIn("drawn_tile",step["board"])
            self.assertNotIn("tile",steps[0]["events"][0],
                             "AI concealed draw identity must stay private")
        self.assertTrue(game.debug_tile_counts()["total"]==108)

    def test_m342_revealed_concealed_kong_public_board_without_other_hands(self):
        from test_four_player_claims import staged_game
        from mahtrain_core.rules import TILES
        from collections import Counter
        from mahtrain_core.four_player import FourPlayerOpening
        dealer=FourPlayerOpening(19).dealer
        source=["m9"]*4
        available=Counter({t:4 for t in TILES})
        available["m9"]-=4
        for tile in TILES:
            while available[tile] and len(source)<14:
                source.append(tile)
                available[tile]-=1
        game=staged_game({dealer:source},{dealer:"p"},seed=19)
        game.declare_kong(dealer,"an_gang","m9")
        view=game.public_state()
        self.assertEqual(view["melds"][dealer][0],
            {"type":"an_gang","tile":"m9","revealed":True})
        self.assertFalse(any("hand" in e for e in view["events"]))
        self.assertFalse(any("wall" in e for e in view["events"]))
        self.assertNotIn("_hands",view)
        self.assertNotIn("_wall",view)

    def test_m346_home_navigation_and_verified_match_statistics_assets(self):
        page,_=self.get("/")
        nav,_=self.get("/navigation.js")
        chart,_=self.get("/match_stats.js")
        archive,_=self.get("/match_archives.js")
        css,_=self.get("/app.css")
        app,_=self.get("/app.js")
        for ident in ("module-home","module-navigation","module-back-home",
                      "module-current-label","solo-intro",
                      "match-stats-dashboard","match-stats-metrics",
                      "match-stats-cumulative","match-stats-outcomes"):
            self.assertEqual(page.count(('id="%s"' % ident).encode()),1)
        for kind in ("solo","quiz","match","records","history","lab"):
            self.assertEqual(page.count(
                ('id="home-open-%s"' % kind).encode()),1)
            self.assertEqual(page.count(
                ('id="module-go-%s"' % kind).encode()),1)
        for route in (b"/navigation.js",b"/match_stats.js"):
            self.assertIn(route,page)
        self.assertIn(b"window.MahTrainNavigation?.init()",app)
        self.assertIn(b"module-inactive",nav)
        self.assertIn(b"match-archives-panel",nav)
        self.assertIn(b"match-panel",nav)
        self.assertIn(b"MahTrainMatchStats?.render(response.scorecard,document)",archive)
        self.assertIn(b"makeLinePoints",chart)
        self.assertIn(b"match-stats-cumulative",chart)
        self.assertIn(b"match-stats-outcomes",chart)
        self.assertIn(b".home-module-grid",css)
        self.assertIn(b".match-stats-line",css)
        self.assertIn(b"\"history\"",nav)
        self.assertIn(b"MahTrainMatchArchives?.refresh?.()",nav)
        self.assertIn(b"MahTrainHistory?.refresh?.()",nav)
        self.assertIn(b"refreshVersion",archive)
        self.assertIn(b"home-match-state",page)
        self.assertIn(b".home-match-state",css)

    def test_m345_fluid_board_no_horizontal_pan_and_contextual_dialog(self):
        page,_=self.get("/")
        script,_=self.get("/match.js")
        css,_=self.get("/app.css")
        self.assertIn(b'id="match-decision"',page)
        self.assertNotIn(b'match-board-scroll" tabindex="0"',page)
        self.assertIn(b"overflow-x:clip;overflow-y:visible",css)
        self.assertIn(b".match-board{",css)
        self.assertIn(b"box-sizing:border-box;width:100%;min-width:0;max-width:100%",css)
        self.assertIn(b"@media(min-width:701px)",css)
        self.assertIn(b"grid-template-areas:\"rt rt rt\" \"rl wall rr\" \"rb rb rb\"",css)
        self.assertIn(b"width:clamp(36px,4.15vw,60px)",css)
        self.assertIn(b"const kongKey=",script)
        self.assertIn(b"pending_discard",script)
        self.assertIn(b"const humanCanRespond=",script)
        self.assertIn(b"if(humanCanRespond)",script)
        self.assertIn(b"state.claim_submitted?.includes(0)",script)
        self.assertIn(b"dismissedKongKey=kongKey",script)
        self.assertIn(b"kongPromptReopened=true",script)
        self.assertIn("暂不杠 · 继续出牌".encode(),script)
        self.assertIn(b"decision.hidden=true;",script)

    def test_m344_owner_ordered_river_and_center_controls_assets(self):
        page,_=self.get("/")
        script,_=self.get("/match.js")
        css,_=self.get("/app.css")
        self.assertEqual(page.count(b'id="match-decision"'),1)
        self.assertNotIn(b'id="match-large-tiles-toggle"',page)
        self.assertNotIn(b"match-large-tiles-toggle",script)
        self.assertNotIn(b"is-large-tiles",script)
        self.assertIn(b"SIDE_RIVER_LANE_SIZE=8",script)
        self.assertIn(b"match-river-lane",script)
        self.assertIn(b"data-discard-order",script)
        self.assertIn(b'const decision=$("match-decision")',script)
        self.assertIn(b"decision.append(reactions)",script)
        self.assertIn(b"decision.append(kongActions)",script)
        for token in (b".match-river--right .match-river-lane",
                      b"flex-direction:column-reverse",
                      b".match-river--left .match-river-lane",
                      b".match-river--right .match-river-tiles",
                      b"flex-direction:row-reverse",
                      b".match-decision[hidden]",
                      b".match-decision .match-reaction-button",
                      b"width:49px;height:68px",
                      b"width:34px;height:46px"):
            self.assertIn(token,css)

    def test_m340_sequential_ai_and_desktop_assets(self):
        page,_=self.get("/")
        js,_=self.get("/match.js")
        css,_=self.get("/app.css")
        voice,_=self.get("/match_voice.js")
        for attr in (b'id="match-back-color"',
                     b'id="match-self-missing-flag"',
                     b'id="match-request-status"'):
            self.assertIn(attr,page)
        for key in (b"match_continue",b"needs_continue",
                    b"data-back-color",b"match-missing-flag"):
            self.assertIn(key,js)
        for key in (b".match-river--top .match-river-cell .tile",
                    b".match-river--left .match-river-cell .tile",
                    b".match-river--right .match-river-cell .tile",
                    b".match-river-tiles::-webkit-scrollbar",
                    b"match-board[data-back-color",b".match-missing-flag"):
            self.assertIn(key,css)
        self.assertIn(b"announceFrameWait",voice)
        created=self.post({"action":"match_new","seed":42,
                           "self_draw_mode":"add_fan"})
        token=created["match_token"]
        self.assertIn("server_elapsed_ms",created)
        self.assertIsInstance(created["server_elapsed_ms"],(float,int))
        self.assertFalse(created["match"].get("needs_continue",False))
        with self.assertRaises(HTTPError):
            self.post({"action":"match_continue","match_token":token})
        hand=created["match"]["hand"]
        chosen=next([t for t in hand if t.startswith(s)][:3] for s in "msp"
                    if sum(x.startswith(s) for x in hand)>=3)
        self.post({"action":"match_exchange","match_token":token,
                   "tiles":chosen})
        turn=self.post({"action":"match_missing","match_token":token,
                        "suit":"p"})
        game=turn["match"]
        self.assertIn("needs_continue",game)
        self.assertLessEqual(len(game["public_steps"]),4)
        if game["needs_continue"]:
            progressed=self.post({"action":"match_continue",
                                  "match_token":token})
            self.assertLessEqual(
                sum(e["type"] in web_server._MATCH_TURN_BEATS
                    for step in progressed["match"]["public_steps"]
                    for e in step["events"]),1)
            self.assertNotIn("_hands",progressed["match"])
            self.assertNotIn("_wall",progressed["match"])

    def test_m338_self_draw_mode_is_validated_and_published(self):
        page, _ = self.get("/")
        client, _ = self.get("/match.js")
        self.assertEqual(page.count(b'id="match-self-draw-mode"'),1)
        self.assertIn("自摸加底".encode(),page)
        self.assertIn("自摸加番".encode(),page)
        self.assertIn(b"self_draw_mode",client)
        for mode in ("add_base","add_fan"):
            with self.subTest(mode=mode):
                result=self.post({"action":"match_new","seed":81,
                                  "room_coefficient":100,
                                  "self_draw_mode":mode})
                state=result["match"]
                self.assertEqual(state["win_ledger"]["self_draw_mode"],mode)
                self.assertEqual(state["win_ledger"]["balances"],[0]*4)
                self.assertNotIn("_wall",state)
                self.assertNotIn("_hands",state)
        # Old API consumers retain old pricing until they opt in.
        legacy=self.post({"action":"match_new","seed":81})
        self.assertEqual(legacy["match"]["win_ledger"]["self_draw_mode"],
                         "legacy")
        for invalid in ("boost","legacy",None,[],True,0,{"private":"x"}):
            with self.subTest(invalid=invalid),self.assertRaises(HTTPError):
                self.post({"action":"match_new","seed":81,
                           "self_draw_mode":invalid})

    def test_m32_rejects_invalid_room_parameters(self):
        for settings in (
            {"room_coefficient":0},
            {"room_coefficient":True},
            {"room_coefficient":-1},
            {"fan_cap":-1},
            {"fan_cap":13},
            {"fan_cap":True},
        ):
            with self.subTest(settings=settings),self.assertRaises(HTTPError):
                self.post({"action":"match_new","seed":42,**settings})

    def test_m351_web_match_prices_kong_by_room_default_but_allows_custom_base(self):
        default=self.post({"action":"match_new","seed":42,
                           "room_coefficient":300})
        m=default["match"]
        self.assertEqual(m["kong_ledger"]["base"],300)
        self.assertTrue(m["kong_included"])
        self.assertEqual(m["kong_ledger"]["balances"],[0]*4)
        self.assertEqual(m["combined_balances"],m["win_ledger"]["balances"])
        self.assertIsNone(m["exhaustive_review"])
        explicit=self.post({"action":"match_new","seed":42,
                            "room_coefficient":300,"kong_base":25})
        m2=explicit["match"]
        self.assertEqual(m2["kong_ledger"]["base"],25)
        self.assertEqual(m2["kong_ledger"]["mode"],"simulated_explicit_base")
        self.assertEqual(m2["settled_balances"],m2["combined_balances"])
        self.assertTrue(m2["kong_ledger"]["zero_sum"])
        self.assertEqual(m2["kong_ledger"]["balances"],[0]*4)
        self.assertNotIn("_wall",str(m2))
        self.assertNotIn("_hands",str(m2))
        markup,_=self.get("/")
        script,mime=self.get("/match.js")
        self.assertIn(b'id="match-enable-kong"',markup)
        self.assertIn(b'id="match-kong-base"',markup)
        self.assertIn(b"match-exhaustive-review",script)
        self.assertIn(b"match-kong-ledger",script)
        self.assertIn("自定义杠钱底分".encode(),markup)
        self.assertIn(b"match-table-scores",markup)
        self.assertIn(b"kong_base",script)
        self.assertIn("javascript",mime)
        for bad in (0,-1,True,1.4,"10",10**6+1):
            with self.subTest(bad=bad),self.assertRaises(HTTPError):
                self.post({"action":"match_new","seed":42,"kong_base":bad})
        with self.assertRaises(HTTPError):
            self.post({"action":"match_settle_review",
                       "match_token":explicit["match_token"],
                       "balances":[100,0,0,-100]})

    def test_m34_three_independent_ai_opponents_and_seed_replay(self):
        settings={"action":"match_new","seed":127,
                  "ai_levels":["challenge","basic","advanced"]}
        first=self.post(settings)
        second=self.post(settings)
        a,b=first["match"],second["match"]
        self.assertEqual(a,b,
            "seed and difficulty should deterministically initialize AI")
        self.assertEqual([x["seat"] for x in a["ai_opponents"]],[1,2,3])
        self.assertEqual([x["difficulty"] for x in a["ai_opponents"]],
                         ["challenge","basic","advanced"])
        self.assertEqual(len({x["description"] for x in a["ai_opponents"]}),3)
        self.assertNotIn("opponent_hands",a)
        self.assertNotIn("future_wall",a)
        self.assertNotIn("opponent_tian_ting",a)
        self.assertNotIn("ai_private_state",a)
        own=a["hand"]
        selected=next([x for x in own if x[0]==s][:3] for s in "msp"
                      if sum(x[0]==s for x in own)>=3)
        one=self.post({"action":"match_exchange",
                       "match_token":first["match_token"],
                       "tiles":selected})["match"]
        two=self.post({"action":"match_exchange",
                       "match_token":second["match_token"],
                       "tiles":selected})["match"]
        self.assertEqual(one,two)
        one=self.post({"action":"match_missing",
                       "match_token":first["match_token"],
                       "suit":"p"})["match"]
        two=self.post({"action":"match_missing",
                       "match_token":second["match_token"],
                       "suit":"p"})["match"]
        self.assertEqual(one,two)
        self.assertEqual(one["ai_opponents"],a["ai_opponents"])
        self.assertNotIn("seed",one)
        self.assertNotIn("_hands",str(one))
        self.assertNotIn("_wall",str(one))
        self.assertIn(one["phase"],(
            "dealer_discard","await_discard","claim_window","rob_kong_window",
            "finished","wall_exhausted"))

    def test_m34_rejects_invalid_ai_levels_and_ui_has_selector_controls(self):
        page,_=self.get("/")
        script,mime=self.get("/match.js")
        for seat in (1,2,3):
            self.assertIn(('id="match-ai-%d"'%seat).encode(),page)
        self.assertIn(b"ai_levels",script)
        self.assertIn(b"ai_opponents",script)
        self.assertIn("javascript",mime)
        for invalid in (
            [],["basic"],["basic","advanced"],
            ["basic","advanced","extreme"],
            ["basic","advanced","challenge", "basic"],
            ["basic","advanced",True],
            "basic",None,{"1":"basic"},[1,2,3],
        ):
            with self.subTest(invalid=invalid),self.assertRaises(HTTPError):
                self.post({"action":"match_new","seed":42,
                           "ai_levels":invalid})
        # Client seat spoofing remains unauthorized despite AI activation.
        created=self.post({"action":"match_new","seed":42})
        self.assertEqual(
            [x["difficulty"] for x in created["match"]["ai_opponents"]],
            ["basic","advanced","challenge"])
        with self.assertRaises(HTTPError):
            self.post({"action":"match_discard",
                       "match_token":created["match_token"],"seat":2,"tile":"m1"})

    def test_m37_async_replay_http_summary_and_public_frames(self):
        frame={
            "action":{"phase":"dealer_discard","seat":0,
                      "level":"basic","action":"discard","tile":"m1"},
            "explanation":{"code":"discard_missing","text":"只使用公开的定缺信息","scope":"public_policy_only"},
            "board":{
                "phase":"claim_window","turn":0,"dealer":0,
                "wall_count":54,"hand_counts":[13,13,13,13],
                "missing_suits":["p","s","p","m"],
                "won":[False]*4,"melds":[[],[],[],[]],
                "discards":[{"seat":0,"tile":"m1","index":1}],
                "winners":[],
            },
        }
        example={
            "seed":11,"rotation":0,"dealer":0,
            "assignment":["basic","advanced","challenge","basic"],
            "terminal_phase":"wall_exhausted","actions":1,
            "winners":[],"wall_remaining":0,
            "partial_win_balances":[0]*4,
            "trace":[{"action":"discard","legal_options":["hu"],
                      "opponent_hand":["m9"]*13}],
            "public_replay":[frame],
            "public_events":[{"type":"draw","tile":"m9"}],
        }
        result={
            "games":3,"terminal_phase_counts":{"finished":0,
                                               "wall_exhausted":3},
            "levels":{level:{
                "seat_exposures":4,"win_events":0,"deal_in_events":0,
                "discard_min_shanten_fraction":1,
                "discard_local_optimal_fraction":1,
                "mean_shanten_regret":0,
            } for level in ("basic","advanced","challenge")},
            "limitations":["non-final settlement"],
            "seed_analysis":{
                "distinct_seed_count":1,
                "interval_status":"insufficient_distinct_seeds_need_5",
                "intervals":None,
                "per_seed":[{"seed":11,"games":3,"levels":{}}],
            },
            "matches":[{**example,"rotation":n} for n in range(3)],
        }
        def cheap_tournament(start,count,*,on_match=None):
            self.assertEqual(start,11)
            self.assertEqual(count,1)
            if on_match:on_match(1,3)
            return result
        with patch.object(web_server,"tournament",side_effect=cheap_tournament):
            opened=self.post({"action":"ai_replay_start",
                              "seed_start":11,"seeds":1})
            token=opened["replay_token"]
            self.assertGreater(len(token),20)
            self.assertEqual(opened["replay"]["total_games"],3)
            latest=None
            for _ in range(40):
                latest=self.post({"action":"ai_replay_status",
                                  "replay_token":token})["replay"]
                if latest["status"]=="done":
                    break
                sleep(.01)
            self.assertEqual(latest["status"],"done")
        self.assertEqual(latest["overview"]["games"],3)
        self.assertEqual(len(latest["overview"]["matches"]),3)
        self.assertEqual(latest["overview"]["seed_analysis"]["distinct_seed_count"],1)
        self.assertNotIn("trace",str(latest))
        response=self.post({"action":"ai_replay_match",
                            "replay_token":token,"match_index":0})
        public=response["match"]
        self.assertEqual(public["privacy"],
                         "public_board_and_public_action_only")
        self.assertEqual(public["steps"],[frame])
        self.assertNotIn("trace",public)
        self.assertNotIn("public_events",public)
        self.assertNotIn("legal_options",str(public))
        self.assertNotIn("opponent_hand",str(public))
        self.assertNotIn("future_wall",str(public))
        self.assertNotIn('"m9"',str(public))
        for bad in (-1,3,"0",True,None):
            with self.subTest(index=bad),self.assertRaises(HTTPError):
                self.post({"action":"ai_replay_match",
                           "replay_token":token,"match_index":bad})
        with self.assertRaises(HTTPError):
            self.post({"action":"ai_replay_match",
                       "replay_token":"forged","match_index":0})
        html,_=self.get("/")
        js,mime=self.get("/ai_replay.js")
        css,_=self.get("/app.css")
        self.assertIn(b'id="ai-replay-panel"',html)
        self.assertIn(b'src="/ai_replay.js"',html)
        self.assertIn(b"ai_replay_status",js)
        self.assertIn(b"ai_replay_match",js)
        self.assertIn(b".ai-replay-board",css)
        self.assertIn(b'id="ai-replay-clusters"',html)
        self.assertIn(b'id="ai-replay-explanation-text"',html)
        self.assertIn(b"value=\"5\"",html)
        self.assertIn(b"paired_challenge_differences",js)
        self.assertIn(b"ai-replay-cluster-download",js)
        self.assertIn("javascript",mime)

    def test_m37_replay_parameters_and_capacity(self):
        for bad in (
            {"seed_start":-1},{"seed_start":True},
            {"seed_start":2**32},{"seed_start":"11"},
            {"seeds":0},{"seeds":6},{"seeds":True},
            {"seed_start":2**32-1,"seeds":2},
        ):
            with self.subTest(payload=bad),self.assertRaises(HTTPError):
                self.post({"action":"ai_replay_start",**bad})
        with self.assertRaises(HTTPError):
            self.post({"action":"ai_replay_status",
                       "replay_token":"unknown"})

    def test_m39_baseline_dashboard_token_isolation_and_safe_aggregate(self):
        lv={
            level:{
                "exposures":4,"wins":0,"deal_ins":0,"discards":10,
                "minimum_shanten":10,"local_optimal":9,
                "win_event_fraction":0,"min_shanten_fraction":1,
                "local_optimal_fraction":.9,
            } for level in ("baseline","basic","advanced","challenge")
        }
        summary={
            "protocol":"independent_shape_baseline_four_seat_rotation_v1",
            "independent_shuffle_seeds":1,"games":4,
            "opponents":["baseline","basic","advanced","challenge"],
            "terminal_phase_counts":{"finished":0,"wall_exhausted":4},
            "levels":lv,
            "paired_differences_vs_baseline":{
                x:{"win_event_fraction":0,
                   "min_shanten_fraction":0,"local_optimal_fraction":0}
                for x in ("basic","advanced","challenge")},
            "interval_status":"insufficient_independent_seeds_need_5",
            "intervals":None,
            "per_seed":[{"seed":11,"rotations":4,"levels":lv}],
            "decision_score_diagnostics":{
                "protocol":"decision_quality_vs_rule_a_official_points_v1",
                "valid_seeds":0,"excluded_seed_count":1,
                "complete_games":0,
                "levels":{level:{
                    "seat_exposures":0,"discards":0,
                    "min_shanten_fraction":None,
                    "local_optimal_fraction":None,
                    "mean_effective_copies":None,
                    "deal_in_events_per_100_discards":None,
                } for level in ("baseline","basic","advanced","challenge")},
                "direction_disagreements_vs_baseline":{},
            },
            "official_score_analysis":{
                "protocol":"paired_initial_shuffle_4_rotation_official_a_v1",
                "room_coefficient":100,"fan_cap":3,
                "requested_seeds":1,"valid_seeds":0,
                "excluded_seed_count":1,"excluded_seed_ids":[11],
                "complete_games":0,"games_per_seed":4,"kong_included":False,
                "levels":{level:{
                    "seat_exposures":0,"official_total":0,
                    "official_mean_per_exposure":None,
                } for level in ("baseline","basic","advanced","challenge")},
                "per_seed":[],"intervals":None,
                "paired_differences_vs_baseline":{
                    level:None for level in ("basic","advanced","challenge")},
            },
            "limitations":["not full settlement"],
            "matches":[{
                "assignment":["baseline","basic","advanced","challenge"],
                "trace":[{"secret":"opponent_hand"}],
                "public_replay":[{"future_wall":"m9"}],
            }],
        }
        def cheap(seed_start,seeds,*,on_match=None):
            self.assertEqual((seed_start,seeds),(11,1))
            if on_match:on_match(4,4)
            return summary
        with patch.object(web_server,"independent_benchmark",side_effect=cheap):
            opened=self.post({"action":"ai_baseline_start","seed_start":11,
                              "seeds":1})
            token=opened["baseline_token"]
            self.assertGreater(len(token),20)
            self.assertEqual(opened["baseline"]["total_games"],4)
            outcome=None
            for _ in range(40):
                outcome=self.post({"action":"ai_baseline_status",
                                   "baseline_token":token})["baseline"]
                if outcome["status"]=="done":break
                sleep(.01)
            self.assertEqual(outcome["status"],"done")
        overview=outcome["overview"]
        self.assertEqual(overview["games"],4)
        self.assertEqual(overview["opponents"][0],"baseline")
        self.assertEqual(overview["intervals"],None)
        official=overview["official_score_analysis"]
        self.assertEqual(official["requested_seeds"],1)
        self.assertEqual(official["valid_seeds"],0)
        self.assertEqual(official["excluded_seed_ids"],[11])
        self.assertEqual(official["levels"]["baseline"]["official_total"],0)
        diagnostic=overview["decision_score_diagnostics"]
        self.assertEqual(diagnostic["valid_seeds"],0)
        self.assertIsNone(diagnostic["levels"]["baseline"]["min_shanten_fraction"])
        self.assertNotIn("trace",str(diagnostic))
        for private in ("secret","opponent_hand","future_wall","trace",
                        "public_replay","matches"):
            self.assertNotIn(private,str(overview))
        with self.assertRaises(HTTPError):
            self.post({"action":"ai_replay_status","replay_token":token})
        with self.assertRaises(HTTPError):
            self.post({"action":"ai_replay_match","replay_token":token,
                       "match_index":0})
        with self.assertRaises(HTTPError):
            self.post({"action":"ai_baseline_status","baseline_token":"bad"})
        page,_=self.get("/")
        js,mime=self.get("/ai_baseline.js")
        css,_=self.get("/app.css")
        self.assertIn(b'id="ai-baseline-panel"',page)
        self.assertIn(b'src="/ai_baseline.js"',page)
        self.assertIn(b"ai_baseline_start",js)
        self.assertIn(b"paired_differences_vs_baseline",js)
        self.assertIn(b".ai-baseline-summary",css)
        for ident in ("ai-baseline-official","ai-baseline-official-export",
                      "ai-baseline-official-caveat",
                      "ai-baseline-official-levels",
                      "ai-baseline-official-differences"):
            self.assertEqual(page.count(('id="%s"' % ident).encode()),1)
        self.assertIn(b"renderOfficialScores",js)
        self.assertIn(b"renderDecisionScoreDiagnostics",js)
        for ident in ("ai-baseline-decision-scores",
                      "ai-baseline-decision-caveat",
                      "ai-baseline-decision-table",
                      "ai-baseline-decision-disagreements",
                      "ai-baseline-decision-export"):
            self.assertEqual(page.count(('id="%s"' % ident).encode()),1)
        self.assertIn(b".ai-decision-row",css)
        self.assertIn(b"exportOfficialScores",js)
        self.assertIn("javascript",mime)

    def test_m39_rejects_invalid_baseline_requests_without_starting(self):
        for bad in (
            {"seeds":0},{"seeds":3},{"seeds":True},{"seeds":"1"},
            {"seed_start":-1},{"seed_start":2**32},
            {"seed_start":True},{"seed_start":2**32-1,"seeds":2},
        ):
            with self.subTest(payload=bad),self.assertRaises(HTTPError):
                self.post({"action":"ai_baseline_start",**bad})
        with self.assertRaises(HTTPError):
            self.post({"action":"ai_baseline_status"})

    def test_fake_token_cannot_grab_other_session(self):
        with self.assertRaises(HTTPError) as err:
            self.post({"action": "draw", "token": "fabricated"})
        self.assertEqual(err.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
