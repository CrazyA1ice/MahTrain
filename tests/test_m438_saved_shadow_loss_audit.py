"""M4.38: forensic analysis of existing, never-replayed private M4.37 data.

Fixtures for this fast suite are contract-shaped five-game seed stand-ins.
M4.36 integration tests execute and reconcile the actual rules engine.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]

from mahtrain_core.ai_selfplay_local_batch import _get_json
from mahtrain_core.ai_shadow_headtohead import (
    _cluster_path, evaluate_frozen_shadow,
)
from mahtrain_core.ai_shadow_loss_audit import (
    PROTOCOL, audit_saved_shadow_results,
)

TARGET="mahtrain_core.ai_shadow_headtohead"


def _fixture_real_seed(seed,weights):
    rows=[]
    for seat in range(4):
        # Signed win, kong, exhaustive ledgers reconcile the net exactly.
        win=(-300+seat*60) if seed%2==0 else (90-seat*10)
        kong=20 if seat!=3 else -20
        exhaustive=10 if seat!=2 else -30
        delta=win+kong+exhaustive
        rows.append({
            "seat":seat,
            "challenge_baseline_official_net":0,
            "shadow_official_net":delta,
            "delta_shadow_minus_challenge":delta,
            "shadow_discard_decisions":4,
            "shadow_override_count":2,
            "challenge_baseline_game_phase":"finished",
            "shadow_game_phase":"finished",
            "real_win_delta":win,
            "real_kong_delta":kong,
            "real_exhaustive_delta":exhaustive,
        })
    return {
        "private_evaluation_shuffle_seed":seed,
        "seat_rotation_results":rows,
        "original_natural_shuffle_seed_is_one_statistical_cluster":True,
        "complete_authoritative_games":5,
        "same_opening_seed_per_comparison":True,
        "no_real_skill_claim":True,
    }


class SavedLossAuditTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.training=self.root/"original-private"
        self.evaluation=self.root/"real-private-M437"
        self.report=self.root/"new-private-M438"
        self.plan={
            "model_sha256":"a"*64,
            "source_m434_train_seed_start":89800,
            "source_m434_seed_end_exclusive":89804,
            "trained_original_shuffle_clusters":2,
        }
        with patch(TARGET+".load_frozen_local_model",
                   return_value=((.1,.01,.03),self.plan)), \
             patch(TARGET+".evaluate_one_seed",
                   side_effect=_fixture_real_seed) as played:
            self.original=evaluate_frozen_shadow(
                training_dir=self.training,seed_start=91100,seeds=2,
                out_dir=self.evaluation,
            )
        self.assertEqual(played.call_count,2)

    def test_read_only_loss_ledger_decomposition_and_private_csv(self):
        before={str(p.relative_to(self.evaluation)):p.read_bytes()
                for p in self.evaluation.rglob("*") if p.is_file()}
        safe=audit_saved_shadow_results(
            evaluation_dir=self.evaluation,report_dir=self.report
        )
        self.assertEqual(safe["protocol"],PROTOCOL)
        self.assertEqual(safe["original_shuffle_seed_clusters"],2)
        self.assertEqual(safe["total_complete_authoritative_games"],10)
        self.assertEqual(safe["correlated_rotated_seat_comparisons"],8)
        self.assertEqual(safe["observed_discard_opportunities"],32)
        self.assertEqual(safe["observed_actual_overrides"],16)
        self.assertEqual(safe["private_rows_available_locally"],8)
        self.assertAlmostEqual(
            sum(safe["paid_net_delta_accounting_by_component_points"].values()),
            safe["paired_mean_official_net_delta_points"],
        )
        self.assertEqual(safe["paired_mean_official_net_delta_points"],
                         self.original["seat_rotated_seed_cluster_mean_delta_points"])
        self.assertEqual(safe["paired_delta_by_seat_points"],
                         self.original["per_seat_conditional_net_delta_means"])
        self.assertEqual(safe["zero_override_rotations_with_nonzero_delta"],0)
        self.assertTrue(safe["no_action_level_causal_attribution"])
        self.assertTrue(safe["too_few_shuffles_for_exploratory_comparison"])
        self.assertTrue((self.report/"PRIVATE_seat_rotations.csv").is_file())
        self.assertTrue((self.report/"PRIVATE_seed_cluster_totals.csv").is_file())
        self.assertEqual(_get_json(
            self.report/"safe_shadow_loss_attribution_summary.json"),safe)
        csv_text=(self.report/"PRIVATE_seat_rotations.csv").read_text(
            encoding="utf-8-sig")
        self.assertIn("91100",csv_text)
        public=json.dumps(safe,ensure_ascii=False)
        for secret in ("91100","91101","89800","private_shuffle_seed",
                       "private_case","hand","future_wall","training_directory",
                       "a"*64):
            self.assertNotIn(secret,public)
        after={str(p.relative_to(self.evaluation)):p.read_bytes()
               for p in self.evaluation.rglob("*") if p.is_file()}
        self.assertEqual(before,after)

    def test_reject_missing_seed_shard_before_writing_any_results(self):
        _cluster_path(self.evaluation,1).unlink()
        with self.assertRaisesRegex(ValueError,"incomplete"):
            audit_saved_shadow_results(
                evaluation_dir=self.evaluation,report_dir=self.report)
        self.assertFalse(self.report.exists())

    def test_reject_compressed_ledger_mismatch(self):
        ledger=self.evaluation/"PRIVATE_four_seat_paired_matches.jsonl.gz"
        with gzip.open(ledger,"rt",encoding="utf8") as f:
            rows=[json.loads(line) for line in f]
        rows[0]["seat_rotation_results"][0]["real_win_delta"]+=999
        with gzip.open(ledger,"wt",encoding="utf8") as f:
            for row in rows:
                f.write(json.dumps(row)+"\n")
        with self.assertRaisesRegex(ValueError,"differs from audited shards"):
            audit_saved_shadow_results(
                evaluation_dir=self.evaluation,report_dir=self.report)
        self.assertFalse(self.report.exists())

    def test_reject_forged_original_safe_summary(self):
        path=self.evaluation/"safe_four_seat_shadow_summary.json"
        bad=_get_json(path)
        bad["candidate_legal_minimum_shanten_overrides"]=999
        path.write_text(json.dumps(bad),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"cannot be reconciled"):
            audit_saved_shadow_results(
                evaluation_dir=self.evaluation,report_dir=self.report)

    def test_reject_reused_output_or_writing_inside_input(self):
        audit_saved_shadow_results(
            evaluation_dir=self.evaluation,report_dir=self.report)
        with self.assertRaisesRegex(ValueError,"do not overwrite"):
            audit_saved_shadow_results(
                evaluation_dir=self.evaluation,report_dir=self.report)
        with self.assertRaisesRegex(ValueError,"outside the input"):
            audit_saved_shadow_results(
                evaluation_dir=self.evaluation,
                report_dir=self.evaluation/"nested-analysis",
            )

    def test_reject_wrong_plan_and_tampered_checksum(self):
        planpath=self.evaluation/"PRIVATE_frozen_benchmark_plan.json"
        old=_get_json(planpath)
        bad=dict(old,resumable_shards_protocol="old")
        planpath.write_text(json.dumps(bad),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"requires a complete M4.37"):
            audit_saved_shadow_results(
                evaluation_dir=self.evaluation,report_dir=self.report)
        planpath.write_text(json.dumps(old),encoding="utf8")
        shard=_cluster_path(self.evaluation,0)
        bad=_get_json(shard)
        bad["private_case"]["made_up"]="hidden"
        shard.write_text(json.dumps(bad),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"checksum mismatch"):
            audit_saved_shadow_results(
                evaluation_dir=self.evaluation,report_dir=self.report)


if __name__=="__main__":
    unittest.main()
