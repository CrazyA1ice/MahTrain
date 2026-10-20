"""M3.82 matched-observation audit: skipped pass-only call evaluation.

This is a policy-parity and local CPU benchmark, not a full-game speed or
win-rate experiment. Compare identical authorized 108-tile claim views with
the previous expensive implementation path. Alternate measurement order to
reduce run-order effects. Only observations with a *single* legal choice are
eligible for the pass-only comparison.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from statistics import mean, median
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from mahtrain_core.ai import (MahjongAgent, _call_outlook, _call_settings,
                              _challenge_claim, _own_view)
from test_ai_calls import offer_peng
from test_four_player_claims import deal_for_ron


def snapshots():
    game = deal_for_ron()
    dealer = game.dealer
    game.discard(dealer, "s9")
    natural_pass = game.private_view((dealer + 3) % 4)
    assert natural_pass["claim_options"] == ["pass"]
    game2, seat, peng_view = offer_peng()
    protected_peng = copy.deepcopy(peng_view)
    protected_peng["claim_options"] = ["pass", "peng"]
    protected_peng["tian_ting"] = {
        "eligible": True, "initial_waits": ["m5"],
    }
    assert game.debug_tile_counts()["total"] == 108
    assert game2.debug_tile_counts()["total"] == 108
    return {
        "real_pass_only": natural_pass,
        "verified_tian_peng_only": protected_peng,
    }


def old_response(agent, view):
    """Historical challenge path before M3.82 short-circuiting.

    HU/rob checks omitted because these matched views only offer
    'pass' or 'pass+peng' and never include legal HU or rob choice.
    """
    # Restore exactly the unnecessary pre-check baseline from M3.81
    # for a verified Tian-Ting hand: original outcome already was pass.
    if view.get("tian_ting", {}).get("eligible") and (
            "ming_gang" not in view["claim_options"]):
        hand, melds, missing = _own_view(view)
        public, cap, tian = _call_settings(view)
        _call_outlook(hand, melds, missing, public, cap, tian)
        return "pass"
    return _challenge_claim(view)


def compare(*, samples: int = 24, warmups: int = 4) -> dict:
    if type(samples) is not int or not 2 <= samples <= 1000:
        raise ValueError("samples must be 2..1000")
    if type(warmups) is not int or not 0 <= warmups <= 100:
        raise ValueError("warmups must be 0..100")
    views = snapshots()
    rows = []
    for label, view in views.items():
        agent = MahjongAgent("challenge", seed=42, seat=view["seat"])
        saved = copy.deepcopy(view)
        counters = {"legacy": [], "optimized": []}
        for i in range(samples + warmups):
            # Strict same view, same RNG state, same policy choice.
            for method in (
                ("legacy", "optimized") if i % 2 == 0
                else ("optimized", "legacy")
            ):
                start = perf_counter_ns()
                choice = (
                    old_response(agent, view) if method == "legacy"
                    else agent.response(view)
                )
                elapsed_ms = (perf_counter_ns() - start) / 1e6
                if choice != "pass":
                    raise RuntimeError("benchmark scenario expected exactly pass")
                if i >= warmups:
                    counters[method].append(elapsed_ms)
            if view != saved:
                raise RuntimeError("policy mutated an authorized observation")
        rows.append({
            "scenario": label,
            "samples_per_policy": samples,
            "legacy_median_ms": round(median(counters["legacy"]), 6),
            "optimized_median_ms": round(median(counters["optimized"]), 6),
            "legacy_mean_ms": round(mean(counters["legacy"]), 6),
            "optimized_mean_ms": round(mean(counters["optimized"]), 6),
            "same_decision_on_every_observation": True,
            "all_108_physical_tiles_legal": True,
        })
    return {
        "protocol": "m382_matched_call_response_microbenchmark_v1",
        "measurement": "wall-clock Python perf_counter; not a UI or full-match ETA",
        "samples": samples,
        "warmups": warmups,
        "rows": rows,
        "caveats": (
            "Both paths share M3.81 cache and may be warm; timing is "
            "hardware-dependent. Compared action windows deliberately have "
            "no permitted action except pass, or verified Tian Ting "
            "where peng is never chosen; no speedup for difficult "
            "multi-choice kong strategy is claimed."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--warmups", type=int, default=4)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report = compare(samples=args.samples, warmups=args.warmups)
    data = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(data + "\n", encoding="utf-8")
    print(data)


if __name__ == "__main__":
    main()
