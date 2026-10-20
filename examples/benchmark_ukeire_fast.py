"""M3.81 microbenchmark: exact old-vs-new ukeire enumeration on same states.

All positions are reproducible physically valid OWN concealed/meld holdings
and public observations. This is a CPU comparison, not whole-game win rate.
No timed assertion: hardware load, caches and CI conditions vary.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from mahtrain_core.efficiency import effective_draws, _cached_effective_types_non_tenpai
from test_ukeire_fast import legal_position, reference_effective_draws


def profile(*, samples: int = 24, repeats: int = 3) -> dict:
    if type(samples) is not int or not 1 <= samples <= 100:
        raise ValueError("samples must be 1..100")
    if type(repeats) is not int or not 1 <= repeats <= 15:
        raise ValueError("repeats must be 1..15")

    fixtures = [
        legal_position(1101 + i * 17, i % 3, ("m", "p", "s")[i % 3])
        for i in range(samples)
    ]
    # Verify every measurement pair is EXACT first. Neither variant is
    # allowed to silently change a recommendation by altering ukeire.
    for hand, melds, missing, public in fixtures:
        if (reference_effective_draws(hand, melds, missing, public)
                != effective_draws(hand, melds, missing, public)):
            raise RuntimeError("optimized ukeire differs from M3.80")

    baseline_ms, fast_ms = [], []
    for repeat in range(repeats):
        # Alternate order to reduce systematic warming bias; the public-only
        # stage cache is deliberately cold at the start of fast measurements.
        _cached_effective_types_non_tenpai.cache_clear()
        tasks = (("old", reference_effective_draws),
                 ("fast", effective_draws))
        if repeat % 2:
            tasks = tuple(reversed(tasks))
        for name, func in tasks:
            started = perf_counter()
            for hand, melds, missing, public in fixtures:
                func(hand, melds, missing, public)
            elapsed = (perf_counter() - started) * 1000
            (baseline_ms if name == "old" else fast_ms).append(elapsed)
    old = mean(baseline_ms) / samples
    fast = mean(fast_ms) / samples
    return {
        "protocol": "exact_ukeire_stage_microbenchmark_v1",
        "positions": samples,
        "repetitions": repeats,
        "parity": "all_equal",
        "baseline_mean_ms_per_position": round(old, 6),
        "optimized_mean_ms_per_position": round(fast, 6),
        "descriptive_speedup_ratio": round(old / fast, 4) if fast else None,
        "cache_size_bound": _cached_effective_types_non_tenpai.cache_info().maxsize,
        "limitations": (
            "Same-process CPU test with warmed shanten cache and bounded "
            "non-tenpai stage cache. Caller time includes ordinary public "
            "copy counting. Hardware loads vary. Not a guarantee of "
            "browser responsiveness, or proof of identical outputs without "
            "independent old-vs-new game action parity."),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--samples", type=int, default=24)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--json-out", type=Path)
    args = p.parse_args()
    data = json.dumps(profile(samples=args.samples, repeats=args.repeats),
                      ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(data+"\n",encoding="utf-8")
    print(data)


if __name__ == "__main__":
    main()
