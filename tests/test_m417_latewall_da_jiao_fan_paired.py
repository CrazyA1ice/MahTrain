"""M4.17: rule-identical possible ready fan, public-only late-wall policy tests."""
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
from mahtrain_core.ai_latewall_da_jiao_fan_paired import (
    ARMS,PROTOCOL,LATE_WALL_TILES,MIN_MAX_FAN_GAIN,
    MIN_EFFECTIVE_COPIES_RETENTION,MIN_WAIT_TYPES_RETENTION,
    MIN_FAN_WEIGHTED_RETENTION,MAX_PUBLIC_THREAT_INCREASE,
    maximum_authorized_da_jiao_fan,propose_late_wall_fan_cut,
    LateWallFanResearchAgent,paired_position,cohort,study,
)
from test_ai_calls import offer_kongs


def view():
    return {
        "seat":0,
        "hand":["m1","m2","m3","m4","m5","m6","m7","m8",
                "m9","s1","s2","s3","s4","s5"],
        "own_melds":[],"missing_suits":["p","m","m","m"],
        "wall_count":18,"tian_ting":{"eligible":False},
        "win_ledger":{"fan_cap":3},
    }


def ranked(shanten=0):
    return [
        {"discard":"m1","shanten":shanten,"effective_tile_count":10,
         "expected_fan_weighted_copies":20.,"table_threat_index":.30},
        {"discard":"m2","shanten":shanten,"effective_tile_count":7,
         "expected_fan_weighted_copies":15.,"table_threat_index":.35},
        {"discard":"m3","shanten":shanten,"effective_tile_count":3,
         "expected_fan_weighted_copies":5.,"table_threat_index":.1},
    ]


def fan(_view,cut):
    return {"m1":(1,2),"m2":(2,2),"m3":(3,1)}[cut]


