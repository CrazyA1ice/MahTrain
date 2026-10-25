"""M4.28 prospective physical-root/tail/rob boundary without hidden peeks."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]

from mahtrain_core.ai_delayed_bugang_targeted import (
    SHARDS,SPECS,construct_checkpoint
)
from mahtrain_core.ai_delayed_bugang_risk_envelope import (
    PROTOCOL,_reference_root_score,_rob_witness,
    _replace_opponents_without_public_change,_resolve,
    evaluate_case,evaluate_shard,combine,
)


class RootTailAndRobEnvelopeTests(unittest.TestCase):
    def test_root_fan_is_real_but_capped_not_automatic_cash(self):
        for cap in (0,1,2,3,6):
            with self.subTest(cap=cap):
                x=_reference_root_score("m9",cap)
                self.assertEqual(x["after_raw_fan"],x["before_raw_fan"]+1)
                self.assertEqual(x["after_multiplier"]-x["before_multiplier"],
                                 x["capped_multiplier_gain"])
                self.assertEqual(x["after_effective_fan"],
                                 min(x["after_raw_fan"],cap))
                self.assertEqual(x["before_effective_fan"],
                                 min(x["before_raw_fan"],cap))
        self.assertEqual(_reference_root_score("m9",1)[
            "capped_multiplier_gain"],0)
        self.assertGreater(_reference_root_score("m9",3)[
            "capped_multiplier_gain"],0)
        for target, _ in SPECS:
            x=_reference_root_score(target,3)
            self.assertEqual(x["after_raw_fan"],x["before_raw_fan"]+1)

    def test_robbed_actor_cannot_see_adversarial_opponent_or_wall(self):
        for case_id in (0,1,10,12,18,20,22,23):
            with self.subTest(case_id=case_id):
                original=construct_checkpoint(case_id,delayed=True)
                target=SPECS[case_id][0]
                public=deepcopy(original.public_state())
                own=deepcopy(original.private_view(0))
                private_hand=tuple(original._hands[1])
                alternate=_replace_opponents_without_public_change(
                    original,target)
                self.assertEqual(original.public_state(),public)
                self.assertEqual(original.private_view(0),own)
                self.assertEqual(original.debug_tile_counts()["total"],108)
                self.assertEqual(original._hands[1],list(private_hand))
                if alternate is None:
                    # No witness of our constrained hand shape was found:
                    # do NOT conclude rob is impossible in all hidden worlds.
                    self.assertIsNone(_rob_witness(original,target))
                else:
                    self.assertEqual(alternate.public_state(),public)
                    self.assertEqual(alternate.private_view(0),own)
                    self.assertEqual(alternate.debug_tile_counts()["total"],108)
                    self.assertEqual(len(_rob_witness(original,target)),13)

    def test_rob_branch_does_not_post_late_cash_or_consume_tail(self):
        for case_id in (0,10,12,20):
            with self.subTest(case=case_id):
                base=construct_checkpoint(case_id,delayed=True)
                target=SPECS[case_id][0]
                safe=_resolve(deepcopy(base),rob=False)
                counterfactual=_replace_opponents_without_public_change(
                    base,target)
                self.assertIsNotNone(counterfactual)
                rob=_resolve(counterfactual,rob=True)
                self.assertFalse(safe["robbed"])
                self.assertEqual(safe["cash_from_late_kong"],0)
                self.assertTrue(safe["kong_was_completed"])
                self.assertTrue(safe["tail_was_consumed"])
                self.assertTrue(rob["robbed"])
                self.assertEqual(rob["cash_from_late_kong"],0)
                self.assertFalse(rob["kong_was_completed"])
                self.assertFalse(rob["tail_was_consumed"])
                self.assertLess(rob["actor_official_wins"],0)
                self.assertEqual(rob["physical_count"],108)

    def test_case_contract_does_not_report_real_rob_probability_or_ev(self):
        row=evaluate_case(10)
        self.assertEqual(row["physical_tiles"],108)
        self.assertEqual(row["case_id"],10)
        self.assertTrue(row["not_a_probability_or_EV_estimate"])
        self.assertTrue(row[
            "constructed_same_view_rob_witness_found"])
        self.assertGreater(row["tail_proxy_unknown_copies"],0)
        self.assertLessEqual(row["tail_proxy_effective_copies"],
                             row["tail_proxy_unknown_copies"])
        self.assertNotIn("rob_probability",row)
        self.assertNotIn("future_wall",row)
        self.assertNotIn("opponent_hands",row)

    def test_registered_scope_rejects_invalid_shards_and_case_types(self):
        with patch(
            "mahtrain_core.ai_delayed_bugang_risk_envelope.evaluate_case"
        ) as evaluate:
            for bad in ("unknown","",123,True):
                with self.subTest(bad=bad),self.assertRaises(ValueError):
                    evaluate_shard(bad)
            evaluate.assert_not_called()
        for bad in (True,-1,24,2.0,"10"):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                evaluate_case(bad)
        for bad in ("p1","m0",None):
            with self.subTest(tile=bad),self.assertRaises(ValueError):
                _reference_root_score(bad,3)

    def test_complete_real_shard_merge_and_tamper_rejection(self):
        # All 24 true physical worlds exercise the authority end-to-end.
        original={name:evaluate_shard(name) for name in SHARDS}
        summary=combine(original)
        self.assertEqual(summary["constructed_checkpoints"],24)
        self.assertEqual(summary["independent_natural_games"],0)
        self.assertGreater(summary["legally_robbed_hidden_world_count"],0)
        self.assertLessEqual(summary["legally_robbed_hidden_world_count"],24)
        self.assertIsNone(summary["rob_probability"])
        self.assertIsNone(summary["official_EV_estimate"])
        self.assertFalse(summary["online_policy_changed"])
        self.assertFalse(summary["future_tail_known_to_actor"])
        cases=[]
        bad=deepcopy(original);del bad["set_b"];cases.append(bad)
        bad=deepcopy(original)
        bad["set_a"]["cases"][0]["case_id"]=8;cases.append(bad)
        bad=deepcopy(original)
        bad["set_a"]["cases"][0]["adversarial_rob_branch"][
            "tail_was_consumed"]=True;cases.append(bad)
        bad=deepcopy(original)
        bad["set_a"]["cases"][0]["constructed_same_view_rob_witness_found"]=False
        cases.append(bad)
        bad=deepcopy(original)
        bad["set_a"]["cases"][0]["no_rob_branch"][
            "cash_from_late_kong"]=60;cases.append(bad)
        bad=deepcopy(original)
        bad["set_a"]["cases"][0]["conditional_completed_hand_root"][
            "after_raw_fan"]=98;cases.append(bad)
        bad=deepcopy(original)
        bad["set_a"]["not_expected_score"]=False;cases.append(bad)
        for i,item in enumerate(cases):
            with self.subTest(tamper=i),self.assertRaises(ValueError):
                combine(item)


if __name__=="__main__":
    unittest.main()
