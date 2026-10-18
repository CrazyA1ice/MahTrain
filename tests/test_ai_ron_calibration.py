"""M3.57 candidate-specific true ron labels and public-only seed-split research."""
from __future__ import annotations

import copy
import json
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.ai_ron_calibration import (
    NAMES, SAFE_INDEX, PROTOCOL, public_candidate_features,
    _sealed_target_payoffs, collect_ron_labels, fit_ron_model,
    evaluate_candidate_ron, run_candidate_ron_pilot,
)


def visible():
    return {
        "seat":0,"phase":"await_discard","wall_count":21,
        "hand":["m1","m2","m3","m4","m5","m6","m7",
                "m8","m9","s1","s2","s3","s4","s5"],
        "missing_suits":["p","p","m","s"],"won":[False]*4,
        "melds":[[],[{"type":"peng","tile":"s7"}],[],[]],
        "discards":[{"seat":1,"tile":"m4"},
                    {"seat":1,"tile":"s8"},
                    {"seat":2,"tile":"p1"}],
    }


def data(seed, label, safe=False):
    x=list(public_candidate_features(visible(),1,"s2"))
    x[SAFE_INDEX]=float(safe)
    return {
        "seed":seed,"features":tuple(x),"ron":int(label),
        "payout_multiplier":(4 if label else 0),
    }


