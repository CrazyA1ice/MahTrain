"""M3.88 period-complete history and completed-only private-hand reveal."""
from __future__ import annotations
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mahtrain_core.four_player import FourPlayerOpening
from mahtrain_core.match_archive import MatchArchive
from mahtrain_core.post_round_review import completed_review,record_transition
from mahtrain_core.rules import TILES

class ArchiveReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=MatchArchive(Path(self.temp.name)/"history.db")

    def tearDown(self):
        self.temp.cleanup()

    def saved(self,seed=17,private=None):
        game=FourPlayerOpening(seed)
        start=game.public_state()
        end={**start,"phase":"finished"}
        board={key:start[key] for key in
            ("phase","turn","hand_counts","wall_count",
             "melds","discards","won")}
        step={"board":board,"events":[{"type":"draw","seat":1}]}
        return self.store.save_completed(end,[step],start,
            ["basic","advanced","challenge"],sealed_review=private)

    def test_new_completed_archive_reveals_all_four_real_hands_without_wall(self):
        game=FourPlayerOpening(34)
        hands=[list(x) for x in game._hands]
        saved=self.saved(17,[{"hands":hands}])
        report=self.store.detail(saved)["report"]
        self.assertEqual(report["version"],2)
        self.assertEqual(report["privacy"],"post_round_full_reveal")
        review=report["post_round_review"]
        self.assertEqual(review["frames"][0]["hands"],hands)
        self.assertEqual(sum(len(x) for x in hands),53)
        raw=json.dumps(report)
        for forbidden in ('"_wall"','"future_wall"','"seed"','"match_token"'):
            self.assertNotIn(forbidden,raw)
        self.assertEqual(self.store.four_seat_scorecard()["valid_games"],1)

    def test_prior_public_only_history_cannot_fabricate_hands(self):
        saved=self.saved()
        result=self.store.detail(saved)["report"]
        self.assertEqual(result["privacy"],"public_board_only")
        self.assertNotIn("post_round_review",result)

    def test_reject_misaligned_or_untrusted_reveal(self):
        with self.assertRaisesRegex(ValueError,"align"):
            self.saved(17,[])
        hands=[["m1"]*15,[],[],[]]
        with self.assertRaisesRegex(ValueError,"invalid completed"):
            self.saved(17,[{"hands":hands}])
        with self.assertRaisesRegex(ValueError,"only completed"):
            g=FourPlayerOpening(8)
            self.store.save_completed(g.public_state(),[],g.public_state(),
                  ["basic"]*3,sealed_review=[])

    def test_real_rule_transition_seals_every_seat_before_public_http(self):
        import web_server
        from test_four_player import to_dealer_turn
        game=to_dealer_turn(27)
        seat=game.turn
        before=list(game._hands[seat])
        game._sealed_review=[]
        outgoing=[]
        played=before[0]
        web_server._match_record(
            game,outgoing,lambda:game.discard(seat,played))
        self.assertEqual(len(outgoing),1)
        self.assertEqual(len(game._sealed_review),1)
        self.assertEqual(game._sealed_review[0]["decision"]["seat"],seat)
        self.assertEqual(game._sealed_review[0]["decision"]["played"],played)
        self.assertEqual(game._sealed_review[0]["decision"]["hand"],before)
        self.assertEqual(len(game._sealed_review[0]["hands"]),4)
        public=json.dumps(outgoing)
        self.assertNotIn('"decision"',public)
        self.assertNotIn('"hands"',public)
        self.assertNotIn('"future_wall"',public)
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_top_three_and_compliance_are_based_on_actual_pre_cut(self):
        # Synthetic but physically plausible full hand, one forced-suit cut.
        g=FourPlayerOpening(57)
        player=g.dealer
        hand=list(g._hands[player])
        missing=hand[0][0]
        before={"seat":0,"played":hand[0],"hand":hand,"melds":[],
                "missing":missing,"visible":[]}
        review=completed_review([{"hands":[list(x) for x in g._hands],
                                  "decision":before}])
        decision=review["decisions"][0]
        self.assertEqual(decision["played"],hand[0])
        self.assertTrue(decision["top_three"])
        self.assertLessEqual(len(decision["top_three"]),3)
        self.assertTrue(all(x["discard"][0]==missing
                            for x in decision["top_three"]))
        self.assertEqual(review["player0"]["compared"],1)
        self.assertIn(review["player0"]["rate"],(0.0,100.0))
        self.assertTrue(decision["played_rank"]>=1)

    def test_periods_apply_consistently_to_scorecard_grouping_and_list(self):
        first=self.saved(17)
        second=self.saved(18)
        third=self.saved(19)
        now=datetime.now(timezone.utc)
        with sqlite3.connect(self.store.path) as db:
            for archive_id,days in ((first,500),(second,20),(third,2)):
                stamp=(now-timedelta(days=days)).isoformat(timespec="seconds")
                db.execute("UPDATE completed_matches SET created_at=? WHERE archive_id=?",
                           (stamp,archive_id))
        checks={"all":3,"year":2,"month":2,"week":1}
        for name,count in checks.items():
            with self.subTest(period=name):
                response=self.store.list_completed(1,period=name)
                self.assertEqual(response["summary"]["games"],count)
                self.assertEqual(response["scorecard"]["valid_games"],count)
                self.assertEqual(len(response["scorecard"]["trend"]),count)
                self.assertEqual(len(response["matches"]),1)
                self.assertEqual(response["has_more"],count>1)
                self.assertEqual(self.store.four_seat_scorecard(
                    period=name,trend_limit=None)["valid_games"],count)
        last=self.store.list_completed(1,period="all",offset=2)
        self.assertEqual(len(last["matches"]),1)
        self.assertFalse(last["has_more"])
        with self.assertRaises(ValueError):self.store.list_completed(period="lifetime")
        with self.assertRaises(ValueError):self.store.list_completed(offset=-1)

if __name__=="__main__":unittest.main()
