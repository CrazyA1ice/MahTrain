"""Paired initial-shuffle challenge CALL policy pilot (not a strength claim).

Each seed runs 4 seat rotations, same lineup, and exact official net
settlement. After a decision changes the future trajectories are NOT held
fixed; seed-cluster statistics, not game counts, are the independent units.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mahtrain_core.ai import MahjongAgent
from mahtrain_core.ai_tournament import simulate_match

CALLS = {"peng", "ming_gang", "an_gang", "bu_gang"}
ROTATION = ("challenge", "advanced", "basic", "baseline")


class LegacyCallChallenge(MahjongAgent):
    """Historical M3.78 claim/kong policy, with UNCHANGED challenge discards."""

    def __init__(self, *, seed: int, seat: int) -> None:
        super().__init__("challenge", seed=seed, seat=seat)

    def response(self, view, *, rob=False):
        old = self.level
        try:
            self.level = "advanced"
            return super().response(view, rob=rob)
        finally:
            self.level = old

    def kong(self, view):
        old = self.level
        try:
            self.level = "advanced"
            return super().kong(view)
        finally:
            self.level = old


def evaluate(seed_start: int, seeds: int) -> dict:
    if type(seed_start) is not int or seed_start < 0 or type(seeds) is not int or seeds < 1:
        raise ValueError("seed_start and seeds must be positive integers")
    if seed_start + seeds > 2**32:
        raise ValueError("seed range exceeds uint32")
    cases = []
    clusters = []
    for seed in range(seed_start, seed_start + seeds):
        changes = []
        for seat in range(4):
            lineup = list(ROTATION[(-seat) % 4:] + ROTATION[:(-seat) % 4])
            assert lineup[seat] == "challenge"
            old = simulate_match(
                seed, lineup=lineup, offline_kong_base=1,
                offline_agent_overrides={
                    seat: LegacyCallChallenge(seed=seed, seat=seat)},
            )
            new = simulate_match(seed, lineup=lineup, offline_kong_base=1)
            for version in (old, new):
                if version["physical_count"] != 108:
                    raise RuntimeError("physical tile conservation violated")
                scores = version["official_settled_balances"]
                if version["terminal_phase"] not in ("finished", "wall_exhausted"):
                    raise RuntimeError("incomplete experimental game")
                if sum(scores) != 0 or version["scoring_rules"]["kong_base"] != 1:
                    raise RuntimeError("not an actual settled zero-sum kong game")
                if version["assignment"] != lineup:
                    raise RuntimeError("comparison changed opponent lineup")
            delta = (new["official_settled_balances"][seat] -
                     old["official_settled_balances"][seat])
            def call_count(outcome):
                return sum(event.get("seat") == seat and
                           event.get("action") in CALLS
                           for event in outcome["trace"])
            cases.append({
                "seed": seed, "seat": seat,
                "legacy_net": old["official_settled_balances"][seat],
                "proposed_net": new["official_settled_balances"][seat],
                "paired_delta": delta,
                "legacy_calls": call_count(old),
                "proposed_calls": call_count(new),
                "legacy_hu_count": sum(w["seat"] == seat for w in old["winners"]),
                "proposed_hu_count": sum(w["seat"] == seat for w in new["winners"]),
                "legacy_terminal": old["terminal_phase"],
                "proposed_terminal": new["terminal_phase"],
            })
            changes.append(delta)
        clusters.append({"seed": seed, "mean_four_seat_delta": mean(changes)})
    return {
        "protocol": "four_seat_paired_initial_shuffle_v1",
        "independent_seed_clusters": seeds,
        "total_games": 8 * seeds,
        "score_scope": "official_zero_sum_with_kong_base_1",
        "per_seed": clusters,
        "mean_seed_cluster_delta": round(
            mean(s["mean_four_seat_delta"] for s in clusters), 4),
        "cases": cases,
        "disclaimer": (
            "Small pilots cannot demonstrate stable AI superiority. Paired "
            "initial RNG does not imply identical post-decision trajectories. "
            "The policy uses weak one-step copy-weighted surrogates, not a "
            "calibrated whole-game expected net return."),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=810)
    parser.add_argument("--seeds", type=int, default=1)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report = evaluate(args.seed_start, args.seeds)
    data = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(data + "\n", encoding="utf-8")
    print(data)


if __name__ == "__main__":
    main()
