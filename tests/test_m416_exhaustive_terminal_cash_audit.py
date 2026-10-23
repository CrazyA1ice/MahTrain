"""M4.16 strict terminal-only official flower-pig / da-jiao audits."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]
from mahtrain_core.exhaustive_review import finalize_active_only
from mahtrain_core.ai_exhaustive_terminal_cash_audit import (
    PROTOCOL,STAGES,LABELS,audited_terminal,paired_position,cohort,study,
)


def synthetic_board():
    coefficient,cap=100,3
    rows=[
        {"seat":0,"classification":"flower_pig","wait_count":0,
         "max_effective_fan":None},
        {"seat":1,"classification":"listening","wait_count":2,
         "max_effective_fan":2},
        {"seat":2,"classification":"unready","wait_count":0,
         "max_effective_fan":None},
        {"seat":3,"classification":"listening","wait_count":3,
         "max_effective_fan":3},
    ]
    entries=[
        {"stage":"flower_pig","payer":0,"recipient":1,"amount":800},
        {"stage":"flower_pig","payer":0,"recipient":2,"amount":800},
        {"stage":"flower_pig","payer":0,"recipient":3,"amount":800},
        {"stage":"da_jiao","payer":2,"recipient":1,
         "amount":400,"effective_fan":2},
        {"stage":"da_jiao","payer":2,"recipient":3,
         "amount":800,"effective_fan":3},
    ]
    balances=[-2400,1200,-400,1600]
    preview={
        "triggered":True,"posted":False,"policy":"active_only_preview",
        "participating_active_seats":[0,1,2,3],
        "seats":rows,"proposed_transfers":entries,
        "preview_balances":balances,
        "reason":"requires_confirmation_of_settlement_participants",
    }
    official=finalize_active_only(preview,won=[False]*4,
                                  coefficient=coefficient,fan_cap=cap)
    return {
        "phase":"wall_exhausted","won":[False]*4,
        "win_ledger":{"room_coefficient":coefficient,"fan_cap":cap},
        "exhaustive_review":preview,"exhaustive_settlement":official,
    }


class M416ExhaustiveCashTests(unittest.TestCase):
    def test_real_one_shot_flower_pig_and_da_jiao_amounts(self):
        board=synthetic_board()
        row=audited_terminal(board,seat=2,phase="wall_exhausted",
                             expected_exhaustive=-400)
        self.assertEqual(row["terminal_class"],"unready")
        self.assertEqual(row["active_count"],4)
        self.assertEqual(row["class_counts"],{
            "flower_pig":1,"listening":2,"unready":1})
        self.assertEqual(row["flower_pig_balance"],800)
        self.assertEqual(row["da_jiao_balance"],-1200)
        self.assertEqual(row["official_exhaustive_balance"],-400)
        self.assertEqual(row["own_stage_payment_counts"]["da_jiao"],2)
        self.assertEqual(row["own_stage_receipt_counts"]["flower_pig"],1)
        self.assertEqual(row["transfer_counts"],{"flower_pig":3,"da_jiao":2})
        self.assertNotIn('"tile"',json.dumps(row))
        self.assertNotIn('"hand"',json.dumps(row))

    def test_ready_max_effective_fan_matches_official_price(self):
        board=synthetic_board()
        listening=audited_terminal(board,seat=3,phase="wall_exhausted",
                                   expected_exhaustive=1600)
        self.assertEqual(listening["terminal_class"],"listening")
        self.assertEqual(listening["own_wait_count"],3)
        self.assertEqual(listening["own_max_effective_fan"],3)
        self.assertEqual(listening["da_jiao_balance"],800)
        self.assertEqual(listening["flower_pig_balance"],800)

    def test_finished_match_can_never_have_exhaustive_settlement(self):
        board={
            "phase":"finished","won":[True,True,True,False],
            "exhaustive_review":None,"exhaustive_settlement":None,
        }
        x=audited_terminal(board,seat=1,phase="finished",
                           expected_exhaustive=0)
        self.assertEqual(x["terminal_class"],"already_won")
        self.assertEqual(x["da_jiao_balance"],0)
        with self.assertRaises(RuntimeError):
            audited_terminal(board,seat=1,phase="finished",
                             expected_exhaustive=100)
        wrong=copy.deepcopy(board)
        wrong["exhaustive_settlement"]={"posted":True,"balances":[0]*4}
        with self.assertRaises(RuntimeError):
            audited_terminal(wrong,seat=1,phase="finished",
                             expected_exhaustive=0)

    def test_unposted_or_corrupt_official_ledger_rejected(self):
        for kind in ("unposted","amount","fan","recipient","balances",
                     "wrong_expected","preview_drift"):
            b=synthetic_board()
            if kind=="unposted":
                b["exhaustive_settlement"]["posted"]=False
            if kind=="amount":
                b["exhaustive_settlement"]["entries"][3]["amount"]=40
            if kind=="fan":
                b["exhaustive_settlement"]["entries"][3]["effective_fan"]=12
            if kind=="recipient":
                b["exhaustive_settlement"]["entries"][3]["recipient"]=0
            if kind=="balances":
                b["exhaustive_settlement"]["balances"][0]+=100
            if kind=="preview_drift":
                b["exhaustive_review"]["preview_balances"][0]+=100
            with self.subTest(kind=kind),self.assertRaises(
                    (RuntimeError,ValueError)):
                audited_terminal(b,seat=2,phase="wall_exhausted",
                                 expected_exhaustive=(
                                     -300 if kind=="wrong_expected" else -400))

    def test_no_hidden_opponent_wait_or_tile_exported(self):
        b=synthetic_board()
        b["opponent_hands"]=[["m1"]*13]*4
        b["future_wall"]=["m1"]*20
        baseline=audited_terminal(synthetic_board(),seat=2,
                                   phase="wall_exhausted",
                                   expected_exhaustive=-400)
        self.assertEqual(audited_terminal(
            b,seat=2,phase="wall_exhausted",
            expected_exhaustive=-400),baseline)
        raw=json.dumps(baseline)
        for forbidden in ('"opponent_hands"','"future_wall"',
                          '"tile"','"melds"','"missing_suit"'):
            self.assertNotIn(forbidden,raw)

    def test_actual_one_108_tile_game_and_authoritative_posting(self):
        row=paired_position(52000,0)
        self.assertEqual(row["seed"],52000)
        self.assertEqual(row["rotation"],0)
        self.assertEqual(row["official_deltas"]["official_net"],sum(
            row["official_deltas"][k] for k in (
                "win_points","kong_points","exhaustive_points")))
        self.assertEqual(row["official_deltas"]["exhaustive_points"],
                         sum(row["terminal_stage_deltas"].values()))
        self.assertEqual(row["real_interventions"],0)
        for arm in ("baseline","nearvalue_defense"):
            if row["arms"][arm]["terminal"]["terminal_phase"]=="finished":
                self.assertEqual(row["arms"][arm]["terminal"][
                    "official_exhaustive_balance"],0)
        raw=json.dumps(row)
        for forbidden in ('"tile"','"hand"','"future_wall"',
                          '"opponent_hands"','"public_events"','"_trace"'):
            self.assertNotIn(forbidden,raw)

    def test_cluster_uses_four_seats_one_seed_and_stage_sums(self):
        def fake(seed,rotation):
            val=-800 if seed==54000 and rotation==1 else 0
            delta={
                "official_net":val,"win_points":0,
                "kong_points":0,"exhaustive_points":val,
                "win_events":0,"deal_in_events":0,"realized_kongs":0,
            }
            return {
                "seed":seed,"rotation":rotation,
                "challenge_seat":rotation,
                "real_interventions":int(val!=0),
                "official_deltas":delta,
                "terminal_stage_deltas":{
                    "flower_pig":0,"da_jiao":val,
                },
            }
        with patch("mahtrain_core.ai_exhaustive_terminal_cash_audit.paired_position",
                   side_effect=fake) as p:
            report=cohort(54000,2)
        self.assertEqual(p.call_count,8)
        self.assertEqual(report["independent_shuffles"],2)
        self.assertEqual(report["complete_games"],16)
        self.assertEqual(report["official_deltas"]["official_net"],-800)
        self.assertEqual(report["stage_deltas"]["da_jiao"],-800)
        self.assertEqual(report["changed_positions"],1)
        self.assertEqual(report["per_seed"][0]["da_jiao_delta"],-800)

    def test_unchanged_frozen_sample_blocks_no_new_holdout(self):
        with patch("mahtrain_core.ai_exhaustive_terminal_cash_audit.cohort",
                   side_effect=lambda start,n:{"start":start,"n":n}) as c:
            data=study()
        self.assertEqual([x.args for x in c.call_args_list],
                         [(52000,4),(53000,4)])
        self.assertEqual(data["protocol"],PROTOCOL)
        self.assertTrue(data["retrospective_not_independent_holdout"])
        self.assertFalse(data["online_policy_modified"])

    def test_invalid_seed_seat_and_winner_mask_rejected(self):
        for seed,rotation in ((True,0),(-1,0),(2**32,0),
                              (52000,True),(52000,4)):
            with self.subTest(seed=seed,rotation=rotation),self.assertRaises(ValueError):
                paired_position(seed,rotation)
        for seed,count in ((True,4),(52000,0),
                           (52000,9),(2**32-2,4)):
            with self.subTest(seed=seed,count=count),self.assertRaises(ValueError):
                cohort(seed,count)
        board=synthetic_board()
        board["won"][1]=1
        with self.assertRaises(RuntimeError):
            audited_terminal(board,seat=2,phase="wall_exhausted",
                             expected_exhaustive=-400)


if __name__=="__main__":
    unittest.main()
