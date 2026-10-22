"""Local read-only four-player public match archives, never a playable save.

Archives are server-generated from public post-rule states only.  No active
match token, PRNG seed, concealed tile identity or future wall is stored.
This module does NOT alter legacy solo/quiz SQLite user_version.
"""
from __future__ import annotations

import json
import re
import secrets
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .settlement import SELF_DRAW_MODES, payer_multiplier
from .post_round_review import completed_review

_TERMINAL = frozenset(("finished", "wall_exhausted"))
_TILES = re.compile(r"^[msp][1-9]$")
_MELDS = frozenset(("peng", "ming_gang", "an_gang", "bu_gang"))
_PUBLIC_TILE_EVENTS = frozenset((
    "discard", "peng", "ming_gang", "bu_gang",
    "ron", "multi_ron", "rob_kong", "bu_gang_declared",
))
_MAX_ARCHIVE_STEPS = 2048


def _tile(value):
    return value if isinstance(value, str) and _TILES.fullmatch(value) else None


def sanitize_board(raw: dict) -> dict:
    """Reject missing or malformed structural state; discard all extra data."""
    counts = raw.get("hand_counts")
    groups = raw.get("melds")
    won = raw.get("won")
    if (not isinstance(counts, list) or len(counts) != 4
            or not all(type(n) is int and 0 <= n <= 14 for n in counts)
            or not isinstance(groups, list) or len(groups) != 4
            or not all(isinstance(g, list) for g in groups)
            or not isinstance(won, list) or len(won) != 4
            or not all(type(x) is bool for x in won)
            or type(raw.get("wall_count")) is not int
            or raw["wall_count"] < 0
            or not (raw.get("turn") is None or
                    (type(raw.get("turn")) is int and
                     raw["turn"] in range(4)))
            or type(raw.get("phase")) is not str):
        raise ValueError("invalid public board for match archive")
    melds = []
    for member in groups:
        out = []
        for meld in member:
            if not isinstance(meld, dict) or meld.get("type") not in _MELDS:
                raise ValueError("invalid public meld")
            kind = meld["type"]
            # Archived games before M3.42 have NO revealed marker and
            # therefore remain concealed, even if malformed input supplies
            # a tile. Only an explicitly disclosed NEW kong may show a face.
            revealed=(kind=="an_gang" and meld.get("revealed") is True)
            tile=(_tile(meld.get("tile"))
                  if kind!="an_gang" or revealed else None)
            if (kind!="an_gang" or revealed) and tile is None:
                raise ValueError("invalid exposed meld tile")
            cleaned={"type":kind,"tile":tile}
            if revealed:cleaned["revealed"]=True
            out.append(cleaned)
        melds.append(out)
    discards = []
    for item in raw.get("discards", []):
        if not isinstance(item, dict) or type(item.get("seat")) is not int:
            raise ValueError("invalid public discard")
        seat = item["seat"]
        tile = _tile(item.get("tile"))
        if seat not in range(4) or tile is None:
            raise ValueError("invalid public discard")
        cleaned = {"seat": seat, "tile": tile}
        if type(item.get("claimed_by")) is int and item["claimed_by"] in range(4):
            cleaned["claimed_by"] = item["claimed_by"]
        if item.get("discard_kind") in ("tsumogiri", "tedashi"):
            cleaned["discard_kind"] = item["discard_kind"]
        if isinstance(item.get("won_by"), list):
            cleaned["won_by"] = [x for x in item["won_by"]
                                  if type(x) is int and x in range(4)]
        discards.append(cleaned)
    return {
        "phase": raw["phase"], "turn": raw["turn"],
        "wall_count": raw["wall_count"], "hand_counts": list(counts),
        "melds": melds, "discards": discards, "won": list(won),
    }


