"""M4.08: terminal, authority-ledger follow-through after legal Ming-Gang.

Offline observer retains a reference to its *own game process* only to read
public_state AFTER the game terminates. Nothing from the terminal state is
used when the acting AI selects a call. No hidden wall or opponent hand is
loaded, and output contains only event counts and official 4-seat balances.
"""
from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Mapping

from .ai_dual_claim_fastpath_paired import _dual_optional_options
from .ai_minggang_public_risk_audit import (
    PublicMingGangRiskObserver, public_minggang_exit_risk,
)
from .ai_action_extended_study import _fixed_lineup
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_tournament import simulate_match

PROTOCOL = "m408_actual_minggang_authoritative_ledger_followthrough_v1"
KONG_TYPES = ("ming_gang", "an_gang", "bu_gang")


def audit_official_kong_lifecycle(
    outcome: Mapping[str, Any], board: Mapping[str, Any], seat: int,
) -> dict[str, int]:
    """Reconcile *all* authoritative Kong transactions, report own Ming-Gang.

    Require an actual terminal board; correlate refunds with the public
    after_kong discard that was won. Never approximate Kong credit as EV.
    """
    if type(seat) is not int or seat not in range(4):
        raise ValueError("invalid audited seat")
    if (outcome.get("terminal_phase") not in ("finished", "wall_exhausted")
            or board.get("phase") != outcome["terminal_phase"]):
        raise ValueError("requires completed authority game")
    ledger = board.get("kong_ledger") or {}
    base = ledger.get("base")
    if type(base) is not int or not 1 <= base <= 10**6:
        raise ValueError("terminal audit requires explicitly priced KongLedger")
    events, entries = ledger.get("events"), ledger.get("entries")
    physical, discards = outcome.get("public_events"), board.get("discards")
    balances = ledger.get("balances")
    if (type(events) is not list or type(entries) is not list or
            type(physical) is not list or type(discards) is not list or
            type(balances) is not list or len(balances) != 4):
        raise ValueError("missing terminal public Kong state")
    if (not ledger.get("zero_sum") or sum(balances) != 0 or
            balances != outcome.get("official_kong_balances")):
        raise RuntimeError("official Kong cash does not reconcile")
    declared = [e for e in physical if e.get("type") in KONG_TYPES]
    if len(declared) != len(events):
        raise RuntimeError("Kong announcement count differs from official ledger")
    by_id: dict[int, Mapping[str, Any]] = {}
    expected_entries: Counter[tuple[Any, ...]] = Counter()
    expected_balances = [0]*4
    counts: Counter[str] = Counter()
    for n, (announcement, event) in enumerate(zip(declared, events), 1):
        kind, actor = event.get("type"), event.get("seat")
        payer_seats, source = event.get("payers"), event.get("source")
        if (event.get("id") != n or kind not in KONG_TYPES or
                type(actor) is not int or actor not in range(4) or
                kind != announcement.get("type") or actor != announcement.get("seat")
                or (kind == "ming_gang" and source != announcement.get("source"))):
            raise RuntimeError("announced Kong identity/order conflicts with ledger")
        if (type(payer_seats) is not list or not payer_seats or
                any(type(p) is not int or p not in range(4) or p == actor
                    for p in payer_seats) or len(set(payer_seats)) != len(payer_seats)
                or (kind == "ming_gang" and (
                    type(source) is not int or source not in range(4)
                    or payer_seats != [source]))
                or (kind != "ming_gang" and source is not None)):
            raise RuntimeError("illegal official Kong payment roles")
        amount = (1 if kind == "bu_gang" else 2)*base
        status = event.get("status")
        if event.get("amount_per_payer") != amount or status not in ("posted","voided"):
            raise RuntimeError("invalid priced Kong amount or terminal status")
        if (status == "voided" and event.get("reason") != "kong_discard_ron"):
            raise RuntimeError("Kong refund reason was not the authorized discard Ron")
        by_id[n] = event
        for payer in payer_seats:
            expected_entries[(n,"charge",payer,actor,amount)] += 1
            expected_balances[payer] -= amount
            expected_balances[actor] += amount
            if status == "voided":
                expected_entries[(n,"reversal",actor,payer,amount)] += 1
                expected_balances[payer] += amount
                expected_balances[actor] -= amount
        if kind != "ming_gang":
            continue
        counts["table_minggang_realized"] += 1
        counts["table_minggang_"+status] += 1
        if actor == seat:
            counts["own_minggang_realized"] += 1
            counts["own_minggang_"+status] += 1
            counts["own_minggang_nominal_credit"] += amount
            if status == "posted":
                counts["own_minggang_final_credit"] += amount
    actual_entries: Counter[tuple[Any, ...]] = Counter()
    for n, entry in enumerate(entries, 1):
        if entry.get("index") != n:
            raise RuntimeError("nonsequential official cash entry")
        key = tuple(entry.get(k) for k in (
            "kong_id","kind","payer","recipient","amount"))
        actual_entries[key] += 1
    if actual_entries != expected_entries or expected_balances != balances:
        raise RuntimeError("official Kong charge/reversal does not add up")
    counts["ledger_kong_events"] = len(events)
    counts["ledger_cash_entries"] = len(entries)
    counts["ledger_refunds"] = sum(e["status"] == "voided" for e in events)
    after_by_id: dict[int, list[Mapping[str, Any]]] = {}
    for item in discards:
        if item.get("after_kong") is True:
            kid = item.get("kong_id")
            if type(kid) is not int or kid not in by_id:
                raise RuntimeError("post-Kong discard references nonexistent Kong")
            if item.get("seat") != by_id[kid]["seat"]:
                raise RuntimeError("post-Kong discard attributed to wrong player")
            after_by_id.setdefault(kid, []).append(item)
    for event_id, event in by_id.items():
        exits = after_by_id.get(event_id, [])
        if len(exits) > 1:
            raise RuntimeError("one Kong cannot own multiple immediate exits")
        hit = bool(exits and exits[0].get("won_by"))
        if (event["status"] == "voided") != hit:
            raise RuntimeError("ledger refund lacks matching actual Ron discard")
        if event["type"] != "ming_gang" or event["seat"] != seat:
            continue
        counts["own_minggang_after_kong_discard"] += int(bool(exits))
        counts["own_minggang_exit_ron"] += int(hit)
        if hit:
            counts["own_minggang_exit_ron_winners"] += len(exits[0]["won_by"])
    if (counts["own_minggang_posted"] +
            counts["own_minggang_voided"] != counts["own_minggang_realized"]):
        raise RuntimeError("own Ming-Gang lifecycle not fully reconciled")
    return dict(counts)


