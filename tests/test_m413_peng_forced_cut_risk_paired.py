"""M4.13: only PUBLIC risk of best exact-stage Peng cuts, OFFLINE paired."""
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
from mahtrain_core.ai_peng_forced_cut_risk_paired import (
    ARMS,GATE,METRICS,PROTOCOL,PengForcedCutResearchAgent,
    licensed_peng_guard,paired_position,cohort,study,
)
from test_ai_calls import offer_peng
from test_m405_dual_claim_fastpath import real_dual_offer


class M413PengForcedCutTests(unittest.TestCase):
    def test_true_108_tile_peng_view_and_immutability(self):
        game,seat,view=offer_peng()
        frozen=copy.deepcopy(view)
        choice,reason=licensed_peng_guard(view,"peng")
        self.assertIn(choice,("peng","pass"))
        self.assertEqual(game.debug_tile_counts()["total"],108)
        self.assertEqual(view,frozen)
        self.assertNotIn("opponent_hands",json.dumps(view))

    def test_risk_gate_only_for_equal_shanten_legal_best_cuts(self):
        _,_,view=offer_peng()
        frozen=copy.deepcopy(view)
        with patch("mahtrain_core.ai_peng_forced_cut_risk_paired.shanten_13",
                   return_value=2),patch(
            "mahtrain_core.ai_peng_forced_cut_risk_paired._cut_shanten",
            return_value=2),patch(
            "mahtrain_core.ai_peng_forced_cut_risk_paired.read_discard_threat",
            return_value={"risk_index":.7}):
            self.assertEqual(licensed_peng_guard(view,"peng"),
                             ("pass","high_threat_all_best_shanten_cuts"))
        self.assertEqual(view,frozen)
        self.assertEqual(GATE,.30)

    def test_any_safe_best_shanten_cut_preserves_selected_peng(self):
        _,_,view=offer_peng()
        with patch("mahtrain_core.ai_peng_forced_cut_risk_paired.shanten_13",
                   return_value=2),patch(
            "mahtrain_core.ai_peng_forced_cut_risk_paired._cut_shanten",
            return_value=2),patch(
            "mahtrain_core.ai_peng_forced_cut_risk_paired.read_discard_threat",
            return_value={"risk_index":.29}):
            self.assertEqual(licensed_peng_guard(view,"peng"),
                             ("peng","at_least_one_lower_risk_cut"))

    def test_shanten_gain_and_existing_tenpai_are_never_overridden(self):
        _,_,view=offer_peng()
        with patch("mahtrain_core.ai_peng_forced_cut_risk_paired.shanten_13",
                   return_value=2),patch(
            "mahtrain_core.ai_peng_forced_cut_risk_paired._cut_shanten",
            return_value=1),patch(
            "mahtrain_core.ai_peng_forced_cut_risk_paired.read_discard_threat",
            side_effect=AssertionError("should skip risk on real shanten improvement")):
            self.assertEqual(licensed_peng_guard(view,"peng"),
                             ("peng","strict_shanten_improvement"))
        with patch("mahtrain_core.ai_peng_forced_cut_risk_paired.shanten_13",
                   return_value=0),patch(
            "mahtrain_core.ai_peng_forced_cut_risk_paired._cut_shanten",
            return_value=0),patch(
            "mahtrain_core.ai_peng_forced_cut_risk_paired.read_discard_threat",
            side_effect=AssertionError("do not risk-discount tenpai")):
            self.assertEqual(licensed_peng_guard(view,"peng"),
                             ("peng","existing_tenpai_preserved"))

    def test_legal_hu_rob_kong_tian_ting_never_downgraded(self):
        _,_,view=offer_peng()
        with patch("mahtrain_core.ai_peng_forced_cut_risk_paired.read_discard_threat",
                   side_effect=AssertionError("forbidden on mandatory pass/Hu")):
            self.assertEqual(licensed_peng_guard(view,"pass"),
                             ("pass","not_selected_peng"))
            guarded=copy.deepcopy(view)
            guarded["tian_ting"]={"eligible":True}
            self.assertEqual(licensed_peng_guard(guarded,"peng"),
                             ("peng","tian_ting_preserved"))
            win=copy.deepcopy(view)
            win["claim_options"]=["pass","peng","hu"]
            self.assertEqual(licensed_peng_guard(win,"hu"),
                             ("hu","mandatory_hu"))
            with self.assertRaises(RuntimeError):
                licensed_peng_guard(win,"peng")
            rob=copy.deepcopy(view)
            rob["phase"]="rob_kong_window"
            rob["rob_options"]=["pass","hu"]
            self.assertEqual(licensed_peng_guard(rob,"hu",rob=True),
                             ("hu","mandatory_hu"))
            with self.assertRaises(RuntimeError):
                licensed_peng_guard(rob,"pass",rob=True)
        with self.assertRaises(ValueError):
            licensed_peng_guard(view,"ming_gang")

    def test_invalid_public_index_and_real_oracle_injection_rejected_or_ignored(self):
        _,_,view=offer_peng()
        polluted=copy.deepcopy(view)
        polluted["future_wall"]=["m1"]*108
        polluted["opponent_hands"]=[["m1"]*13]*4
        self.assertEqual(licensed_peng_guard(view,"peng"),
                         licensed_peng_guard(polluted,"peng"))
        for raw in (float("nan"),float("inf"),-1):
            with patch("mahtrain_core.ai_peng_forced_cut_risk_paired.shanten_13",
                       return_value=2),patch(
                "mahtrain_core.ai_peng_forced_cut_risk_paired._cut_shanten",
                return_value=2),patch(
                "mahtrain_core.ai_peng_forced_cut_risk_paired.read_discard_threat",
                return_value={"risk_index":raw}),self.assertRaises(RuntimeError):
                licensed_peng_guard(view,"peng")

    def test_exact_baseline_and_only_licensed_pass(self):
        game,seat,view=offer_peng()
        frozen=copy.deepcopy(view)
        with patch("mahtrain_core.ai.MahjongAgent.response",return_value="peng"), \
             patch("mahtrain_core.ai_peng_forced_cut_risk_paired.shanten_13",
                   return_value=2), \
             patch("mahtrain_core.ai_peng_forced_cut_risk_paired._cut_shanten",
                   return_value=2), \
             patch("mahtrain_core.ai_peng_forced_cut_risk_paired.read_discard_threat",
                   return_value={"risk_index":.45}):
            base=PengForcedCutResearchAgent(seed=42,seat=seat,arm="baseline")
            trial=PengForcedCutResearchAgent(seed=42,seat=seat,arm="peng_guard")
            self.assertEqual(base.response(view),"peng")
            self.assertEqual(trial.response(view),"pass")
            self.assertEqual(base.safe_counts().get("actual_changes",0),0)
            self.assertEqual(trial.safe_counts()["actual_changes"],1)
            self.assertEqual(trial.safe_counts()["selected_peng_windows"],1)
        self.assertEqual(frozen,view)
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_real_paired_complete_game_unchanged_path_is_identical(self):
        x=paired_position(50000,0)
        self.assertEqual(x["seed"],50000)
        self.assertEqual(x["rotation"],0)
        self.assertIn(x["challenge_seat"],range(4))
        for arm in ARMS:
            score=x["arms"][arm]["official"]
            self.assertEqual(score["official_net"],sum(score[k] for k in
                ("win_points","kong_points","exhaustive_points")))
            self.assertIn(x["arms"][arm]["phase"],("finished","wall_exhausted"))
        if x["actual_interventions"]==0:
            self.assertTrue(x["identical_if_untouched"])
            self.assertEqual(x["official_deltas"]["official_net"],0)
        raw=json.dumps(x)
        for forbidden in ('"tile"','"hand"','opponent_hands','future_wall','full_wall'):
            self.assertNotIn(forbidden,raw)

    def test_seed_cluster_paired_official_totals_and_nonindependent_seats(self):
        def fake(seed,rotation):
            difference=4 if seed==52000 and rotation==1 else 0
            ds={k:0 for k in METRICS}
            ds["official_net"]=difference
            ds["win_points"]=difference
            official=dict(ds)
            return {
              "seed":seed,"rotation":rotation,"challenge_seat":rotation,
              "arms":{"baseline":{"counts":{}},
                      "peng_guard":{"counts":{"actual_changes":int(difference!=0),
                                               "selected_peng_windows":1}}},
              "official_deltas":ds,"actual_interventions":int(difference!=0)}
        with patch("mahtrain_core.ai_peng_forced_cut_risk_paired.paired_position",
                   side_effect=fake) as called:
            x=cohort(52000,2)
        self.assertEqual(called.call_count,8)
        self.assertEqual(x["complete_official_games"],16)
        self.assertEqual(x["candidate_policy_interventions"],1)
        self.assertEqual(x["mean_four_seat_net_delta"],.5)
        self.assertEqual(x["positive_seeds"],1)
        self.assertEqual(x["unchanged_seeds"],1)
        self.assertIsNone(x["confidence_interval"])

    def test_disjoint_frozen_seeds_and_offline_nonprobability(self):
        for args in ({"seeds":0},{"seeds":True},{"seeds":9},
                     {"development":True},{"holdout":50000},
                     {"holdout":50003},{"holdout":2**32-1}):
            with self.subTest(args=args),self.assertRaises(ValueError):
                study(**args)
        with patch("mahtrain_core.ai_peng_forced_cut_risk_paired.cohort",
                   return_value={"independent_shuffles":4}) as c:
            x=study()
        self.assertEqual([a.args for a in c.call_args_list],
                         [(50000,4),(51000,4)])
        self.assertEqual(x["protocol"],PROTOCOL)
        self.assertFalse(x["online_policy_modified"])
        self.assertEqual(x["frozen_risk_gate"],.30)


if __name__=="__main__": unittest.main()