def sanitize_events(events: list) -> list[dict]:
    clean = []
    for entry in events:
        if not isinstance(entry, dict) or type(entry.get("type")) is not str:
            continue
        event = {"type": entry["type"]}
        for field in ("seat", "source"):
            if type(entry.get(field)) is int and entry[field] in range(4):
                event[field] = entry[field]
        revealed_kong=(entry["type"]=="an_gang" and
                       entry.get("revealed") is True)
        if entry["type"] in _PUBLIC_TILE_EVENTS or revealed_kong:
            tile = _tile(entry.get("tile"))
            if tile:
                event["tile"] = tile
                if revealed_kong:event["revealed"]=True
        if entry.get("discard_kind") in ("tsumogiri", "tedashi") and entry["type"]=="discard":
            event["discard_kind"] = entry["discard_kind"]
        if entry["type"] == "win_settlement":
            for field in ("amount", "effective_fan"):
                if type(entry.get(field)) is int and entry[field] >= 0:
                    event[field] = entry[field]
            if entry.get("kind") in ("ron", "rob_kong", "self_draw"):
                event["kind"] = entry["kind"]
        if entry["type"] in ("multi_ron", "rob_kong") and isinstance(entry.get("seats"), list):
            event["seats"] = [n for n in entry["seats"]
                              if type(n) is int and n in range(4)]
        clean.append(event)
    return clean


_MAIN_PATTERNS = frozenset((
    "pinghu", "seven_pairs", "dragon_seven_pairs", "pure_seven_pairs",
    "pure_dragon_seven_pairs", "golden_hook", "all_pungs",
    "pure_all_pungs", "pure_suit", "heaven_win", "earth_win",
))
_BONUS_NAMES = frozenset((
    "kong_bloom", "kong_discard_ron", "rob_added_kong", "roots",
    "sea_bottom_draw", "river_bottom_ron",
))
_WIN_KINDS = frozenset(("ron", "rob_kong", "self_draw"))


def _balances(value, label: str) -> list[int]:
    if (type(value) is not list or len(value) != 4 or
            any(type(n) is not int for n in value) or sum(value) != 0):
        raise ValueError(f"invalid zero-sum {label}")
    return list(value)


def sanitize_win_ledger(ledger: dict) -> dict:
    """Copy typed, rule-known settlement fields only; verify all four balances.

    In particular, the nested payers and bonuses must never be copied from
    public_state using an unchecked dictionary or list value.
    """
    if not isinstance(ledger, dict):
        raise ValueError("invalid win ledger")
    balances = _balances(ledger.get("balances"), "win balances")
    mode = ledger.get("self_draw_mode", "legacy")
    if type(mode) is not str or mode not in SELF_DRAW_MODES:
        raise ValueError("invalid win ledger self draw mode")
    wins = ledger.get("wins")
    if not isinstance(wins, list) or type(ledger.get("zero_sum")) is not bool or not ledger["zero_sum"]:
        raise ValueError("invalid win ledger entries/zero_sum")
    expected = [0, 0, 0, 0]
    cleaned = []
    for record in wins:
        if not isinstance(record, dict):
            raise ValueError("invalid win settlement")
        winner = record.get("winner")
        payers = record.get("payers")
        if (type(winner) is not int or winner not in range(4) or
                type(payers) is not list or not 1 <= len(payers) <= 3 or
                any(type(seat) is not int or seat not in range(4) or
                    seat == winner for seat in payers) or
                len(set(payers)) != len(payers)):
            raise ValueError("invalid win settlement seats")
        kind = record.get("kind")
        main = record.get("main_pattern")
        if type(kind) is not str or kind not in _WIN_KINDS or type(main) is not str or main not in _MAIN_PATTERNS:
            raise ValueError("invalid win settlement kind/pattern")
        fields = ("raw_fan", "effective_fan", "multiplier",
                  "amount_per_payer", "total_received")
        if any(type(record.get(key)) is not int for key in fields):
            raise ValueError("invalid win settlement numeric values")
        raw_fan, fan, multiplier, unit, total = (record[k] for k in fields)
        if (raw_fan < 0 or fan < 0 or fan > 12 or fan > raw_fan or
                multiplier != (1 << fan) or unit <= 0 or
                total != unit * len(payers)):
            raise ValueError("inconsistent win settlement amounts")
        if record.get("self_draw_mode", mode) != mode:
            raise ValueError("win record self draw mode mismatch")
        bonuses = record.get("bonuses", {})
        if (type(bonuses) is not dict or any(
            type(key) is not str or key not in _BONUS_NAMES or
            type(value) is not int or value < 0 or value > 14
            for key, value in bonuses.items()
        )):
            raise ValueError("invalid win settlement bonuses")
        if kind in ("ron", "rob_kong") and len(payers) != 1:
            raise ValueError("discard win requires exactly one payer")
        expected[winner] += total
        for seat in payers:
            expected[seat] -= unit
        cleaned.append({
            **({"self_draw_mode": mode} if mode != "legacy" else {}),
            "winner": winner, "kind": kind, "main_pattern": main,
            "raw_fan": raw_fan, "effective_fan": fan,
            "multiplier": multiplier, "amount_per_payer": unit,
            "total_received": total, "payers": list(payers),
            "bonuses": dict(bonuses),
        })
    if expected != balances:
        raise ValueError("win balances disagree with settled win records")
    return {"balances": balances, "wins": cleaned, "zero_sum": True,
            **({"self_draw_mode": mode} if mode != "legacy" else {})}


