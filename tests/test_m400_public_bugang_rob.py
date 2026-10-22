"""M4.00 tests: public features cannot peek at sealed rob-Hu labels."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]

from mahtrain_core.ai_public_bugang_rob_pilot import (
    PROTOCOL,BANDS,public_bugang_features,
    _sealed_potential_robbers,natural_position,cohort,study,
)


def public_snapshot():
    return {
        "phase":"await_discard","turn":0,"wall_count":35,
        "missing_suits":["p","m","p","m"],
        "won":[False,False,False,False],
        "melds":[
            [{"type":"peng","tile":"s9"}],
            [{"type":"peng","tile":"s1"},{"type":"peng","tile":"s4"}],
            [{"type":"peng","tile":"m3"}],
            [],
        ],
        "discards":[{"seat":1,"tile":"s2"},{"seat":2,"tile":"m2"},
                    {"seat":3,"tile":"p1"}],
    }


class M400PublicRobPotentialTests(unittest.TestCase):
    def test_only_public_meld_exposure_river_dingque_and_wall_matter(self):
        view=public_snapshot()
        frozen=copy.deepcopy(view)
        report=public_bugang_features(view,0,"s9")
        self.assertEqual(view,frozen)
        self.assertEqual(report["band"],"same_suit_focus")
        self.assertEqual(report["wall_band"],"early")
        self.assertEqual(report["active_opponents"],3)
        self.assertEqual(report["dingque_eligible_opponents"],2)
        self.assertEqual(report["same_suit_focus_opponents"],1)
        self.assertEqual(report["same_suit_open_melds"],2)
        self.assertEqual(report["other_public_suit_discards"],1)
        self.assertNotIn("s9",json.dumps(report))
        dirty=copy.deepcopy(view)
        dirty["hand"]=["s9"]*14
        dirty["future_wall"]=["m1"]*50
        dirty["opponent_hands"]=[["s9"]*13]*3
        dirty["_hands"]=[["s9"]*13]*4
        self.assertEqual(report,public_bugang_features(dirty,0,"s9"))
        dirty["hand"]=["p9"]*14
        dirty["future_wall"]=["s1"]*50
        self.assertEqual(report,public_bugang_features(dirty,0,"s9"))

    def test_dingque_structurally_excludes_all_robbers(self):
        board=public_snapshot()
        board["missing_suits"]=["p","s","s","s"]
        answer=public_bugang_features(board,0,"s9")
        self.assertEqual(answer["band"],"dingque_excluded")
        self.assertEqual(answer["dingque_eligible_opponents"],0)
        self.assertEqual(answer["active_opponents"],3)
        board["won"]=[False,True,True,True]
        answer=public_bugang_features(board,0,"s9")
        self.assertEqual(answer["band"],"dingque_excluded")
        self.assertEqual(answer["active_opponents"],0)

    def test_reject_publicly_illegal_bugang_and_bad_turns(self):
        view=public_snapshot()
        for owner,tile in ((True,"s9"),(4,"s9"),(0,"x3"),
                           (0,"s8"),(1,"s9")):
            with self.subTest(owner=owner,tile=tile),self.assertRaises(ValueError):
                public_bugang_features(view,owner,tile)
        for mutation in (
            {"turn":1},{"phase":"rob_kong_window"},
            {"missing_suits":["s","m","p","m"]},
            {"wall_count":0},{"won":[True,False,False,False]},
            {"discards":[{"seat":8,"tile":"p2"}]},
        ):
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                public_bugang_features({**view,**mutation},0,"s9")

    def test_public_features_do_not_read_secret_dict_keys(self):
        class PublicOnly(dict):
            def __getitem__(self,k):
                if k in ("hand","future_wall","opponent_hands","_hands"):
                    raise AssertionError("attempted private read")
                return super().__getitem__(k)
            def get(self,k,default=None):
                if k in ("hand","future_wall","opponent_hands","_hands"):
                    raise AssertionError("attempted private read")
                return super().get(k,default)
        public=PublicOnly(public_snapshot())
        report=public_bugang_features(public,0,"s9")
        self.assertIn(report["band"],BANDS)

    def test_sealed_legality_is_separate_and_never_shown_in_features(self):
        # Three m-triplets, m9 pair and s7/s8 is a 13-tile legal ready
        # hand waiting s9 without privately holding an impossible 5th copy.
        ready=["m1"]*3+["m4"]*3+["m7"]*3+["m9"]*2+["s7","s8"]
        game=SimpleNamespace(
            _won=[False,False,True,True],
            missing_suits=["p","p","s","s"],
            _hands=[[],ready,[],[]],
            _melds=[[],[],[],[]],
        )
        self.assertEqual(_sealed_potential_robbers(game,0,"s9"),1)
        game.missing_suits[1]="s"
        self.assertEqual(_sealed_potential_robbers(game,0,"s9"),0)
        # The independent public predictor is unchanged by any hidden
        # ground-truth labeling data.
        state=public_snapshot()
        a=public_bugang_features(state,0,"s9")
        game._hands[1]=["p9"]*13
        b=public_bugang_features(state,0,"s9")
        self.assertEqual(a,b)

    def test_really_finished_game_satisfies_de_duplication_and_ledgers(self):
        row=natural_position(24000,0)
        self.assertEqual(row["challenge_seat"],0)
        self.assertEqual(row["seed"],24000)
        self.assertEqual(row["offered_windows"],
                         len(row["first_distinct_candidates"])+row["repeated_windows"])
        r=row["attempts"]
        self.assertEqual(r["attempted_bu_gang"],
                         r["successful_bu_gang"]+r["robbed_bu_gang"])
        sc=row["official_score"]
        self.assertEqual(sc["official_net"],sc["win_points"]+
                         sc["kong_points"]+sc["exhaustive_points"])
        raw=json.dumps(row)
        for forbidden in ("opponent_hands","future_wall","_hands",
                          "_wall","s9","offer_signature"):
            self.assertNotIn(forbidden,raw)
        for entry in row["first_distinct_candidates"]:
            f=entry["features"]
            self.assertIn(f["band"],BANDS)
            self.assertLessEqual(entry["potential_robbers"],
                                 f["dingque_eligible_opponents"])

    def test_only_shuffled_seeds_are_independent_no_probability_from_zero_labels(self):
        def fake(seed,rotation):
            self.assertIn(rotation,range(4))
            f={"band":"unresolved","dingque_eligible_opponents":1}
            row={"features":f,"rob_possible":0,"potential_robbers":0}
            return {
                "seed":seed,"rotation":rotation,
                "challenge_seat":(4-rotation)%4,
                "first_distinct_candidates":[row] if rotation==0 else [],
                "offered_windows":3 if rotation==0 else 0,
                "repeated_windows":2 if rotation==0 else 0,
                "attempts":{"attempted_bu_gang":0,
                            "successful_bu_gang":0,
                            "robbed_bu_gang":0,"rob_kong_winners":0},
            }
        with patch("mahtrain_core.ai_public_bugang_rob_pilot.natural_position",
                   side_effect=fake) as run:
            data=cohort(30000,3)
        self.assertEqual(run.call_count,12)
        self.assertEqual(data["four_seat_positions"],12)
        self.assertEqual(data["counts"]["windows"],9)
        self.assertEqual(data["counts"]["repeated"],6)
        self.assertEqual(data["counts"]["first_distinct"],3)
        self.assertEqual(data["predictive_validation_status"],
                         "unestimable_no_positives")
        self.assertIsNone(data["estimated_rob_probability"])

    def test_seed_disjoint_and_report_modes(self):
        for kw in (
            {"holdout":24000},{"holdout":24007},
            {"development":25000},{"development":True},
            {"seeds":0},{"seeds":17},{"seeds":True},
            {"holdout":2**32-4},{"development":-1},
        ):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                study(**kw)
        with patch("mahtrain_core.ai_public_bugang_rob_pilot.cohort",
                   return_value={"independent_seeds":8}) as run:
            data=study()
        self.assertEqual(run.call_count,2)
        self.assertEqual(data["protocol"],PROTOCOL)
        self.assertFalse(data["live_policy_modified"])
        self.assertEqual(data["feature_source"],"public_state_only")
        self.assertEqual(data["development_seed_range"],[24000,24008])
        self.assertEqual(data["holdout_seed_range"],[25000,25008])


if __name__=="__main__":
    unittest.main()
