"""M3.80 holdout seed-cluster comparison of legacy vs current challenge CALL policy.

Identical *initial* shuffles and opponent seat lineups, 4 candidate seats per
seed, two complete authoritative games per candidate seat. The resulting games
diverge after the first different decision. Use seed clusters for inference,
NOT 8*N matches pretending to be independent samples.

All scoring comes from PUBLIC, server-authoritative win/kong/exhaustive ledgers.
No opponent concealed hands or future-wall contents are read or retained.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from random import Random
from statistics import mean
from time import perf_counter_ns
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mahtrain_core.ai import MahjongAgent
from mahtrain_core.ai_tournament import simulate_match

CALLS = {"peng", "ming_gang", "an_gang", "bu_gang"}
KONGS = {"ming_gang", "an_gang", "bu_gang"}
ROTATION = ("challenge", "advanced", "basic", "baseline")
# Statistics are defined BEFORE inspecting the new holdout seed results.
CLUSTER_KEYS = (
    "net", "hu_points", "kong_points", "exhaustive_points", "win_events",
    "self_draws", "ron_wins", "deal_in_events", "rob_kong_deal_ins",
    "resolved_calls", "resolved_kongs", "attempted_calls",
)
BOOTSTRAP_REPLICATES = 2000
BOOTSTRAP_SEED = 3802026


class TimedChallenge(MahjongAgent):
    """Instrument only real legal call-choice opportunities; no extra RNG."""

    def __init__(self, *, seed: int, seat: int, legacy_calls: bool = False):
        super().__init__("challenge", seed=seed, seat=seat)
        self.legacy_calls = legacy_calls
        self._call_wall_ms: list[float] = []
        self._real_call_decisions = 0

    def _decision(self, name: str, view, *, rob=False):
        # Timing only if there are at least two legal choices. A "pass"-only
        # window is not a strategy decision and would bias mean wall time.
        if name == "response":
            options = view["rob_options"] if rob else view["claim_options"]
            measurable = len(options) > 1
        else:
            measurable = bool(view["kong_options"])
        old = self.level
        started = perf_counter_ns() if measurable else None
        if self.legacy_calls:
            self.level = "advanced"
        try:
            if name == "response":
                return super().response(view, rob=rob)
            return super().kong(view)
        finally:
            self.level = old
            if measurable:
                self._real_call_decisions += 1
                self._call_wall_ms.append(
                    (perf_counter_ns() - started) / 1_000_000
                )

    def response(self, view, *, rob=False):
        return self._decision("response", view, rob=rob)

    def kong(self, view):
        return self._decision("kong", view)


# Keep the old public class name for downstream offline imports.
class LegacyCallChallenge(TimedChallenge):
    def __init__(self, *, seed: int, seat: int):
        super().__init__(seed=seed, seat=seat, legacy_calls=True)


def public_outcome(match: dict[str, Any], seat: int,
                   agent: TimedChallenge) -> dict[str, Any]:
    """Attribute a rule-finalized, public net balance without double counts."""
    total = match["official_settled_balances"]
    hu = match["partial_win_balances"]
    kong = match["official_kong_balances"]
    wall = match["official_exhaustive_balances"]
    for part in (total, hu, kong, wall):
        if (type(part) is not list or len(part) != 4
                or any(type(value) is not int for value in part)
                or sum(part) != 0):
            raise RuntimeError("invalid public rule ledger")
    if any(total[i] != hu[i] + kong[i] + wall[i] for i in range(4)):
        raise RuntimeError("official balance components do not reconcile")
    winners = match["winners"]
    claimed = [
        event for event in match["public_events"]
        if event["type"] in CALLS and event.get("seat") == seat
    ]
    attempted = [
        event for event in match["trace"]
        if event.get("seat") == seat and event.get("action") in CALLS
    ]
    return {
        "net": total[seat], "hu_points": hu[seat],
        "kong_points": kong[seat], "exhaustive_points": wall[seat],
        "win_events": sum(w["seat"] == seat for w in winners),
        "self_draws": sum(w["seat"] == seat and
                          w["kind"] == "self_draw" for w in winners),
        "ron_wins": sum(w["seat"] == seat and
                        w["kind"] == "ron" for w in winners),
        "deal_in_events": sum(
            w["source"] == seat and w["seat"] != seat
            and w["kind"] in ("ron", "rob_kong") for w in winners
        ),
        "rob_kong_deal_ins": sum(
            w["source"] == seat and w["seat"] != seat
            and w["kind"] == "rob_kong" for w in winners
        ),
        "resolved_calls": len(claimed),
        "resolved_kongs": sum(e["type"] in KONGS for e in claimed),
        "attempted_calls": len(attempted),
        "call_decision_opportunities": agent._real_call_decisions,
        "call_decision_wall_ms": round(sum(agent._call_wall_ms), 5),
        "mean_legal_call_decision_wall_ms": (
            round(mean(agent._call_wall_ms), 5)
            if agent._call_wall_ms else None
        ),
        "wall_exhausted": match["terminal_phase"] == "wall_exhausted",
    }


def cluster_bootstrap_ci(
    values: list[float], *, replicates: int = BOOTSTRAP_REPLICATES,
    random_seed: int = BOOTSTRAP_SEED,
) -> list[float] | None:
    """Resample WHOLE seeds, never individual rotations or seat outcomes."""
    if len(values) < 8:
        return None
    if any(not isinstance(x, (int, float)) for x in values):
        raise ValueError("bootstrap expects numeric seed-cluster means")
    rng = Random(random_seed)
    n = len(values)
    samples = sorted(
        mean(values[rng.randrange(n)] for _ in range(n))
        for _ in range(replicates)
    )
    # Observational 95% percentile interval, not a significance verdict.
    return [
        round(samples[int((replicates - 1) * .025)], 4),
        round(samples[int((replicates - 1) * .975)], 4),
    ]


def summarize_cases(cases: list[dict[str, Any]], seeds: int) -> dict[str, Any]:
    by_seed: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_seed[case["seed"]].append(case)
    if len(by_seed) != seeds or any(
        sorted(row["seat"] for row in rows) != [0, 1, 2, 3]
        for rows in by_seed.values()
    ):
        raise ValueError("expected exactly four distinct seat comparisons per seed")
    per_seed = []
    for seed in sorted(by_seed):
        rows = by_seed[seed]
        deltas = {
            name: mean(
                row["proposed"][name] - row["legacy"][name]
                for row in rows
            )
            for name in CLUSTER_KEYS
        }
        per_seed.append({
            "seed": seed,
            "mean_four_seat_delta": deltas["net"],
            "paired_deltas": deltas,
        })
    means = {
        name: round(mean(r["paired_deltas"][name] for r in per_seed), 4)
        for name in CLUSTER_KEYS
    }
    intervals = {
        name: cluster_bootstrap_ci(
            [r["paired_deltas"][name] for r in per_seed])
        for name in CLUSTER_KEYS
    }
    return {
        "per_seed": per_seed,
        "mean_seed_cluster_delta": means["net"],
        "mean_paired_deltas": means,
        "cluster_bootstrap_95pct_intervals": intervals,
        "number_of_independent_seed_clusters": seeds,
        "confidence_interval_method": (
            "seed-cluster percentile bootstrap; 2000 deterministic "
            "resamples; descriptive, not formal evidence of superiority"
        ),
    }


def evaluate(seed_start: int, seeds: int) -> dict[str, Any]:
    if (type(seed_start) is not int or seed_start < 0
            or type(seeds) is not int or not 1 <= seeds <= 100):
        raise ValueError("seed_start must be uint32, seeds 1..100")
    if seed_start + seeds > 2**32:
        raise ValueError("seed range exceeds uint32")
    cases = []
    for seed in range(seed_start, seed_start + seeds):
        for seat in range(4):
            lineup = list(ROTATION[(-seat) % 4:] + ROTATION[:(-seat) % 4])
            assert lineup[seat] == "challenge"
            old_agent = LegacyCallChallenge(seed=seed, seat=seat)
            new_agent = TimedChallenge(seed=seed, seat=seat)
            old = simulate_match(
                seed, lineup=lineup, offline_kong_base=1,
                offline_agent_overrides={seat: old_agent},
            )
            new = simulate_match(
                seed, lineup=lineup, offline_kong_base=1,
                offline_agent_overrides={seat: new_agent},
            )
            for version in (old, new):
                if version["physical_count"] != 108:
                    raise RuntimeError("physical tile conservation violated")
                if version["terminal_phase"] not in ("finished", "wall_exhausted"):
                    raise RuntimeError("incomplete experimental game")
                if version["scoring_rules"] != {
                    "room_coefficient": 100, "fan_cap": 3, "kong_base": 1
                }:
                    raise RuntimeError("unexpected score rule configuration")
                if version["assignment"] != lineup:
                    raise RuntimeError("comparison changed opponent lineup")
            legacy = public_outcome(old, seat, old_agent)
            proposed = public_outcome(new, seat, new_agent)
            cases.append({
                "seed": seed, "seat": seat,
                "legacy": legacy, "proposed": proposed,
                # Historical fields retained for existing M3.79 readers.
                "legacy_net": legacy["net"], "proposed_net": proposed["net"],
                "paired_delta": proposed["net"] - legacy["net"],
                "legacy_calls": legacy["attempted_calls"],
                "proposed_calls": proposed["attempted_calls"],
                "legacy_resolved_calls": legacy["resolved_calls"],
                "proposed_resolved_calls": proposed["resolved_calls"],
                "legacy_hu_count": legacy["win_events"],
                "proposed_hu_count": proposed["win_events"],
                "legacy_terminal": old["terminal_phase"],
                "proposed_terminal": new["terminal_phase"],
            })
    aggregated = summarize_cases(cases, seeds)
    return {
        "protocol": "four_seat_paired_initial_shuffle_v2_authoritative_ledger",
        "seed_start": seed_start,
        "independent_seed_clusters": seeds,
        "total_games": 8 * seeds,
        "score_scope": "official_zero_sum_with_kong_base_1",
        "metrics_scope": (
            "public winner and claim settlement events; authoritative "
            "Hu/kong/exhaustion ledger; challenge call-choice wall latency"
        ),
        **aggregated,
        "cases": cases,
        "disclaimer": (
            "Seed clusters are the units of inference; four seats within a "
            "seed are dependent. Paired initial shuffles do not make "
            "post-decision games identical. CI compute time is noisy; "
            "report call-decision timing descriptively only. No claim of "
            "AI superiority from small or selected samples."),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=900)
    parser.add_argument("--seeds", type=int, default=8)
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