def sanitize_exhaustive_settlement(raw, final_board: dict) -> dict | None:
    """Strict archive allowlist for the official active-only terminal ledger."""
    if raw is None:  # Old archives / synthetic historical tests.
        return None
    if not isinstance(raw, dict):
        raise ValueError("invalid exhaustive settlement")
    if raw.get("policy") != "active_only_final" or type(raw.get("posted")) is not bool:
        raise ValueError("invalid exhaustive policy or posted flag")
    balances = _balances(raw.get("balances"), "exhaustive balances")
    entries = raw.get("entries")
    coefficient = raw.get("room_coefficient")
    cap = raw.get("fan_cap")
    if (type(entries) is not list or type(coefficient) is not int or
            coefficient <= 0 or type(cap) is not int or not 0 <= cap <= 12 or
            raw.get("zero_sum") is not True):
        raise ValueError("invalid exhaustive ledger header")
    posted = raw["posted"]
    reason = raw.get("reason")
    if (posted and reason != "settled") or (not posted and reason != "unresolved_terminal_hand"):
        raise ValueError("invalid exhaustive ledger status")
    if not posted and (entries or balances != [0, 0, 0, 0]):
        raise ValueError("unsettled exhaustive ledger cannot contain payments")
    expected = [0, 0, 0, 0]
    cleaned, seen = [], set()
    for index, item in enumerate(entries, start=1):
        if not isinstance(item, dict):
            raise ValueError("invalid exhaustive transfer")
        stage, payer, recipient, amount = (
            item.get("stage"), item.get("payer"), item.get("recipient"),
            item.get("amount"),
        )
        if (stage not in ("flower_pig", "da_jiao") or
                type(payer) is not int or type(recipient) is not int or
                payer not in range(4) or recipient not in range(4) or
                payer == recipient or final_board["won"][payer] or
                final_board["won"][recipient] or
                type(amount) is not int or amount <= 0 or
                type(item.get("index")) is not int or item["index"] != index):
            raise ValueError("invalid exhaustive payment or participating seats")
        identifier = (stage, payer, recipient)
        if identifier in seen:
            raise ValueError("duplicate exhaustive payout")
        seen.add(identifier)
        entry = {"index": index, "stage": stage, "payer": payer,
                 "recipient": recipient, "amount": amount}
        if stage == "flower_pig":
            if amount != 8 * coefficient:
                raise ValueError("incorrect flower pig payment")
        else:
            fan = item.get("effective_fan")
            if (type(fan) is not int or not 0 <= fan <= cap or
                    amount != coefficient * 2**fan):
                raise ValueError("incorrect da-jiao payment")
            entry["effective_fan"] = fan
        expected[payer] -= amount
        expected[recipient] += amount
        cleaned.append(entry)
    if balances != expected:
        raise ValueError("exhaustive balance/payout mismatch")
    if posted and final_board["phase"] != "wall_exhausted":
        raise ValueError("cannot post exhaustive payments outside exhausted wall")
    return {
        "policy": "active_only_final", "posted": posted, "reason": reason,
        "balances": balances, "entries": cleaned, "zero_sum": True,
        "room_coefficient": coefficient, "fan_cap": cap,
    }


