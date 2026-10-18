"""M3.5 same-state AI benchmarking and public-only defensive tie-break."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from mahtrain_core.ai import AI_LEVELS, MahjongAgent, public_suit_pressure
from mahtrain_core.ai_benchmark import benchmark, sample_views
from mahtrain_core.four_player import FourPlayerOpening


class AIBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=benchmark(seed_start=0,seeds=2)

    def test_all_tiers_evaluated_on_the_identical_samples(self):
        report=self.report
        self.assertEqual(report["protocol"],"paired_same_public_position_v1")
        n=report["usable_positions"]
        self.assertGreaterEqual(n,2)
        self.assertEqual(n+report["skipped_already_winning"],
                         report["samples_generated"])
        pairs=[]
        for level in AI_LEVELS:
            records=report["levels"][level]["decisions_detail"]
            self.assertEqual(len(records),n)
            selected=[(r["seed"],r["scenario"]) for r in records]
            if not pairs:
                pairs=selected
            else:
                self.assertEqual(selected,pairs)
            for record in records:
                self.assertGreaterEqual(record["shanten_regret"],0)
                self.assertIn(record["chosen_shanten"],
                              range(record["minimum_shanten"],8))
                self.assertGreaterEqual(record["decision_ms"],0.0)
                if record["best_ukeire"]:
                    self.assertTrue(record["best_shanten"])
                    self.assertEqual(
                        record["chosen_effective_copies"],
                        record["best_effective_copies_at_minimum"])

    def test_experts_retain_minimum_shanten_on_controlled_no_missing(self):
        for level in ("advanced","challenge"):
            records=self.report["levels"][level]["decisions_detail"]
            controlled=[r for r in records if r["scenario"]=="controlled_no_missing"]
            self.assertTrue(controlled)
            for record in controlled:
                self.assertEqual(record["shanten_regret"],0)
                if level=="challenge":
                    self.assertGreaterEqual(record["chosen_effective_copies"],0)
                    # Scoring value can legitimately beat maximum ukeire.

    def test_rates_and_report_json_are_auditable(self):
        report=self.report
        self.assertIn("not a game win-rate estimate",report["limitations"])
        json.dumps(report,ensure_ascii=False)
        for level in AI_LEVELS:
            data=report["levels"][level]
            records=data["decisions_detail"]
            self.assertEqual(
                data["best_shanten_rate"],
                round(sum(r["best_shanten"] for r in records)/len(records),4))
            self.assertEqual(
                data["best_ukeire_rate"],
                round(sum(r["best_ukeire"] for r in records)/len(records),4))
            self.assertGreaterEqual(data["average_decision_ms"],0)

    def test_seed_samples_replay_without_hidden_wall_in_agent_view(self):
        one=sample_views(17,1)
        two=sample_views(17,1)
        self.assertEqual(one,two)
        for item in one:
            view=item["view"]
            self.assertEqual(len(view["hand"]),14)
            self.assertNotIn("future_wall",view)
            self.assertNotIn("opponent_hands",view)
            if item["scenario"]=="controlled_no_missing":
                missing=view["missing_suits"][view["seat"]]
                self.assertFalse(any(t.startswith(missing) for t in view["hand"]))
        with self.assertRaises(ValueError):
            sample_views(-1,2)
        with self.assertRaises(ValueError):
            sample_views(0,0)
        with self.assertRaises(ValueError):
            sample_views(0,1001)
        with self.assertRaises(ValueError):
            sample_views(True,2)

    def test_challenge_uses_expected_value_ranking_on_min_shanten(self):
        hand=["m1","m1","m2","m2","m3","m3","m4",
              "s1","s1","s2","s2","s3","s3","s4"]
        view={
            "seat":0,"hand":hand,"own_melds":[],"phase":"dealer_discard",
            "missing_suits":["p","p","p","p"],
            "won":[False]*4,"melds":[[],[],[],[]],"discards":[],
        }
        decision=MahjongAgent("challenge",seed=1,seat=0)
        with patch("mahtrain_core.ai._cut_shanten",return_value=1):
            with patch("mahtrain_core.ai.challenge_discard_scores",
                       return_value=[{"discard":"s1"}]) as score:
                self.assertEqual(decision.discard(view),"s1")
                # All candidates passed to EV evaluator were minimum-shanten.
                self.assertEqual(set(score.call_args.args[1]),set(hand))
        with patch("mahtrain_core.ai._cut_shanten",return_value=1):
            with patch("mahtrain_core.ai.challenge_discard_scores",
                       return_value=[{"discard":"m1"}]):
                self.assertEqual(decision.discard(view),"m1")

    def test_public_open_meld_suit_pressure_only_active_and_visible(self):
        game=FourPlayerOpening(42)
        view=game.private_view(0)
        view["missing_suits"]=["p","p","s","p"]
        view["won"]=[False]*4
        view["melds"]=[
            [],[{"type":"peng","tile":"m3"},{"type":"ming_gang","tile":"m5"}],
            [{"type":"an_gang","tile":None},{"type":"peng","tile":"m2"}],
            [{"type":"peng","tile":"s2"},{"type":"peng","tile":"s7"}],
        ]
        self.assertEqual(public_suit_pressure("m4",view),1)
        self.assertEqual(public_suit_pressure("s3",view),1)
        self.assertEqual(public_suit_pressure("p8",view),0)
        view["won"][1]=True
        self.assertEqual(public_suit_pressure("m4",view),0)
        view["won"][1]=False
        view["missing_suits"][1]="m"
        self.assertEqual(public_suit_pressure("m4",view),0)
        view["missing_suits"][1]="p"
        # Injected invented hidden data cannot change the public-only risk
        extra=copy.deepcopy(view)
        extra["future_wall"]=["m4"]*4
        extra["opponent_hands"]=[["m4"]*13]*3
        self.assertEqual(public_suit_pressure("m4",view),
                         public_suit_pressure("m4",extra))
        with self.assertRaises(ValueError):
            public_suit_pressure("dragon",view)


if __name__=="__main__":
    unittest.main()
