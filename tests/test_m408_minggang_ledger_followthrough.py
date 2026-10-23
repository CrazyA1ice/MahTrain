"""M4.08: public terminal Ming-Gang event-to-cash reconciliation and privacy."""
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
from mahtrain_core.ai_minggang_ledger_followthrough import (
    PROTOCOL, MingGangFollowThroughAgent, audit_official_kong_lifecycle,
    natural_position,natural_cohort,study,
)
from test_m405_dual_claim_fastpath import real_dual_offer


def terminal_case(*, voided=False):
    public=[{"type":"ming_gang","seat":1,"source":0}]
    discard={"seat":1,"after_kong":True,"kong_id":1}
    if voided:
        discard["won_by"]=[0,2]
        public.append({"type":"ron","source":1,"seats":[0,2]})
    else:
        public.append({"type":"all_pass"})
    events=[{"id":1,"type":"ming_gang","seat":1,"source":0,
             "payers":[0],"amount_per_payer":2,
             "status":"voided" if voided else "posted",
             "reason":"kong_discard_ron" if voided else "simulation_using_explicit_kong_base"}]
    entries=[{"index":1,"kong_id":1,"kind":"charge",
              "payer":0,"recipient":1,"amount":2}]
    balance=[-2,2,0,0]
    if voided:
        entries.append({"index":2,"kong_id":1,"kind":"reversal",
                        "payer":1,"recipient":0,"amount":2})
        balance=[0,0,0,0]
    board={"phase":"wall_exhausted","kong_ledger":{
        "base":1,"zero_sum":True,"events":events,
        "entries":entries,"balances":balance},"discards":[discard]}
    outcome={"terminal_phase":"wall_exhausted","public_events":public,
             "official_kong_balances":list(balance)}
    return outcome,board