def _archived_score_components(report: dict) -> tuple[list[int], list[int]]:
    """Return trustworthy four-seat HU/official-draw scores from OLD or NEW JSON.

    The archive is a server-written, sanitized public snapshot. Unreadable or
    inconsistent legacy snapshots cannot silently contaminate a leaderboard.
    No concealed tiles, events or opponent hand information are materialized.
    """
    if (type(report) is not dict or
            report.get("privacy") not in ("public_board_only","post_round_full_reveal") or
            report.get("phase") not in _TERMINAL):
        raise ValueError("not a completed public archive")
    ledger = report.get("win_ledger")
    if not isinstance(ledger, dict):
        raise ValueError("missing archived HU ledger")
    hu = _balances(ledger.get("balances"), "archived HU balances")
    terminal = report.get("exhaustive_settlement")
    if terminal is None:
        draw = [0] * 4
    else:
        board = report.get("final_board")
        if type(board) is not dict:
            raise ValueError("missing verified terminal board")
        clean = sanitize_exhaustive_settlement(terminal, board)
        draw = clean["balances"]
    # Earlier archived trial kong scores must NEVER be retroactively counted.
    # Only M3.51+ snapshots explicitly enrolled in official kong settlement do.
    kong = _archived_kong_component(report)
    expected = [a + b + c for a, b, c in zip(hu, draw, kong)]
    # Pre-M3.26 JSON can have no explicit 'settled_balances'; for old
    # matches that means HU was the only officially posted payment.
    if "settled_balances" in report:
        declared = _balances(report["settled_balances"], "archived settled balances")
        if declared != expected:
            raise ValueError("archived official totals disagree with ledgers")
    return hu, draw


def _archived_kong_component(report: dict) -> list[int]:
    included = report.get("kong_included", False)
    if type(included) is not bool:
        raise ValueError("invalid archived kong-inclusion marker")
    if not included:
        return [0] * 4
    if report.get("kong_priced") is not True:
        raise ValueError("official kong scores require an explicit priced ledger")
    return _balances(report.get("kong_balances"), "archived kong balances")


_AI_LEVELS = frozenset(("basic", "advanced", "challenge"))


def _archive_ai_lineup(report: dict) -> tuple[str, str, str] | None:
    values = report.get("ai_levels")
    if values is None:  # A historical record may predate AI level archiving.
        return None
    if (type(values) is not list or len(values) != 3 or
            any(type(x) is not str or x not in _AI_LEVELS for x in values)):
        raise ValueError("unverified historical AI lineup")
    return tuple(values)


