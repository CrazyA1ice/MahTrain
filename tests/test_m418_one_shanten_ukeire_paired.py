"""M4.18: licensed one-shanten intervention, four-seat pairing, cash tests."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]
from mahtrain_core.ai import MahjongAgent
from mahtrain_core.ai_one_shanten_ukeire_paired import (
    ARMS, PROTOCOL, MIN_ABSOLUTE_EXTRA_COPIES,
    MIN_RELATIVE_COPY_MULTIPLIER, MIN_WEIGHTED_VALUE_RETENTION,
    MAX_PUBLIC_RISK_INCREASE, MIN_PUBLIC_WALL_REMAINING,
    suggest_one_shanten_ukeire, OneShantenUkeireResearchAgent,
    paired_position,cohort,study,
)
from test_ai_calls import offer_kongs


def own_view():
    return {"hand":["m1","m2","m3","m4","m5","s1","s2","s3",
                    "s4","s5","s6","s7","s8","s9"],
            "wall_count":35,"tian_ting":{"eligible":False}}


def ranked(shanten=1):
    return [
        {"discard":"m1","shanten":shanten,"effective_tile_count":12,
         "expected_fan_weighted_copies":14.0,"table_threat_index":.30},
        {"discard":"m2","shanten":shanten,"effective_tile_count":15,
         "expected_fan_weighted_copies":13.5,"table_threat_index":.37},
        {"discard":"m3","shanten":shanten,"effective_tile_count":22,
         "expected_fan_weighted_copies":11.0,"table_threat_index":.1},
    ]


class M418OneShantenUkeireTests(unittest.TestCase):
    def test_frozen_hypothesis_thresholds(self):
        self.assertEqual(MIN_ABSOLUTE_EXTRA_COPIES,2)
        self.assertEqual(MIN_RELATIVE_COPY_MULTIPLIER,1.10)
        self.assertEqual(MIN_WEIGHTED_VALUE_RETENTION,.90)
        self.assertEqual(MAX_PUBLIC_RISK_INCREASE,.12)
        self.assertEqual(MIN_PUBLIC_WALL_REMAINING,9)

    def test_valid_more_effective_copies_preserves_90pct_value(self):
        v=own_view()
        frozen=copy.deepcopy(v)
        result=suggest_one_shanten_ukeire("m1",ranked(),v)
        self.assertEqual(result,("m2","more_visible_effective_copies"))
        self.assertEqual(v,frozen)

    def test_reject_small_absolute_gain_relative_gain_and_loss_of_value(self):
        for tile,key,bad in (
            (1,"effective_tile_count",13),
            (1,"expected_fan_weighted_copies",12.5),
            (1,"table_threat_index",.43),
        ):
            rows=ranked()
            rows[tile][key]=bad
            self.assertEqual(suggest_one_shanten_ukeire(
                "m1",rows,own_view())[0],"m1")
        rows=ranked()
        rows[1]["effective_tile_count"]=13
        rows[0]["effective_tile_count"]=12.5
        # No candidate has both >10% relative and 2 absolute copies.
        with self.assertRaises(RuntimeError):
            suggest_one_shanten_ukeire("m1",rows,own_view())

    def test_must_already_be_one_shanten_not_tenpai_or_two(self):
        for number in (0,2,3):
            self.assertEqual(suggest_one_shanten_ukeire(
                "m1",ranked(number),own_view()),
                ("m1","not_one_shanten"))

    def test_short_wall_or_verified_tian_ting_preserve_baseline(self):
        v=own_view()
        v["wall_count"]=8
        self.assertEqual(suggest_one_shanten_ukeire(
            "m1",ranked(),v)[0],"m1")
        v["wall_count"]=9
        self.assertEqual(suggest_one_shanten_ukeire(
            "m1",ranked(),v)[0],"m2")
        v["tian_ting"]={"eligible":True,"initial_waits":["s9"]}
        self.assertEqual(suggest_one_shanten_ukeire(
            "m1",ranked(),v)[0],"m1")

    def test_no_multiple_authorized_best_cuts_or_misaligned_source(self):
        self.assertEqual(suggest_one_shanten_ukeire(
            "m1",None,own_view()),
            ("m1","not_multiple_minimum_cuts"))
        self.assertEqual(suggest_one_shanten_ukeire(
            "m1",ranked()[:1],own_view())[0],"m1")
        with self.assertRaises(RuntimeError):
            suggest_one_shanten_ukeire("m2",ranked(),own_view())

    def test_reject_worse_shanten_duplicate_unknown_and_nan(self):
        for alternative in (
            dict(ranked()[1],shanten=2),
            dict(ranked()[1],discard="p9"),
            dict(ranked()[1],discard="m1"),
            dict(ranked()[1],effective_tile_count=float("nan")),
            dict(ranked()[1],table_threat_index=-.1),
        ):
            rows=[ranked()[0],alternative]
            with self.subTest(row=alternative),self.assertRaises(RuntimeError):
                suggest_one_shanten_ukeire("m1",rows,own_view())
        v=own_view()
        v["wall_count"]=True
        with self.assertRaises(ValueError):
            suggest_one_shanten_ukeire("m1",ranked(),v)

    def test_deterministic_maximum_available_copies_then_value_and_risk(self):
        rows=ranked()
        rows[2]["expected_fan_weighted_copies"]=13
        rows[2]["effective_tile_count"]=20
        self.assertEqual(suggest_one_shanten_ukeire(
            "m1",rows,own_view())[0],"m3")

    def test_shadow_agent_keeps_true_baseline_and_strict_legal_cut(self):
        v=own_view()
        frozen=copy.deepcopy(v)
        with patch("mahtrain_core.ai.MahjongAgent.discard",return_value="m1"):
            baseline=OneShantenUkeireResearchAgent(
                seed=42,seat=0,arm="baseline")
            candidate=OneShantenUkeireResearchAgent(
                seed=42,seat=0,arm="one_shanten_ukeire")
            baseline._last_discard_scores=ranked()
            candidate._last_discard_scores=ranked()
            self.assertEqual(baseline.discard(v),"m1")
            self.assertEqual(candidate.discard(v),"m2")
        self.assertEqual(baseline.safe_counts().get("actual_changes",0),0)
        self.assertEqual(candidate.safe_counts()["actual_changes"],1)
        self.assertEqual(candidate.safe_counts()["one_shanten_multi"],1)
        self.assertEqual(v,frozen)
        self.assertTrue(candidate._offline_reference_cut)

    def test_live_108_tile_baseline_no_unseen_future_wall(self):
        game,seat,v=offer_kongs()
        a=OneShantenUkeireResearchAgent(seed=77,seat=seat,arm="baseline")
        selected=a.discard(v)
        self.assertEqual(selected,
                         MahjongAgent("challenge",seed=77,seat=seat).discard(v))
        self.assertIn(selected,v["hand"])
        self.assertEqual(game.debug_tile_counts()["total"],108)
        self.assertNotIn("future_wall",json.dumps(a.safe_counts()))

    def test_actual_one_full_paired_match_and_official_cash_components(self):
        p=paired_position(56000,0)
        self.assertEqual((p["seed"],p["rotation"]),(56000,0))
        for arm in ARMS:
            o=p["arms"][arm]["official"]
            self.assertEqual(o["official_net"],sum(o[k] for k in (
                "win_points","kong_points","exhaustive_points")))
        if p["actual_interventions"]==0:
            self.assertTrue(p["identical_if_untouched"])
            self.assertTrue(all(v==0 for v in p["official_deltas"].values()))
        raw=json.dumps(p)
        for forbidden in ('"tile"','"hand"','"opponent_hands"',
                          '"future_wall"','"_trace"','"_events"'):
            self.assertNotIn(forbidden,raw)

    def test_four_seat_paired_money_is_one_independent_shuffle(self):
        def fake(seed,rotation):
            one=int(seed==58000 and rotation==1)
            d={k:0 for k in ("official_net","win_points","kong_points",
                             "exhaustive_points","win_events","deal_in_events",
                             "realized_kongs")}
            d["official_net"]=one*400
            d["win_points"]=one*200
            d["exhaustive_points"]=one*200
            return {
                "seed":seed,"rotation":rotation,
                "challenge_seat":rotation,"actual_interventions":one,
                "official_deltas":d,
                "arms":{
                    "baseline":{"counts":{"total_cuts":5,
                                          "one_shanten_ranked":3,
                                          "one_shanten_multi":2}},
                    "one_shanten_ukeire":{"counts":{
                        "total_cuts":5,"actual_changes":one}},
                },
            }
        with patch("mahtrain_core.ai_one_shanten_ukeire_paired.paired_position",
                   side_effect=fake) as observer:
            output=cohort(58000,2)
        self.assertEqual(observer.call_count,8)
        self.assertEqual(output["independent_shuffle_seeds"],2)
        self.assertEqual(output["complete_official_games"],16)
        self.assertEqual(output["actual_discard_interventions"],1)
        self.assertEqual(output["independent_seeds_with_interventions"],1)
        self.assertEqual(output["mean_four_seat_net_delta"],50)
        self.assertEqual(output["baseline_one_shanten_multi"],16)

    def test_new_development_and_holdout_are_disjoint_no_live_rollout(self):
        for bad in (
            {"seeds":0},{"seeds":9},{"seeds":True},{"holdout":56000},
            {"holdout":56003},{"development":True},{"holdout":2**32-1},
        ):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                study(**bad)
        with patch("mahtrain_core.ai_one_shanten_ukeire_paired.cohort",
                   side_effect=lambda start,n:{"start":start,"seeds":n}
                   ) as run:
            output=study()
        self.assertEqual([x.args for x in run.call_args_list],
                         [(56000,4),(57000,4)])
        self.assertEqual(output["protocol"],PROTOCOL)
        self.assertFalse(output["online_ai_modified"])
        self.assertTrue(output["candidate_only_offline"])


if __name__=="__main__":
    unittest.main()
