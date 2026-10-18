"""M3.56: true offline labels may NEVER contaminate public input features."""
from __future__ import annotations

import copy
import json
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core.ai_tenpai_calibration import (
    FEATURE_NAMES, REPORT_PROTOCOL, _truth_label,
    collect_offline_observations, public_tenpai_features,
    fit_public_logistic, evaluate_calibration, run_seed_split_pilot,
)
from mahtrain_core.four_player import FourPlayerOpening


def public_view():
    return {
        "seat": 0, "wall_count": 19,
        "missing_suits": ["p", "m", "s", "p"],
        "won": [False] * 4,
        "melds": [[], [{"type": "peng", "tile": "s2"},
                       {"type": "peng", "tile": "s5"}], [], []],
        "discards": [
            {"seat": 1, "tile": t} for t in
            ("m1", "m4", "p1", "s8", "m8", "s6", "p2", "p3")
        ],
    }


def labeled(seed, good, repetitions=1):
    # All source features in [0,1]; positive labels are correlated with
    # public evidence, never with an opponent's hidden hand.
    public = ((1., 1., 1., 1., 1., 0., 1.) if good else
              (1., 0., 0., 0., 0., 1., 0.))
    return [{"seed": seed, "tenpai": int(good),
             "features": public} for _ in range(repetitions)]


