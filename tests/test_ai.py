"""M3.4 heuristic opponent regression, legality, observability and seed parity."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.ai import AI_LEVELS, MahjongAgent, visible_tiles
from mahtrain_core.efficiency import shanten_13, analyze_discards
from mahtrain_core.ai import challenge_discard_scores
from mahtrain_core.four_player import FourPlayerOpening
from mahtrain_core.rules import TILE_INDEX, is_legal_win
from test_four_player_claims import deal_for_ron, staged_game


class MahjongAIUnitTests(unittest.TestCase):
    def test_levels_are_strict_and_random_actions_repeat_by_seed(self):
        for bad in ("", "professional", True, None, "easy", "expert"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                MahjongAgent(bad, seed=42, seat=1)
        for seat in (-1, 4, True, "1"):
            with self.subTest(seat=seat), self.assertRaises(ValueError):
                MahjongAgent("basic",seed=42,seat=seat)
        game=FourPlayerOpening(42)
        own=game.private_view(1)
        a=MahjongAgent("basic",seed=42,seat=1)
        b=MahjongAgent("basic",seed=42,seat=1)
        self.assertEqual([a.exchange(own) for _ in range(10)],
                         [b.exchange(own) for _ in range(10)])
        self.assertEqual(len(AI_LEVELS),3)

    def test_each_level_exchanges_exactly_three_owned_same_suit(self):
        for seed in (0,17,42,99):
            for level in AI_LEVELS:
                for seat in (1,2,3):
                    with self.subTest(seed=seed,level=level,seat=seat):
                        game=FourPlayerOpening(seed)
                        view=game.private_view(seat)
                        agent=MahjongAgent(level,seed=seed,seat=seat)
                        offered=agent.exchange(view)
                        self.assertEqual(len(offered),3)
                        self.assertEqual(len({t[0] for t in offered}),1)
                        source=list(view["hand"])
                        for tile in offered:
                            source.remove(tile)
                        game.select_exchange(seat,offered)
                        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_missing_choice_is_legal_post_exchange_and_independent(self):
        game=FourPlayerOpening(17)
        for seat in range(4):
            view=game.private_view(seat)
            strategy=MahjongAgent("advanced",seed=17,seat=seat)
            game.select_exchange(seat,strategy.exchange(view))
        self.assertEqual(game.phase,"missing_select")
        for seat,level in zip(range(4),("challenge","basic","advanced","challenge")):
            view=game.private_view(seat)
            agent=MahjongAgent(level,seed=17,seat=seat)
            missing=agent.missing(view)
            self.assertIn(missing,("m","s","p"))
            game.select_missing(seat,missing)
        self.assertEqual(game.phase,"dealer_discard")
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_bots_always_accept_verified_discard_hu(self):
        game=deal_for_ron()
        source=game.dealer
        seat=(source+1)%4
        game.discard(source,"s9")
        view=game.private_view(seat)
        self.assertIn("hu",view["claim_options"])
        for level in AI_LEVELS:
            self.assertEqual(
                MahjongAgent(level,seed=42,seat=seat).response(view),"hu")
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_private_view_only_nonpeeking_even_when_extra_hidden_objects_exist(self):
        game=FourPlayerOpening(42)
        dealer=game.dealer
        view=game.private_view(dealer)
        # This game is at dealer's first discard. Suit already decided in
        # trusted stage here to exercise actual expert discard logic.
        game.missing_suits=["p"]*4
        game.phase="dealer_discard"
        game.turn=dealer
        view=game.private_view(dealer)
        original=copy.deepcopy(view)
        def sabotage(v):
            v["future_wall"]=["m9"]*55
            v["opponent_hands"]=[["m9"]*13]*3
            v["all_private_tian_ting"]=[["m1"]]*3
            return v
        for level in AI_LEVELS:
            first=MahjongAgent(level,seed=91,seat=dealer).discard(
                copy.deepcopy(original))
            second=MahjongAgent(level,seed=91,seat=dealer).discard(
                sabotage(copy.deepcopy(original)))
            self.assertEqual(first,second,
                             "AI cannot use leaked hidden wall/opponent hands")
            self.assertIn(first,original["hand"])
        # Own concealed (not other seats') is the only private information in
        # a server-authorized seat view.
        self.assertNotIn("wall",original)
        self.assertNotIn("opponent_hands",original)
        self.assertNotIn("hands",original)

    def test_visible_tiles_do_not_count_meld_and_discard_twice(self):
        game=FourPlayerOpening(42)
        view=game.private_view(1)
        view["discards"]=[
            {"tile":"m1","seat":0,"claimed_by":2},
            {"tile":"m2","seat":1},
            {"tile":"m3","seat":3,"claimed_by":0},
            {"tile":"p1","seat":3,"won_by":[2]},
        ]
        view["melds"]=[
            [{"type":"an_gang","tile":None}],
            [],
            [{"type":"peng","tile":"m1"}],
            [{"type":"ming_gang","tile":"p6"}],
        ]
        self.assertEqual(
            visible_tiles(view),["m2","p1"]+["m1"]*3+["p6"]*4)
        view["seat"]=3
        view["melds"][3]=[{"type":"ming_gang","tile":"p6"}]
        self.assertEqual(
            visible_tiles(view),["m2","p1"]+["m1"]*3)

    def test_advanced_always_minimizes_post_cut_shanten(self):
        game=FourPlayerOpening(42)
        game.missing_suits=["p"]*4
        game.phase="dealer_discard"
        game.turn=game.dealer
        dealer=game.dealer
        view=game.private_view(dealer)
        level=MahjongAgent("advanced",seed=42,seat=dealer)
        cut=level.discard(view)
        own=view["hand"]
        eligible=[t for t in set(own) if t[0]=="p"] or list(set(own))
        def score(t):
            after=list(own);after.remove(t)
            return shanten_13(after, view["own_melds"],"p")
        self.assertEqual(score(cut),min(score(t) for t in eligible))

    def test_challenge_tie_break_is_consistent_with_public_ukeire(self):
        # Stage a valid 14-card hand containing no missing suit, so this
        # exercises effective-draw tie breaking rather than trivial dingque.
        dealer=FourPlayerOpening(42).dealer
        hand=["m1","m1","m2","m3","m3","m4","m5","m6",
              "s2","s3","s5","s6","s8","s9"]
        game=staged_game({dealer:hand},{dealer:"p"})
        view=game.private_view(dealer)
        self.assertFalse(is_legal_win(hand,missing_suit="p"))
        proposed=MahjongAgent(
            "challenge",seed=42,seat=dealer).discard(view)
        self.assertIn(proposed,hand)
        options=analyze_discards(hand,missing_suit="p",visible_tiles=[])
        scores={x["discard"]:x["shanten"]
                for x in options["candidates"]}
        self.assertEqual(scores[proposed], min(scores.values()))
        ranking=challenge_discard_scores(view)
        self.assertEqual(proposed,ranking[0]["discard"])
        self.assertTrue(all(x["shanten"] == ranking[0]["shanten"]
                            for x in ranking))
        self.assertTrue(all(ranking[i]["score"] >= ranking[i+1]["score"]
                            for i in range(len(ranking)-1)))

    def test_challenge_considers_real_tenpai_fan_and_remaining_copies(self):
        # Four complete groups plus an orphan: after the orphan cut, only
        # another m5 completes the pair. Winning multiplier is rule-scored,
        # not guessed from the number of distinct wait types.
        dealer=FourPlayerOpening(42).dealer
        hand=["m1","m2","m3","m4","m5","m6","m7","m8","m9",
              "p2","p3","p4","m5","p9"]
        game=staged_game({dealer:hand},{dealer:"s"})
        view=game.private_view(dealer)
        rank=challenge_discard_scores(view)
        matching=next(item for item in rank if item["discard"]=="p9")
        self.assertEqual(matching["shanten"],0)
        self.assertGreater(matching["effective_tile_count"],0)
        self.assertGreaterEqual(matching["expected_fan_weighted_copies"],
                                matching["effective_tile_count"])
        self.assertEqual(MahjongAgent("challenge",seed=42,seat=dealer).discard(view),
                         rank[0]["discard"])
        hidden={**view,"opponent_hands":[["m1"]*13]*3,"future_wall":["p9"]*55}
        self.assertEqual(challenge_discard_scores(hidden),rank,
                         "hidden wall and opponent hands must never influence ranking")

    def test_challenge_keeps_nonregression_even_when_shapes_are_valuable(self):
        dealer=FourPlayerOpening(42).dealer
        game=staged_game({dealer:["m1","m1","m2","m3","m3","m4","m5","m6",
                                  "s2","s3","s5","s6","s8","s9"]},
                         {dealer:"p"})
        view=game.private_view(dealer)
        cuts=challenge_discard_scores(view)
        best=min(x["shanten"] for x in cuts)
        self.assertTrue(all(x["shanten"]==best for x in cuts))
        self.assertEqual(cuts[0]["discard"],
                         MahjongAgent("challenge",seed=99,seat=dealer).discard(view))



if __name__=="__main__":
    unittest.main()
