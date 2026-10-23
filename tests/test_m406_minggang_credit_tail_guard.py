"""M4.06: rule-based reversible cash, tail draw and conservative dual guard."""
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
from mahtrain_core.ai_joint_optional_action_slate import optional_claim_slate
from mahtrain_core.ai_minggang_credit_tail_guard import (
    ARMS,PROTOCOL,authorized_public_minggang_evidence,
    cash_preserving_optional_choice,CashGuardResearchAgent,
    paired_position,cohort,study,
)
from test_m405_dual_claim_fastpath import real_dual_offer
from test_ai_calls import offer_peng,offer_kongs


def row(action,shanten=1,ukeire=8,value=8):
    return {"action":action,"admissible":True,
            "mandatory_win":False,"shanten":shanten,
            "ukeire":ukeire,"value":value,
            "relative_value":float(value)/10,
            "relative_ukeire":float(ukeire)/10}


def slate_pass_best():
    return [row("pass",1,10,12),row("peng",1,9,10),
            row("ming_gang",1,7,8)]


class M406MingGangCreditTailGuard(unittest.TestCase):
    def test_real_108_tile_dual_offer_public_cash_and_tail(self):
        game,seat,view=real_dual_offer()
        self.assertEqual(game.debug_tile_counts()["total"],108)
        before=copy.deepcopy(view)
        original=optional_claim_slate(view)
        data=authorized_public_minggang_evidence(view,original)
        # Real staged fixture deliberately has NO priced kong base.
        self.assertIsNone(data["payment_if_posted"])
        self.assertEqual(data["payment_payer_count"],1)
        self.assertTrue(data["payment_is_reversible_on_kong_discard_ron"])
        self.assertTrue(data["tail_draw_exists"])
        self.assertIsNone(data["expected_official_net_from_kong"])
        self.assertEqual(data["remaining_wall_count"],view["wall_count"])
        self.assertGreater(data["unknown_physical_copies"],0)
        self.assertLess(data["unknown_physical_copies"],108)
        self.assertTrue(0<=data["tail_next_draw_effective_copy_ratio"]<=1)
        self.assertEqual(view,before)

    def test_cash_amount_is_authoritative_two_times_base_not_room_coefficient(self):
        _,_,v=real_dual_offer()
        s=slate_pass_best()
        v["kong_ledger"]["base"]=7
        x=authorized_public_minggang_evidence(v,s)
        self.assertEqual(x["payment_if_posted"],14)
        self.assertIsNone(x["expected_official_net_from_kong"])
        v["kong_ledger"]["base"]=None
        y=authorized_public_minggang_evidence(v,s)
        self.assertIsNone(y["payment_if_posted"])
        v["kong_ledger"]["base"]=True
        with self.assertRaises(ValueError):
            authorized_public_minggang_evidence(v,s)

    def test_minggang_protected_when_slate_suggests_equal_shanten_pass(self):
        _,_,v=real_dual_offer()
        choice,reason,evidence=cash_preserving_optional_choice(
            v,"ming_gang",slate_pass_best())
        self.assertEqual(choice,"ming_gang")
        self.assertEqual(reason,"retain_official_minggang")
        self.assertIsNone(evidence["payment_if_posted"])
        self.assertIsNone(evidence["expected_official_net_from_kong"])

    def test_allowed_peng_only_for_strict_shanten_improvement(self):
        _,_,v=real_dual_offer()
        s=[row("pass",2,11,12),row("peng",0,3,20),
           row("ming_gang",2,8,9)]
        action,reason,_=cash_preserving_optional_choice(v,"ming_gang",s)
        self.assertEqual(action,"peng")
        self.assertEqual(reason,"strict_shanten_improves_over_minggang")

    def test_do_not_promote_new_cash_only_minggang_without_strict_improvement(self):
        _,_,v=real_dual_offer()
        s=[row("pass",1,7,7),row("peng",1,5,6),
           row("ming_gang",1,9,12)]
        action,reason,_=cash_preserving_optional_choice(v,"pass",s)
        self.assertEqual(action,"pass")
        self.assertEqual(reason,"no_strict_profitable_minggang_proof")
        s[2]["shanten"]=0
        v["kong_ledger"]["base"]=1  # priced official ming-gang explicitly
        action,reason,_=cash_preserving_optional_choice(v,"pass",s)
        self.assertEqual(action,"ming_gang")
        self.assertEqual(reason,"strict_shanten_and_priced_minggang")
        v["kong_ledger"]["base"]=None
        action,_,_=cash_preserving_optional_choice(v,"pass",s)
        self.assertEqual(action,"pass")

    def test_only_true_dual_window_invokes_extra_slate(self):
        _,seat,single=offer_peng()
        with patch("mahtrain_core.ai_minggang_credit_tail_guard.optional_claim_slate",
                   side_effect=AssertionError("no expensive single-window slate")):
            for arm in ARMS:
                m=CashGuardResearchAgent(seed=42,seat=seat,arm=arm)
                self.assertIn(m.response(single),single["claim_options"])
                self.assertEqual(m.counts["joint_slate_evaluations"],0)
                self.assertEqual(m.counts["no_extra_slate"],1)
        _,seat,dual=real_dual_offer()
        with (patch("mahtrain_core.ai.MahjongAgent.response",
                    return_value="ming_gang"),
              patch("mahtrain_core.ai_minggang_credit_tail_guard.optional_claim_slate",
                    return_value=slate_pass_best()) as evaluate):
            for arm in ARMS:
                m=CashGuardResearchAgent(seed=42,seat=seat,arm=arm)
                self.assertEqual(m.response(dual),"ming_gang")
                self.assertEqual(m.counts["joint_slate_evaluations"],1)
                self.assertEqual(m.counts["reason_retain_official_minggang"],1)
                self.assertEqual(m.counts["actual_changes"],0)
            self.assertEqual(evaluate.call_count,2)

    def test_hu_rob_hu_protected_and_own_kong_keeps_original(self):
        _,seat,dual=real_dual_offer()
        canhu=copy.deepcopy(dual)
        canhu["claim_options"]+=["hu"]
        robber=copy.deepcopy(dual)
        robber["phase"]="rob_kong_window"
        robber["rob_options"]=["pass","hu"]
        with (patch("mahtrain_core.ai.MahjongAgent.response",
                    return_value="hu"),
              patch("mahtrain_core.ai_minggang_credit_tail_guard.optional_claim_slate",
                    side_effect=AssertionError("no extra when Hu"))):
            for arm in ARMS:
                m=CashGuardResearchAgent(seed=42,seat=seat,arm=arm)
                self.assertEqual(m.response(canhu),"hu")
                self.assertEqual(m.response(robber,rob=True),"hu")
                self.assertEqual(m.counts["legal_hu_unchanged"],2)
        g,seat,v=offer_kongs()
        for arm in ARMS:
            m=CashGuardResearchAgent(seed=42,seat=seat,arm=arm)
            self.assertEqual(m.kong(v),
                MahjongAgent("challenge",seed=42,seat=seat).kong(v))
        self.assertEqual(g.debug_tile_counts()["total"],108)

    def test_hidden_opponents_and_future_wall_cannot_affect_public_evidence(self):
        _,seat,dual=real_dual_offer()
        s=optional_claim_slate(dual)
        original=authorized_public_minggang_evidence(dual,s)
        polluted=copy.deepcopy(dual)
        polluted["future_wall"]=["m1"]*55
        polluted["opponent_hands"]=[["s9"]*13]*3
        polluted["oracle_rob_hu"]=42
        self.assertEqual(original,authorized_public_minggang_evidence(polluted,s))
        baseline=MahjongAgent("challenge",seed=42,seat=seat).response(dual)
        self.assertEqual(
            cash_preserving_optional_choice(dual,baseline,s)[0],
            cash_preserving_optional_choice(polluted,baseline,s)[0])

    def test_guards_reject_corrupt_physical_and_missing_legal_action(self):
        _,seat,v=real_dual_offer()
        s=slate_pass_best()
        with self.assertRaises(ValueError):
            cash_preserving_optional_choice(v,"draw",s)
        v["wall_count"]=0
        with self.assertRaises(ValueError):
            authorized_public_minggang_evidence(v,s)
        v["wall_count"]=12
        v["hand"]=["s9"]*13
        with self.assertRaises(RuntimeError):
            authorized_public_minggang_evidence(v,s)

    def test_real_held_out_style_game_terminal_balance_and_no_secrets(self):
        data=paired_position(36000,0)
        self.assertEqual(set(data["arms"]),set(ARMS))
        for arm in ARMS:
            report=data["arms"][arm]
            o=report["official"]
            self.assertEqual(o["official_net"],sum(o[k] for k in (
                "win_points","kong_points","exhaustive_points")))
            self.assertEqual(report["latency"]["actual_slate_evaluations"],
                report["counts"].get("dual_legal_windows",0))
        raw=json.dumps(data)
        for term in ("future_wall","opponent_hands","oracle_rob_hu","full_wall"):
            self.assertNotIn(term,raw)

    def test_four_seat_seed_cluster_paired_math_without_false_intervals(self):
        def dummy(seed,r):
            base={k:0 for k in ("official_net","win_points","kong_points",
                "exhaustive_points","win_events","deal_in_events","realized_kongs")}
            alt=dict(base);alt["official_net"]=8;alt["win_points"]=8
            return {"seed":seed,"rotation":r,"challenge_seat":(4-r)%4,
                "arms":{ "baseline":{"official":base,"counts":{},"latency":{
                    "additional_slate_ms":0,"peak_additional_slate_ms":0}},
                    "credit_tail_guard":{"official":alt,"counts":{},"latency":{
                    "additional_slate_ms":0,"peak_additional_slate_ms":0}} }}
        with patch("mahtrain_core.ai_minggang_credit_tail_guard.paired_position",
                   side_effect=dummy) as fn:
            x=cohort(40000,2)
        self.assertEqual(fn.call_count,8)
        self.assertEqual(x["independent_initial_shuffle_seeds"],2)
        self.assertEqual(x["paired_seat_positions"],8)
        self.assertEqual(x["complete_games"],16)
        self.assertEqual(x["average_official_net_delta"],8)
        self.assertEqual(x["components"]["official_net"],64)
        self.assertIsNone(x["confidence_interval"])

    def test_new_seed_blocks_predeclared_and_disjoint(self):
        for args in (
            {"holdout":36000},{"holdout":36007},{"development":37000},
            {"seeds":0},{"seeds":9},{"seeds":True},
            {"development":True},{"holdout":2**32-3}):
            with self.subTest(args=args),self.assertRaises(ValueError):
                study(**args)
        with patch("mahtrain_core.ai_minggang_credit_tail_guard.cohort",
                   return_value={"independent_initial_shuffle_seeds":8}) as fn:
            data=study()
        self.assertEqual(fn.call_args_list[0].args,(36000,8))
        self.assertEqual(fn.call_args_list[1].args,(37000,8))
        self.assertEqual(data["protocol"],PROTOCOL)
        self.assertFalse(data["online_policy_modified"])

if __name__=="__main__":
    unittest.main()
