"""M3.94 regression tests: ties are not regrets, holdout is independent."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]

from mahtrain_core.ai import MahjongAgent
from mahtrain_core.ai_challenge_regret_holdout import (
    PROTOCOL, REASONS, REGRET_REASONS, RegretOnlyResearchAgent,
    classify_disagreement, _cluster_bootstrap, _pair, study,
)

def candidate(tile, *, best=False, shanten=1, copies=5, fan=None):
    return {
        "discard":tile,"reference_best":best,
        "shanten":shanten,"effective_tile_count_upper_bound":copies,
        "fan_weighted_unknown_copies":fan,
    }


class GenuineRegretHoldoutTests(unittest.TestCase):
    def test_identical_best_and_distinct_but_equal_best_are_not_errors(self):
        first=candidate("m1",best=True,copies=8)
        second=candidate("m2",best=True,copies=8)
        self.assertEqual(classify_disagreement([first,second],"m1"),
                         ("agreed_first","m1"))
        self.assertEqual(classify_disagreement([first,second],"m2"),
                         ("equal_best_other_tile","m1"))
        self.assertEqual(classify_disagreement([],"m2"),("unscored",None))
        with self.assertRaises(ValueError):
            classify_disagreement([first],"m2")
        with self.assertRaises(ValueError):
            classify_disagreement([candidate("m1")],"m1")

    def test_distinct_suboptimal_reasons(self):
        cases=[
            ([candidate("m1",best=True,shanten=0,copies=7,fan=20),
              candidate("m2",shanten=1,copies=10)],"shanten_gap"),
            ([candidate("m1",best=True,shanten=0,copies=5,fan=16),
              candidate("m2",shanten=0,copies=9,fan=10)],
             "tenpai_fan_weighted_gap"),
            ([candidate("m1",best=True,shanten=0,copies=8,fan=16),
              candidate("m2",shanten=0,copies=4,fan=16)],
             "tenpai_ukeire_gap"),
            ([candidate("m1",best=True,copies=12),
              candidate("m2",copies=8)],"ukeire_gap"),
            ([candidate("m1",best=True,copies=8),
              candidate("m2",copies=8)],"other_reference_gap"),
        ]
        for cuts,reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(classify_disagreement(cuts,"m2"),
                                 (reason,"m1"))

    def test_research_agent_does_not_override_equal_best_tie(self):
        agent=RegretOnlyResearchAgent(seed=10,seat=1)
        agent._last_discard_scores=None
        view={"hand":["m1","m2"],"seat":1}
        advice={"candidates":[candidate("m1",best=True,copies=8),
                              candidate("m2",best=True,copies=8)]}
        with patch.object(MahjongAgent,"discard",return_value="m2"),patch(
                "mahtrain_core.ai_challenge_regret_holdout.classic_archive_seat_hint",
                return_value=advice):
            chosen=agent.discard(view)
        self.assertEqual(chosen,"m2","different top tile does NOT imply a mistake")
        self.assertEqual(agent.safe_counts()["changed_cuts"],0)
        self.assertEqual(agent.safe_counts()["equal_best_other_tile"],1)
        self.assertEqual(agent.safe_counts()["decisions"],1)

    def test_true_regret_changes_cut_and_risk_count_is_descriptive(self):
        bot=RegretOnlyResearchAgent(seed=12,seat=2)
        bot._last_discard_scores=[
            {"discard":"m2","expected_fan_weighted_copies":8.,
             "effective_tile_count":7},
            {"discard":"m1","expected_fan_weighted_copies":9.,
             "effective_tile_count":11},
        ]
        view={"hand":["m1","m2"],"seat":2}
        advice={"candidates":[candidate("m1",best=True,copies=11),
                              candidate("m2",copies=7)]}
        with patch.object(MahjongAgent,"discard",return_value="m2"),patch(
                "mahtrain_core.ai_challenge_regret_holdout.classic_archive_seat_hint",
                return_value=advice):
            changed=bot.discard(view)
        self.assertEqual(changed,"m1")
        count=bot.safe_counts()
        self.assertEqual(count["changed_cuts"],1)
        self.assertEqual(count["ukeire_gap"],1)
        self.assertEqual(count["regret_and_risk_flip"],1)
        self.assertEqual(count["risk_flip_from_reference"],1)
        self.assertEqual(count["decisions"],sum(count[k] for k in REASONS))
        self.assertEqual(count["changed_cuts"],sum(count[k] for k in REGRET_REASONS))
        self.assertNotIn("m1",str(count))
        self.assertNotIn("hand",str(count))

    def test_seed_holdout_rejects_overlap_bool_and_out_of_bounds(self):
        for kw in (
            {"development_start":9400,"holdout_start":9401,"seeds_per_group":2},
            {"development_start":True},{"holdout_start":True},
            {"seeds_per_group":True},{"seeds_per_group":0},
            {"seeds_per_group":17},{"rotations":True},{"rotations":0},
            {"development_start":-1},
            {"holdout_start":2**32-1,"seeds_per_group":2},
        ):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                study(**kw)

    def test_independent_cluster_bootstrap_is_deterministic(self):
        first=_cluster_bootstrap([0.,100.,-50.])
        self.assertEqual(first,_cluster_bootstrap([0.,100.,-50.]))
        self.assertEqual(first["independent_seeds"],3)
        self.assertGreaterEqual(first["lower"],-50.)
        self.assertLessEqual(first["upper"],100.)
        self.assertIn("Exploratory",first["warning"])

    def test_mocked_development_and_holdout_partition_stay_separate(self):
        calls=[]
        def fake(seed,rotation):
            calls.append((seed,rotation))
            blank={k:0 for k in REASONS}
            blank["agreed_first"]=2
            blank.update({"decisions":2,"changed_cuts":0})
            return {
                "seed":seed,"rotation":rotation,"seat":rotation,
                "baseline":{"official_net":0,"wins":0,"deal_ins":0},
                "regret_only":{"official_net":rotation,"wins":0,"deal_ins":0},
                "delta_net":rotation,"decision_counts":blank,
            }
        with patch("mahtrain_core.ai_challenge_regret_holdout._pair",
                   side_effect=fake):
            report=study(development_start=100,holdout_start=200,
                         seeds_per_group=2,rotations=4)
        self.assertEqual(len(calls),16)
        self.assertEqual(set(s for s,_ in calls),{100,101,200,201})
        self.assertEqual(report["protocol"],PROTOCOL)
        self.assertTrue(report["holdout_predeclared"])
        self.assertFalse(report["live_ai_modified"])
        for name in ("development","holdout"):
            group=report[name]
            self.assertEqual(group["paired_games"],8)
            self.assertEqual(group["mean_delta_net"],1.5)
            self.assertEqual(group["decision_counts"]["decisions"],16)
            self.assertEqual(group["decision_counts"]["changed_cuts"],0)
            self.assertEqual(group["cluster_interval_exploratory"]["independent_seeds"],2)

    def test_one_real_four_seat_rules_pair_keeps_official_zero_sum(self):
        original=_pair(8407,0)
        again=_pair(8407,0)
        self.assertEqual(original,again)
        self.assertEqual(original["seed"],8407)
        self.assertEqual(original["seat"],0)
        self.assertEqual(original["delta_net"],
                         original["regret_only"]["official_net"]-
                         original["baseline"]["official_net"])
        counts=original["decision_counts"]
        self.assertGreater(counts["decisions"],0)
        self.assertEqual(counts["decisions"],sum(counts[k] for k in REASONS))
        self.assertEqual(counts["changed_cuts"],
                         sum(counts[k] for k in REGRET_REASONS))
        self.assertNotIn("trace",original)
        self.assertNotIn("hands_before",json.dumps(original))


if __name__=="__main__":
    unittest.main()
