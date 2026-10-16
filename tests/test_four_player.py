"""Four-player seeded opening: atomic exchange, sealed missing suit, physical deck.

Not a full Mahjong game: claim resolution and payments remain intentionally
unimplemented. All-pass is an explicit uns cored demo-only transition.
"""
from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mahtrain_core.four_player import FourPlayerOpening, EXCHANGE_OFFSETS
from mahtrain_core.rules import TILES


def choose_three(hand: list[str]) -> list[str]:
    for suit in "msp":
        picked = [t for t in hand if t[0] == suit]
        if len(picked) >= 3:
            return picked[:3]
    raise AssertionError("all initial four-player hands must offer a suit triplet")


def make_exchanged(seed=17):
    game = FourPlayerOpening(seed)
    offers = {
        seat: choose_three(game.private_view(seat)["hand"])
        for seat in range(4)
    }
    before = [game.private_view(seat)["hand"] for seat in range(4)]
    for seat in range(4):
        game.select_exchange(seat, offers[seat])
    return game, before, offers


def to_dealer_turn(seed=17):
    game, before, offers = make_exchanged(seed)
    for seat, suit in enumerate(("m", "s", "p", "m")):
        game.select_missing(seat, suit)
    return game


class FourPlayerOpeningTests(unittest.TestCase):
    def test_seed_reproducible_exact_108_physical_tiles_and_55_wall(self):
        for seed in (0, 1, 17, 42, 1777):
            with self.subTest(seed=seed):
                a, b = FourPlayerOpening(seed), FourPlayerOpening(seed)
                self.assertEqual(a.public_state(), b.public_state())
                self.assertEqual(a.debug_tile_counts()["total"],108)
                self.assertEqual(a.debug_tile_counts()["wall"],55)
                self.assertEqual(sorted(a.public_state()["hand_counts"]),
                                 [13,13,13,14])
                self.assertEqual(a.public_state()["hand_counts"][a.dealer],14)
                self.assertIn(a.exchange_direction, EXCHANGE_OFFSETS)
                full = [t for i in range(4) for t in a.private_view(i)["hand"]]
                full += a._wall
                self.assertEqual(Counter(full),Counter({t:4 for t in TILES}))

    def test_atomic_exchange_uses_all_four_sealed_offers(self):
        for seed in (0,17,42):
            with self.subTest(seed=seed):
                game=FourPlayerOpening(seed)
                before=[game.private_view(s)["hand"] for s in range(4)]
                choice=[choose_three(before[s]) for s in range(4)]
                for seat in range(3):
                    game.select_exchange(seat,choice[seat])
                    self.assertEqual(game.phase,"exchange_select")
                    self.assertEqual([game.private_view(s)["hand"] for s in range(4)],
                                     before,"no one receives early")
                    self.assertNotIn("m1",str(game.public_state().get("sealed_exchange")))
                    self.assertNotIn("exchange_offers",game.public_state())
                    self.assertIsNone(game.private_view((seat+1)%4)["sealed_exchange"])
                game.select_exchange(3,choice[3])
                self.assertEqual(game.phase,"missing_select")
                offset=EXCHANGE_OFFSETS[game.exchange_direction]
                for seat in range(4):
                    source=(seat-offset)%4
                    expected=Counter(before[seat])-Counter(choice[seat])
                    expected.update(choice[source])
                    self.assertEqual(Counter(game.private_view(seat)["hand"]),expected)
                self.assertEqual(game.public_state()["wall_count"],55)
                self.assertEqual(game.debug_tile_counts()["total"],108)
                self.assertEqual(game.public_state()["events"],[{
                    "type":"exchange_complete","direction":game.exchange_direction
                }])

    def test_invalid_exchange_never_modifies_physical_deck_or_sealed_status(self):
        g=FourPlayerOpening(17)
        original=g.private_view(0)["hand"]
        valid=choose_three(original)
        cases=[
            [], valid[:2], [valid[0]]*5, "m1m2m3",
            ["bad","m1","m2"], [valid[0],valid[1],"p100"],
        ]
        alternate=next((t for t in original if t[0]!=valid[0][0]),None)
        self.assertIsNotNone(alternate)
        cases.append([valid[0],valid[1],alternate])
        cases.append([valid[0]]*3 if original.count(valid[0])<3 else
                     [valid[0]]*5)
        for value in cases:
            with self.subTest(value=value),self.assertRaises(ValueError):
                g.select_exchange(0,value)
            self.assertEqual(g.private_view(0)["hand"],original)
            self.assertEqual(g.public_state()["exchange_submitted"],[])
        g.select_exchange(0,valid)
        with self.assertRaises(ValueError):
            g.select_exchange(0,valid)
        self.assertEqual(g.public_state()["exchange_submitted"],[0])
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_missing_is_forbidden_before_exchange_and_sealed_until_all(self):
        g=FourPlayerOpening(1)
        with self.assertRaises(ValueError):
            g.select_missing(0,"p")
        g,before,offers=make_exchanged(1)
        counts=g.public_state()["hand_counts"]
        self.assertEqual(counts[g.dealer],14)
        for seat,suit in enumerate(("p","m","s")):
            g.select_missing(seat,suit)
            self.assertEqual(g.phase,"missing_select")
            self.assertIsNone(g.public_state()["missing_suits"])
            self.assertIsNone(g.private_view((seat+1)%4)["sealed_missing"])
            self.assertEqual(g.private_view(seat)["sealed_missing"],suit)
        with self.assertRaises(ValueError):
            g.select_missing(0,"m")
        g.select_missing(3,"p")
        self.assertEqual(g.public_state()["missing_suits"],["p","m","s","p"])
        self.assertEqual(g.phase,"dealer_discard")
        self.assertEqual(g.turn,g.dealer)
        self.assertEqual(g.public_state()["events"][-1]["type"],
                         "missing_suits_revealed")

    def test_tianque_after_exchange_is_neither_extra_tile_nor_forced_suit(self):
        g,before,offers=make_exchanged(17)
        for s in range(4):
            hand=g.private_view(s)["hand"]
            self.assertEqual(g.private_view(s)["tianque"],
                             len({t[0] for t in hand})==2)
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_dealer_has_first_cut_without_draw_others_draw_then_cut(self):
        g=to_dealer_turn(17)
        with self.assertRaises(ValueError):
            g.draw(g.dealer)
        dealer=g.dealer
        others=(dealer+1)%4
        with self.assertRaises(ValueError):
            g.discard(others,g.private_view(others)["hand"][0])
        cut=g.private_view(dealer)["hand"][0]
        g.discard(dealer,cut)
        state=g.public_state()
        self.assertEqual(state["phase"],"claim_window")
        self.assertEqual(state["pending_discard"]["tile"],cut)
        self.assertEqual(state["hand_counts"][dealer],13)
        self.assertEqual(state["wall_count"],55)
        with self.assertRaises(ValueError):
            g.draw(others)
        g.pass_all_claims_demo()
        self.assertEqual(g.turn,others)
        self.assertEqual(g.phase,"await_draw")
        with self.assertRaises(ValueError):
            g.draw(dealer)
        drawn=g.draw(others)
        self.assertIn(drawn,g.private_view(others)["hand"])
        self.assertEqual(g.public_state()["wall_count"],54)
        self.assertEqual(g.public_state()["hand_counts"][others],14)
        self.assertNotIn(drawn,g.public_state()["events"][-1].values())
        g.discard(others,drawn)
        self.assertEqual(g.phase,"claim_window")
        self.assertEqual(g.public_state()["discards"][-1]["tile"],drawn)
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_cannot_implicitly_skip_claim_response_or_double_discard(self):
        g=to_dealer_turn()
        first=g.private_view(g.dealer)["hand"][0]
        g.discard(g.dealer,first)
        with self.assertRaises(ValueError):
            g.discard(g.dealer,first)
        with self.assertRaises(ValueError):
            g.draw((g.dealer+1)%4)
        g.pass_all_claims_demo()
        with self.assertRaises(ValueError):
            g.pass_all_claims_demo()
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_private_view_is_one_seat_only_public_has_no_hidden_cards(self):
        g=FourPlayerOpening(42)
        public=json.dumps(g.public_state(),sort_keys=True)
        self.assertNotIn('"hand"',public)
        self.assertNotIn('"wall"',public)
        self.assertNotIn("seed",public)
        for seat in range(4):
            own=g.private_view(seat)
            self.assertEqual(own["seat"],seat)
            self.assertEqual(len(own["hand"]),14 if seat==g.dealer else 13)
            for other in range(4):
                if other!=seat:
                    self.assertNotIn("opponent_hand",own)
                    self.assertNotIn(f"hand_{other}",own)
        for invalid in (True,-1,4,"0",None):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                g.private_view(invalid)

    def test_operations_wrong_phase_are_rejected(self):
        g=FourPlayerOpening(1)
        with self.assertRaises(ValueError):
            g.pass_all_claims_demo()
        with self.assertRaises(ValueError):
            g.discard(g.dealer,"m1")
        with self.assertRaises(ValueError):
            g.draw(g.dealer)
        with self.assertRaises(ValueError):
            g.select_exchange(True,["m1"]*3)
        g,before,offers=make_exchanged(1)
        with self.assertRaises(ValueError):
            g.select_exchange(0,["m1"]*3)
        with self.assertRaises(ValueError):
            g.select_missing(0,"wind")
        self.assertEqual(g.phase,"missing_select")

    def test_repeatable_opening_event_log_and_no_claims_demo_turns(self):
        def replay(seed):
            g=FourPlayerOpening(seed)
            for s in range(4):
                g.select_exchange(s,choose_three(g.private_view(s)["hand"]))
            for s in range(4):
                hand=g.private_view(s)["hand"]
                suit=min("msp",key=lambda x:(sum(t[0]==x for t in hand),"msp".index(x)))
                g.select_missing(s,suit)
            for step in range(16):
                if g.phase=="await_draw":
                    g.draw(g.turn)
                seat=g.turn
                cut=g.private_view(seat)["hand"][0]
                g.discard(seat,cut)
                g.pass_all_claims_demo()
            self.assertEqual(g.debug_tile_counts()["total"],108)
            self.assertEqual(g.public_state()["wall_count"],40)
            return g.public_state(),[g.private_view(s)["hand"] for s in range(4)]
        self.assertEqual(replay(123),replay(123))


if __name__=="__main__":
    unittest.main()