class CandidateSpecificRonTests(unittest.TestCase):
    def test_candidate_features_use_public_and_own_tiles_not_hidden_state(self):
        view=visible()
        original=public_candidate_features(view,1,"s2")
        injected=copy.deepcopy(view)
        injected.update({
            "_hands":[["m9"]*14]*4,
            "opponent_hands":[["s2"]*13]*3,
            "private_draw":"s2",
            "future_wall":["s2"]*60,
            "match_seed":99,
        })
        self.assertEqual(original,public_candidate_features(injected,1,"s2"))
        self.assertEqual(len(original),len(NAMES))
        self.assertTrue(all(0<=v<=1 for v in original))
        self.assertEqual(original[SAFE_INDEX],0)
        changed=copy.deepcopy(view)
        changed["missing_suits"][1]="s"
        self.assertEqual(public_candidate_features(changed,1,"s2")[SAFE_INDEX],1)
        changed=copy.deepcopy(view)
        changed["discards"].append({"seat":1,"tile":"s2"})
        self.assertNotEqual(original,public_candidate_features(changed,1,"s2"))
        with self.assertRaises(ValueError):
            public_candidate_features(view,0,"s2")
        with self.assertRaises(ValueError):
            public_candidate_features(view,1,"flower")
        with self.assertRaises(ValueError):
            public_candidate_features(view,1,"p1")
        forced=copy.deepcopy(view)
        forced["hand"][0]="p4"
        with self.assertRaises(ValueError):
            public_candidate_features(forced,1,"s2")
        self.assertEqual(public_candidate_features(forced,1,"p4")[SAFE_INDEX],0)

    def test_sealed_target_payoffs_use_true_waits_and_game_fan_rules(self):
        target=1
        hand=["m1","m2","m3","m4","m5","m6","m7",
              "m8","m9","s1","s1","s1","s2"]
        game=SimpleNamespace(
            _won=[False]*4,
            _hands=[[],hand[:],[],[]],
            _melds=[[],[],[],[]],
            missing_suits=["p"]*4,
            _tian_ting=[{"eligible":False} for _ in range(4)],
            ledger=SimpleNamespace(fan_cap=3),
        )
        payoffs=_sealed_target_payoffs(game,target)
        self.assertIn("s2",payoffs)
        self.assertGreaterEqual(payoffs["s2"],1)
        self.assertNotIn("m9",payoffs)
        game._won[target]=True
        self.assertIsNone(_sealed_target_payoffs(game,target))
        game._won[target]=False
        game._hands[target].append("m1")
        self.assertIsNone(_sealed_target_payoffs(game,target))

    def test_collector_only_seals_numeric_labels_and_filters_illegal_cuts(self):
        hand=["m1","m2","m3","m4","m5","m6","m7",
              "m8","m9","s1","s1","s1","s2"]
        fixture=SimpleNamespace(
            turn=0,_won=[False,False,True,True],
            _hands=[[],hand[:],[],[]],
            _melds=[[],[],[],[]],
            missing_suits=["p"]*4,
            _tian_ting=[{"eligible":False} for _ in range(4)],
            ledger=SimpleNamespace(fan_cap=3),
        )
        fixture.private_view=lambda seat: dict(visible(),seat=seat,
                         won=[False,False,True,True],
                         missing_suits=["p"]*4, melds=[[],[],[],[]])
        def simulated(seed,rotation,offline_observer):
            self.assertEqual(seed,41)
            self.assertEqual(rotation,41%3)
            for _ in range(4):
                offline_observer(fixture)
            return {"trace":[],"public_replay":[]}
        with patch("mahtrain_core.ai_ron_calibration.simulate_match",
                   side_effect=simulated):
            rows=collect_ron_labels(41,stride=2)
        self.assertGreaterEqual(len(rows),20)
        self.assertTrue(all(row["seed"]==41 for row in rows))
        self.assertEqual(sum(row["ron"] for row in rows),2)
        self.assertTrue(all("tile" not in row and "hand" not in row
                            and "target" not in row for row in rows))
        self.assertTrue(all(row["payout_multiplier"]>=row["ron"]
                            for row in rows))
        self.assertNotIn("s2",json.dumps(rows))
        with self.assertRaises(ValueError):
            collect_ron_labels(True)
        with self.assertRaises(ValueError):
            collect_ron_labels(41,stride=0)

    def test_brier_rule_safe_baseline_and_multiplier_mse(self):
        rows=[data(1,1),data(1,0),data(2,0,safe=True)]
        report=evaluate_candidate_ron(rows,None,actionable_prior=.5,
                                       conditional_multiplier=4)
        self.assertEqual(report["n"],3)
        self.assertEqual(report["ron_events"],1)
        self.assertEqual(report["actionable_n"],2)
        self.assertAlmostEqual(report["brier"],(0.25+0.25)/3)
        self.assertAlmostEqual(report["payout_multiplier_mse"],8/3)
        self.assertEqual(sum(b["n"] for b in report["reliability"]),3)
        with self.assertRaises(ValueError):
            evaluate_candidate_ron(rows,None,actionable_prior=1.2,
                                   conditional_multiplier=4)
        with self.assertRaises(ValueError):
            evaluate_candidate_ron(rows,[0.]*2,actionable_prior=.5,
                                   conditional_multiplier=4)
        bad=data(3,1,safe=True)
        with self.assertRaises(ValueError):
            evaluate_candidate_ron([bad],None,actionable_prior=.5,
                                   conditional_multiplier=4)

    def test_model_uses_only_eligible_labels_deterministically(self):
        positives=[data(10,1) for _ in range(9)]
        negatives=[data(10,0) for _ in range(9)]
        for x in negatives:
            y=list(x["features"])
            y[1]=0.
            x["features"]=tuple(y)
        safe=[data(11,0,safe=True) for _ in range(40)]
        rows=positives+negatives+safe
        a=fit_ron_model(rows)
        self.assertEqual(a,fit_ron_model(rows))
        self.assertEqual(len(a),len(NAMES))
        self.assertEqual(a[SAFE_INDEX],0)
        self.assertTrue(all(math.isfinite(v) for v in a))
        with self.assertRaises(ValueError):
            fit_ron_model(safe)
        with self.assertRaises(ValueError):
            fit_ron_model(rows,epochs=False)

    def test_seed_isolation_and_no_export_of_real_player_waits(self):
        def sample(seed,*,stride=4):
            self.assertEqual(stride,2)
            return [data(seed,1),data(seed,0),data(seed,0,safe=True)]
        with patch("mahtrain_core.ai_ron_calibration.collect_ron_labels",
                   side_effect=sample) as called:
            report=run_candidate_ron_pilot([50,51],[52,53],stride=2)
        self.assertEqual(called.call_count,4)
        self.assertEqual(report["protocol"],PROTOCOL)
        self.assertEqual(report["train_n"],6)
        self.assertEqual(report["test_n"],6)
        self.assertEqual(len(report["by_test_seed"]),2)
        self.assertEqual(report["candidate"]["actionable_n"],4)
        self.assertFalse(report["can_claim_generalization"])
        self.assertFalse(report["contains_private_hands"])
        blob=json.dumps(report)
        for forbidden in ('"_hands":','"opponent_hands":','"future_wall":',
                          '"candidate_tile":','"target_seat":',
                          '"raw_observations":','"waits":'):
            self.assertNotIn(forbidden,blob)
        with self.assertRaises(ValueError):
            run_candidate_ron_pilot([50],[50])
        with self.assertRaises(ValueError):
            run_candidate_ron_pilot([50,50],[51])
        with self.assertRaises(ValueError):
            run_candidate_ron_pilot([50],[True])


if __name__=="__main__":
    unittest.main()