class M417LateWallReadyFanTests(unittest.TestCase):
    def test_freeze_heuristics_prior_to_independent_games(self):
        self.assertEqual(LATE_WALL_TILES,32)
        self.assertEqual(MIN_MAX_FAN_GAIN,1)
        self.assertEqual(MIN_EFFECTIVE_COPIES_RETENTION,.60)
        self.assertEqual(MIN_WAIT_TYPES_RETENTION,.50)
        self.assertEqual(MIN_FAN_WEIGHTED_RETENTION,.65)
        self.assertEqual(MAX_PUBLIC_THREAT_INCREASE,.15)

    def test_higher_real_max_fan_only_for_legal_equal_tenpai(self):
        v=view()
        original=copy.deepcopy(v)
        with patch("mahtrain_core.ai_latewall_da_jiao_fan_paired.maximum_authorized_da_jiao_fan",
                   side_effect=fan) as run:
            choice,reason=propose_late_wall_fan_cut("m1",ranked(),v)
        self.assertEqual((choice,reason),
                         ("m2","more_possible_max_da_jiao_fan"))
        self.assertEqual(run.call_count,2)
        self.assertEqual(v,original)

    def test_wall_and_protected_tian_ting_never_intervene(self):
        v=view()
        v["wall_count"]=33
        with patch("mahtrain_core.ai_latewall_da_jiao_fan_paired.maximum_authorized_da_jiao_fan",
                   side_effect=AssertionError("not late")):
            self.assertEqual(propose_late_wall_fan_cut(
                "m1",ranked(),v)[0],"m1")
        v["wall_count"]=32
        v["tian_ting"]={"eligible":True,"initial_waits":["m9"]}
        with patch("mahtrain_core.ai_latewall_da_jiao_fan_paired.maximum_authorized_da_jiao_fan",
                   side_effect=AssertionError("Tian Ting must stay intact")):
            self.assertEqual(propose_late_wall_fan_cut(
                "m1",ranked(),v)[0],"m1")

    def test_cannot_regress_strict_shanten_or_force_non_tenpai(self):
        v=view()
        with patch("mahtrain_core.ai_latewall_da_jiao_fan_paired.maximum_authorized_da_jiao_fan",
                   side_effect=AssertionError("1-shanten is excluded")):
            self.assertEqual(propose_late_wall_fan_cut(
                "m1",ranked(1),v),
                ("m1","not_already_tenpai_after_cut"))
        invalid=ranked()
        invalid[1]["shanten"]=1
        with self.assertRaises(RuntimeError):
            propose_late_wall_fan_cut("m1",invalid,v)

    def test_remaining_copy_weighted_value_waits_and_risk_protection(self):
        v=view()
        for i,key,bad in (
            (1,"effective_tile_count",5),
            (1,"expected_fan_weighted_copies",12),
            (1,"table_threat_index",.46),
        ):
            rows=ranked()
            rows[i][key]=bad
            with patch("mahtrain_core.ai_latewall_da_jiao_fan_paired.maximum_authorized_da_jiao_fan",
                       side_effect=fan):
                self.assertEqual(propose_late_wall_fan_cut(
                    "m1",rows,v)[0],"m1")
        with patch("mahtrain_core.ai_latewall_da_jiao_fan_paired.maximum_authorized_da_jiao_fan",
                   side_effect=lambda _v,cut:(
                       (1,2) if cut=="m1" else (2,0))):
            self.assertEqual(propose_late_wall_fan_cut(
                "m1",ranked(),v)[0],"m1")

    def test_malformed_rank_not_a_hidden_candidate(self):
        v=view()
        for rows in (
            [*ranked()[:2],dict(ranked()[2],discard="p9")],
            [*ranked()[:2],dict(ranked()[2],discard="m1")],
            [*ranked()[:2],dict(ranked()[2],effective_tile_count=float("nan"))],
            [*ranked()[:2],dict(ranked()[2],table_threat_index=-1)],
        ):
            with self.subTest(rows=rows),self.assertRaises(RuntimeError):
                propose_late_wall_fan_cut("m1",rows,v)
        with self.assertRaises(RuntimeError):
            propose_late_wall_fan_cut("m2",ranked(),v)
        broken=view()
        broken["wall_count"]=-1
        with self.assertRaises(ValueError):
            propose_late_wall_fan_cut("m1",ranked(),broken)

    def test_official_rules_13_tile_maximum_fan_no_opponent_data(self):
        v=view()
        v["hand"]=["m1","m1","m1","m2","m3","m4","m5","m6",
                    "m7","m8","m8","m8","m9","m9"]
        output=maximum_authorized_da_jiao_fan(v,"m9")
        self.assertGreaterEqual(output[0],2)
        self.assertGreaterEqual(output[1],1)
        polluted=copy.deepcopy(v)
        polluted["opponent_hands"]=[["p9"]*13]*4
        polluted["future_wall"]=["p9"]*30
        self.assertEqual(maximum_authorized_da_jiao_fan(polluted,"m9"),output)
        with self.assertRaises(ValueError):
            maximum_authorized_da_jiao_fan(v,"p9")

    def test_no_extra_discard_policy_recalculation_on_baseline_arm(self):
        v=view()
        with patch("mahtrain_core.ai.MahjongAgent.discard",return_value="m1"), \
             patch("mahtrain_core.ai_latewall_da_jiao_fan_paired.maximum_authorized_da_jiao_fan",
                   side_effect=fan):
            baseline=LateWallFanResearchAgent(seed=42,seat=0,arm="baseline")
            candidate=LateWallFanResearchAgent(seed=42,seat=0,arm="late_wall_fan")
            baseline._last_discard_scores=ranked()
            candidate._last_discard_scores=ranked()
            self.assertEqual(baseline.discard(v),"m1")
            self.assertEqual(candidate.discard(v),"m2")
        self.assertEqual(baseline.safe_counts().get("actual_changes",0),0)
        self.assertEqual(candidate.safe_counts()["actual_changes"],1)
        self.assertTrue(candidate._offline_reference_cut)
        self.assertEqual(candidate.safe_counts()["total_cuts"],1)
        self.assertNotIn('"tile"',json.dumps(candidate.safe_counts()))

    def test_real_108_tile_paired_match_no_changes_same_trace_and_cash(self):
        row=paired_position(54000,0)
        self.assertEqual((row["seed"],row["rotation"]),(54000,0))
        for arm in ARMS:
            official=row["arms"][arm]["official"]
            self.assertEqual(official["official_net"],
                             sum(official[k] for k in (
                                 "win_points","kong_points","exhaustive_points")))
        if row["actual_interventions"]==0:
            self.assertTrue(row["identical_if_untouched"])
            self.assertTrue(all(x==0 for x in row["official_deltas"].values()))
        raw=json.dumps(row)
        for forbidden in ('"hand"','"tile"','"future_wall"',
                          '"opponent_hands"','"_trace"','"_events"'):
            self.assertNotIn(forbidden,raw)

    def test_independent_shuffle_aggregation_not_four_independent_seats(self):
        def fake(seed,r):
            n=int(seed==56000 and r==0)
            d={k:0 for k in ("official_net","win_points","kong_points",
                             "exhaustive_points","win_events","deal_in_events",
                             "realized_kongs")}
            d["official_net"]=400*n
            d["exhaustive_points"]=400*n
            return {
                "seed":seed,"challenge_seat":r,
                "actual_interventions":n,"official_deltas":d,
                "arms":{"baseline":{"counts":{"total_cuts":3}},
                        "late_wall_fan":{"counts":{"actual_changes":n}}},
            }
        with patch("mahtrain_core.ai_latewall_da_jiao_fan_paired.paired_position",
                   side_effect=fake) as called:
            result=cohort(56000,2)
        self.assertEqual(called.call_count,8)
        self.assertEqual(result["independent_shuffles"],2)
        self.assertEqual(result["complete_official_games"],16)
        self.assertEqual(result["seed_clusters_with_interventions"],1)
        self.assertEqual(result["actual_interventions"],1)
        self.assertEqual(result["mean_four_seat_net_delta"],50)

    def test_disjoint_new_seed_blocks_and_no_live_change(self):
        for args in ({"development":True},{"seeds":True},{"seeds":9},
                     {"seeds":0},{"holdout":54000},{"holdout":54003},
                     {"holdout":2**32-1}):
            with self.subTest(args=args),self.assertRaises(ValueError):
                study(**args)
        with patch("mahtrain_core.ai_latewall_da_jiao_fan_paired.cohort",
                   return_value={"independent_shuffles":4}) as call:
            report=study()
        self.assertEqual([c.args for c in call.call_args_list],
                         [(54000,4),(55000,4)])
        self.assertEqual(report["protocol"],PROTOCOL)
        self.assertFalse(report["online_policy_modified"])
        self.assertTrue(report["candidate_only_offline"])


if __name__=="__main__":
    unittest.main()
