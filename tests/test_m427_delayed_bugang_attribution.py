"""M4.27 true same-view delayed supplement-kong guard reason tests."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"src"),str(ROOT)]

from mahtrain_core.ai_delayed_bugang_targeted import (
    SPECS, SHARDS, construct_checkpoint
)
from mahtrain_core.ai_delayed_bugang_attribution import (
    PROTOCOL, REASONS, STRICT_REASONS, diagnose_view, diagnose_case,
    diagnose_shard, combine
)


def _stub_case(case_id: int, *, reason="guard_ukeire_down", different=True):
    target, family = SPECS[case_id]
    return {
        "case_id":case_id,
        "exposed_peng":target,
        "shape_family":family,
        "physical_count":108,
        "baseline_shanten":1,
        "candidate_shanten":1,
        "baseline_effective_copies":10,
        "candidate_effective_copies":9,
        "baseline_fan_proxy":10,
        "candidate_fan_proxy":10,
        "passed_original_75pct_policy":True,
        "strict_guard_reason":reason,
        "guard_only_rejection_of_target":reason in STRICT_REASONS,
        "same_view_action_changed":different,
        "guarded_action":"pass",
        "unguarded_action":"bu_gang" if different else "pass",
        "competing_other_kongs":0,
    }


def _stub_shards():
    return {
        name:{
            "protocol":PROTOCOL,
            "shard":name,
            "case_ids":list(ids),
            "constructs_only":True,
            "no_expected_score_claim":True,
            "cases":[_stub_case(i) for i in ids],
        }
        for name,ids in SHARDS.items()
    }


class M427GuardAttributionTests(unittest.TestCase):
    def test_no_authoritative_rules_mutation_or_future_wall_lookahead(self):
        for case_id in (0,1,8,12,23):
            with self.subTest(case_id=case_id):
                game=construct_checkpoint(case_id,delayed=True)
                before=game.debug_tile_counts()
                public=game.public_state()
                view=game.private_view(0)
                original=deepcopy(view)
                outcome=diagnose_view(view,target=SPECS[case_id][0])
                self.assertEqual(view,original)
                self.assertEqual(game.debug_tile_counts(),before)
                self.assertEqual(game.public_state(),public)
                self.assertIn(outcome["strict_guard_reason"],REASONS)
                self.assertEqual(
                    outcome["guard_only_rejection_of_target"],
                    outcome["strict_guard_reason"] in STRICT_REASONS)
                self.assertEqual(outcome["same_view_action_changed"],
                    outcome["guarded_action"]!=outcome["unguarded_action"])
                self.assertNotIn("hand",outcome)
                self.assertNotIn("future_wall",outcome)

    def test_reject_non_delayed_or_legacy_and_nonlegal_target(self):
        view=construct_checkpoint(0,delayed=True).private_view(0)
        paid=construct_checkpoint(0,delayed=False).private_view(0)
        target=SPECS[0][0]
        cases=(
            ({**view,"legacy_bugang_cash_rule":True}, target),
            (paid,target),
            (view,"p9"),
            ({**view,"kong_options":[]},target),
            ({**view,"seat":1},target),
        )
        for i,(check,tile) in enumerate(cases):
            with self.subTest(index=i),self.assertRaises(ValueError):
                diagnose_view(check,target=tile)
        for case in (True,-1,24,1.0,"0"):
            with self.subTest(case=case),self.assertRaises(ValueError):
                diagnose_case(case)

    def test_same_view_guard_ablation_has_no_official_money_side_effect(self):
        for case_id in (2,13):
            with self.subTest(case_id=case_id):
                game=construct_checkpoint(case_id,delayed=True)
                balance=game.kong_ledger.public_state()
                state=game.public_state()
                diagnose_view(game.private_view(0),target=SPECS[case_id][0])
                self.assertEqual(game.kong_ledger.public_state(),balance)
                self.assertEqual(game.public_state(),state)
                self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_structural_rejection_is_not_mislabeled_as_strict_guard(self):
        with patch("mahtrain_core.ai_delayed_bugang_attribution._outlook_better_than_baseline",
                   return_value=False):
            # A deliberately tampered historical scorer must cause a
            # mismatch if the strict guard label is internally inconsistent.
            # This check exercises the existing prohibition on invented
            # "guard effect" under an old-floor rejection.
            with self.assertRaises(RuntimeError):
                diagnose_view(
                    construct_checkpoint(1,delayed=True).private_view(0),
                    target=SPECS[1][0])

    def test_complete_constructed_grid_has_no_population_claim(self):
        with patch("mahtrain_core.ai_delayed_bugang_attribution.diagnose_case",
                   side_effect=lambda i:_stub_case(i)):
            pieces={name:diagnose_shard(name) for name in SHARDS}
        merged=combine(pieces)
        self.assertEqual(merged["total_constructed_checkpoints"],24)
        self.assertEqual(merged["independent_natural_shuffle_seeds"],0)
        self.assertEqual(merged["completed_natural_games"],0)
        self.assertTrue(merged["no_ev_conclusion"])
        self.assertFalse(merged["policy_changed"])
        self.assertEqual(merged["same_view_policy_disagreement_count"],24)
        self.assertEqual(merged["guard_reason_counts"]["guard_ukeire_down"],24)
        self.assertEqual(len(merged["disagreement_cases"]),24)

    def test_fail_closed_on_missing_or_tampered_case(self):
        good=_stub_shards()
        wrongs=[]
        missing=deepcopy(good); del missing["set_c"]; wrongs.append(missing)
        bad=deepcopy(good); bad["set_a"]["cases"][0]["case_id"]=9
        wrongs.append(bad)
        bad=deepcopy(good);bad["set_a"]["cases"][0]["physical_count"]=107
        wrongs.append(bad)
        bad=deepcopy(good);bad["set_a"]["cases"][0]["baseline_fan_proxy"]=-3
        wrongs.append(bad)
        bad=deepcopy(good);bad["set_a"]["cases"][0]["strict_guard_reason"]="made_up"
        wrongs.append(bad)
        bad=deepcopy(good);bad["set_a"]["cases"][0]["same_view_action_changed"]=False
        wrongs.append(bad)
        bad=deepcopy(good);bad["set_a"]["cases"][0]["guard_only_rejection_of_target"]=False
        wrongs.append(bad)
        bad=deepcopy(good);bad["set_a"]["no_expected_score_claim"]=False
        wrongs.append(bad)
        for i, candidate in enumerate(wrongs):
            with self.subTest(case=i),self.assertRaises(ValueError):
                combine(candidate)

    def test_invalid_shard_never_runs_private_expensive_diagnostics(self):
        with patch("mahtrain_core.ai_delayed_bugang_attribution.diagnose_case") as fn:
            for name in ("set_x","",0,True,None):
                with self.subTest(shard=name),self.assertRaises(ValueError):
                    diagnose_shard(name)
            fn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
