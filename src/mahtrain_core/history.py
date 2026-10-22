"""SQLite archive of completed local MahTrain solo sessions and mistake retries.

The archive intentionally stores NO shuffled future wall, PRNG seed, active
session tokens, or in-progress ungraded answers.  This is a local single-user
prototype: anyone with access to the loopback service may read its history.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .retry import MistakeRetry
from .review import build_round_review
from .quiz_progress import QuizProgressMixin
from .history_periods import history_since

SCHEMA_VERSION = 2


class HistoryStore(QuizProgressMixin):
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def _init_schema(self):
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS local_history (
                    archive_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    missing_suit TEXT NOT NULL CHECK (missing_suit IN ('m','s','p')),
                    completed_rounds INTEGER NOT NULL,
                    correct_rounds INTEGER NOT NULL,
                    mistake_count INTEGER NOT NULL,
                    accuracy REAL NOT NULL,
                    report_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_history_created
                    ON local_history(created_at DESC, archive_id DESC);
                CREATE TABLE IF NOT EXISTS local_retries (
                    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    archive_id TEXT NOT NULL REFERENCES local_history(archive_id)
                        ON DELETE CASCADE,
                    round_number INTEGER NOT NULL,
                    attempted_at TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_retries_archive
                    ON local_retries(archive_id, round_number, attempt_id);
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    answer_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    rule_version TEXT NOT NULL,
                    correct INTEGER NOT NULL CHECK (correct IN (0,1)),
                    family TEXT NOT NULL,
                    question_json TEXT NOT NULL,
                    selection_json TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_quiz_progress
                    ON quiz_attempts(mode,difficulty,created_at DESC,answer_id DESC);
                CREATE TABLE IF NOT EXISTS quiz_retries (
                    retry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    answer_id TEXT NOT NULL REFERENCES quiz_attempts(answer_id)
                        ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    correct INTEGER NOT NULL CHECK(correct IN (0,1)),
                    selection_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_quiz_retries
                    ON quiz_retries(answer_id,retry_id DESC);
            """)
            current = db.execute("PRAGMA user_version").fetchone()[0]
            if current in (0,1):
                # Add-only upgrade; existing solo history/retries remain intact.
                db.execute("PRAGMA user_version = 2")
            elif current > SCHEMA_VERSION:
                raise ValueError("history database schema is newer than this app")

    @staticmethod
    def _encode(data: Any) -> str:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    def save_finished(self, game: Any, archive_id: str | None = None) -> str:
        if not game.finished:
            raise ValueError("cannot archive a live training session")
        report = game.report()
        if not report["finished"]:
            raise ValueError("only finished sessions can be archived")
        archive_id = archive_id or secrets.token_urlsafe(18)
        if type(archive_id) is not str or not archive_id:
            raise ValueError("invalid archive id")
        wrong = sum(not r["correct"] for r in report["history"])
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute("""
                INSERT OR IGNORE INTO local_history(
                    archive_id,created_at,session_id,missing_suit,
                    completed_rounds,correct_rounds,mistake_count,accuracy,report_json
                ) VALUES(?,?,?,?,?,?,?,?,?)
            """, (
                archive_id, timestamp, game.session_id, game.missing_suit,
                report["completed_rounds"], report["correct_rounds"],wrong,
                report["accuracy"], self._encode(report),
            ))
        return archive_id

    def _row(self, archive_id: str):
        if type(archive_id) is not str or not archive_id or len(archive_id)>100:
            raise ValueError("invalid archive identifier")
        with self._connect() as db:
            row = db.execute("SELECT * FROM local_history WHERE archive_id = ?",
                             (archive_id,)).fetchone()
        if row is None:
            raise ValueError("history item does not exist")
        return dict(row)

    def detail(self, archive_id: str) -> dict[str, Any]:
        row = self._row(archive_id)
        report = json.loads(row["report_json"])
        # Enrich older v0.5-v0.10 archives at read time, without rewriting
        # frozen grades or changing the SQLite schema/record on disk.
        if "error_summary" not in report and "history" in report:
            reviewed = build_round_review(report["history"])
            report["error_summary"] = reviewed["errors"]
            previous = {r["round"]: r for r in reviewed["rounds"]}
            for r in report.get("round_review", ()):
                if r["round"] in previous:
                    r["error_types"] = previous[r["round"]]["error_types"]
                    r["error_labels"] = previous[r["round"]]["error_labels"]
        return {
            "archive_id": row["archive_id"],
            "created_at": row["created_at"],
            "missing_suit": row["missing_suit"],
            "report": report,
            "retry": self.retry_list(archive_id),
        }

    def list_history(self, limit: int = 30, *, period: str = "all",
                     offset: int = 0) -> dict[str, Any]:
        if type(limit) is not int or limit < 1 or limit > 100:
            raise ValueError("history limit must be 1 to 100")
        if type(offset) is not int or not 0 <= offset <= 10000000:
            raise ValueError("invalid history page")
        since=history_since(period)
        where="WHERE created_at >= ?" if since is not None else ""
        params=(since,) if since is not None else ()
        with self._connect() as db:
            rows = db.execute(f"""
                SELECT archive_id,created_at,session_id,missing_suit,
                       completed_rounds,correct_rounds,mistake_count,accuracy
                FROM local_history {where}
                ORDER BY created_at DESC,archive_id DESC
                LIMIT ? OFFSET ?""", (*params,limit,offset)).fetchall()
            aggregate = db.execute(f"""
                SELECT COUNT(*) AS sessions, COALESCE(SUM(completed_rounds),0) AS rounds,
                       COALESCE(SUM(correct_rounds),0) AS correct,
                       COALESCE(SUM(mistake_count),0) AS mistakes,
                       COALESCE(AVG(accuracy),0) AS average_accuracy
                FROM local_history {where}""",params).fetchone()
            recent = db.execute(f"""
                SELECT accuracy FROM local_history {where}
                ORDER BY created_at DESC,archive_id DESC LIMIT 5""",
                params).fetchall()
            oldest = db.execute(f"""
                SELECT accuracy FROM local_history {where}
                ORDER BY created_at ASC,archive_id ASC LIMIT 5""",
                params).fetchall()
            trend = db.execute(f"""
                SELECT created_at,accuracy FROM local_history {where}
                ORDER BY created_at ASC,archive_id ASC""",params).fetchall()
        return {
            "period":period,"offset":offset,"limit":limit,
            "has_more":offset+len(rows)<aggregate["sessions"],
            "sessions":[dict(row) for row in rows],
            "trend":[dict(row) for row in trend],
            "summary":{
                "session_count":aggregate["sessions"],
                "rounds_total":aggregate["rounds"],
                "correct_total":aggregate["correct"],
                "mistake_total":aggregate["mistakes"],
                "average_session_accuracy":aggregate["average_accuracy"],
                "first_five_average":(
                    sum(x["accuracy"] for x in oldest)/len(oldest) if oldest else None),
                "latest_five_average":(
                    sum(x["accuracy"] for x in recent)/len(recent) if recent else None),
            },
        }

    def _retry(self, archive_id: str) -> MistakeRetry:
        row = self._row(archive_id)
        report = json.loads(row["report_json"])
        proxy = SimpleNamespace(
            finished=True, _history=report["history"],
            missing_suit=row["missing_suit"],
        )
        retry = MistakeRetry(proxy)
        with self._connect() as db:
            attempts = db.execute("""
                SELECT round_number,result_json FROM local_retries
                WHERE archive_id=? ORDER BY attempt_id
            """, (archive_id,)).fetchall()
        for attempt in attempts:
            retry._attempts.setdefault(attempt["round_number"], []).append(
                json.loads(attempt["result_json"])
            )
        return retry

    def retry_list(self, archive_id: str) -> dict[str, Any]:
        return self._retry(archive_id).list()

    def retry_question(self, archive_id: str, round_number: int) -> dict[str, Any]:
        return self._retry(archive_id).question(round_number)

    def retry_submit(
        self, archive_id: str, round_number: int, action: str
    ) -> dict[str, Any]:
        retry = self._retry(archive_id)
        result = retry.grade(round_number, action)
        with self._connect() as db:
            db.execute("""
                INSERT INTO local_retries(archive_id,round_number,attempted_at,result_json)
                VALUES(?,?,?,?)
            """, (
                archive_id, round_number,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                self._encode(result),
            ))
        return {"result": result, "retry": self.retry_list(archive_id)}

    def delete_history(self, archive_id: str) -> None:
        self._row(archive_id)
        with self._connect() as db:
            db.execute("DELETE FROM local_history WHERE archive_id=?", (archive_id,))
