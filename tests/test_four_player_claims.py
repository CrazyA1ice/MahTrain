"""M3.1 collision / kong regression tests with complete physical fixtures."""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.four_player import FourPlayerOpening
from mahtrain_core.rules import TILES


def staged_game(hands: dict[int,list[str]], missing: dict[int,str] | None=None, *, seed=42):
    """Build a legal physical 108-deck at dealer's first-discard checkpoint."""
    game=FourPlayerOpening(seed)
    dealer=game.dealer
    deck=Counter({tile:4 for tile in TILES})
    for cards in hands.values():
        for tile in cards:
            deck[tile]-=1
            if deck[tile]<0:
                raise AssertionError("fixture has >4 physical copies of "+tile)
    for seat in range(4):
        size=14 if seat==dealer else 13
        if seat not in hands:
            hand=[]
            for tile in TILES:
                while deck[tile] and len(hand)<size:
                    hand.append(tile)
                    deck[tile]-=1
            hands[seat]=hand
        if len(hands[seat])!=size:
            raise AssertionError(f"seat {seat} should have {size} cards")
    game._hands=[list(hands[s]) for s in range(4)]
    game._wall=[tile for tile in TILES for _ in range(deck[tile])]
    game._melds=[[],[],[],[]]
    game._won=[False]*4
    game._winners=[]
    game._discards=[]
    game._pending_discard=None
    game._pending_kong=None
    game._responses={}
    game.missing_suits=[(missing or {}).get(s,"p") for s in range(4)]
    game.phase="dealer_discard"
    game.turn=dealer
    game._assert_physical_tiles()
    return game


def deal_for_ron():
    g=FourPlayerOpening(42)
    d=g.dealer
    s1,s2,s3=(d+1)%4,(d+2)%4,(d+3)%4
    ready1=["m1"]*3+["m4"]*3+["s1"]*3+["s4"]*3+["s9"]
    ready2=["p1"]*3+["p4"]*3+["s2"]*3+["s5"]*3+["s9"]
    # Reserve one source s9; draw fillers from remaining pool deterministically.
    reserved=Counter(ready1+ready2+["s9"])
    avail=Counter({t:4 for t in TILES})-reserved
    source=["s9"]
    for tile in TILES:
        while avail[tile] and len(source)<14:
            source.append(tile);avail[tile]-=1
    return staged_game({d:source,s1:ready1,s2:ready2},
                       {d:"p",s1:"p",s2:"m",s3:"m"})


