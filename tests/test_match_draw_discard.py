"""M3.15 public discard classification and seat-specific draw privacy."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.four_player import FourPlayerOpening  # noqa: E402
from mahtrain_core.rules import winning_tiles  # noqa: E402
from test_four_player import to_dealer_turn  # noqa: E402


class DrawVsHandDiscardTests(unittest.TestCase):
    def _ready_to_draw(self,seed=17):
        game=to_dealer_turn(seed)
        first=game.dealer
        game.discard(first,game.private_view(first)["hand"][0])
        self.assertEqual(game.public_state()["discards"][-1]["discard_kind"],
                         "tedashi")
        game.pass_all_claims_demo()
        other=game.turn
        self.assertNotEqual(first,other)
        return game,other

    def test_private_drawn_tile_and_true_draw_cut_are_authoritative(self):
        game,other=self._ready_to_draw()
        tile=game.draw(other)
        self.assertEqual(game.private_view(other)["drawn_tile"],tile)
        public=game.public_state()
        self.assertNotIn("drawn_tile",public)
        self.assertNotIn(tile,public["events"][-1].values())
        game.discard(other,tile,from_draw=True)
        cut=game.public_state()["discards"][-1]
        self.assertEqual(cut["discard_kind"],"tsumogiri")
        self.assertEqual(game.private_view(other)["drawn_tile"],None)
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_hand_cut_and_invalid_draw_cut(self):
        game,other=self._ready_to_draw(23)
        drawn=game.draw(other)
        cut=next(t for t in game.private_view(other)["hand"] if t!=drawn)
        with self.assertRaises(ValueError):
            game.discard(other,cut,from_draw=True)
        with self.assertRaises(ValueError):
            game.discard(other,drawn,from_draw="yes")
        self.assertEqual(game.private_view(other)["drawn_tile"],drawn)
        game.discard(other,cut,from_draw=False)
        self.assertEqual(game.public_state()["discards"][-1]["discard_kind"],
                         "tedashi")
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_equal_tile_duplicates_can_explicitly_choose_both_kinds(self):
        seed=None
        for n in range(1,70):
            game,other=self._ready_to_draw(n)
            drawn=game.draw(other)
            if game.private_view(other)["hand"].count(drawn)>=2:
                seed=n
                break
        self.assertIsNotNone(seed,"search did not find an equal physical copy")
        game,other=self._ready_to_draw(seed)
        drawn=game.draw(other)
        self.assertGreaterEqual(game.private_view(other)["hand"].count(drawn),2)
        game.discard(other,drawn,from_draw=False)
        self.assertEqual(game.public_state()["discards"][-1]["discard_kind"],"tedashi")
        game,other=self._ready_to_draw(seed)
        drawn=game.draw(other)
        game.discard(other,drawn,from_draw=True)
        self.assertEqual(game.public_state()["discards"][-1]["discard_kind"],"tsumogiri")

    def test_draw_tile_without_duplicate_cannot_be_mislabelled_hand_cut(self):
        for n in range(1,70):
            game,other=self._ready_to_draw(n)
            drawn=game.draw(other)
            if game.private_view(other)["hand"].count(drawn)==1:
                break
        else:
            self.fail("search did not find a single-copy draw")
        with self.assertRaises(ValueError):
            game.discard(other,drawn,from_draw=False)
        self.assertEqual(game.private_view(other)["drawn_tile"],drawn)
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_structural_waits_do_not_expose_hidden_walls(self):
        from web_server import _match_private_view
        game=to_dealer_turn(25)
        # At this point seat zero has 13 or 14 effective tiles, depending
        # on the randomly selected dealer; all hints are seat-zero only.
        result=_match_private_view(game,{seat: type("Bot",(),{
            "level":"basic","policy_description":lambda self:"simple"
        })() for seat in (1,2,3)})
        self.assertIn("ready_waits",result)
        self.assertIn("ready_after_discards",result)
        self.assertNotIn("_wall",result)
        self.assertNotIn("_hands",result)
        if game.missing_suits[0] in ("m","s","p"):
            hand=result["hand"]; melds=result["own_melds"]
            if len(hand)+3*len(melds)==13 and all(
                    t[0]!=game.missing_suits[0] for t in hand):
                self.assertEqual(
                    result["ready_waits"],
                    winning_tiles(hand,melds,game.missing_suits[0]))


if __name__=="__main__":
    unittest.main()