def _archive_scoring_rules(report: dict) -> tuple[int, int, str] | None:
    config = report.get("match_config")
    if config is None:
        # Pre-M3.29 did NOT archive the game's room parameters; don't
        # guess defaults or infer them from a non-exhaustive win.
        return None
    if type(config) is not dict:
        raise ValueError("unverified historical match config")
    coefficient, cap = config.get("room_coefficient"), config.get("fan_cap")
    mode = config.get("self_draw_mode", "legacy")
    if (type(coefficient) is not int or coefficient <= 0 or
            type(cap) is not int or not 0 <= cap <= 12 or
            type(mode) is not str or mode not in SELF_DRAW_MODES):
        raise ValueError("unverified historical match config")
    ledger = report.get("win_ledger")
    for payment in ledger.get("wins", []) if isinstance(ledger, dict) else []:
        if (type(payment) is not dict or
                type(payment.get("effective_fan")) is not int or
                payment["effective_fan"] > cap or
                type(payment.get("multiplier")) is not int or
                type(payment.get("amount_per_payer")) is not int or
                payment.get("self_draw_mode",mode) != mode or
                payment["amount_per_payer"] != coefficient *
                payer_multiplier(payment.get("kind"),
                                 payment["multiplier"], mode)):
            raise ValueError("archived HU payout incompatible with room rules")
    terminal = report.get("exhaustive_settlement")
    if terminal is not None and (
            coefficient != terminal.get("room_coefficient") or
            cap != terminal.get("fan_cap")):
        raise ValueError("historic HU/draw scoring settings disagree")
    return (coefficient, cap, mode)


def _group_score(groups: dict, key: tuple, score: int, hu: int, draw: int,
                 rules: tuple[int, int, str] | None) -> None:
    item = groups.setdefault(key, {
        "games": 0, "settled_total": 0, "hu_total": 0, "draw_total": 0,
        "positive_games": 0, "negative_games": 0, "zero_games": 0,
        "normalized_sum": 0.0, "normalized_games": 0, "rules_seen": set(),
    })
    item["games"] += 1
    item["settled_total"] += score
    item["hu_total"] += hu
    item["draw_total"] += draw
    item[("positive_games" if score > 0 else
          "negative_games" if score < 0 else "zero_games")] += 1
    item["rules_seen"].add(rules)
    if rules is not None:
        item["normalized_sum"] += score / rules[0]
        item["normalized_games"] += 1


def _group_rows(groups: dict, kind: str) -> list[dict]:
    rows = []
    for key, item in groups.items():
        count = item["games"]
        row = {
            "games": count,
            "settled_total": item["settled_total"],
            "hu_total": item["hu_total"],
            "draw_total": item["draw_total"],
            "average_settled": round(item["settled_total"] / count, 2),
            "positive_games": item["positive_games"],
            "negative_games": item["negative_games"],
            "zero_games": item["zero_games"],
            # Normalized by ROOM COEFFICIENT only; different fan caps or AI
            # lineups are still not directly comparable or causal evidence.
            "normalized_games": item["normalized_games"],
            "average_per_coefficient": (
                round(item["normalized_sum"] / item["normalized_games"], 3)
                if item["normalized_games"] else None
            ),
            "rules_variant_count": len(item["rules_seen"]),
            "small_sample": count < 5,
        }
        if kind == "ai":
            row["ai_levels"] = list(key)
        else:
            row["room_coefficient"], row["fan_cap"], row["self_draw_mode"] = key
        rows.append(row)
    if kind == "ai":
        return sorted(rows, key=lambda x: (-x["games"], x["ai_levels"]))
    return sorted(rows, key=lambda x: (-x["games"], x["room_coefficient"],
                                      x["fan_cap"]))


