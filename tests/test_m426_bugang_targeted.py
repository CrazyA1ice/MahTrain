"""M4.26 legally constructed full-physical cash timing / challenge guard audit."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from mahtrain_core.ai import MahjongAgent
from mahtrain_core.ai_delayed_bugang_targeted import (
    PROTOCOL, SHARDS, SPECS, _spec, construct_checkpoint,
    evaluate_case, evaluate_shard, audit_and_combine,
)
from mahtrain_core.rules import score_win


class TargetedBuGangCoverageTests(unittest.TestCase):
    def test_fixed_grid_is_disjoint_and_not_prior_natural_seeds(self):
        self.assertEqual(len(SPECS), 24)
        self.assertEqual(
            sorted(x for s in SHARDS.values() for x in s),
            list(range(24)))
        self.assertEqual({family for _, family in SPECS},
                         {"mixed", "concentrated"})
        self.assertTrue({target for target, _ in SPECS}
                        <= {s + str(r) for s in "ms"
                            for r in (1,2,3,5,7,9)})
        for bad in (-1, 24, 1.0, True, "1"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _spec(bad)
        with self.assertRaises(ValueError):
            construct_checkpoint(0, delayed=0)

    def test_real_turns_and_private_boundary_for_two_shapes(self):
        for case_id in (0, 1, 12, 23):
            with self.subTest(case=case_id):
                target, _ = SPECS[case_id]
                paid = construct_checkpoint(case_id, delayed=False)
                delayed = construct_checkpoint(case_id, delayed=True)
                pv, dv = paid.private_view(0), delayed.private_view(0)
                self.assertEqual(pv["drawn_tile"], target)
                self.assertNotEqual(dv["drawn_tile"], target)
                self.assertEqual(dv["hand"].count(target), 1)
                self.assertIn(
                    {"type":"bu_gang","tile":target}, dv["kong_options"])
                self.assertEqual(paid.debug_tile_counts()["total"],108)
                self.assertEqual(delayed.debug_tile_counts()["total"],108)
                self.assertEqual(len(delayed.public_state()["discards"]),4)
                for game in (paid, delayed):
                    st=game.public_state()
                    self.assertNotIn("hand", st)
                    self.assertNotIn("drawn_tile", st)
                    self.assertNotIn("future_wall", st)
                    self.assertFalse(game.private_view(0)[
                        "legacy_bugang_cash_rule"])

    def test_real_authoritative_money_does_not_depend_on_legacy_ai_flag(self):
        for case_id in (0, 12):
            with self.subTest(case=case_id):
                row=evaluate_case(case_id)
                self.assertEqual(row["paid_event_status"], "posted")
                self.assertEqual(row["paid_kong_money"],60)
                self.assertEqual(row["delayed_event_status"],"not_payable")
                self.assertEqual(row["delayed_kong_money"],0)
                self.assertEqual(row["physical_count"],108)
                self.assertIn(row["delayed_guarded_action"],
                              ("pass","bu_gang","an_gang"))
                self.assertIn(row["delayed_unguarded_action"],
                              ("pass","bu_gang","an_gang"))
                self.assertIs(
                    row["guard_disagreement"],
                    row["delayed_guarded_action"] !=
                    row["delayed_unguarded_action"])

    def test_same_physical_case_is_seed_deterministic(self):
        first=evaluate_case(2)
        self.assertEqual(first,evaluate_case(2))

    def test_root_bonus_remains_a_real_score_component(self):
        # This is the existing score_win mechanism, NOT a claim that the
        # constructed uncompleted hand itself has won.
        concealed = ["m1"]*3 + ["m2", "m3", "m4"] + [
            "s1", "s2", "s3", "s5", "s5"]
        win=score_win(concealed,[{"type":"bu_gang","tile":"m9"}],
                      "p",cap=6)
        self.assertTrue(win["legal"])
        self.assertEqual(win["bonuses"]["roots"],1)
        self.assertEqual(win["effective_fan"],win["main_fan"]+1)

    def test_audit_rejects_missing_shard_or_tampered_pricing(self):
        originals={}
        # Purely synthetic TEST rows; no observed performance assertions
        for name, ids in SHARDS.items():
            originals[name]={"protocol":PROTOCOL,"shard":name,
                "not_natural_games":True,"no_ev_claim":True,
                "case_ids":list(ids),"cases":[{
                    "case_id":i, "declared_peng_tile":SPECS[i][0],
                    "shape_family":SPECS[i][1],
                    "physical_count":108,
                    "paid_event_status":"posted","paid_kong_money":60,
                    "delayed_event_status":"not_payable",
                    "delayed_kong_money":0,
                    "paid_action":"pass",
                    "delayed_guarded_action":"pass",
                    "delayed_unguarded_action":"pass",
                    "guard_disagreement":False,
                    "paid_vs_delayed_action_changed":False,
                    "other_kong_options":0,
                } for i in ids]}
        good=audit_and_combine(originals)
        self.assertEqual(good["total_constructed_checkpoints"],24)
        self.assertEqual(good["independent_natural_shuffle_seeds"],0)
        self.assertEqual(good["complete_natural_games"],0)
        self.assertEqual(good["measured_counts"]["guard_disagreements"],0)
        with self.assertRaises(ValueError):
            audit_and_combine({k:v for k,v in originals.items()
                               if k!="set_d"})
        bad=deepcopy(originals)
        bad["set_a"]["cases"][0]["delayed_kong_money"]=60
        with self.assertRaises(ValueError):
            audit_and_combine(bad)
        bad=deepcopy(originals)
        bad["set_a"]["cases"][0]["case_id"]=4
        with self.assertRaises(ValueError):
            audit_and_combine(bad)
        bad=deepcopy(originals)
        bad["set_a"]["no_ev_claim"]=False
        with self.assertRaises(ValueError):
            audit_and_combine(bad)

    def test_invalid_shard_fails_before_running_any_ai(self):
        with patch(
            "mahtrain_core.ai_delayed_bugang_targeted.evaluate_case"
        ) as f:
            for shard in ("unknown", True, 1, ""):
                with self.subTest(shard=shard),self.assertRaises(ValueError):
                    evaluate_shard(shard)
            f.assert_not_called()


if __name__ == "__main__":
    unittest.main()
