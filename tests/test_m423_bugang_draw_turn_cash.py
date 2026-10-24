"""M4.23 authoritative current-draw-only supplement-kong cash and AI tests."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tests")]

from mahtrain_core.ai import MahjongAgent
from mahtrain_core.four_player import FourPlayerOpening
from mahtrain_core.kong_ledger import KongLedger
from mahtrain_core.rules import TILES, score_win


def ready_to_draw_fourth(*, base=20):
    """Legitimate physical 108-tile game with PENG and one m9 at wall front."""
    g = FourPlayerOpening(42, kong_base=base, dealer_override=0)
    target = "m9"
    counts = Counter({tile: 4 for tile in TILES})
    counts[target] -= 3
    hands = []
    for seat in range(4):
        needed = 10 if seat == 0 else 13
        hand = []
        for tile in TILES:
            if tile == target:
                continue
            while counts[tile] and len(hand) < needed:
                hand.append(tile)
                counts[tile] -= 1
        if len(hand) != needed:
            raise AssertionError("fixture depleted")
        hands.append(hand)
    counts[target] -= 1
    g._hands = hands
    g._melds = [[{"type": "peng", "tile": target}], [], [], []]
    g._wall = [target, *(t for t in TILES for _ in range(counts[t]))]
    g.missing_suits = ["p", "p", "p", "p"]
    g.turn = 0
    g.phase = "await_draw"
    g._assert_physical_tiles()
    assert g.draw(0) == target
    assert {"type": "bu_gang", "tile": target} in g.kong_options(0)
    return g


def resolve_rob_as_pass(g):
    assert g.phase == "rob_kong_window"
    for seat in (1, 2, 3):
        g.respond_rob_kong(seat, "pass")
    assert g.phase == "await_discard"
    assert g.debug_tile_counts()["total"] == 108


def reach_next_turn_holding_fourth(g):
    """Actually play four discard/response windows, never directly spoof draw."""
    assert g.private_view(0)["drawn_tile"] == "m9"
    tile = next(t for t in g._hands[0] if t != "m9")
    g.discard(0, tile, from_draw=False)
    for seat in (1, 2, 3):
        g.respond_discard(seat, "pass")
    for seat in (1, 2, 3):
        assert g.phase == "await_draw" and g.turn == seat
        drawn = g.draw(seat)
        g.discard(seat, drawn, from_draw=True)
        for other in range(4):
            if other != seat:
                g.respond_discard(other, "pass")
    assert g.phase == "await_draw" and g.turn == 0
    assert g.draw(0) != "m9"
    assert g.private_view(0)["drawn_tile"] != "m9"
    assert {"type": "bu_gang", "tile": "m9"} in g.kong_options(0)
    assert g.debug_tile_counts()["total"] == 108
    return g


class M423BugangCashTests(unittest.TestCase):
    def test_immediate_fourth_tile_bugang_is_paid_after_rob_window(self):
        g = ready_to_draw_fourth()
        before = g.public_state()["wall_count"]
        private = g.private_view(0)
        self.assertEqual(private["drawn_tile"], "m9")
        self.assertNotIn("drawn_tile", g.public_state())
        g.declare_kong(0, "bu_gang", "m9")
        self.assertTrue(g.public_state()["pending_rob_kong"]["cash_eligible"])
        self.assertEqual(g.public_state()["kong_ledger"]["entries"], [])
        resolve_rob_as_pass(g)
        ledger = g.public_state()["kong_ledger"]
        self.assertEqual(ledger["balances"], [60, -20, -20, -20])
        self.assertEqual(ledger["events"][0]["status"], "posted")
        self.assertTrue(ledger["events"][0]["cash_eligible"])
        self.assertEqual(len(ledger["entries"]), 3)
        self.assertEqual(g.public_state()["wall_count"], before - 1)
        self.assertEqual(g._melds[0][0]["type"], "bu_gang")

    def test_retained_fourth_delayed_bugang_has_no_money_but_supplements(self):
        g = reach_next_turn_holding_fourth(ready_to_draw_fourth())
        before = g.public_state()["wall_count"]
        g.declare_kong(0, "bu_gang", "m9")
        self.assertFalse(g.public_state()["pending_rob_kong"]["cash_eligible"])
        self.assertEqual(g.public_state()["kong_ledger"]["entries"], [])
        resolve_rob_as_pass(g)
        s = g.public_state()
        self.assertEqual(s["kong_ledger"]["balances"], [0, 0, 0, 0])
        self.assertEqual(s["kong_ledger"]["entries"], [])
        event = s["kong_ledger"]["events"][0]
        self.assertEqual(event["status"], "not_payable")
        self.assertEqual(event["reason"], "delayed_bu_gang_no_cash")
        self.assertEqual(event["amount_per_payer"], 0)
        self.assertFalse(event["cash_eligible"])
        self.assertEqual(s["settled_balances"], [0, 0, 0, 0])
        self.assertEqual(s["wall_count"], before-1)
        self.assertEqual(g._melds[0][0]["type"], "bu_gang")
        self.assertTrue(s["kong_ledger"]["zero_sum"])
        self.assertNotIn("hand", event)
        self.assertNotIn("future_wall", event)

    def test_dealer_initial_fourth_without_new_draw_never_gets_bugang_money(self):
        g = ready_to_draw_fourth()
        # An initial fourth copy is not the last drawn tile.
        g._drawn_tiles[0] = None
        g.declare_kong(0, "bu_gang", "m9")
        resolve_rob_as_pass(g)
        self.assertEqual(g.public_state()["kong_ledger"]["events"][0]["status"],
                         "not_payable")
        self.assertEqual(g.public_state()["kong_ledger"]["balances"], [0]*4)

    def test_delayed_kong_event_can_be_voided_without_phantom_reversal(self):
        k = KongLedger(30)
        idx = k.declare(kind="bu_gang", winner=0, payers=[1,2,3],
                        cash_eligible=False)
        self.assertEqual(k.public_state()["events"][0]["status"], "not_payable")
        k.void(idx, reason="kong_discard_ron")
        self.assertEqual(k.public_state()["events"][0]["status"], "voided")
        self.assertEqual(k.public_state()["entries"], [])
        self.assertEqual(k.public_state()["balances"], [0]*4)
        with self.assertRaises(ValueError):
            k.void(idx, reason="kong_discard_ron")

    def test_delayed_unpriced_kong_still_expressly_nonpayable(self):
        k = KongLedger()
        k.declare(kind="bu_gang", winner=0, payers=[1,2,3],
                  cash_eligible=False)
        e = k.public_state()["events"][0]
        self.assertEqual(e["status"], "not_payable")
        self.assertEqual(e["amount_per_payer"], 0)
        self.assertTrue(k.public_state()["zero_sum"])

    def test_never_disable_money_for_regular_or_concealed_kongs(self):
        k = KongLedger(20)
        for kind in ("ming_gang", "an_gang"):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                k.declare(kind=kind, winner=0,
                          payers=[1] if kind=="ming_gang" else [1,2,3],
                          source=1 if kind=="ming_gang" else None,
                          cash_eligible=False)
        with self.assertRaises(ValueError):
            k.declare(kind="bu_gang",winner=0,payers=[1,2,3],
                      cash_eligible=0)
        self.assertEqual(k.public_state()["events"], [])

    def test_root_bonus_is_unchanged_for_cashless_delayed_upgrade(self):
        # Three concealed groups + pair, plus completed bu-gang: one m9 root.
        concealed = ["m1"]*3 + ["m2", "m3", "m4"] + [
            "s1", "s2", "s3", "s5", "s5"]
        win = score_win(
            concealed, [{"type":"bu_gang", "tile":"m9"}], "p", cap=6)
        self.assertTrue(win["legal"])
        self.assertEqual(win["bonuses"]["roots"], 1)
        self.assertEqual(win["effective_fan"], win["main_fan"]+1)
        self.assertEqual(win["multiplier"], 2 ** win["effective_fan"])
        # Cash timing never enters score_win: a late legal kong gets this
        # same official rooted win score as a timely legal kong.

    def test_challenge_refuses_cashless_equal_stage_unimproved_bugang(self):
        g = ready_to_draw_fourth()
        view = g.private_view(0)
        before = deepcopy(view)
        def outlook(hand, melds, missing, public, cap, tian, **kwargs):
            if any(m["type"]=="bu_gang" for m in melds):
                return {"shanten":1,"ukeire":9,"value":9,"tian_kept":False}
            return {"shanten":1,"ukeire":10,"value":10,"tian_kept":False}
        with patch("mahtrain_core.ai._cut_shanten", return_value=1), \
             patch("mahtrain_core.ai.shanten_13", return_value=1), \
             patch("mahtrain_core.ai._call_outlook", side_effect=outlook):
            paid = MahjongAgent("challenge", seed=42, seat=0).kong(view)
            self.assertEqual(paid, {"type":"bu_gang", "tile":"m9"})
            delayed = deepcopy(view)
            delayed["drawn_tile"] = "m1"
            free = MahjongAgent("challenge", seed=42, seat=0).kong(delayed)
            self.assertIsNone(free)
        self.assertEqual(view, before)

    def test_challenge_can_choose_cashless_upgrade_if_both_metrics_improve(self):
        g = reach_next_turn_holding_fourth(ready_to_draw_fourth())
        view = g.private_view(0)
        def outlook(hand, melds, missing, public, cap, tian, **kwargs):
            value = 13 if any(m["type"]=="bu_gang" for m in melds) else 10
            return {"shanten":1,"ukeire":value,"value":value,"tian_kept":False}
        with patch("mahtrain_core.ai._cut_shanten", return_value=1), \
             patch("mahtrain_core.ai.shanten_13", return_value=1), \
             patch("mahtrain_core.ai._call_outlook", side_effect=outlook):
            self.assertEqual(
                MahjongAgent("challenge",seed=42,seat=0).kong(view),
                {"type":"bu_gang","tile":"m9"})

if __name__ == "__main__":
    unittest.main()