class M408MingGangLifecycleTests(unittest.TestCase):
    def test_exact_priced_credit_after_physical_minggang(self):
        outcome,board=terminal_case()
        a=audit_official_kong_lifecycle(outcome,board,1)
        self.assertEqual(a["own_minggang_posted"],1)
        self.assertEqual(a.get("own_minggang_voided",0),0)
        self.assertEqual(a["own_minggang_nominal_credit"],2)
        self.assertEqual(a["own_minggang_final_credit"],2)
        self.assertEqual(a["own_minggang_after_kong_discard"],1)
        self.assertEqual(a.get("own_minggang_exit_ron",0),0)

    def test_multi_ron_after_kong_voids_cash_once_with_two_winners(self):
        outcome,board=terminal_case(voided=True)
        a=audit_official_kong_lifecycle(outcome,board,1)
        self.assertEqual(a["own_minggang_voided"],1)
        self.assertEqual(a["own_minggang_exit_ron"],1)
        self.assertEqual(a["own_minggang_exit_ron_winners"],2)
        self.assertEqual(a["own_minggang_nominal_credit"],2)
        self.assertEqual(a.get("own_minggang_final_credit",0),0)
        self.assertEqual(a["ledger_refunds"],1)
        self.assertEqual(a["ledger_cash_entries"],2)

    def test_corrupted_ledger_and_unmatched_refund_fail_closed(self):
        for edit in ("missing_reversal","wrong_charge","false_refund",
                     "wrong_source","wrong_balance","bad_kong_id"):
            outcome,board=terminal_case(voided=True)
            if edit=="missing_reversal":
                board["kong_ledger"]["entries"].pop()
            elif edit=="wrong_charge":
                board["kong_ledger"]["entries"][0]["amount"]=3
            elif edit=="false_refund":
                board["discards"][0].pop("won_by")
            elif edit=="wrong_source":
                board["kong_ledger"]["events"][0]["source"]=3
            elif edit=="wrong_balance":
                board["kong_ledger"]["balances"][1]=1
            elif edit=="bad_kong_id":
                board["discards"][0]["kong_id"]=7
            with self.subTest(edit=edit),self.assertRaises((RuntimeError,ValueError)):
                audit_official_kong_lifecycle(outcome,board,1)

    def test_terminal_only_and_kong_base_are_authoritative(self):
        outcome,board=terminal_case()
        board["phase"]="await_discard"
        with self.assertRaises(ValueError):
            audit_official_kong_lifecycle(outcome,board,1)
        outcome,board=terminal_case()
        board["kong_ledger"]["base"]=None
        with self.assertRaises(ValueError):
            audit_official_kong_lifecycle(outcome,board,1)

    def test_true_108_dual_agent_preserves_choice_and_observes_pre_tail(self):
        game,seat,view=real_dual_offer()
        frozen=copy.deepcopy(view)
        expected=MahjongAgent("challenge",seed=42,seat=seat).response(view)
        agent=MingGangFollowThroughAgent(seed=42,seat=seat)
        self.assertEqual(agent.response(view),expected)
        self.assertEqual(game.debug_tile_counts()["total"],108)
        self.assertEqual(view,frozen)
        self.assertEqual(agent.public_counts()["dual_windows"],1)
        assert len(agent._dual_windows)==1
        self.assertNotIn("tile",agent._dual_windows[0])
        self.assertNotIn("hand",agent._dual_windows[0])
        # Choice is what original challenge selected, NOT whether the rules
        # eventually award the claim over all competing responders.
        i=view["pending_discard"]["index"]
        events=[{"type":"discard","index":i},{"type":"ming_gang","seat":seat}]
        obs=agent.reconcile_dual_windows(events)
        self.assertEqual(obs["dual_windows"],1)
        self.assertEqual(obs["dual_chosen_minggang_actual_award"],
                         int(expected=="ming_gang"))
        self.assertEqual(obs.get("dual_chosen_minggang_preempted",0),0)

    def test_actual_ron_priority_can_preempt_chosen_minggang(self):
        _,seat,view=real_dual_offer()
        agent=MingGangFollowThroughAgent(seed=42,seat=seat)
        with patch("mahtrain_core.ai.MahjongAgent.response",
                   return_value="ming_gang"):
            self.assertEqual(agent.response(view),"ming_gang")
        i=view["pending_discard"]["index"]
        observed=agent.reconcile_dual_windows([
            {"type":"discard","index":i},
            {"type":"multi_ron","source":view["pending_discard"]["seat"]},
        ])
        self.assertEqual(observed["dual_chosen_minggang_preempted"],1)
        self.assertEqual(observed.get("dual_chosen_minggang_actual_award",0),0)

    def test_single_actual_complete_natural_terminal_is_anonymous(self):
        x=natural_position(40000,0)
        self.assertEqual(x["terminal_phase"] in ("finished","wall_exhausted"),True)
        self.assertEqual(x["official"]["official_net"],sum(
            x["official"][k] for k in ("win_points","kong_points","exhaustive_points")))
        serialized=json.dumps(x)
        for forbidden in ("future_wall","opponent_hands","full_wall","tile","hand"):
            self.assertNotIn('"'+forbidden+'"',serialized)

    def test_four_seat_independent_clusters_and_holdout_boundaries(self):
        def fake(seed,rotation):
            return {"seed":seed,"rotation":rotation,"challenge_seat":(4-rotation)%4,
                    "ledger":{"table_minggang_realized":1,
                              "own_minggang_realized":1,
                              "own_minggang_exit_ron":0},
                    "windows":{"dual_windows":1}}
        with patch("mahtrain_core.ai_minggang_ledger_followthrough.natural_position",
                   side_effect=fake) as fn:
            c=natural_cohort(42000,2)
        self.assertEqual(fn.call_count,8)
        self.assertEqual(c["complete_games"],8)
        self.assertEqual(c["actual_all_seat_minggang"],8)
        self.assertEqual(c["total_dual_windows"],8)
        self.assertEqual([x["seed"] for x in c["per_seed"]],[42000,42001])
        self.assertIsNone(c["confidence_interval"])
        for bad in ({"holdout":40000},{"holdout":40003},
                    {"seeds":0},{"seeds":9},{"seeds":True},
                    {"development":True},{"holdout":2**32-1}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                study(**bad)
        with patch("mahtrain_core.ai_minggang_ledger_followthrough.natural_cohort",
                   return_value={"independent_initial_shuffle_seeds":4}) as fn:
            s=study()
        self.assertEqual(fn.call_args_list[0].args,(40000,4))
        self.assertEqual(fn.call_args_list[1].args,(41000,4))
        self.assertFalse(s["online_policy_modified"])
        self.assertEqual(s["protocol"],PROTOCOL)


if __name__=="__main__":
    unittest.main()
