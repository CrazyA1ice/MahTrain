"""M4.05: strict real dual-claim fastpath, privacy and paired ledger."""
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
from mahtrain_core.four_player import FourPlayerOpening
from mahtrain_core.ai_dual_claim_fastpath_paired import (
    ARMS,PROTOCOL,DualFastpathResearchAgent,choose_dual_claim,
    _dual_optional_options,paired_position,cohort,study,
)
from test_four_player_claims import staged_game
from test_ai_calls import offer_peng,offer_kongs


def real_dual_offer():
    dealer=FourPlayerOpening(42).dealer
    receiver=(dealer+1)%4
    receiver_hand=(
        ["m1"]*2+["m2"]*2+["m3"]*2+["p1"]*2+
        ["p3","p5","s9","s9","s9"])
    dealer_hand=[
        "s9","m4","m5","m6","m7","m8","m9",
        "p2","p4","p6","p7","p8","s1","s2"]
    game=staged_game(
        {dealer:dealer_hand,receiver:receiver_hand},
        {dealer:"p",receiver:"p"},seed=42)
    game.discard(dealer,"s9")
    view=game.private_view(receiver)
    assert "peng" in view["claim_options"]
    assert "ming_gang" in view["claim_options"]
    assert "hu" not in view["claim_options"]
    return game,receiver,view


