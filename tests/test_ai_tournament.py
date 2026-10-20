"""M3.6 full-turn AI self-play regression and paired-seat fairness."""
from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.ai_tournament import (seat_assignment, simulate_match, tournament, explain_public_action)
from mahtrain_core.rules import TILE_INDEX


class FourAgentTrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=tournament(seed_start=11,seeds=1)

    def test_all_rotations_balance_each_level_in_every_seat(self):
        result=self.result
        self.assertEqual(result["protocol"],"seat_rotated_closed_loop_v1")
        self.assertEqual(result["games"],3)
        self.assertEqual(
            {seat:sorted(seat_assignment(r)[seat] for r in range(3))
             for seat in range(4)},
            {seat:["advanced","basic","challenge"] for seat in range(4)},
        )
        for level in ("basic","advanced","challenge"):
            self.assertEqual(result["levels"][level]["seat_exposures"],4)

    def test_closed_loop_finishes_legally_without_demo_claim_skips(self):
        for match in self.result["matches"]:
            self.assertIn(match["terminal_phase"],("finished","wall_exhausted"))
            self.assertEqual(match["physical_count"],108)
            self.assertGreater(match["actions"],8)
            self.assertLess(match["actions"],800)
            self.assertEqual(sum(match["partial_win_balances"]),0)
            self.assertTrue(match["exhaustive_preview_not_posted"]
                            if match["terminal_phase"]=="wall_exhausted"
                            else not match["exhaustive_preview_not_posted"])
            self.assertFalse(any(e["type"]=="demo_no_claims"
                                 for e in match["public_events"]))
            discarded=sum(e["action"]=="discard" for e in match["trace"])
            self.assertGreater(discarded,0)
            for record in match["trace"]:
                self.assertIn("phase",record)
                self.assertNotIn("opponent_hands",record)
                self.assertNotIn("wall",record)
                self.assertNotIn("future_wall",record)
                if record["action"]=="an_gang":
                    self.assertIsNone(record["tile"])
                if record["action"]=="discard":
                    self.assertGreaterEqual(record["shanten_regret"],0)
            for event in match["public_events"]:
                if event["type"]=="an_gang":
                    # The CURRENT physical engine officially flips one
                    # identifying tile face from a declared concealed kong;
                    # other tiles in all concealed hands remain private.
                    self.assertIs(event.get("revealed"),True)
                    self.assertIn(event["tile"],TILE_INDEX)
            if match["terminal_phase"]=="finished":
                self.assertEqual(len(match["winners"]),3)
            else:
                self.assertEqual(match["wall_remaining"],0)

    def test_m330_official_balances_and_server_summary_are_rule_a_verified(self):
        scores=self.result["official_score_analysis"]
        self.assertEqual(scores["requested_seeds"],1)
        self.assertEqual(scores["room_coefficient"],100)
        self.assertEqual(scores["fan_cap"],3)
        self.assertTrue(scores["zero_sum"])
        self.assertEqual(scores["kong_included"],False)
        self.assertEqual(scores["valid_seeds"]+
                         scores["excluded_seed_count"],1)
        self.assertEqual(scores["complete_games"],scores["valid_seeds"]*3)
        for match in self.result["matches"]:
            self.assertEqual(sum(match["official_settled_balances"]),0)
            self.assertEqual(match["scoring_rules"],{
                "room_coefficient":100,"fan_cap":3,"kong_base":None})
            if match["terminal_phase"]=="finished":
                self.assertFalse(match["official_exhaustive_posted"])
                self.assertEqual(match["partial_win_balances"],
                                 match["official_settled_balances"])
            if match["terminal_phase"]=="wall_exhausted":
                self.assertTrue(match["official_exhaustive_posted"] or
                                match["partial_win_balances"]==
                                match["official_settled_balances"])
        from web_server import _replay_summary
        response=_replay_summary({
            "mode":"replay","status":"done","completed_games":3,
            "seed_start":11,"seeds":1,"result":self.result,
        })
        self.assertEqual(
            response["overview"]["official_score_analysis"],scores)
        self.assertNotIn("trace",str(scores))
        self.assertNotIn("private_hand",str(scores))
        self.assertNotIn("future_wall",str(scores))

    def test_level_summary_matches_explicit_per_match_counts(self):
        for level,stat in self.result["levels"].items():
            self.assertEqual(stat["win_events"],sum(
                x["level"]==level for m in self.result["matches"]
                for x in m["winners"]))
            self.assertEqual(stat["discards"],sum(
                x.get("level")==level and x["action"]=="discard"
                for m in self.result["matches"] for x in m["trace"]))
            if stat["discards"]:
                self.assertTrue(0<=stat["discard_min_shanten_fraction"]<=1)
                self.assertTrue(0<=stat["discard_local_optimal_fraction"]<=1)
                self.assertGreaterEqual(stat["mean_shanten_regret"],0)

    def test_reproducible_actions_without_timing_leak(self):
        first=self.result["matches"][0]
        second=simulate_match(11,rotation=0)
        self.assertEqual(first["assignment"],second["assignment"])
        self.assertEqual(first["terminal_phase"],second["terminal_phase"])
        self.assertEqual(first["winners"],second["winners"])
        self.assertEqual(first["public_events"],second["public_events"])
        self.assertEqual(first["trace"],second["trace"])
        self.assertEqual(first["public_replay"],second["public_replay"])
        self.assertEqual(first["partial_win_balances"],
                         second["partial_win_balances"])

    def test_public_replay_frames_are_step_aligned_and_never_leak_hands(self):
        for match in self.result["matches"]:
            self.assertEqual(len(match["public_replay"]),len(match["trace"]))
            self.assertEqual(match["public_replay"][-1]["board"]["phase"],
                             match["terminal_phase"])
            for index,frame in enumerate(match["public_replay"]):
                original=match["trace"][index]
                if original["phase"] in ("claim_window","rob_kong_window"):
                    if frame["board"]["phase"]==original["phase"]:
                        self.assertEqual(frame["action"]["action"],
                                         "response_submitted")
                        self.assertNotIn("resolution",frame["action"])
                    else:
                        self.assertEqual(frame["action"]["action"],
                                         "response_resolved")
                        self.assertIn("resolution",frame["action"])
                    self.assertNotIn(original["action"],
                                     ("response_submitted","response_resolved"))
                else:
                    self.assertEqual(frame["action"]["action"],
                                     original["action"])
                self.assertNotIn("shanten_after",frame["action"])
                self.assertNotIn("legal_options",frame["action"])
                self.assertNotIn("effective_copies",frame["action"])
                self.assertEqual(
                    set(frame["board"]),
                    {"phase","turn","dealer","wall_count","hand_counts",
                     "missing_suits","won","melds","discards","winners"})
                self.assertEqual(len(frame["board"]["hand_counts"]),4)
                for melds in frame["board"]["melds"]:
                    for meld in melds:
                        if meld["type"]=="an_gang":
                            self.assertIs(meld.get("revealed"),True)
                            self.assertIn(meld["tile"],TILE_INDEX)
                if frame["action"]["action"]=="an_gang":
                    self.assertNotIn("tile",frame["action"])
                if frame["action"]["action"]=="draw":
                    self.assertNotIn("tile",frame["action"])
                if frame["action"]["action"]=="declare_missing":
                    self.assertNotIn("suit",frame["action"])
                    if index < 7:
                        self.assertIsNone(frame["board"]["missing_suits"])
                    else:
                        self.assertTrue(all(
                            suit in ("m","s","p") for suit in
                            frame["board"]["missing_suits"]
                        ))
            self.assertIsNone(
                match["public_replay"][0]["board"]["missing_suits"])

    def test_m38_public_explanations_do_not_depend_on_hidden_tiles(self):
        sample=self.result["matches"][0]["public_replay"]
        self.assertTrue(any(frame["action"]["action"]=="discard" for frame in sample))
        for frame in sample:
            rationale=frame["explanation"]
            self.assertEqual(set(rationale),{"code","text","scope"})
            self.assertEqual(rationale["scope"],"public_policy_only")
            self.assertIsInstance(rationale["text"],str)
            self.assertGreater(len(rationale["text"]),10)
            for secret in ("opponent_hands","future_wall","legal_options",
                           "shanten_after","effective_copies"):
                self.assertNotIn(secret,rationale)
            if frame["action"]["action"]=="response_submitted":
                self.assertEqual(rationale["code"],"sealed_response")
            if frame["action"]["action"]=="declare_missing":
                self.assertIn(rationale["code"],
                              ("sealed_missing","missing_revealed"))
        board={"missing_suits":["p","s","p","m"],
               "opponent_hands":[["m9"]*13]*3}
        action={"action":"discard","seat":0,"level":"challenge","tile":"p8"}
        self.assertEqual(
            explain_public_action(action,board),
            explain_public_action(
                {**action,"private_ukeire":999},
                {**board,"opponent_hands":[["p8"]*13]*3,
                 "future_wall":["p8"]*70},
            ),
        )
        self.assertEqual(
            explain_public_action(action,board)["code"],"discard_missing")
        self.assertEqual(
            explain_public_action({"action":"response_submitted","seat":2},board)[
                "code"],"sealed_response")

    def test_json_and_sanitized_summary(self):
        output=json.dumps(self.result,ensure_ascii=False)
        self.assertIn("unpriced",output)
        # Reuse the already validated games instead of re-playing a second
        # tournament. Hardware clock time is intentionally not deterministic.
        with patch("mahtrain_core.ai_tournament.simulate_match",
                   side_effect=lambda seed, rotation: self.result["matches"][rotation]):
            compact=tournament(seed_start=11,seeds=1,include_traces=False)
        self.assertEqual(compact["levels"],self.result["levels"])
        self.assertNotIn("trace",compact["matches"][0])
        self.assertNotIn("public_events",compact["matches"][0])
        self.assertNotIn("public_replay",compact["matches"][0])

    def test_bad_seed_and_rotation_do_not_run(self):
        for value in (-1,True,2**32,"2"):
            with self.subTest(value=value),self.assertRaises(ValueError):
                simulate_match(value)
        for rotation in (-1,3,True,"1"):
            with self.subTest(rotation=rotation),self.assertRaises(ValueError):
                seat_assignment(rotation)
        for value in (0,-1,101,True,"2"):
            with self.subTest(seeds=value),self.assertRaises(ValueError):
                tournament(seeds=value)
        with self.assertRaises(ValueError):
            simulate_match(11,max_actions=5)


if __name__=="__main__":
    unittest.main()
