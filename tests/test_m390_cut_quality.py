"""M3.90 verified player-choice metrics: original scoring and safe archives."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]
from mahtrain_core.four_player import FourPlayerOpening
from mahtrain_core.classic_hint import classic_hand_hint
from mahtrain_core.match_archive import MatchArchive, sanitize_private_review
from test_four_player_claims import staged_game
import web_server


class CutQualityArchiveTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.store=MatchArchive(Path(self.directory.name)/"match.sqlite3")
    def tearDown(self):
        self.directory.cleanup()

    @staticmethod
    def fixture():
        game=FourPlayerOpening(42)
        hand=[list(h) for h in game._hands]
        choice=hand[0][0]
        distinct=list(dict.fromkeys(hand[0]))
        picks=(distinct+["m1","m2","m3"])[:3]
        # A stored alternate must be a real tile from the prior hand.
        picks=distinct[:3]
        if len(picks)<3:
            raise AssertionError("seed 42 unexpectedly has fewer than three tile types")
        top=[{"tile":t,"shanten":1,"effective_copies":12-i*2,
              "fan_weighted":None,"reference_best":i==0}
             for i,t in enumerate(picks)]
        return game,hand,choice,top

    def test_off_top_three_actual_metrics_stored_only_in_terminal(self):
        game,hands,choice,top=self.fixture()
        summary={
          "opening":hands,
          "steps":[{"hands_before":hands,"hands_after":hands,
                     "events":[{"type":"discard","seat":0,"tile":choice}],
                     "cut_review":{
                       "seat":0,"discard":choice,"rank":4,"optimal":False,
                       "top3":top,
                       "played_candidate":{
                         "tile":choice,"shanten":2,"effective_copies":7,
                         "fan_weighted":None,"reference_best":False}
                     }}],
        }
        data=game.public_state()
        final={**data,"phase":"finished"}
        key=self.store.save_completed(
            final,[],data,["basic"]*3,private_review=summary)
        report=self.store.detail(key)["report"]
        saved=report["terminal_review"]["steps"][0]["cut_review"]
        self.assertEqual(saved["played_candidate"]["effective_copies"],7)
        self.assertEqual(saved["played_candidate"]["shanten"],2)
        self.assertEqual(saved["rank"],4)
        self.assertNotIn("terminal_review",game.private_view(0))
        self.assertNotIn("terminal_review",data)
        self.assertNotIn("_wall",report)
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_before_m390_archive_with_no_chosen_metrics_is_valid(self):
        game,hands,choice,top=self.fixture()
        data={"opening":hands,"steps":[{
          "hands_before":hands,"hands_after":hands,"events":[],
          "cut_review":{"seat":0,"discard":choice,"rank":4,
                        "optimal":False,"top3":top}
        }]}
        res=sanitize_private_review(data)
        self.assertNotIn("played_candidate",res["steps"][0]["cut_review"])

    def test_reject_fake_or_negative_selected_metrics_without_leaking(self):
        game,hands,choice,top=self.fixture()
        base={"opening":hands,"steps":[{
            "hands_before":hands,"hands_after":hands,"events":[],
            "cut_review":{"seat":0,"discard":choice,"rank":4,
                          "optimal":False,"top3":top}
        }]}
        for wrong in (
            {"tile":"INVALID","shanten":1,"effective_copies":7,
             "fan_weighted":None,"reference_best":False},
            {"tile":choice,"shanten":1,"effective_copies":-3,
             "fan_weighted":None,"reference_best":False},
            {"tile":choice,"shanten":True,"effective_copies":3,
             "fan_weighted":None,"reference_best":False},
            {"tile":choice,"shanten":0,"effective_copies":3,
             "fan_weighted":"many","reference_best":False},
        ):
            sample={"opening":hands,"steps":[{
                **base["steps"][0],
                "cut_review":{
                    **base["steps"][0]["cut_review"],
                    "played_candidate":wrong},
            }]}
            with self.subTest(wrong=wrong),self.assertRaises(ValueError):
                sanitize_private_review(sample)

    def test_actual_record_uses_only_contemporaneous_public_adviser(self):
        seed=next(i for i in range(60)
                  if FourPlayerOpening(i).dealer==0)
        game=staged_game({},seed=seed)
        game._terminal_review_trace=[]
        before_view=game.private_view(0)
        advice=classic_hand_hint(before_view)
        candidates=advice.get("candidates",[])
        self.assertGreaterEqual(len(candidates),1)
        chosen=candidates[-1]
        expected=chosen["effective_tile_count_upper_bound"]
        steps=[]
        web_server._match_record(
            game,steps,lambda:game.discard(0,chosen["discard"]))
        self.assertEqual(len(game._terminal_review_trace),1)
        trace=game._terminal_review_trace[0]
        self.assertIn("cut_review",trace)
        saved=trace["cut_review"]["played_candidate"]
        self.assertEqual(saved["tile"],chosen["discard"])
        self.assertEqual(saved["effective_copies"],expected)
        self.assertEqual(saved["shanten"],chosen["shanten"])
        self.assertEqual(saved["fan_weighted"],
                         chosen["fan_weighted_unknown_copies"])
        self.assertEqual(game.debug_tile_counts()["total"],108)
        self.assertNotIn("terminal_review",game.private_view(0))
        self.assertNotIn("terminal_review",game.public_state())


if __name__=="__main__":
    unittest.main()