class M405DualClaimFastpathTests(unittest.TestCase):
    def test_true_physical_108_deal_has_simultaneous_peng_ming_gang(self):
        game,seat,view=real_dual_offer()
        self.assertTrue(_dual_optional_options(view,rob=False))
        frozen=copy.deepcopy(view)
        baseline=MahjongAgent("challenge",seed=42,seat=seat).response(view)
        proposed=choose_dual_claim(view,baseline)
        self.assertIn(proposed,view["claim_options"])
        self.assertEqual(frozen,view)
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_zero_slate_on_single_kind_authorized_offer(self):
        _,seat,view=offer_peng()
        before=copy.deepcopy(view)
        self.assertFalse(_dual_optional_options(view,rob=False))
        with patch("mahtrain_core.ai_dual_claim_fastpath_paired.optional_claim_slate",
                   side_effect=AssertionError("no slate on single kinds")):
            for arm in ARMS:
                agent=DualFastpathResearchAgent(seed=42,seat=seat,arm=arm)
                result=agent.response(view)
                self.assertIn(result,view["claim_options"])
                self.assertEqual(agent.counts["single_kind_fastpath"],1)
                self.assertEqual(agent.counts["joint_slate_evaluations"],0)
                self.assertEqual(agent.safe_latency()["extra_slate_evaluations"],0)
        self.assertEqual(view,before)

    def test_true_dual_evaluates_slate_exactly_once_per_arm(self):
        _,seat,view=real_dual_offer()
        with (patch("mahtrain_core.ai.MahjongAgent.response",
                    return_value="ming_gang"),
              patch("mahtrain_core.ai_dual_claim_fastpath_paired.choose_dual_claim",
                    return_value="peng") as slate):
            base=DualFastpathResearchAgent(seed=42,seat=seat,arm="baseline")
            alt=DualFastpathResearchAgent(seed=42,seat=seat,arm="dual_fastpath")
            self.assertEqual(base.response(view),"ming_gang")
            self.assertEqual(alt.response(view),"peng")
            self.assertEqual(slate.call_count,2)
            for a in (base,alt):
                self.assertEqual(a.counts["dual_active_windows"],1)
                self.assertEqual(a.counts["joint_slate_evaluations"],1)
                self.assertEqual(a.counts["dual_action_disagreements"],1)
                self.assertEqual(a.safe_latency()["extra_slate_evaluations"],1)
            self.assertEqual(base.counts["actual_policy_changes"],0)
            self.assertEqual(alt.counts["actual_policy_changes"],1)

    def test_verified_hu_rob_hu_and_tian_ting_no_unsafe_override(self):
        _,seat,view=real_dual_offer()
        mandatory=copy.deepcopy(view)
        mandatory["claim_options"]=["pass","hu","peng","ming_gang"]
        rob=copy.deepcopy(view)
        rob["phase"]="rob_kong_window"
        rob["rob_options"]=["pass","hu"]
        with (patch("mahtrain_core.ai.MahjongAgent.response",
                    return_value="hu"),
              patch("mahtrain_core.ai_dual_claim_fastpath_paired.choose_dual_claim",
                    side_effect=AssertionError("must not rescore legal Hu"))):
            for arm in ARMS:
                m=DualFastpathResearchAgent(seed=42,seat=seat,arm=arm)
                self.assertEqual(m.response(mandatory),"hu")
                self.assertEqual(m.response(rob,rob=True),"hu")
                self.assertEqual(m.counts["authorized_hu_taken"],2)
                self.assertEqual(m.counts["joint_slate_evaluations"],0)
        tian=copy.deepcopy(view)
        tian["tian_ting"]={"eligible":True,"initial_waits":["m1"]}
        with patch("mahtrain_core.ai_dual_claim_fastpath_paired.choose_dual_claim",
                   wraps=choose_dual_claim):
            for arm in ARMS:
                m=DualFastpathResearchAgent(seed=42,seat=seat,arm=arm)
                self.assertEqual(m.response(tian),"pass")

    def test_never_read_synthetic_future_wall_opponent_hands(self):
        _,seat,view=real_dual_offer()
        standard=choose_dual_claim(
            view,MahjongAgent("challenge",seed=42,seat=seat).response(view))
        polluted=copy.deepcopy(view)
        polluted["opponent_hands"]=[["s9"]*13]*3
        polluted["future_wall"]=["s9"]*55
        polluted["oracle_rob_hu_risk"]=1
        self.assertEqual(standard,choose_dual_claim(
            polluted,MahjongAgent("challenge",seed=42,seat=seat).response(polluted)))

    def test_original_all_self_kong_options_remain_unmodified(self):
        g,seat,v=offer_kongs()
        reference=MahjongAgent("challenge",seed=42,seat=seat).kong(v)
        for arm in ARMS:
            model=DualFastpathResearchAgent(seed=42,seat=seat,arm=arm)
            self.assertEqual(model.kong(v),reference)
            self.assertEqual(model.counts["self_kong_choices"],2)
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_illegal_baseline_action_or_slate_rejected(self):
        _,_,v=real_dual_offer()
        with self.assertRaises(ValueError):
            choose_dual_claim(v,"draw_wall")
        with patch("mahtrain_core.ai_dual_claim_fastpath_paired.optional_claim_slate",
                   return_value=[{"action":"illegal","admissible":True,
                                  "shanten":1,"relative_value":1,
                                  "relative_ukeire":1}]):
            # A malformed slate cannot be passed to the real engine.
            with self.assertRaises((RuntimeError,KeyError)):
                choose_dual_claim(v,"pass")

    def test_real_full_paired_match_reconciles_win_kong_and_wall(self):
        row=paired_position(34000,0)
        self.assertEqual(row["challenge_seat"],0)
        self.assertEqual(set(row["arms"]),set(ARMS))
        for arm in ARMS:
            score=row["arms"][arm]["official"]
            self.assertEqual(score["official_net"],sum(score[k] for k in (
                "win_points","kong_points","exhaustive_points")))
            metrics=row["arms"][arm]["latency"]
            self.assertGreaterEqual(metrics["baseline_response_ms"],0)
            self.assertEqual(metrics["extra_slate_evaluations"],
                             row["arms"][arm]["counts"].get(
                                 "dual_active_windows",0))
        raw=json.dumps(row)
        for private in ("opponent_hands","future_wall","full_wall",
                        "offer_signature","oracle_rob_hu"):
            self.assertNotIn(private,raw)

    def test_seed_cluster_four_rotations_are_not_independent_trials(self):
        def fake(seed,rotation):
            left={key:0 for key in (
                "official_net","win_points","kong_points","exhaustive_points",
                "win_events","deal_in_events","realized_kongs")}
            right=dict(left);right["official_net"]=3;right["win_points"]=3
            return {"seed":seed,"rotation":rotation,"challenge_seat":(4-rotation)%4,
                    "arms":{
                        "baseline":{"official":left,"counts":{},"latency":{
                            "baseline_response_ms":3,"additional_joint_slate_ms":0,
                            "maximum_single_extra_slate_ms":0}},
                        "dual_fastpath":{"official":right,"counts":{},"latency":{
                            "baseline_response_ms":3,"additional_joint_slate_ms":0,
                            "maximum_single_extra_slate_ms":0}},
                    }}
        with patch("mahtrain_core.ai_dual_claim_fastpath_paired.paired_position",
                   side_effect=fake) as runner:
            report=cohort(36000,2)
        self.assertEqual(runner.call_count,8)
        self.assertEqual(report["independent_shuffle_seeds"],2)
        self.assertEqual(report["paired_four_seat_positions"],8)
        self.assertEqual(report["complete_official_games"],16)
        self.assertEqual(report["seed_average_official_net_delta"],3)
        self.assertEqual(report["official_component_deltas"]["official_net"],24)
        self.assertIsNone(report["confidence_interval"])

    def test_fixed_new_seed_blocks_and_policy_status(self):
        for kw in (
            {"holdout":34000},{"holdout":34007},{"development":35000},
            {"development":True},{"seeds":0},{"seeds":9},
            {"seeds":True},{"holdout":2**32-1}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                study(**kw)
        with patch("mahtrain_core.ai_dual_claim_fastpath_paired.cohort",
                   return_value={"independent_shuffle_seeds":8}) as fn:
            x=study()
        self.assertEqual(fn.call_args_list[0].args,(34000,8))
        self.assertEqual(fn.call_args_list[1].args,(35000,8))
        self.assertEqual(x["protocol"],PROTOCOL)
        self.assertFalse(x["online_challenge_modified"])


if __name__=="__main__":
    unittest.main()