class MingGangFollowThroughAgent(PublicMingGangRiskObserver):
    """Records only pre-choice aggregates; action is still unmodified challenge."""

    def __init__(self, *, seed: int, seat: int) -> None:
        super().__init__(seed=seed, seat=seat)
        self._dual_windows: list[dict[str, Any]] = []

    def response(self, view: Mapping[str, Any], *, rob: bool = False) -> str:
        choice = super().response(view, rob=rob)
        if _dual_optional_options(view, rob=rob):
            risk = public_minggang_exit_risk(view)
            idx = (view.get("pending_discard") or {}).get("index")
            if type(idx) is not int or idx < 1:
                raise RuntimeError("missing public discard index")
            self._dual_windows.append({
                "discard_index": idx, "choice": choice,
                "wall_band": risk["wall_band"],
                "pre_tail_min_threat": risk["min_existing_cut_threat_index"],
            })
        return choice

    def reconcile_dual_windows(
        self, public_events: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Associate offered responses with actually awarded call priority.

        Public event after the offered discard is the settled resolution.
        Retain identities only in memory; export risk-band counts, not tiles.
        """
        resolution = {}
        for n, action in enumerate(public_events):
            if action.get("type") == "discard":
                idx = action.get("index")
                if type(idx) is not int or idx in resolution:
                    raise RuntimeError("invalid or duplicate public discard index")
                resolution[idx] = (public_events[n+1]
                                   if n+1 < len(public_events) else {})
        result: Counter[str] = Counter()
        for row in self._dual_windows:
            resolved = resolution.get(row["discard_index"])
            if resolved is None:
                raise RuntimeError("observed dual window lacks its settled discard")
            taken = (resolved.get("type") == "ming_gang" and
                     resolved.get("seat") == self.seat and
                     row["choice"] == "ming_gang")
            result["dual_windows"] += 1
            result["dual_"+row["choice"]] += 1
            result["dual_wall_"+row["wall_band"]] += 1
            result["dual_risk_low" if row["pre_tail_min_threat"] < .25 else
                   "dual_risk_mid" if row["pre_tail_min_threat"] < .5 else
                   "dual_risk_high"] += 1
            result["dual_chosen_minggang_actual_award"] += int(taken)
            result["dual_chosen_minggang_preempted"] += int(
                row["choice"] == "ming_gang" and not taken)
        if result["dual_windows"] != self.public_counts().get("dual_windows",0):
            raise RuntimeError("risk observation windows do not reconcile")
        return dict(result)


def natural_position(seed: int, rotation: int) -> dict[str, Any]:
    if (type(seed) is not int or not 0 <= seed < 2**32 or
            type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid natural independent position")
    lineup, seat = _fixed_lineup(rotation)
    observer = MingGangFollowThroughAgent(seed=seed,seat=seat)
    terminal: dict[str, Any] = {}
    def keep_authority_reference(game: Any) -> None:
        # Callback fires in this OFFLINE simulator, before a discard turn,
        # but only retain the instance and read its PUBLIC state at terminal.
        terminal["game"] = game
    outcome = simulate_match(
        seed, rotation=rotation%3, lineup=lineup, offline_kong_base=1,
        offline_agent_overrides={seat:observer},
        offline_observer=keep_authority_reference)
    if "game" not in terminal or terminal["game"].phase != outcome["terminal_phase"]:
        raise RuntimeError("lost authority terminal reference")
    board = terminal["game"].public_state()
    ledger = audit_official_kong_lifecycle(outcome,board,seat)
    windows = observer.reconcile_dual_windows(outcome["public_events"])
    if windows.get("dual_chosen_minggang_actual_award",0) > ledger.get(
            "own_minggang_realized",0):
        raise RuntimeError("dual Ming-Gang awards exceed own actual Kong ledger")
    score = _official_outcome(outcome,seat,lineup)
    return {
        "seed":seed,"rotation":rotation,"challenge_seat":seat,
        "official":score,"ledger":ledger,"windows":windows,
        "terminal_phase":outcome["terminal_phase"],
    }


def natural_cohort(start: int, seeds: int) -> dict[str, Any]:
    if (type(start) is not int or type(seeds) is not int or
            not 0 <= start < 2**32 or not 1 <= seeds <= 8 or
            start+seeds > 2**32):
        raise ValueError("invalid natural independent seed group")
    positions = [natural_position(s,r) for s in range(start,start+seeds)
                 for r in range(4)]
    counters = {"ledger":Counter(),"windows":Counter()}
    per_seed = []
    for s in range(start,start+seeds):
        rows=[p for p in positions if p["seed"]==s]
        if sorted(x["challenge_seat"] for x in rows)!=[0,1,2,3]:
            raise RuntimeError("unbalanced independent seed seating")
        local = {"ledger":Counter(),"windows":Counter()}
        for row in rows:
            for cat in local:
                local[cat].update(row[cat])
                counters[cat].update(row[cat])
        per_seed.append({
            "seed":s,
            "dual_windows":local["windows"]["dual_windows"],
            "actual_own_minggang":local["ledger"]["own_minggang_realized"],
            "own_minggang_exit_ron":local["ledger"]["own_minggang_exit_ron"],
        })
    return {
        "independent_initial_shuffle_seeds":seeds,
        "four_seat_positions":len(positions),
        "complete_games":len(positions),
        "actual_all_seat_minggang":counters["ledger"]["table_minggang_realized"],
        "actual_challenge_seat_minggang":counters["ledger"]["own_minggang_realized"],
        "total_dual_windows":counters["windows"]["dual_windows"],
        "counts":{k:dict(v) for k,v in counters.items()},
        "per_seed":per_seed,"positions":positions,
        "confidence_interval":None,
    }


def study(*, development: int = 40000, holdout: int = 41000,
          seeds: int = 4) -> dict[str, Any]:
    if (type(development) is not int or type(holdout) is not int or
            type(seeds) is not int or not 1 <= seeds <= 8 or
            not 0 <= development < 2**32 or not 0 <= holdout < 2**32 or
            max(development,holdout)+seeds > 2**32 or
            (development < holdout+seeds and holdout < development+seeds)):
        raise ValueError("new independent fixed seed ranges must not overlap")
    return {
        "protocol":PROTOCOL,"online_policy_modified":False,
        "development_seed_range":[development,development+seeds],
        "holdout_seed_range":[holdout,holdout+seeds],
        "development":natural_cohort(development,seeds),
        "holdout":natural_cohort(holdout,seeds),
        "limitations":[
            "Actual Kong outcomes and cancellation are measured only after a match terminates.",
            "A public pre-tail threat index is not a calibrated chance of a Ron.",
            "The actual tail tile identity and all opponent hidden hands are never exported.",
            "This is unmodified baseline observation, not paired policy treatment.",
            "Seat rotations and response windows are correlated within each shuffle seed.",
            "All-seat Kong counts may count the same natural game in other seat rotations.",
        ],
    }
