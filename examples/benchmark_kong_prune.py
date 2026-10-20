"""Compare M3.82 and M3.83 kong evaluators on IDENTICAL legal views.

This is CPU cost for a local own-kong candidate decision, not AI win rate.
Both paths share the M3.81 bounded effective-draw cache, and run in
alternating order with identical public/private authorization.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from statistics import median
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
from mahtrain_core.ai import _challenge_kong
from test_ai_calls import offer_kongs
from test_ai_kong_prune import (
    _legacy_challenge_kong, offer_seven_pairs_disrupting_kong,
)


def benchmark(samples: int = 24, warmups: int = 4) -> dict:
    if type(samples) is not int or not 2 <= samples <= 500:
        raise ValueError("samples must be in 2..500")
    if type(warmups) is not int or not 0 <= warmups <= 100:
        raise ValueError("warmups must be in 0..100")
    cases = [
        ("two_concealed_kong_choices", offer_kongs),
        ("real_shanten_regressing_kong", offer_seven_pairs_disrupting_kong),
    ]
    rows = []
    for name, builder in cases:
        game, seat, view = builder()
        snapshot = copy.deepcopy(view)
        del seat
        durations = {"legacy": [], "pruned": []}
        for index in range(samples + warmups):
            sequence = ("legacy", "pruned") if index % 2 == 0 else (
                "pruned", "legacy")
            actions = {}
            for version in sequence:
                started = perf_counter_ns()
                action = (_legacy_challenge_kong(view) if version == "legacy"
                          else _challenge_kong(view))
                elapsed = (perf_counter_ns() - started) / 1_000_000
                actions[version] = action
                if index >= warmups:
                    durations[version].append(elapsed)
            if actions["legacy"] != actions["pruned"]:
                raise RuntimeError(
                    f"{name}: old={actions['legacy']}, new={actions['pruned']}")
            if snapshot != view or game.debug_tile_counts()["total"] != 108:
                raise RuntimeError("authorized view mutated or tile count lost")
        legacy_med = median(durations["legacy"])
        optimized_med = median(durations["pruned"])
        rows.append({
            "scenario": name,
            "samples_per_version": samples,
            "legacy_median_ms": round(legacy_med, 6),
            "optimized_median_ms": round(optimized_med, 6),
            "median_speedup": (
                round(legacy_med / optimized_med, 3)
                if optimized_med > 0 else None),
            "matched_decision": True,
            "physical_tiles": 108,
        })
    return {
        "protocol": "m383_authorized_kong_same_view_matched_cpu_v1",
        "warmups": warmups,
        "rows": rows,
        "scope": ("Local action-selection CPU on a staged, legal own-turn view."
                  " Shared warmed caches, mixed CI runners; not full-match "
                  "latency, not win rate or expected net score."),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--samples", type=int, default=24)
    p.add_argument("--warmups", type=int, default=4)
    p.add_argument("--json-out", type=Path)
    options = p.parse_args()
    result = benchmark(options.samples, options.warmups)
    data = json.dumps(result, indent=2, ensure_ascii=False)
    if options.json_out:
        options.json_out.parent.mkdir(parents=True, exist_ok=True)
        options.json_out.write_text(data + "\n", encoding="utf-8")
    print(data)


if __name__ == "__main__":
    main()
