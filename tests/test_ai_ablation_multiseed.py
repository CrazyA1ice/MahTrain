"""M3.11 multi-shuffle stability, leave-one-seed-out and HTML privacy tests."""
from __future__ import annotations

import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from mahtrain_core.ai_ablation_benchmark import (  # noqa: E402
    LEVELS, CONTRASTS, METRICS, ablation_benchmark,
    _empty, _difference,
)
from mahtrain_core.ai_ablation_report import render_ablation_html  # noqa: E402
from examples import benchmark_ablation_ai  # noqa: E402


def _fake(seed, rotation=0, *, lineup=None):
    # Alternates which policy has a verified event; seed 32 has no winner.
    preferred = ("challenge" if seed % 3 == 0 else
                 "baseline" if seed % 3 == 1 else None)
    seat = lineup.index(preferred) if preferred in lineup else None
    wins = ([{"seat": seat, "source": (seat+1) % 4, "kind": "ron"}]
            if seat is not None else [])
    return {
        "seed": seed, "rotation": rotation, "assignment": lineup,
        "terminal_phase": "wall_exhausted", "winners": wins,
        "trace": [
            {"action": "discard", "seat": idx,
             "shanten_regret": int(level == "baseline"),
             "locally_optimal": level != "baseline"}
            for idx, level in enumerate(lineup)
        ],
        "public_events": [{"type": "safe_public_only"}],
        "public_replay": [],
        "physical_count": 108, "actions": 15,
        "partial_win_balances": [0]*4, "wall_remaining": 0,
    }


class MultiSeedReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("mahtrain_core.ai_ablation_benchmark.simulate_match",
                   side_effect=_fake):
            cls.report = ablation_benchmark(
                30, 5, bootstrap_replicates=100)

    def test_seed_direction_counts_and_each_seed_has_five_rotations(self):
        report = self.report
        analysis = report["seed_analysis"]
        self.assertEqual(analysis["unit"], "independent_shuffle_seed_cluster")
        self.assertEqual(analysis["distinct_seed_count"], 5)
        self.assertEqual(len(analysis["per_seed_differences"]), 5)
        self.assertEqual(report["games"], 25)
        self.assertEqual(
            [r["seed"] for r in analysis["per_seed_differences"]],
            [30,31,32,33,34])
        signs = analysis["direction_counts"]["challenge_vs_baseline"][
            "win_event_fraction"]
        self.assertEqual(signs, {
            "positive": 2, "negative": 2, "tied": 1, "undefined": 0})
        for policy in LEVELS:
            self.assertEqual(report["levels"][policy]["exposures"], 20)
        for contrast in analysis["direction_counts"].values():
            for metric in METRICS:
                self.assertEqual(sum(contrast[metric].values()), 5)

    def test_leave_one_out_recomputes_pooled_denominators(self):
        report = self.report
        result = report["seed_analysis"]["leave_one_seed_out"]
        self.assertIsNotNone(result)
        for a, b in CONTRASTS:
            key = a+"_vs_"+b
            for metric in METRICS:
                values = []
                for left_out in range(5):
                    combined = {level: _empty() for level in LEVELS}
                    for n, group in enumerate(report["per_seed"]):
                        if n == left_out:
                            continue
                        for level, row in group["levels"].items():
                            for field, amount in row.items():
                                combined[level][field] += amount
                    value = _difference(combined, a, b, metric)
                    if value is not None:
                        values.append(value)
                reported = result[key][metric]
                self.assertEqual(
                    reported["min"] if reported else None,
                    round(min(values),4) if values else None)
                self.assertEqual(
                    reported["max"] if reported else None,
                    round(max(values),4) if values else None)
                if reported:
                    self.assertEqual(reported["valid_exclusions"],
                                     len(values))

    def test_five_seed_bootstrap_unit_and_single_seed_boundary(self):
        report = self.report
        self.assertEqual(report["intervals"]["replications"], 100)
        self.assertEqual(report["interval_status"], "exploratory_only")
        with patch("mahtrain_core.ai_ablation_benchmark.simulate_match",
                   side_effect=_fake):
            one = ablation_benchmark(30,1)
        self.assertIsNone(one["intervals"])
        self.assertIsNone(one["seed_analysis"]["leave_one_seed_out"])
        self.assertEqual(one["seed_analysis"]["distinct_seed_count"], 1)
        self.assertEqual(
            sum(one["seed_analysis"]["direction_counts"][
                "challenge_vs_baseline"]["win_event_fraction"].values()), 1)

    def test_html_is_self_contained_and_aggregate_only(self):
        page = render_ablation_html(self.report)
        self.assertIn('<svg role="img"',page)
        self.assertIn("逐种子",page)
        self.assertIn("留一种子",page)
        self.assertIn("M3.11",page)
        self.assertNotIn("<script",page)
        self.assertNotIn('src="http',page)
        self.assertNotIn('href="http',page)
        self.assertNotIn("opponent_hands",page)
        self.assertNotIn("future_wall",page)
        self.assertNotIn("trace",page)
        self.assertNotIn("safe_public_only",page)
        modified = json.loads(json.dumps(self.report))
        modified["seed_analysis"]["per_seed_differences"][0]["seed"] = (
            '<img src=x onerror=alert(1)>')
        escaped = render_ablation_html(modified)
        self.assertIn("&lt;img",escaped)
        self.assertNotIn("<img",escaped)
        with self.assertRaises(ValueError):
            render_ablation_html({"protocol": "unrelated"})

    def test_cli_writes_per_seed_contrast_and_offline_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            args = ["benchmark_ablation_ai.py",
                    "--seed-start", "30", "--seeds", "5",
                    "--json-out", str(root/"report.json"),
                    "--csv-out", str(root/"policy.csv"),
                    "--contrast-csv-out", str(root/"contrasts.csv"),
                    "--html-out", str(root/"report.html")]
            with (patch.object(benchmark_ablation_ai, "ablation_benchmark",
                               return_value=self.report),
                  patch("sys.argv",args),
                  contextlib.redirect_stdout(io.StringIO())):
                benchmark_ablation_ai.main()
            with (root/"contrasts.csv").open(
                    encoding="utf-8-sig",newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows),5*len(CONTRASTS))
            self.assertEqual(rows[0]["seed"],"30")
            self.assertIn("win_event_fraction_delta_pp",rows[0])
            self.assertIn("M3.11", (root/"report.html").read_text(
                encoding="utf-8"))
            with (root/"report.json").open(encoding="utf-8") as fh:
                output = json.load(fh)
            self.assertEqual(
                output["seed_analysis"]["distinct_seed_count"],5)
            self.assertNotIn("safe_public_only",
                             (root/"report.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
