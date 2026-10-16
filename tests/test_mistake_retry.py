"""Regression for isolated replay of incorrectly graded Mahjong decisions."""
from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core import SoloTrainingSession, analyze_discards, sort_hand  # noqa: E402
from mahtrain_core.rules import TILES  # noqa: E402


def produce_mistake(seed=17):
    game=SoloTrainingSession(seed,missing_suit="p",rounds=1)
    state=game.draw_next()
    while state["phase"] in ("offer_win","offer_kong"):
        state=(game.decide_win(False) if state["phase"]=="offer_win"
               else game.decide_kong(None))
    analysis=analyze_discards(state["hand"],missing_suit="p")
    if analysis["status"]=="already_winning":
        action=state["choices"][0]
    else:
        action=next(
            (tile for tile in state["choices"]
             if tile not in analysis["best_discards"]),None)
    if action is None:
        raise AssertionError("seed unexpectedly had only optimal actions")
    feedback=game.submit(action)
    assert not feedback["correct"]
    return game,feedback


class MistakeRetryTests(unittest.TestCase):
    def test_refuses_to_replay_before_training_ends(self):
        game=SoloTrainingSession(17,missing_suit="p")
        with self.assertRaises(ValueError):
            game.retry_list()
        with self.assertRaises(ValueError):
            game.retry_question(1)
        with self.assertRaises(ValueError):
            game.retry_submit(1,"m1")

    def test_round_question_hides_original_answer_and_grades_two_attempts(self):
        game,feedback=produce_mistake()
        self.assertTrue(game.finished)
        before_report=json.dumps(game.report(),sort_keys=True)
        before_state=json.dumps(game.public_state(),sort_keys=True)
        rows=game.retry_list()
        self.assertEqual(rows["mistake_count"],1)
        self.assertEqual(rows["attempted_count"],0)
        q=game.retry_question(1)
        self.assertEqual(q["mode"],"mistake_retry")
        self.assertEqual(q["round"],1)
        self.assertEqual(q["concealed"],sort_hand(q["concealed"]))
        self.assertEqual(len(q["concealed"]),14)
        self.assertEqual(q["drawn_tile"],feedback["drawn_tile"])
        for field in ("best_actions","answer","correct","original_choice",
                      "analysis","seed","wall","next_wall_tile"):
            self.assertNotIn(field,q)
        self.assertEqual(q["attempt_number"],1)
        with self.assertRaises(ValueError):
            game.retry_submit(1,"not-a-tile")
        self.assertEqual(game.retry_list()["attempted_count"],0)
        first=game.retry_submit(1,feedback["choice"])
        self.assertFalse(first["correct"])
        self.assertEqual(first["original_choice"],feedback["choice"])
        self.assertEqual(first["retry_choice"],feedback["choice"])
        self.assertEqual(first["original_candidate"]["shanten"],
                         feedback["selected_candidate"]["shanten"])
        best=feedback["best_actions"][0]
        second=game.retry_submit(1,best)
        self.assertTrue(second["correct"])
        self.assertTrue(second["improved"])
        self.assertEqual(second["retry_choice"],best)
        self.assertEqual(second["attempt_number"],2)
        status=game.retry_list()
        self.assertEqual(status["attempted_count"],1)
        self.assertEqual(status["corrected_count"],1)
        self.assertEqual(status["questions"][0]["latest_correct"],True)
        self.assertEqual(game.retry_question(1)["attempt_number"],3)
        # Repeat answers do not change training deck, graded history, or grade.
        self.assertEqual(json.dumps(game.report(),sort_keys=True),before_report)
        self.assertEqual(json.dumps(game.public_state(),sort_keys=True),before_state)

    def test_cannot_replay_valid_rounds_or_fake_numbers(self):
        game,_=produce_mistake()
        for x in (0,-1,2,True,1.0,"1",None):
            with self.subTest(x=x),self.assertRaises(ValueError):
                game.retry_question(x)
        game._history[0]["correct"]=True
        self.assertEqual(game.retry_list()["mistake_count"],0)
        with self.assertRaises(ValueError):
            game.retry_question(1)

    def test_exposed_kong_is_preserved_in_frozen_question(self):
        # Fixed 108-tile wall, concealed kong and replacement give completed hand.
        game=SoloTrainingSession(100,missing_suit="s",rounds=1)
        cards=["m1"]*3+["m4"]*3+["p1"]*3+["p4"]*3+["m9"]
        deck=Counter({t:4 for t in TILES})
        for t in cards+["m1","m9"]:
            deck[t]-=1
            self.assertGreaterEqual(deck[t],0)
        remaining=[t for t in TILES for _ in range(deck[t])]
        game._hand=cards
        game._wall=["m1",*remaining,"m9"]
        game._assert_deck()
        state=game.draw_next()
        self.assertEqual(state["phase"],"offer_kong")
        state=game.decide_kong("m1")
        self.assertEqual(state["phase"],"offer_win")
        state=game.decide_win(False)
        self.assertEqual(state["phase"],"await_discard")
        action=state["choices"][0]
        feedback=game.submit(action)
        self.assertFalse(feedback["correct"])
        self.assertEqual(feedback["best_actions"],["win"])
        q=game.retry_question(1)
        self.assertEqual(len(q["concealed"]),11)
        self.assertNotIn("m1",q["choices"])
        self.assertIn("win",q["choices"])
        self.assertEqual(q["exposed_kongs"][0]["tiles"],["m1"]*4)
        initial=json.dumps(game.public_state(),sort_keys=True)
        good=game.retry_submit(1,"win")
        self.assertTrue(good["correct"])
        self.assertEqual(good["retry_candidate"],None)
        self.assertEqual(game.public_state()["kong_count"],1)
        self.assertEqual(json.dumps(game.public_state(),sort_keys=True),initial)

    def test_failed_retry_does_not_consume_wall_or_generate_future_draws(self):
        game,_=produce_mistake()
        state=game.public_state()
        total=game.report()["remaining_wall_count"]
        self.assertGreater(total,0)
        self.assertNotIn("future_wall",game.retry_question(1))
        for _ in range(3):
            game.retry_submit(1,game._history[0]["choice"])
        self.assertEqual(game.report()["remaining_wall_count"],total)
        self.assertEqual(game.public_state(),state)


if __name__=="__main__":
    unittest.main()
