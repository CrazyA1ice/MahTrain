"""M3.97 OFFLINE first-opportunity Hu-safe single-decision counterfactual study.

Three preregistered policies branch ONLY at the earliest optional action of
the named kind for one challenge seat: unchanged, pass, or highest priority
legal active call/kong. All later decisions use the exact original challenge
policy; terminal outcomes come exclusively from the REAL official rule engine.

This is NOT a live look-ahead engine: no online access to future wall, hidden
opponents or paired results. Exports contain no own hand or other hidden tiles.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from statistics import mean
from typing import Any, Mapping

from .ai import MahjongAgent
from .ai_challenge_call_kong_ablation import _official_outcome, _wall_band
from .ai_challenge_reference_paired import LEVELS
from .ai_tournament import simulate_match

PROTOCOL = "m397_first_optional_action_terminal_counterfactual_v1"
TARGETS = ("claim", "own_kong")
POLICIES = ("baseline", "force_pass", "force_active")
METRICS = ("official_net", "win_points", "kong_points", "exhaustive_points",
           "win_events", "deal_in_events", "realized_kongs")
# Secret tile identities stay in trusted memory; never serialize these.
_SIGNATURE_FIELDS = (
    "seat", "phase", "turn", "hand", "own_melds", "discards", "melds",
    "won", "missing_suits", "wall_count", "tian_ting",
    "pending_discard", "claim_options", "kong_options",
)


def _signature(view: Mapping[str, Any]) -> str:
    """Authorize the *same* decision input without exporting its contents."""
    serial = json.dumps(
        {key: view.get(key) for key in _SIGNATURE_FIELDS},
        sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(serial.encode("ascii")).hexdigest()


def _decision_space(kind: str, view: Mapping[str, Any]) -> tuple:
    if kind == "claim":
        if (view.get("phase") != "claim_window" or
                "hu" in view.get("claim_options", []) or
                not any(x in view.get("claim_options", ())
                        for x in ("peng", "ming_gang"))):
            return ()
        return ("pass", *(
            action for action in ("ming_gang", "peng")
            if action in view["claim_options"]))
    if kind == "own_kong":
        if (view.get("phase") not in ("await_discard", "dealer_discard") or
                view.get("can_self_draw_win") or
                not view.get("kong_options")):
            return ()
        return (None, *(
            dict(row) for row in view["kong_options"]))
    raise ValueError("unknown optional action kind")


def _same_action(left: Any, right: Any) -> bool:
    return left == right


def _public_label(choice: Any, kind: str) -> str:
    if kind == "claim":
        return str(choice)
    if choice is None:
        return "pass"
    # Distinguish multiple legal same-kind kongs by an index in the offered
    # ordered list, never by a concealed tile name or salted tile hash.
    return choice["type"]


class FirstOpportunityAgent(MahjongAgent):
    """Exact challenge baseline except first eligible decision of one kind."""

    def __init__(self, *, seed: int, seat: int, target: str,
                 policy: str = "baseline",
                 expected_signature: str | None = None) -> None:
        if target not in TARGETS or policy not in POLICIES:
            raise ValueError("unsupported frozen action target/policy")
        super().__init__("challenge", seed=seed, seat=seat)
        self.target = target
        self.policy = policy
        self.expected_signature = expected_signature
        self.offer_signature: str | None = None
        self.offer: dict[str, Any] | None = None
        self._private_choices: tuple = ()
        self._original: Any = None
        self._chosen: Any = None
        self._matched = False

    def _resolve(self, kind: str, view: Mapping[str, Any],
                 baseline: Any) -> Any:
        if self.target != kind or self.offer is not None:
            return baseline
        legal = _decision_space(kind, view)
        if not legal:
            return baseline
        if not any(_same_action(baseline, candidate) for candidate in legal):
            raise RuntimeError("challenge baseline chose unavailable operation")
        signature = _signature(view)
        if (self.expected_signature is not None and
                signature != self.expected_signature):
            raise RuntimeError("counterfactual did not reach the SAME decision")
        self._matched = True
        self.offer_signature = signature
        self._private_choices = legal
        self._original = baseline
        chosen = (baseline if self.policy == "baseline"
                  else legal[0] if self.policy == "force_pass"
                  else legal[1])
        if chosen not in legal:
            raise RuntimeError("counterfactual proposed illegal action")
        self._chosen = chosen
        # Diagnostic export is coarse: no tile identities, no private hand,
        # no wall composition, and no signature.
        self.offer = {
            "kind":kind,
            "wall_band":_wall_band(view),
            "options":[_public_label(x,kind) for x in legal],
            "candidate_count":len(legal),
            "baseline_choice":_public_label(baseline,kind),
            "chosen_choice":_public_label(chosen,kind),
            "original_is_pass":baseline == legal[0],
            "changed":chosen != baseline,
            "self_public_melds":len(view.get("own_melds") or []),
            "remaining_opponents":sum(
                i != self.seat and not won for i,won in
                enumerate(view.get("won") or [False]*4)),
        }
        return chosen

    def response(self, view: Mapping[str, Any], *, rob: bool = False) -> str:
        baseline = super().response(view, rob=rob)
        # Hu and robbing Hu MUST remain untouched, including multi-winner Hu.
        if rob or "hu" in (view.get("claim_options") or []):
            return baseline
        return self._resolve("claim", view, baseline)

    def kong(self, view: Mapping[str, Any]) -> dict[str, str] | None:
        baseline = super().kong(view)
        return self._resolve("own_kong", view, baseline)

    def validate_branch(self, expected: "FirstOpportunityAgent") -> None:
        if expected.offer is None:
            if self.offer is not None:
                raise RuntimeError("invented a counterfactual opportunity")
            return
        if (not self._matched or
                self.offer_signature != expected.offer_signature or
                self._private_choices != expected._private_choices or
                self._original != expected._original):
            raise RuntimeError("counterfactual initial decision was not paired")


def _run(seed: int, rotation: int, target: str, policy: str,
         *, expected: FirstOpportunityAgent | None = None
         ) -> tuple[dict[str, Any], FirstOpportunityAgent]:
    lineup = [LEVELS[(seat + rotation) % 4] for seat in range(4)]
    seat = lineup.index("challenge")
    agent = FirstOpportunityAgent(
        seed=seed, seat=seat, target=target, policy=policy,
        expected_signature=(
            expected.offer_signature if expected and expected.offer else None))
    game = simulate_match(
        seed, rotation=rotation % 3, lineup=lineup, offline_kong_base=1,
        offline_agent_overrides={seat: agent})
    score = _official_outcome(game, seat, lineup)
    if expected is not None:
        agent.validate_branch(expected)
    return {
        "score":score,
        "actions_until_terminal":game["actions"],
        "terminal_phase":game["terminal_phase"],
        "opportunity":agent.offer,
    },agent


def _one(seed: int, rotation: int, target: str) -> dict[str, Any]:
    if (type(seed) is not int or not 0 <= seed < 2**32 or
            type(rotation) is not int or rotation not in range(4) or
            target not in TARGETS):
        raise ValueError("invalid counterfactual game identity")
    baseline,model = _run(seed,rotation,target,"baseline")
    row = {
        "seed":seed, "rotation":rotation,
        "challenge_seat": (4-rotation)%4,
        "target":target,
        "offered": model.offer is not None,
        "baseline":baseline,
        "alternatives":{},
    }
    if model.offer is None:
        return row
    for policy in POLICIES[1:]:
        # If forcing the registered alternative yields the unchanged action,
        # it has exactly the same path, ledger and event sequence. Avoid a
        # redundant full simulator replay.
        forced = model._private_choices[
            0 if policy=="force_pass" else 1]
        if forced == model._original:
            row["alternatives"][policy] = {
                **baseline,"reused_unchanged_baseline":True,
                "delta":{metric:0 for metric in METRICS},
                "changed":False,
            }
            continue
        counter, agent = _run(seed, rotation, target, policy, expected=model)
        if agent.offer is None or not agent.offer["changed"]:
            raise RuntimeError("counterfactual did not actually intervene")
        row["alternatives"][policy] = {
            **counter, "reused_unchanged_baseline":False,
            "delta":{
                metric:counter["score"][metric]-baseline["score"][metric]
                for metric in METRICS
            }, "changed":True,
        }
    return row


def _aggregate(seed_start: int, seeds: int) -> dict[str, Any]:
    rows = [
        _one(seed, rotation, target)
        for seed in range(seed_start, seed_start+seeds)
        for rotation in range(4)
        for target in TARGETS
    ]
    summary: dict[str, Any] = {}
    for target in TARGETS:
        subset=[x for x in rows if x["target"]==target]
        by_seed={}
        for seed in range(seed_start,seed_start+seeds):
            group=[x for x in subset if x["seed"]==seed]
            if sorted(x["challenge_seat"] for x in group)!=[0,1,2,3]:
                raise RuntimeError("missing a four-seat independent seed cluster")
            per_policy={}
            for policy in POLICIES[1:]:
                affected=[x for x in group if x["offered"] and
                          x["alternatives"][policy]["changed"]]
                per_policy[policy]={
                    "mean_four_seat_official_net_delta":
                    round(sum(
                        row["alternatives"][policy]["delta"]["official_net"]
                        if row["offered"] else 0
                        for row in group)/4,4),
                    "changed_positions":len(affected),
                }
            by_seed[seed]=per_policy
        comparisons={}
        for policy in POLICIES[1:]:
            values=[
                by_seed[seed][policy]["mean_four_seat_official_net_delta"]
                for seed in sorted(by_seed)]
            deltas=Counter()
            for row in subset:
                if row["offered"]:
                    deltas.update(
                        row["alternatives"][policy]["delta"]
                    )
            comparisons[policy]={
                "mean_seed_cluster_net_delta":round(mean(values),4),
                "positive_seeds":sum(x>0 for x in values),
                "negative_seeds":sum(x<0 for x in values),
                "tied_seeds":sum(x==0 for x in values),
                "changed_positions":sum(
                    row["alternatives"][policy]["changed"]
                    for row in subset if row["offered"]),
                "cumulative_official_component_deltas":{
                    metric:deltas[metric] for metric in METRICS},
                "interval_95pct":None,
                "interval_status":"not_estimated_fewer_than_8_independent_seeds",
            }
        summary[target]={
            "offered_positions":sum(row["offered"] for row in subset),
            "eligible_positions":len(subset),
            "policy_comparisons":comparisons,
            "per_seed": [
                {"seed":seed,"policy_comparisons":by_seed[seed]}
                for seed in sorted(by_seed)],
        }
    # Keep individual outcome records for auditing but NOT decision signatures,
    # choice tile identities, opening concealed hands or future wall content.
    return {
        "independent_seeds":seeds,
        "four_seat_positions":seeds*4,
        "target_positions":len(rows),
        "targets":summary,
        "positions":rows,
    }


def study(*, development_start: int = 14000,
          holdout_start: int = 15000,
          seeds_per_group: int = 2) -> dict[str, Any]:
    if (type(development_start) is not int or
            type(holdout_start) is not int or
            type(seeds_per_group) is not int or
            not 0 <= development_start < 2**32 or
            not 0 <= holdout_start < 2**32 or
            not 1 <= seeds_per_group <= 4 or
            development_start+seeds_per_group > 2**32 or
            holdout_start+seeds_per_group > 2**32 or
            not (development_start+seeds_per_group <= holdout_start or
                 holdout_start+seeds_per_group <= development_start)):
        raise ValueError("overlapping or invalid fixed seed cohorts")
    return {
        "protocol":PROTOCOL,
        "frozen_targets":list(TARGETS),
        "frozen_policies":list(POLICIES),
        "development":_aggregate(development_start,seeds_per_group),
        "holdout":_aggregate(holdout_start,seeds_per_group),
        "live_policy_changed":False,
        "limitations":[
            "All terminal outcomes use the true rules engine; wall and rival hands are NOT observable to the policy.",
            "Each paired world starts with the same shuffle, but paths may diverge after the one forced decision.",
            "The first optional opportunity is predeclared; no cherry-picked successful interventions.",
            "First-claim and first-own-kong opportunities are separate target groups, not independently shuffled samples.",
            "An option absent in a seed/seat is recorded as NO OPPORTUNITY, never a zero-value optimization.",
            "No Han/rob-kong Hu is ever overridden, even if another call is also offered.",
            "A completed-world delta is not an online probability, conditional causal attribution, or guaranteed EV.",
            "Four seat rotations are one seed cluster; the default two independent seeds prohibit confidence intervals.",
        ],
    }
