"""M3.3 reversible kong ledger, wall-exhausted inspection and no premature payment."""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.kong_ledger import KongLedger
from mahtrain_core.exhaustive_review import review_exhaustive_draw
from mahtrain_core.four_player import FourPlayerOpening
from mahtrain_core.rules import TILES
from test_four_player_claims import staged_game


class KongLedgerTests(unittest.TestCase):
    def test_default_records_no_currency(self):
        k=KongLedger()
        key=k.declare(kind="an_gang",winner=0,payers=[1,2,3])
        state=k.public_state()
        self.assertIsNone(state["base"])
        self.assertEqual(state["events"][0]["status"],"unpriced")
        self.assertEqual(state["balances"],[0]*4)
        self.assertEqual(state["entries"],[])
        k.void(key,reason="kong_discard_ron")
        self.assertEqual(k.public_state()["events"][0]["status"],"voided")
        self.assertEqual(k.public_state()["balances"],[0]*4)

    def test_kong_simulation_three_types_and_exact_reversals(self):
        k=KongLedger(25)
        ming=k.declare(kind="ming_gang",winner=0,source=1,payers=[1])
        self.assertEqual(k.public_state()["balances"],[50,-50,0,0])
        hidden=k.declare(kind="an_gang",winner=2,payers=[0,1,3])
        self.assertEqual(k.public_state()["balances"],[0,-100,150,-50])
        bu=k.declare(kind="bu_gang",winner=3,payers=[0,1,2])
        self.assertEqual(k.public_state()["balances"],[-25,-125,125,25])
        self.assertEqual(len(k.public_state()["entries"]),7)
        k.void(ming,reason="kong_discard_ron")
        self.assertEqual(k.public_state()["balances"],[-75,-75,125,25])
        self.assertEqual(k.public_state()["entries"][-1]["kind"],"reversal")
        k.void(bu,reason="rob_kong")
        self.assertEqual(k.public_state()["balances"],[-50,-50,150,-50])
        self.assertEqual(len(k.public_state()["entries"]),11)
        self.assertTrue(k.public_state()["zero_sum"])
        self.assertEqual(k.public_state()["events"][hidden-1]["status"],"posted")
        with self.assertRaises(ValueError):
            k.void(ming,reason="kong_discard_ron")
        self.assertEqual(len(k.public_state()["entries"]),11)

    def test_rejects_invalid_base_payers_or_untrusted_rollback(self):
        for base in (0,-3,True,1.1,"100",10**6+1):
            with self.subTest(base=base),self.assertRaises(ValueError):
                KongLedger(base)
        k=KongLedger(100)
        for bad in (
            {"kind":"ming_gang","winner":0,"source":0,"payers":[0]},
            {"kind":"an_gang","winner":0,"payers":[1,1]},
            {"kind":"an_gang","winner":True,"payers":[1,2]},
            {"kind":"bu_gang","winner":0,"source":1,"payers":[1]},
            {"kind":"ming_gang","winner":0,"source":1,"payers":[2]},
        ):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                k.declare(**bad)
        self.assertEqual(k.public_state()["entries"],[])
        with self.assertRaises(ValueError):
            k.void(1,reason="kong_discard_ron")

    def test_real_angang_posts_only_with_explicit_base(self):
        game=FourPlayerOpening(19,kong_base=20)
        dealer=game.dealer
        pool=Counter({t:4 for t in TILES})
        cards=["m9"]*4
        for t in cards:pool[t]-=1
        for tile in TILES:
            while pool[tile] and len(cards)<14:
                cards.append(tile);pool[tile]-=1
        game=staged_game({dealer:cards},{dealer:"p"},seed=19)
        game.kong_ledger=KongLedger(20)
        game.declare_kong(dealer,"an_gang","m9")
        st=game.public_state()
        self.assertEqual(st["kong_ledger"]["balances"][dealer],120)
        self.assertEqual(sum(st["kong_ledger"]["balances"]),0)
        self.assertEqual(st["kong_ledger"]["balances"].count(-40),3)
        self.assertEqual(st["combined_balances"],st["kong_ledger"]["balances"])
        self.assertEqual(st["pending_kong_payments"][0]["status"],"posted")
        self.assertNotIn("tile",st["pending_kong_payments"][0])
        self.assertIsNone(st["melds"][dealer][0]["tile"])
        self.assertTrue(st["kong_ledger"]["zero_sum"])

    def test_identified_kong_void_does_not_void_an_older_different_kong(self):
        k=KongLedger(10)
        older=k.declare(kind="an_gang",winner=0,payers=[1,2,3])
        newer=k.declare(kind="an_gang",winner=0,payers=[1,2,3])
        k.void(newer,reason="kong_discard_ron")
        st=k.public_state()
        self.assertEqual(st["events"][older-1]["status"],"posted")
        self.assertEqual(st["events"][newer-1]["status"],"voided")
        self.assertEqual(st["balances"],[60,-20,-20,-20])