class FourPlayerClaimsTests(unittest.TestCase):
    def test_multi_ron_precedes_peng_and_winners_exit(self):
        g=deal_for_ron()
        source=g.dealer
        s1,s2,s3=(source+1)%4,(source+2)%4,(source+3)%4
        g.discard(source,"s9")
        self.assertIn("hu",g.claim_options(s1))
        self.assertIn("hu",g.claim_options(s2))
        self.assertEqual(g.claim_options(source),[])
        self.assertNotIn("hu",g.claim_options(s3))
        before=g.public_state()
        g.respond_discard(s2,"hu")
        self.assertEqual(g.phase,"claim_window")
        self.assertFalse(any(g._won))
        self.assertEqual(g.public_state()["claim_submitted"],[s2])
        with self.assertRaises(ValueError):
            g.respond_discard(s2,"hu")
        g.respond_discard(s1,"hu")
        g.respond_discard(s3,"pass")
        self.assertEqual(g.public_state()["won"].count(True),2)
        self.assertEqual(g.phase,"await_draw")
        self.assertEqual(g.turn,s3)
        self.assertEqual(g.public_state()["discards"][-1]["won_by"],[s1,s2])
        self.assertEqual(g.public_state()["events"][-1]["type"],"multi_ron")
        self.assertEqual(g.debug_tile_counts()["total"],108)
        with self.assertRaises(ValueError):
            g.draw(s1)

    def test_hu_claim_preempts_peng_even_when_both_are_legal(self):
        g=FourPlayerOpening(42)
        d=g.dealer
        peng_seat=(d+1)%4
        hu_seat=(d+2)%4
        # A valid wait without holding m9: m7+m8 finishes the fourth meld.
        ready=["m1"]*3+["m4"]*3+["s1"]*3+["s4"]*2+["m7","m8"]
        deck=Counter({tile:4 for tile in TILES})
        for t in ready:deck[t]-=1
        deck["m9"]-=3  # source discard + peng claimant 2
        source=["m9"]
        claimant=["m9","m9"]
        for hand,length in ((source,14),(claimant,13)):
            for t in TILES:
                while deck[t] and len(hand)<length:
                    hand.append(t);deck[t]-=1
        g=staged_game({d:source,peng_seat:claimant,hu_seat:ready},
                      {d:"p",peng_seat:"p",hu_seat:"p"})
        g.discard(d,"m9")
        self.assertIn("peng",g.claim_options(peng_seat))
        self.assertIn("hu",g.claim_options(hu_seat))
        for seat in range(4):
            if seat==d:continue
            action=("peng" if seat==peng_seat else
                    "hu" if seat==hu_seat else "pass")
            g.respond_discard(seat,action)
        self.assertEqual(g.public_state()["winners"][0]["seat"],hu_seat)
        self.assertEqual(g.private_view(peng_seat)["own_melds"],[])
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_three_winners_end_without_another_draw(self):
        g=FourPlayerOpening(42)
        d=g.dealer
        winning=["m1"]*3+["m4"]*3+["s1"]*3+["s4"]*3+["s9"]*2
        g=staged_game({d:winning},{d:"p"})
        others=[s for s in range(4) if s!=d]
        g._won[others[0]]=True
        g._won[others[1]]=True
        wall_before=g.public_state()["wall_count"]
        g.declare_self_win(d)
        self.assertEqual(g.phase,"finished")
        self.assertIsNone(g.turn)
        self.assertEqual(g.public_state()["wall_count"],wall_before)
        self.assertEqual(g.public_state()["won"].count(True),3)
        with self.assertRaises(ValueError):
            g.draw(others[2])
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_illegal_ron_and_duplicate_response_do_not_corrupt_deck(self):
        g=deal_for_ron()
        d=g.dealer
        s3=(d+3)%4
        g.discard(d,"s9")
        with self.assertRaises(ValueError):
            g.respond_discard(s3,"hu")
        with self.assertRaises(ValueError):
            g.respond_discard(d,"pass")
        self.assertEqual(g.public_state()["claim_submitted"],[])
        g.respond_discard(s3,"pass")
        with self.assertRaises(ValueError):
            g.respond_discard(s3,"pass")
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_peng_transfers_discard_and_claimant_must_cut_without_draw(self):
        g=FourPlayerOpening(17)
        d=g.dealer
        receiver=(d+1)%4
        # Four distinct hand setups with 2 of m9 in receiver and 1 in dealer.
        original=Counter({t:4 for t in TILES})
        source=["m9"]; original["m9"]-=1
        claimant=["m9"]*2; original["m9"]-=2
        for seat in (d,receiver):
            target=source if seat==d else claimant
            size=14 if seat==d else 13
            for tile in TILES:
                while original[tile] and len(target)<size:
                    target.append(tile);original[tile]-=1
        g=staged_game({d:source,receiver:claimant},
                      {d:"p",receiver:"p"},seed=17)
        # The other players might have valid claims, but all explicitly pass.
        g.discard(d,"m9")
        self.assertIn("peng",g.claim_options(receiver))
        for seat in range(4):
            if seat==d:continue
            g.respond_discard(seat,"peng" if seat==receiver else "pass")
        self.assertEqual(g.phase,"await_discard")
        self.assertEqual(g.turn,receiver)
        self.assertEqual(g.private_view(receiver)["own_melds"],
                         [{"type":"peng","tile":"m9"}])
        self.assertEqual(g.debug_tile_counts()["total"],108)
        self.assertEqual(g._effective(receiver),14)
        with self.assertRaises(ValueError):
            g.draw(receiver)
        self.assertEqual(g.public_state()["discards"][-1]["claimed_by"],receiver)
        g.discard(receiver,g.private_view(receiver)["hand"][0])
        self.assertEqual(g.phase,"claim_window")
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_ming_gang_takes_tail_supplement_and_claimant_cuts(self):
        d=FourPlayerOpening(19).dealer
        p=(d+1)%4
        g=FourPlayerOpening(19)
        counts=Counter({t:4 for t in TILES})
        source=["m9"]; counts["m9"]-=1
        contestant=["m9"]*3; counts["m9"]-=3
        for seat,hand in ((d,source),(p,contestant)):
            size=14 if seat==d else 13
            for tile in TILES:
                while counts[tile] and len(hand)<size:
                    hand.append(tile);counts[tile]-=1
        g=staged_game({d:source,p:contestant},{d:"p",p:"p"},seed=19)
        old_tail=g._wall[-1]
        g.discard(d,"m9")
        self.assertIn("ming_gang",g.claim_options(p))
        for seat in range(4):
            if seat!=d:
                g.respond_discard(seat,"ming_gang" if seat==p else "pass")
        self.assertEqual(g.phase,"await_discard")
        self.assertEqual(g.turn,p)
        self.assertIn(old_tail,g.private_view(p)["hand"])
        self.assertEqual(g.public_state()["wall_count"],54)
        self.assertEqual(g._effective(p),14)
        self.assertEqual(g._melds[p],[{"type":"ming_gang","tile":"m9"}])
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_concealed_gang_hidden_from_public_and_tail_supplement(self):
        g=FourPlayerOpening(19)
        d=g.dealer
        deck=Counter({t:4 for t in TILES})
        source=["m9"]*4
        for tile in source:deck[tile]-=1
        for tile in TILES:
            while deck[tile] and len(source)<14:
                source.append(tile);deck[tile]-=1
        g=staged_game({d:source},{d:"p"},seed=19)
        old_tail=g._wall[-1]
        self.assertIn({"type":"an_gang","tile":"m9"},g.kong_options(d))
        with self.assertRaises(ValueError):
            g.declare_kong(d,"bu_gang","m9")
        g.declare_kong(d,"an_gang","m9")
        self.assertEqual(g.phase,"await_discard")
        self.assertEqual(g._effective(d),14)
        self.assertEqual(g.private_view(d)["own_melds"][0]["tile"],"m9")
        self.assertIsNone(g.public_state()["melds"][d][0]["tile"])
        self.assertIn(old_tail,g.private_view(d)["hand"])
        self.assertEqual(g.public_state()["wall_count"],54)
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_supplement_kong_window_with_no_rob_upgrades_after_passes(self):
        g=FourPlayerOpening(42); d=g.dealer
        game=staged_game({})
        d=game.dealer
        tile=game.private_view(d)["hand"][0]
        # Install a physically valid PENG+4th in source while preserving all
        # remaining cards; only other three players can ever rob.
        suit="m" if tile[0]!="m" else "s"
        target="m9"
        from collections import Counter
        pool=Counter({t:4 for t in TILES})
        pool[target]-=4
        dealer_hand=[target]
        for t in TILES:
            while pool[t] and len(dealer_hand)<11:
                dealer_hand.append(t);pool[t]-=1
        game._hands[d]=dealer_hand
        game._melds[d]=[{"type":"peng","tile":target}]
        for s in range(4):
            if s==d:continue
            hand=[]
            for t in TILES:
                while pool[t] and len(hand)<13:
                    hand.append(t);pool[t]-=1
            game._hands[s]=hand
        game._wall=[t for t in TILES for _ in range(pool[t])]
        game.missing_suits=["p"]*4
        game._assert_physical_tiles()
        self.assertIn({"type":"bu_gang","tile":target},game.kong_options(d))
        game.declare_kong(d,"bu_gang",target)
        self.assertEqual(game.phase,"rob_kong_window")
        self.assertEqual(game.public_state()["pending_rob_kong"]["tile"],target)
        for s in range(4):
            if s!=d:game.respond_rob_kong(s,"pass")
        self.assertEqual(game.phase,"await_discard")
        self.assertEqual(game._melds[d][0]["type"],"bu_gang")
        self.assertEqual(game._effective(d),14)
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_self_win_retired_player_skipped_and_seat_guarded(self):
        g=deal_for_ron()
        d=g.dealer
        # Winning hand after self draw, no missing-suit tiles.
        winning=["m1"]*3+["m4"]*3+["s1"]*3+["s4"]*3+["s9"]*2
        # Fixture is complete, reconstruct rest from a complete physical pool.
        pool=Counter({t:4 for t in TILES})
        for t in winning:pool[t]-=1
        others={}
        for s in range(4):
            if s==d:continue
            hand=[]
            for t in TILES:
                while pool[t] and len(hand)<13:
                    hand.append(t);pool[t]-=1
            others[s]=hand
        g=staged_game({d:winning,**others},{d:"p"})
        self.assertTrue(g.private_view(d)["can_self_draw_win"])
        g.declare_self_win(d)
        self.assertTrue(g.public_state()["won"][d])
        self.assertEqual(g.phase,"await_draw")
        self.assertEqual(g.turn,(d+1)%4)
        self.assertEqual(g.debug_tile_counts()["total"],108)
        with self.assertRaises(ValueError):
            g.discard(d,"s9")

    def test_rob_kong_winners_cancel_upgrade_and_keep_real_fourth_tile(self):
        g=FourPlayerOpening(42)
        d=g.dealer
        r=(d+1)%4
        # Three melds + pair + open-taatsu m7 m8: added m9 makes sequence.
        ready=["m1"]*3+["m4"]*3+["s1"]*3+["s4"]*2+["m7","m8"]
        deck=Counter({t:4 for t in TILES})
        for t in ready:deck[t]-=1
        deck["m9"]-=4
        # Start with a legal 14-tile dealer and move three concealed
        # cards to wall after installing the peng meld.
        source=["m9"]
        for t in TILES:
            while deck[t] and len(source)<14:
                source.append(t);deck[t]-=1
        g=staged_game({d:source,r:ready},{d:"p",r:"p"})
        # Ensure the three copies not in dealer's hand are in the wall,
        # rather than incorrectly being dealt to an unrelated filler seat.
        for s in range(4):
            if s in (d,r):continue
            for _ in range(g._hands[s].count("m9")):
                g._hands[s].remove("m9")
                g._hands[s].append(g._wall.pop(0))
                g._wall.append("m9")
        g._melds[d]=[{"type":"peng","tile":"m9"}]
        g._wall.extend(g._hands[d][-3:])
        del g._hands[d][-3:]
        for _ in range(3):g._wall.remove("m9")
        g._assert_physical_tiles()
        self.assertEqual(g._effective(d),14)
        g.declare_kong(d,"bu_gang","m9")
        self.assertIn("hu",g.rob_options(r))
        for s in range(4):
            if s!=d:g.respond_rob_kong(s,"hu" if s==r else "pass")
        self.assertEqual(g._melds[d],[{"type":"peng","tile":"m9"}])
        self.assertEqual(g.phase,"await_draw")
        self.assertIn(r,[x["seat"] for x in g.public_state()["winners"]])
        self.assertEqual(g.public_state()["events"][-1]["type"],"rob_kong")
        self.assertEqual(g.debug_tile_counts()["total"],108)


if __name__=="__main__":
    unittest.main()
