"""M3.54 physical proposal sampler, privacy, bounded compute and EV fusion."""
from __future__ import annotations

import copy
import random
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core.ai_hidden_worlds import (
    _private_world_inputs, _deal, sample_discard_losses,
)
from mahtrain_core.ai import challenge_discard_scores
from mahtrain_core.four_player import FourPlayerOpening
from mahtrain_core.rules import TILES, score_win


def live_view():
    game=FourPlayerOpening(41)
    game.missing_suits=["p"]*4
    game.phase="dealer_discard"
    game.turn=game.dealer
    return game.private_view(game.dealer)


class HiddenWorldsTests(unittest.TestCase):
    def test_shared_worlds_draw_exact_physical_copies_without_replacement(self):
        view=live_view()
        inputs=_private_world_inputs(view)
        self.assertIsNotNone(inputs)
        pool, seats=inputs
        self.assertEqual(len(seats),3)
        self.assertEqual(sum(length for _, length, _, _ in seats),39)
        known=Counter(TILES)
        known.update(view["hand"])
        for tile in view["hand"]:
            self.assertLessEqual(view["hand"].count(tile),4)
        for i in range(12):
            sampled=_deal(pool,seats,random.Random(i),late=(i%2==0))
            self.assertEqual(sum(len(h) for _,h,_,_ in sampled),39)
            self.assertEqual(len({seat for seat,_,_,_ in sampled}),3)
            self.assertFalse(Counter(t for _,h,_,_ in sampled for t in h)-Counter(pool))
            self.assertLessEqual(max(Counter(
                [*view["hand"],*(tile for _,h,_,_ in sampled for tile in h)]
            ).values()),4)
        result=sample_discard_losses(["m1","s5"],view,worlds=5)
        self.assertTrue(result["available"])
        self.assertEqual(result["worlds"],5)
        self.assertEqual(set(result["by_tile"]),{"m1","s5"})
        self.assertEqual(result["model"],"proposal_mc_v1")

    def test_same_observation_same_sample_and_hidden_injection_ignored(self):
        view=live_view()
        baseline=sample_discard_losses(["m1","s5"],view,worlds=9)
        copied=copy.deepcopy(view)
        copied["opponent_hands"]=[["m1"]*13]*3
        copied["future_wall"]=["s5"]*55
        copied["private_draw"]="s5"
        copied["match_seed"]=99999
        self.assertEqual(baseline,sample_discard_losses(["s5","m1"],copied,worlds=9))
        self.assertEqual(baseline,sample_discard_losses(["m1","s5"],view,worlds=9))

    def test_budget_validation_and_absent_observation_fallback(self):
        view=live_view()
        for bad in (-1,0,65,True,1.5):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                sample_discard_losses(["m1"],view,worlds=bad)
        with self.assertRaises(ValueError):
            sample_discard_losses(["flower"],view)
        bad=copy.deepcopy(view)
        bad.pop("hand_counts")
        no_sample=sample_discard_losses(["m1"],bad)
        self.assertFalse(no_sample["available"])
        self.assertEqual(no_sample["worlds"],0)
        bad=copy.deepcopy(view)
        opponent=next(seat for seat in range(4) if seat != bad["seat"])
        bad["melds"][opponent]=[{"type":"an_gang","tile":None}]
        # A redacted kong consumes four unknown matching copies; without
        # knowing the actual kind, declining ALL sampling is safer than
        # misallocating those four physical cards to another player.
        result=sample_discard_losses(["m1"],bad,worlds=3)
        self.assertFalse(result["available"])
        self.assertEqual(result["worlds"],0)

    def test_valid_actual_ron_pattern_uses_rules_multiplier_not_fake_odds(self):
        view={
            "seat":0,"hand":["m1","m1","m2","m2","m3","m3","m4","m4",
                             "s1","s1","s2","s2","s3","p8"],
            "own_melds":[],"hand_counts":[14,1,13,13],
            "missing_suits":["s","m","p","s"],"won":[False]*4,
            "melds":[[],[{"type":"peng","tile":t} for t in
                         ("p1","p2","p3","p4")],[],[]],
            "discards":[],"wall_count":8,"win_ledger":{"fan_cap":3},
        }
        self.assertIsNotNone(_private_world_inputs(view))
        pungs=view["melds"][1]
        with patch("mahtrain_core.ai_hidden_worlds._deal",
                   return_value=[(1,["p8"],"m",pungs)]):
            result=sample_discard_losses(["p8"],view,worlds=4)
        self.assertEqual(result["by_tile"]["p8"]["hits"],4)
        expected=score_win(["p8","p8"],pungs,"m",cap=3)
        self.assertTrue(expected["legal"])
        self.assertEqual(result["by_tile"]["p8"]["mean_loss_multiplier"],
                         expected["multiplier"])
        self.assertNotIn("hand",str(result))
        self.assertNotIn("opponent",str(result))

    def test_bounded_mc_can_change_close_cut_but_never_shanten_priority(self):
        view={
            "seat":0,"phase":"dealer_discard",
            "hand":["m1","m2","m3","m4","m5","m6","m7","m8","m9",
                    "s1","s2","s3","s4","s5"],
            "own_melds":[],"missing_suits":["p","m","m","s"],
            # Seat 1 has two published, non-missing-suit pungs.
            # This is the case in which bounded sampling is enabled.
            "melds":[[],[{"type":"peng","tile":"p1"},
                         {"type":"peng","tile":"p2"}],[],[]],
            "won":[False]*4,"discards":[],"wall_count":8,
        }
        info={"shanten":0,"effective_tile_count":6,
              "effective_types":["p1"],
              "effective_details":[{"tile":"p1","remaining":6}]}
        probe={"available":True,"worlds":24,"model":"proposal_mc_v1",
               "by_tile":{"m4":{"hits":3,"mean_loss_multiplier":8.0},
                          "s4":{"hits":0,"mean_loss_multiplier":0.0}}}
        with patch("mahtrain_core.ai.effective_draws",return_value=info), \
             patch("mahtrain_core.ai.score_win",return_value={"multiplier":2}), \
             patch("mahtrain_core.ai.sample_discard_losses",return_value=probe):
            protected=challenge_discard_scores(view,cuts=["m4","s4"])
            bare=challenge_discard_scores(view,cuts=["m4","s4"],
                                           use_pressure=False)
        self.assertEqual(protected[0]["discard"],"s4")
        self.assertEqual(protected[1]["sampled_ron_hits"],3)
        self.assertEqual(protected[0]["sampled_worlds"],24)
        self.assertEqual(bare[0]["score"],bare[1]["score"])
        self.assertTrue(all(x["shanten"]==0 for x in protected))

    def test_no_opaque_mc_work_without_two_exposed_opponent_melds(self):
        view={
            "seat":0,"phase":"dealer_discard",
            "hand":["m1","m2","m3","m4","m5","m6","m7","m8","m9",
                    "s1","s2","s3","s4","s5"],
            "own_melds":[],"missing_suits":["p","m","m","s"],
            "melds":[[],[],[],[]],"won":[False]*4,
            "discards":[],"wall_count":2, # even at the final wall
        }
        fake={"shanten":0,"effective_tile_count":3,
              "effective_types":["p1"],
              "effective_details":[{"tile":"p1","remaining":3}]}
        with patch("mahtrain_core.ai.effective_draws",return_value=fake), \
             patch("mahtrain_core.ai.score_win",return_value={"multiplier":2}), \
             patch("mahtrain_core.ai.sample_discard_losses",
                   side_effect=AssertionError("unexpected expensive sampler")):
            ranked=challenge_discard_scores(view,cuts=["m4","s4"])
        self.assertEqual(len(ranked),2)
        self.assertTrue(all(x["sampled_worlds"]==0 for x in ranked))


if __name__=="__main__":
    unittest.main()