class ExhaustiveReviewTests(unittest.TestCase):
    def test_inactive_players_excluded_and_no_real_money_posted(self):
        ready=["m1"]*3+["m4"]*3+["s1"]*3+["s4"]*3+["s9"]
        game=FourPlayerOpening(42)
        s=(game.dealer+1)%4
        pig=(game.dealer+2)%4
        pool=Counter({t:4 for t in TILES})
        for t in ready:pool[t]-=1
        pigcards=["p1"];pool["p1"]-=1
        for t in TILES:
            while pool[t] and len(pigcards)<13:
                pigcards.append(t);pool[t]-=1
        g=staged_game({s:ready,pig:pigcards},
                      {i:"p" for i in range(4)})
        d=g.dealer
        # Emulate a terminal wall; preserve every physical tile in the
        # public discard pile, with dealer's first cut reducing 14 to 13.
        first=g._hands[d].pop()
        g._discards.append({"seat":d,"tile":first,"index":1})
        for t in list(g._wall):
            g._discards.append({"seat":d,"tile":t,
                                "index":len(g._discards)+1})
        g._wall.clear()
        g.phase="wall_exhausted";g.turn=None
        before=g.ledger.public_state()
        g._assert_physical_tiles()
        preview=g.public_state()["exhaustive_review"]
        self.assertTrue(preview["triggered"])
        self.assertFalse(preview["posted"])
        self.assertEqual(preview["policy"],"active_only_preview")
        self.assertEqual(sum(preview["preview_balances"]),0)
        status={x["seat"]:x for x in preview["seats"]}
        self.assertEqual(status[pig]["classification"],"flower_pig")
        self.assertEqual(status[s]["classification"],"listening")
        self.assertGreater(status[s]["wait_count"],0)
        self.assertEqual(status[s]["max_effective_fan"],min(
            status[s]["max_raw_fan"],g.ledger.fan_cap))
        self.assertTrue(any(x["stage"]=="flower_pig"
                            and x["payer"]==pig for x in preview["proposed_transfers"]))
        self.assertEqual(g.ledger.public_state(),before)
        self.assertEqual(g.public_state()["win_ledger"]["balances"],[0]*4)
        g._won[(d+3)%4]=True
        preview2=g.public_state()["exhaustive_review"]
        self.assertNotIn((d+3)%4,preview2["participating_active_seats"])
        self.assertEqual(g.ledger.public_state(),before)

    def test_no_preview_before_end_and_less_than_two_active(self):
        game=FourPlayerOpening(17)
        self.assertIsNone(game.public_state()["exhaustive_review"])
        g=review_exhaustive_draw(
            hands=[[]]*4, melds=[[]]*4, missing_suits=["p"]*4,
            won=[True,True,True,False],
            tian_ting=[{"eligible":False} for _ in range(4)],
            coefficient=100,fan_cap=3)
        self.assertFalse(g["triggered"])
        self.assertEqual(g["reason"],"fewer_than_two_active")

    def test_exposed_missing_meld_suppresses_unconfirmed_preview(self):
        out=review_exhaustive_draw(
            hands=[["m1"]*3+["m2"]*3+["s1"]*3+["s4"]*3+["s9"],
                   ["m3"]*3+["m5"]*3+["s2"]*3+["s6"]*3+["s8"],[],[]],
            melds=[[{"type":"peng","tile":"p1"}],[],[],[]],
            missing_suits=["p","p","p","p"],
            won=[False,False,True,True],
            tian_ting=[{"eligible":False} for _ in range(4)],
            coefficient=100,fan_cap=3)
        self.assertEqual(out["seats"][0]["classification"],
                         "unresolved_exposed_missing")
        self.assertFalse(out["posted"])
        self.assertEqual(out["proposed_transfers"],[])
        self.assertEqual(out["preview_balances"],[0]*4)


if __name__=="__main__":
    unittest.main()