class MatchArchive:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS completed_matches (
                    archive_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    dealer INTEGER NOT NULL,
                    win_count INTEGER NOT NULL,
                    steps_count INTEGER NOT NULL,
                    win_b0 INTEGER NOT NULL,
                    record_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_matches_created
                    ON completed_matches(created_at DESC,archive_id DESC);
            """)
            # Additive, backward-compatible SQLite migration: legacy archives
            # keep win_b0 and implicitly use it as their settled total.
            columns = {row[1] for row in db.execute(
                "PRAGMA table_info(completed_matches)"
            )}
            if "settled_b0" not in columns:
                db.execute(
                    "ALTER TABLE completed_matches ADD COLUMN settled_b0 INTEGER"
                )

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def save_completed(self, public: dict, history: list[dict],
                       initial_board: dict, ai_levels: list[str],
                       sealed_review: list[dict] | None = None,
                       sealed_opening_hands: list[list[str]] | None = None) -> str:
        if public.get("phase") not in _TERMINAL:
            raise ValueError("only completed matches can be archived")
        if (type(ai_levels) is not list or len(ai_levels) != 3 or
                any(type(level) is not str or level not in
                    ("basic", "advanced", "challenge") for level in ai_levels)):
            raise ValueError("invalid AI assignment")
        if type(public.get("dealer")) is not int or public["dealer"] not in range(4):
            raise ValueError("invalid dealer in match archive")
        safe_steps = [{
            "board": sanitize_board(step["board"]),
            "events": sanitize_events(step.get("events", [])),
        } for step in history[-_MAX_ARCHIVE_STEPS:]]
        safe_board = sanitize_board(public)
        ledger = sanitize_win_ledger(public["win_ledger"])
        # Explicitly preserve ONLY the public, typed room scoring settings.
        # Legacy archives are not altered or retroactively assigned settings.
        raw_ledger = public["win_ledger"]
        coefficient = raw_ledger.get("room_coefficient")
        fan_cap = raw_ledger.get("fan_cap")
        self_draw_mode = raw_ledger.get("self_draw_mode","legacy")
        if type(self_draw_mode) is not str or self_draw_mode not in SELF_DRAW_MODES:
            raise ValueError("invalid archived self draw mode")
        if (type(coefficient) is not int or coefficient <= 0 or
                type(fan_cap) is not int or not 0 <= fan_cap <= 12):
            raise ValueError("invalid archived room scoring configuration")
        for win in ledger["wins"]:
            if (win["effective_fan"] > fan_cap or
                    win.get("self_draw_mode",self_draw_mode) != self_draw_mode or
                    win["amount_per_payer"] != coefficient *
                    payer_multiplier(win["kind"],win["multiplier"],self_draw_mode)):
                raise ValueError("win payout incompatible with room configuration")
        exhaustive = sanitize_exhaustive_settlement(
            public.get("exhaustive_settlement"), safe_board,
        )
        kong = public.get("kong_ledger")
        if not isinstance(kong, dict):
            raise ValueError("invalid kong ledger")
        kong_balances = _balances(kong.get("balances"), "kong balances")
        if exhaustive is not None and (
                exhaustive["room_coefficient"] != coefficient or
                exhaustive["fan_cap"] != fan_cap):
            raise ValueError("exhaustive and HU room configurations disagree")
        base = kong.get("base")
        if base is not None and (type(base) is not int or not 1 <= base <= 10**6):
            raise ValueError("invalid kong base")
        # Old synthetic/legacy snapshots have no kong-inclusion marker.
        kong_included = public.get("kong_included", False)
        if type(kong_included) is not bool or (kong_included and base is None):
            raise ValueError("invalid official kong settlement marker")
        expected_settled = [
            ledger["balances"][i] + kong_balances[i] * int(kong_included) +
            (exhaustive["balances"][i] if exhaustive else 0)
            for i in range(4)
        ]
        if (kong_included and "settled_balances" in public and
                public["settled_balances"] != expected_settled):
            raise ValueError("public match scores do not match the three ledgers")
        payload = {
            "privacy": "public_board_only", "version": 1,
            "phase": public["phase"], "dealer": public["dealer"],
            "ai_levels": list(ai_levels),
            "match_config": {
                "room_coefficient": coefficient,
                "fan_cap": fan_cap,
                **({"self_draw_mode": self_draw_mode}
                   if self_draw_mode != "legacy" else {}),
            },
            "opening": sanitize_board(initial_board),
            "steps": safe_steps, "truncated": max(0, len(history)-len(safe_steps)),
            "final_board": safe_board,
            "win_ledger": ledger,
            "exhaustive_settlement": exhaustive,
            "settled_balances": expected_settled,
            "kong_balances": kong_balances,
            "kong_priced": base is not None,
            "kong_included": kong_included,
            "note": ("胡牌、杠钱及已确认流局赔付计入正式净额。"
                     if kong_included else
                     "历史兼容模式：杠钱仅为试验积分，不计入正式净额。"),
        }
        # M3.88: PRIVATE during the match, but fully reviewable only AFTER
        # a verified terminal result. Old public-only archives stay public-only.
        # Do not silently reconstruct absent historical hands from the wall.
        if sealed_review is not None:
            if len(sealed_review) != len(history):
                raise ValueError("sealed completed history does not align with public steps")
            payload["post_round_review"] = completed_review(
                sealed_review[-len(safe_steps):],
                opening_hands=sealed_opening_hands)
            payload["version"] = 2
            payload["privacy"] = "post_round_full_reveal"
        archive_id = secrets.token_urlsafe(18)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute("""
                INSERT INTO completed_matches(
                    archive_id,created_at,phase,dealer,win_count,
                    steps_count,win_b0,settled_b0,record_json
                ) VALUES(?,?,?,?,?,?,?,?,?)
            """, (archive_id,stamp,public["phase"],public["dealer"],
                  len(ledger["wins"]),len(safe_steps),
                  ledger["balances"][0],payload["settled_balances"][0],
                  json.dumps(payload,ensure_ascii=False,separators=(",",":"))))
        return archive_id

    @staticmethod
    def _id(value: str):
        if type(value) is not str or len(value) > 100 or not value:
            raise ValueError("invalid match archive id")
        return value

    @staticmethod
    def _period_start(period: str) -> str | None:
        if period not in ("all", "week", "month", "year"):
            raise ValueError("period must be all, week, month or year")
        if period == "all":
            return None
        days = {"week":7,"month":30,"year":365}[period]
        return (datetime.now(timezone.utc)-timedelta(days=days)).isoformat(
            timespec="seconds")

    def list_completed(self, limit: int=50, *,
                       period: str="all", offset: int=0) -> dict:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("match archive limit must be between 1 and 100")
        if type(offset) is not int or offset < 0 or offset > 10000000:
            raise ValueError("invalid archive page offset")
        since=self._period_start(period)
        where="WHERE created_at >= ?" if since is not None else ""
        args=(since,) if since is not None else ()
        with self._connect() as db:
            rows=db.execute(f"""
                SELECT archive_id,created_at,phase,dealer,win_count,
                       steps_count,win_b0,
                       COALESCE(settled_b0,win_b0) AS settled_b0
                FROM completed_matches {where}
                ORDER BY created_at DESC,archive_id DESC LIMIT ? OFFSET ?""",
                (*args,limit,offset)).fetchall()
            total=db.execute(f"""
                SELECT COUNT(*) AS games,COALESCE(AVG(win_b0),0) AS average_b0,
                COALESCE(AVG(COALESCE(settled_b0,win_b0)),0)
                    AS average_settled_b0,
                COALESCE(SUM(win_count),0) AS paid_wins
                FROM completed_matches {where}""",args).fetchone()
        return {"matches":[dict(x) for x in rows],
                "period":period,"offset":offset,"limit":limit,
                "has_more":offset+len(rows)<total["games"],
                "summary":{"games":total["games"],
                           "average_player0_win_balance":total["average_b0"],
                           "average_player0_settled_balance":
                               total["average_settled_b0"],
                           "paid_wins":total["paid_wins"]},
                "scorecard":self.four_seat_scorecard(
                    period=period, trend_limit=None)}

    def four_seat_scorecard(self, *, trend_limit: int | None = 30,
                            period: str = "all") -> dict:
        """Aggregate ALL completed public archive scores for fixed seats.

        Seats 1-3 are positions, NOT persistent AI identities: difficulty
        assignments may change between games. Exclude malformed legacy
        archives visibly instead of fabricating missing settled scores.
        """
        if trend_limit is not None and (
                type(trend_limit) is not int or not 1 <= trend_limit <= 100):
            raise ValueError("trend limit must be from 1 to 100")
        since=self._period_start(period)
        totals = [[0] * 4 for _ in range(4)]  # HU, draw, kong, official
        kong_included_games = 0
        pos = [0] * 4
        neg = [0] * 4
        ties = [0] * 4
        valid = 0
        skipped = 0
        trends = []
        cumulative = 0
        ai_groups, room_groups = {}, {}
        missing_ai, missing_rules = 0, 0
        with self._connect() as db:
            rows = db.execute(f"""
                SELECT archive_id,created_at,record_json
                FROM completed_matches
                {"WHERE created_at >= ?" if since is not None else ""}
                ORDER BY created_at ASC,archive_id ASC
            """, (since,) if since is not None else ())
            for row in rows:
                try:
                    report = json.loads(row["record_json"])
                    hu, draw = _archived_score_components(report)
                    kong = _archived_kong_component(report)
                    lineup = _archive_ai_lineup(report)
                    rules = _archive_scoring_rules(report)
                except (ValueError, TypeError, KeyError, IndexError,
                        json.JSONDecodeError):
                    skipped += 1
                    continue
                official = [a + b + c for a, b, c in zip(hu, draw, kong)]
                if report.get("kong_included") is True:
                    kong_included_games += 1
                if lineup is None:
                    missing_ai += 1
                else:
                    _group_score(ai_groups, lineup, official[0],
                                 hu[0], draw[0], rules)
                if rules is None:
                    missing_rules += 1
                else:
                    _group_score(room_groups, rules, official[0],
                                 hu[0], draw[0], rules)
                for seat in range(4):
                    totals[0][seat] += hu[seat]
                    totals[1][seat] += draw[seat]
                    totals[2][seat] += kong[seat]
                    totals[3][seat] += official[seat]
                    if official[seat] > 0:
                        pos[seat] += 1
                    elif official[seat] < 0:
                        neg[seat] += 1
                    else:
                        ties[seat] += 1
                valid += 1
                cumulative += official[0]
                trends.append({
                    "archive_id": row["archive_id"],
                    "created_at": row["created_at"],
                    "score": official[0],
                    "cumulative": cumulative,
                })
                if trend_limit is not None and len(trends) > trend_limit:
                    trends.pop(0)
        if any(sum(values) != 0 for values in totals):
            raise ValueError("non-zero-sum archived history")
        return {
            "valid_games": valid,
            "excluded_games": skipped,
            "scope": "completed_games_in_selected_period",
            "period": period,
            "kong_included": kong_included_games > 0,
            "kong_included_games": kong_included_games,
            "seats": [{
                "seat": seat,
                "hu_total": totals[0][seat],
                "draw_total": totals[1][seat],
                "kong_total": totals[2][seat],
                "settled_total": totals[3][seat],
                "average_settled": (
                    round(totals[3][seat] / valid, 2) if valid else 0
                ),
                "positive_games": pos[seat],
                "negative_games": neg[seat],
                "zero_games": ties[seat],
            } for seat in range(4)],
            "zero_sum": True,
            "trend": trends,
            "trend_limit": trend_limit,
            "groupings": {
                "ai_lineups": _group_rows(ai_groups, "ai"),
                "room_rules": _group_rows(room_groups, "rules"),
                "missing_ai_games": missing_ai,
                "missing_rules_games": missing_rules,
                "scope": "only_verified_completed_matches",
                "player_seat": 0,
            },
        }

    def detail(self, archive_id: str) -> dict:
        with self._connect() as db:
            row = db.execute("""
                SELECT archive_id,created_at,record_json
                FROM completed_matches WHERE archive_id=?""",
                (self._id(archive_id),)).fetchone()
        if row is None:
            raise ValueError("match archive not found")
        return {"archive_id":row["archive_id"],
                "created_at":row["created_at"],
                "report":json.loads(row["record_json"])}
