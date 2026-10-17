"""M3.3 reversible kong ledger, wall-exhausted inspection and no premature payment."""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.kong_ledger import KongLedger
from mahtrain_core.exhaustive_review import review_exhaustive_draw, compare_exhaustive_scopes, finalize_active_only
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

    def test_real_an_gang_then_two_rons_exactly_reverses_that_kong(self):
        game=FourPlayerOpening(42)
        d=game.dealer
        s1,s2,s3=[(d+i)%4 for i in (1,2,3)]
        ready1=["m1"]*3+["m4"]*3+["s1"]*3+["s4"]*3+["s9"]
        ready2=["p1"]*3+["p4"]*3+["s2"]*3+["s5"]*3+["s9"]
        dealer_hand=["m9"]*4+["s9"]
        remaining=Counter({t:4 for t in TILES})
        for t in ready1+ready2+dealer_hand:
            remaining[t]-=1
            self.assertGreaterEqual(remaining[t],0)
        for tile in TILES:
            while remaining[tile] and len(dealer_hand)<14:
                dealer_hand.append(tile)
                remaining[tile]-=1
        g=staged_game({d:dealer_hand,s1:ready1,s2:ready2},
                      {d:"p",s1:"p",s2:"m",s3:"m"})
        g.kong_ledger=KongLedger(25)
        g.declare_kong(d,"an_gang","m9")
        before=g.public_state()
        self.assertEqual(before["kong_ledger"]["balances"][d],150)
        self.assertEqual(before["kong_ledger"]["balances"].count(-50),3)
        self.assertEqual(before["kong_ledger"]["events"][0]["status"],"posted")
        self.assertEqual(g._effective(d),14)
        self.assertIn("s9",g.private_view(d)["hand"])
        g.discard(d,"s9")
        self.assertTrue(g.public_state()["pending_discard"]["after_kong"])
        for seat in (s1,s2,s3):
            g.respond_discard(seat,"hu" if seat in (s1,s2) else "pass")
        st=g.public_state()
        self.assertEqual(st["kong_ledger"]["balances"],[0]*4)
        self.assertEqual(st["kong_ledger"]["events"][0]["status"],"voided")
        self.assertEqual(
            [e["kind"] for e in st["kong_ledger"]["entries"]],
            ["charge"]*3+["reversal"]*3,
        )
        self.assertEqual(len(st["win_ledger"]["wins"]),2)
        self.assertEqual(st["combined_balances"],st["win_ledger"]["balances"])
        self.assertTrue(st["kong_ledger"]["zero_sum"])
        self.assertTrue(st["win_ledger"]["zero_sum"])
        self.assertEqual(g.debug_tile_counts()["total"],108)

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
        comparison=preview["scope_comparison"]
        self.assertFalse(comparison["posted"])
        self.assertTrue(comparison["available"])
        self.assertEqual(len(comparison["scenarios"]),2)
        for scenario in comparison["scenarios"]:
            self.assertFalse(scenario["posted"])
            self.assertEqual(sum(scenario["balances"]),0)
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
        # Real wall exhaustion, NOT public_state() read, posts the A-only ledger.
        g._continue_after(d)
        official=g.public_state()["exhaustive_settlement"]
        self.assertTrue(official["posted"])
        self.assertEqual(official["policy"],"active_only_final")
        self.assertEqual(official["balances"],preview2["preview_balances"])
        self.assertEqual(sum(official["balances"]),0)
        self.assertEqual(official["balances"][(d+3)%4],0,
                         "already-won players never pay or collect at exhaustion")
        self.assertEqual(g.public_state()["settled_balances"],official["balances"])
        self.assertEqual(g.ledger.public_state(),before)
        self.assertEqual(g.public_state()["combined_balances"],official["balances"])
        event_count=len(g._events)
        g._settle_exhaustive_once()
        g._continue_after(d)
        self.assertEqual(len(g._events),event_count,
                         "repeat transitions cannot charge a second time")
        self.assertEqual(g.public_state()["exhaustive_settlement"],official)

    def test_won_inclusive_flower_pig_scope_is_auditable_not_posted(self):
        # Completed winner 3 is never charged da-jiao in the alternative.
        current={
            "triggered": True, "posted": False,
            "reason": "requires_confirmation_of_settlement_participants",
            "participating_active_seats": [0, 1, 2],
            "seats": [
                {"seat": 0, "classification": "flower_pig"},
                {"seat": 1, "classification": "listening"},
                {"seat": 2, "classification": "unready"},
            ],
            "proposed_transfers": [
                {"stage": "flower_pig", "payer": 0,
                 "recipient": 1, "amount": 800},
                {"stage": "flower_pig", "payer": 0,
                 "recipient": 2, "amount": 800},
                {"stage": "da_jiao", "payer": 2,
                 "recipient": 1, "amount": 400, "effective_fan": 2},
            ],
        }
        from copy import deepcopy
        before=deepcopy(current)
        comparison=compare_exhaustive_scopes(
            current, won=[False,False,False,True], coefficient=100)
        self.assertEqual(current,before,"audit must never alter actual preview")
        self.assertFalse(comparison["posted"])
        self.assertTrue(comparison["available"])
        active,inclusive=comparison["scenarios"]
        self.assertEqual(active["balances"],[-1600,1200,400,0])
        self.assertEqual(inclusive["balances"],[-2400,1200,400,800])
        self.assertEqual(inclusive["transfers"][-1],{
            "stage":"flower_pig","payer":0,"recipient":3,"amount":800})
        for scenario in comparison["scenarios"]:
            self.assertFalse(scenario["posted"])
            self.assertTrue(scenario["zero_sum"])
            self.assertEqual(sum(scenario["balances"]),0)
        self.assertEqual(
            [x for x in inclusive["transfers"] if x["stage"]=="da_jiao"],
            [x for x in active["transfers"] if x["stage"]=="da_jiao"])

    def test_scope_disallows_undetermined_classification_or_invalid_state(self):
        bad={"triggered":True,"posted":False,
             "reason":"unresolved_missing_meld_or_nonstable_hand",
             "seats":[],"participating_active_seats":[0,1],
             "proposed_transfers":[]}
        report=compare_exhaustive_scopes(
            bad,won=[False,False,True,True],coefficient=100)
        self.assertFalse(report["available"])
        self.assertEqual(report["scenarios"],[])
        for won,coeff in (([0,False,True,True],100),
                          ([False]*4,0),
                          ([False]*3,100)):
            with self.subTest(won=won,coeff=coeff),self.assertRaises(ValueError):
                compare_exhaustive_scopes(
                    bad,won=won,coefficient=coeff)

    def test_official_a_only_flower_pig_then_dajiao_and_rejects_tampering(self):
        import copy
        preview={
            "triggered":True,"posted":False,
            "participating_active_seats":[0,1,2],
            "seats":[
                {"seat":0,"classification":"flower_pig"},
                {"seat":1,"classification":"listening","max_effective_fan":2},
                {"seat":2,"classification":"unready"},
            ],
            "proposed_transfers":[
                {"stage":"flower_pig","payer":0,"recipient":1,"amount":800},
                {"stage":"flower_pig","payer":0,"recipient":2,"amount":800},
                {"stage":"da_jiao","payer":2,"recipient":1,
                 "amount":400,"effective_fan":2},
            ],
            "preview_balances":[-1600,1200,400,0],
        }
        flags=[False,False,False,True]
        before=copy.deepcopy(preview)
        settled=finalize_active_only(preview,won=flags,coefficient=100,fan_cap=3)
        self.assertEqual(settled["balances"],[-1600,1200,400,0])
        self.assertTrue(settled["posted"])
        self.assertTrue(settled["zero_sum"])
        self.assertEqual([x["index"] for x in settled["entries"]],[1,2,3])
        self.assertEqual(preview,before,"never mutate historical preview")
        for tweak in ("recipient","amount","balances","effective_fan"):
            bad=copy.deepcopy(preview)
            if tweak=="recipient":bad["proposed_transfers"][0]["recipient"]=3
            elif tweak=="amount":bad["proposed_transfers"][1]["amount"]=300
            elif tweak=="balances":bad["preview_balances"][0]=0
            else:bad["seats"][1]["max_effective_fan"]=True
            with self.subTest(tweak=tweak),self.assertRaises(ValueError):
                finalize_active_only(bad,won=flags,coefficient=100,fan_cap=3)
        bad=copy.deepcopy(preview)
        bad["seats"][2]["classification"]="unresolved_nonstable_hand"
        withheld=finalize_active_only(bad,won=flags,coefficient=100,fan_cap=3)
        self.assertFalse(withheld["posted"])
        self.assertEqual(withheld["balances"],[0,0,0,0])
        self.assertEqual(withheld["entries"],[])

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