class OfflineTenpaiCalibrationTests(unittest.TestCase):
    def test_only_public_inputs_affect_features(self):
        view = public_view()
        original = public_tenpai_features(view, 1)
        evil = copy.deepcopy(view)
        evil.update({
            "opponent_hands": [["m9"] * 13] * 3,
            "_hands": [["s9"] * 13] * 4,
            "future_wall": ["s1"] * 55,
            "match_seed": 12345,
            "private_draw": "s3",
            "can_self_draw_win": True,
            "hand": ["m9"] * 14,
        })
        self.assertEqual(original, public_tenpai_features(evil, 1))
        self.assertEqual(len(original), len(FEATURE_NAMES))
        self.assertTrue(all(0 <= x <= 1 for x in original))
        self.assertGreater(original[2], 0)
        self.assertGreater(original[3], 0)
        self.assertGreater(original[6], 0)
        self.assertGreater(public_tenpai_features(view, 1)[5], 0)
        changed = copy.deepcopy(view)
        changed["discards"].append({"seat": 1, "tile": "p5"})
        self.assertNotEqual(original, public_tenpai_features(changed, 1))
        with self.assertRaises(ValueError):
            public_tenpai_features(view, 0)
        with self.assertRaises(ValueError):
            public_tenpai_features(view, 4)
        changed["wall_count"] = -1
        with self.assertRaises(ValueError):
            public_tenpai_features(changed, 1)

    def test_sealed_truth_label_uses_real_rules_on_thirteen_tiles(self):
        game = FourPlayerOpening(17)
        game.phase = "await_discard"
        game.missing_suits = ["p"] * 4
        ready = ["m1", "m2", "m3", "m4", "m5", "m6", "m7",
                 "m8", "m9", "s1", "s1", "s1", "s2"]
        game._hands[1] = ready[:]
        game._melds[1] = []
        self.assertEqual(_truth_label(game, 1), 1)
        game._hands[1] = ["m1", "m1", "m2", "m4", "m5", "m7",
                          "m8", "s1", "s2", "s4", "s5", "s7", "s9"]
        self.assertEqual(_truth_label(game, 1), 0)
        game._hands[1].append("s8")
        self.assertIsNone(_truth_label(game, 1))
        game._won[1] = True
        self.assertIsNone(_truth_label(game, 1))

    def test_brier_reliability_and_prior_calibration(self):
        rows = labeled(30, True) + labeled(30, False, repetitions=3)
        metrics = evaluate_calibration(rows, None, prior=.25)
        self.assertEqual(metrics["n"], 4)
        self.assertEqual(metrics["positives"], 1)
        self.assertAlmostEqual(metrics["brier"], .1875)
        self.assertEqual(sum(b["count"] for b in metrics["reliability"]), 4)
        self.assertAlmostEqual(metrics["ece"], 0)
        with self.assertRaises(ValueError):
            evaluate_calibration(rows, None)
        with self.assertRaises(ValueError):
            evaluate_calibration(rows, [0.] * len(FEATURE_NAMES), prior=.25)
        with self.assertRaises(ValueError):
            evaluate_calibration(rows, [float("nan")] * len(FEATURE_NAMES))
        with self.assertRaises(ValueError):
            evaluate_calibration(rows, None, prior=1.1)

    def test_logistic_can_learn_public_signal_and_is_deterministic(self):
        train = (
            labeled(100, True, repetitions=12) +
            labeled(100, False, repetitions=12) +
            labeled(101, True, repetitions=12) +
            labeled(101, False, repetitions=12)
        )
        test = labeled(102, True, repetitions=4) + labeled(
            102, False, repetitions=4)
        first = fit_public_logistic(train)
        self.assertEqual(first, fit_public_logistic(train))
        fitted = evaluate_calibration(test, first)
        prior = evaluate_calibration(test, None, prior=.5)
        self.assertLess(fitted["brier"], prior["brier"])
        self.assertLess(fitted["log_loss"], prior["log_loss"])
        self.assertEqual(len(first), len(FEATURE_NAMES))
        self.assertTrue(all(math.isfinite(value) for value in first))

    def test_seed_split_and_private_output_contract(self):
        def fake_collect(seed, *, stride=3):
            self.assertEqual(stride, 2)
            return labeled(seed, True) + labeled(seed, False)
        with patch("mahtrain_core.ai_tenpai_calibration.collect_offline_observations",
                   side_effect=fake_collect) as collect:
            report = run_seed_split_pilot([10, 11], [12], stride=2)
        self.assertEqual(collect.call_count, 3)
        self.assertEqual(report["protocol"], REPORT_PROTOCOL)
        self.assertEqual(report["train_n"], 4)
        self.assertEqual(report["test_n"], 2)
        self.assertEqual(report["train_seeds"], [10, 11])
        self.assertEqual(report["test_seeds"], [12])
        self.assertFalse(report["can_claim_improvement"])
        self.assertFalse(report["contains_hidden_hands"])
        dumped = json.dumps(report)
        for forbidden in ("_hands", "opponent_hands", "future_wall",
                          '"hand":', '"raw_observations":'):
            self.assertNotIn(forbidden, dumped)
        with self.assertRaises(ValueError):
            run_seed_split_pilot([10, 11], [11, 12])
        with self.assertRaises(ValueError):
            run_seed_split_pilot([10, 10], [12])
        with self.assertRaises(ValueError):
            run_seed_split_pilot([], [12])
        with self.assertRaises(ValueError):
            run_seed_split_pilot([10], [True])

    def test_trusted_callback_keeps_hidden_labels_off_online_replay(self):
        ready = ["m1", "m2", "m3", "m4", "m5", "m6", "m7",
                 "m8", "m9", "s1", "s1", "s1", "s2"]
        fake = SimpleNamespace(
            turn=0, _won=[False] * 4,
            _hands=[["m1"] * 14, ready[:], ready[:], ready[:]],
            _melds=[[], [], [], []],
            missing_suits=["p"] * 4,
        )
        view = public_view()
        view["missing_suits"] = ["p"] * 4
        fake.private_view = lambda seat: dict(view, seat=seat)
        def offline_simulate(seed, rotation, offline_observer):
            self.assertEqual(seed, 38)
            self.assertEqual(rotation, 38 % 3)
            for _ in range(4):
                offline_observer(fake)
            return {"public_replay": [], "trace": []}
        with patch("mahtrain_core.ai_tenpai_calibration.simulate_match",
                   side_effect=offline_simulate):
            rows = collect_offline_observations(38, stride=2)
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(r["tenpai"] == 1 for r in rows))
        self.assertTrue(all("hand" not in r for r in rows))
        self.assertTrue(all("wall" not in r for r in rows))
        self.assertEqual(set(r["seed"] for r in rows), {38})


if __name__ == "__main__":
    unittest.main()
