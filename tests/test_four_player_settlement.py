"""M3.2 verified Tian Ting checkpoints and zero-sum HU settlements."""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.four_player import FourPlayerOpening
from mahtrain_core.settlement import WinLedger
from mahtrain_core.rules import TILES
from test_four_player_claims import staged_game, deal_for_ron


class M32SettlementTests(unittest.TestCase):
    def test_multi_ron_two_earth_wins_are_independently_paid(self):
        game=deal_for_ron()
        dealer=game.dealer
        s1,s2,s3=[(dealer+i)%4 for i in (1,2,3)]
        game.discard(dealer,"s9")
        for seat in (s1,s2,s3):
            game.respond_discard(seat,"hu" if seat in (s1,s2) else "pass")
        ledger=game.public_state()["win_ledger"]
        self.assertEqual(ledger["balances"][dealer],-1600)
        self.assertEqual(ledger["balances"][s1],800)
        self.assertEqual(ledger["balances"][s2],800)
        self.assertEqual(ledger["balances"][s3],0)
        self.assertEqual(len(ledger["entries"]),2)
        self.assertEqual(len(ledger["wins"]),2)
        self.assertTrue(ledger["zero_sum"])
        posted=[event for event in game.public_state()["events"]
                if event["type"]=="win_settlement"]
        self.assertEqual(len(posted),2)
        for record in posted:
            self.assertEqual(record["payers"],[dealer])
            self.assertEqual(record["amount_per_payer"],800)
            self.assertEqual(record["amount"],800)
            self.assertIn(record["seat"],(s1,s2))
            self.assertEqual(record["effective_fan"],3)
            self.assertNotIn("hand",record)
            self.assertNotIn("future_wall",record)
        for payout in ledger["wins"]:
            self.assertEqual(payout["raw_fan"],4)
            self.assertEqual(payout["effective_fan"],3)
            self.assertEqual(payout["multiplier"],8)
            self.assertEqual(payout["amount_per_payer"],800)
            self.assertEqual(payout["kind"],"ron")
        with self.assertRaises(ValueError):
            game.respond_discard(s3,"pass")
        self.assertEqual(game.public_state()["win_ledger"],ledger)

    def test_dealer_first_turn_self_draw_is_heaven_and_paid_by_three(self):
        g=FourPlayerOpening(42)
        dealer=g.dealer
        hand=["m1"]*3+["m4"]*3+["s1"]*3+["s4"]*3+["s9"]*2
        g=staged_game({dealer:hand},{dealer:"p"})
        g.declare_self_win(dealer)
        ledger=g.public_state()["win_ledger"]
        self.assertEqual(ledger["balances"][dealer],2400)
        self.assertEqual(ledger["balances"].count(-800),3)
        self.assertEqual(sum(ledger["balances"]),0)
        self.assertEqual(len(ledger["entries"]),3)
        self.assertEqual(ledger["wins"][0]["main_pattern"],"heaven_win")
        self.assertEqual(ledger["wins"][0]["raw_fan"],4)
        self.assertEqual(ledger["wins"][0]["effective_fan"],3)
        events=[event for event in g.public_state()["events"]
                if event["type"]=="win_settlement"]
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]["seat"],dealer)
        self.assertEqual(events[0]["amount"],2400)
        self.assertEqual(events[0]["amount_per_payer"],800)
        self.assertEqual(sorted(events[0]["payers"]),
                         sorted(s for s in range(4) if s!=dealer))
        self.assertEqual(events[0]["amount"],
                         len(events[0]["payers"])*events[0]["amount_per_payer"])

    def test_public_balances_have_explicit_unpriced_kong_limits(self):
        g=FourPlayerOpening(19)
        d=g.dealer
        pool=Counter({t:4 for t in TILES})
        cards=["m9"]*4
        for t in cards:pool[t]-=1
        for tile in TILES:
            while pool[tile] and len(cards)<14:
                cards.append(tile);pool[tile]-=1
        g=staged_game({d:cards},{d:"p"},seed=19)
        g.declare_kong(d,"an_gang","m9")
        public=g.public_state()
        self.assertEqual(public["win_ledger"]["balances"],[0,0,0,0])
        self.assertEqual(public["pending_kong_payments"][0]["type"],"an_gang")
        self.assertNotIn("tile",public["pending_kong_payments"][0])
        self.assertTrue(public["prototype_limitations"]["kong_payments_pending"])
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_starting_w0_is_only_after_four_sealed_missing_selections(self):
        g=FourPlayerOpening(17)
        for seat in range(4):
            suit=next(s for s in "msp"
                      if sum(x.startswith(s) for x in g.private_view(seat)["hand"])>=3)
            tiles=[x for x in g.private_view(seat)["hand"] if x.startswith(suit)][:3]
            g.select_exchange(seat,tiles)
        self.assertEqual(g.phase,"missing_select")
        self.assertTrue(all(e["reason"]=="not_initialized" for e in g._tian_ting))
        for seat in range(4):
            cards=g.private_view(seat)["hand"]
            declared=min("msp",key=lambda x:sum(z.startswith(x) for z in cards))
            g.select_missing(seat,declared)
            if seat<3:
                self.assertTrue(all(
                    e["reason"]=="not_initialized" for e in g._tian_ting))
        self.assertEqual(g._tian_ting[g.dealer]["reason"],"dealer_not_eligible")
        self.assertEqual(g.phase,"dealer_discard")
        for seat in range(4):
            if seat!=g.dealer:
                self.assertIn(g._tian_ting[seat]["reason"],
                              ("active","not_initially_listening"))

    def test_tian_ting_stable_waits_preserved_then_changed_irreversibly(self):
        g=FourPlayerOpening(42)
        dealer=g.dealer
        target=(dealer+1)%4
        ready=["m1"]*3+["m4"]*3+["s1"]*3+["s4"]*3+["s9"]
        g=staged_game({target:ready},{target:"p"})
        g._initialize_tian_ting()
        self.assertTrue(g._tian_ting[target]["eligible"])
        old=g._tian_ting[target]["initial_waits"]
        self.assertIn("s9",old)
        filler=next(t for t in g._wall if t.startswith("p"))
        g._wall.remove(filler)
        g._hands[target].append(filler)
        g.turn=target;g.phase="await_discard"
        g.discard(target,filler)
        self.assertTrue(g._tian_ting[target]["eligible"])
        self.assertEqual(g._tian_ting[target]["initial_waits"],old)
        self.assertEqual(g._tian_ting[target]["checkpoints"],1)
        # Another draw and a different discard changes the whole winning set.
        g.phase="await_draw";g.turn=target
        g.draw(target)
        if g._hands[target][-1]=="s9":
            # The stable checkpoint may remain the same; instead use an
            # explicit different tile while preserving physical conservation.
            g.phase="await_discard"
        g.discard(target,"s9")
        self.assertFalse(g._tian_ting[target]["eligible"])
        self.assertEqual(g._tian_ting[target]["reason"],"waiting_set_changed")
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_peng_cancels_prior_tian_ting_even_if_waits_could_stay_equal(self):
        g=FourPlayerOpening(42)
        d=g.dealer; target=(d+1)%4
        ready=["m1","m2","m3","m4","m5","m6",
               "s1","s2","s3","s5","s5","s7","s8"]
        pool=Counter({t:4 for t in TILES})
        for t in ready:pool[t]-=1
        source=["s5"];pool["s5"]-=1
        for t in TILES:
            while pool[t] and len(source)<14:
                source.append(t);pool[t]-=1
        g=staged_game({d:source,target:ready},{d:"p",target:"p"})
        g._initialize_tian_ting()
        self.assertTrue(g._tian_ting[target]["eligible"])
        g.discard(d,"s5")
        self.assertIn("peng",g.claim_options(target))
        for s in range(4):
            if s!=d:g.respond_discard(s,"peng" if s==target else "pass")
        self.assertEqual(g._tian_ting[target]["reason"],"peng_called")
        self.assertFalse(g._tian_ting[target]["eligible"])
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_kong_bloom_records_event_bonus_before_cap(self):
        g=FourPlayerOpening(19)
        dealer=g.dealer
        # One concealed dark kong, three triplets and a singleton; the tail
        # supplement completes the pair for an authentic kong-bloom win.
        hand=["m1"]*4+["m2"]*3+["s2"]*3+["s5"]*3+["s9"]
        g=staged_game({dealer:hand},{dealer:"p"},seed=19)
        self.assertIn("s9",g._wall)
        g._wall.remove("s9")
        g._wall.append("s9")
        g.declare_kong(dealer,"an_gang","m1")
        self.assertTrue(g.private_view(dealer)["can_self_draw_win"])
        self.assertEqual(g._kong_draw[dealer],True)
        self.assertEqual(g.debug_tile_counts()["total"],108)
        g.declare_self_win(dealer)
        info=g.public_state()["win_ledger"]["wins"][0]
        self.assertEqual(info["bonuses"]["kong_bloom"],1)
        self.assertEqual(info["bonuses"]["roots"],1)
        self.assertEqual(info["raw_fan"],3)
        self.assertEqual(info["effective_fan"],3)
        self.assertEqual(info["total_received"],2400)
        self.assertEqual(g.public_state()["win_ledger"]["balances"][dealer],2400)

    def test_kong_discard_ron_bonus_is_derived_from_source_draw_event(self):
        g=deal_for_ron()
        dealer=g.dealer
        s1,s2,s3=[(dealer+i)%4 for i in (1,2,3)]
        # This starts at a deliberately staged "just supplemented" state;
        # the normal discard method records the causal event itself.
        g._kong_draw[dealer]=True
        # Record the antecedent unresolved kong payment without posting
        # invented currency, then ensure the successful kong-discard ron
        # flags it as voided.
        g._pending_kong_price(dealer,"an_gang")
        g.discard(dealer,"s9")
        self.assertTrue(g.public_state()["pending_discard"]["after_kong"])
        for seat in (s1,s2,s3):
            g.respond_discard(seat,"hu" if seat in (s1,s2) else "pass")
        self.assertEqual(
            g.public_state()["pending_kong_payments"][0]["status"],"voided"
        )
        for item in g.public_state()["win_ledger"]["wins"]:
            self.assertEqual(item["bonuses"]["kong_discard_ron"],1)
            self.assertEqual(item["raw_fan"],5)
            self.assertEqual(item["effective_fan"],3)

    def test_m339_self_draw_quote_matches_actual_booking(self):
        dealer=FourPlayerOpening(42).dealer
        hand=["m1"]*3+["m4"]*3+["s1"]*3+["s4"]*3+["s9"]*2
        for mode,unit in (("add_base",900),("add_fan",1600),
                          ("legacy",800)):
            with self.subTest(mode=mode):
                game=staged_game({dealer:hand.copy()},{dealer:"p"})
                game.ledger=WinLedger(100,3,mode)
                quote=game.private_view(dealer)["self_draw_preview"]
                self.assertTrue(game.private_view(dealer)["can_self_draw_win"])
                self.assertEqual(quote["amount_per_payer"],unit)
                self.assertEqual(quote["total_received"],3*unit)
                self.assertEqual(quote["payment_multiplier"],unit//100)
                self.assertEqual(quote["raw_fan"],4)
                self.assertEqual(quote["effective_fan"],3)
                self.assertFalse(quote["posted"])
                self.assertEqual(game.ledger.public_state()["balances"],[0]*4,
                                 "preview must never mutate confirmed balances")
                self.assertNotIn("self_draw_preview",game.public_state())
                self.assertIsNone(game.private_view((dealer+1)%4)
                                  ["self_draw_preview"])
                self.assertNotIn("hand",quote)
                self.assertNotIn("tile",quote)
                self.assertNotIn("wall",str(quote).lower())
                game.declare_self_win(dealer)
                booking=game.public_state()["win_ledger"]["wins"][0]
                self.assertEqual(booking["payers"],quote["payers"])
                self.assertEqual(booking["amount_per_payer"],
                                 quote["amount_per_payer"])
                self.assertEqual(booking["total_received"],
                                 quote["total_received"])
                self.assertIsNone(game.private_view(dealer)
                                  ["self_draw_preview"])

    def test_m339_self_draw_preview_only_charges_active_seats(self):
        dealer=FourPlayerOpening(42).dealer
        hand=["m1"]*3+["m4"]*3+["s1"]*3+["s4"]*3+["s9"]*2
        game=staged_game({dealer:hand},{dealer:"p"})
        game.ledger=WinLedger(100,3,"add_base")
        already_won=(dealer+1)%4
        game._won[already_won]=True
        quote=game.private_view(dealer)["self_draw_preview"]
        self.assertNotIn(already_won,quote["payers"])
        self.assertEqual(len(quote["payers"]),2)
        self.assertEqual(quote["total_received"],1800)
        game.declare_self_win(dealer)
        self.assertEqual(game.public_state()["win_ledger"]
                         ["balances"][already_won],0)
        self.assertEqual(sum(game.public_state()["settled_balances"]),0)
        # Quote validation is strict even when manually invoked by a client.
        with self.assertRaises(ValueError):
            game.ledger.preview_self_draw(payers=[1,1],score={
                "legal":True,"raw_fan":2,"effective_fan":2,
                "multiplier":4,"main_pattern":"pure_suit"})
        self.assertIsNone(FourPlayerOpening(17).private_view(0)
                          ["self_draw_preview"])

    def test_self_draw_modes_two_fan_three_payers_and_normal_ron(self):
        score={"legal":True,"raw_fan":2,"effective_fan":2,
               "multiplier":4,"main_pattern":"pure_suit",
               "combinations":{},"bonuses":{}}
        for mode,unit in (("add_base",500),("add_fan",800)):
            with self.subTest(mode=mode):
                ledger=WinLedger(100,3,mode)
                posted=ledger.pay_win(
                    winner=0,payers=[1,2,3],score=score,
                    source=0,kind="self_draw",tile="m1")
                self.assertEqual(posted["multiplier"],4)
                self.assertEqual(posted["self_draw_mode"],mode)
                self.assertEqual(posted["amount_per_payer"],unit)
                self.assertEqual(posted["total_received"],unit*3)
                self.assertEqual(ledger.public_state()["balances"],
                                 [unit*3,-unit,-unit,-unit])
                self.assertEqual(len(ledger.public_state()["entries"]),3)
                self.assertTrue(ledger.public_state()["zero_sum"])
                # The selected self-draw mode must not uplift a discard win.
                ron=WinLedger(100,3,mode)
                ticket=ron.pay_win(
                    winner=0,payers=[1],source=1,kind="ron",
                    score=score,tile="m1")
                self.assertEqual(ticket["amount_per_payer"],400)
                rob=WinLedger(100,3,mode)
                result=rob.pay_win(winner=0,payers=[2],source=2,
                                  kind="rob_kong",score=score,tile="m1")
                self.assertEqual(result["amount_per_payer"],400)
        # Internal legacy default retains prior historical/AI fixture scores.
        self.assertEqual(WinLedger().public_state()["self_draw_mode"],"legacy")
        for invalid in ("add_two",True,None,0,{},[], "AddFan"):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                WinLedger(100,3,invalid)

    def test_real_dealer_self_draw_mode_changes_verified_winner_balance(self):
        dealer=FourPlayerOpening(42).dealer
        hand=["m1"]*3+["m4"]*3+["s1"]*3+["s4"]*3+["s9"]*2
        for mode,unit in (("add_base",900),("add_fan",1600)):
            with self.subTest(mode=mode):
                g=staged_game({dealer:hand.copy()},{dealer:"p"})
                g.ledger=WinLedger(100,3,mode)
                g.declare_self_win(dealer)
                wins=g.public_state()["win_ledger"]["wins"]
                self.assertEqual(wins[0]["effective_fan"],3)
                self.assertEqual(wins[0]["amount_per_payer"],unit)
                self.assertEqual(wins[0]["total_received"],unit*3)
                self.assertEqual(sum(g.public_state()["settled_balances"]),0)
                self.assertEqual(g.public_state()["winners"][0]["score"]
                                 ["total_received"],unit*3)

    def test_ledger_rejects_invalid_amounts_and_requires_zero_sum(self):
        game=WinLedger(200,3)
        valid={"legal":True,"raw_fan":4,"effective_fan":3,"multiplier":8,
               "main_pattern":"pure_seven_pairs",
               "combinations":{},"bonuses":{}}
        with self.assertRaises(ValueError):
            game.pay_win(winner=0,payers=[1,1],score=valid,
                         source=0,kind="self_draw",tile="m1")
        with self.assertRaises(ValueError):
            game.pay_win(winner=0,payers=[1],score={**valid,"multiplier":16},
                         source=1,kind="ron",tile="m1")
        self.assertEqual(game.public_state()["balances"],[0,0,0,0])
        game.pay_win(winner=0,payers=[1,2,3],score=valid,
                     source=0,kind="self_draw",tile="m1")
        self.assertEqual(game.public_state()["balances"],[4800,-1600,-1600,-1600])
        self.assertTrue(game.public_state()["zero_sum"])
        for config in ((0,3),(100,-1),(True,3),(100,True)):
            with self.assertRaises(ValueError):
                WinLedger(*config)


if __name__=="__main__":
    unittest.main()
