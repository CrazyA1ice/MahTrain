"""Persistent graded single-question archive and explainable level recommendation.

This mixin operates on HistoryStore's SQLite connection, and never stores
private quiz seeds, active tokens, a future wall, or unanswered problems.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any

from .training import MODES, RULE_VERSION
from .training_levels import DIFFICULTIES
from .error_focus import ERROR_LABELS, FOCUS_BY_MODE, diagnose_quiz

MIN_RECOMMENDATION_SAMPLES = 5
RECENT_WINDOW = 10


def _validate_mode_level(mode: str, difficulty: str) -> None:
    if type(mode) is not str or mode not in MODES:
        raise ValueError("无效的单题训练模式")
    if type(difficulty) is not str or difficulty not in DIFFICULTIES:
        raise ValueError("无效的难度等级")


def _valid_choice(question: dict, selected: Any) -> Any:
    choices = question["choices"]
    if question["answer_type"] == "tile_set":
        if type(selected) not in (list, tuple) or any(
            type(t) is not str for t in selected
        ):
            raise ValueError("多选答案必须是牌种列表")
        if len(selected) != len(set(selected)) or not set(selected).issubset(choices):
            raise ValueError("多选牌种重复或不属于合法选项")
        return list(selected)
    if type(selected) is not str or selected not in choices:
        raise ValueError("只能选择该题合法的牌")
    return selected


class QuizProgressMixin:
    def save_quiz_answer(
        self, question: dict[str, Any], result: dict[str, Any], selection: Any
    ) -> str:
        """Insert exactly one previously graded answer; caller enforces one-shot."""
        mode, difficulty = question["mode"], question["difficulty"]
        _validate_mode_level(mode, difficulty)
        if question["question_id"] != result["question_id"]:
            raise ValueError("题目编号与评分不一致")
        if question["rule_version"] != RULE_VERSION:
            raise ValueError("题目规则版本不一致")
        selection = _valid_choice(question, selection)
        for name in ("seed", "token", "wall", "best_actions", "correct_tiles"):
            if name in question:
                raise ValueError("题目不能包含隐藏答案或私有种子")
        answer_id = secrets.token_urlsafe(18)
        created = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        with self._connect() as db:
            db.execute("""
                INSERT INTO quiz_attempts (
                    answer_id,created_at,mode,difficulty,question_id,rule_version,
                    correct,family,question_json,selection_json,result_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                answer_id,created,mode,difficulty,question["question_id"],
                question["rule_version"],int(result["correct"]),
                result.get("construction_family",""),
                self._encode(question),self._encode(selection),self._encode(result),
            ))
        return answer_id

    def _quiz_row(self, answer_id: str) -> dict[str, Any]:
        if type(answer_id) is not str or not 8 <= len(answer_id) <= 100:
            raise ValueError("非法的题目存档编号")
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM quiz_attempts WHERE answer_id=?", (answer_id,)
            ).fetchone()
        if row is None:
            raise ValueError("单题历史记录不存在")
        return dict(row)

    def quiz_detail(self, answer_id: str) -> dict[str, Any]:
        row = self._quiz_row(answer_id)
        return {
            "answer_id":row["answer_id"],
            "created_at":row["created_at"],
            "mode":row["mode"],
            "difficulty":row["difficulty"],
            "correct":bool(row["correct"]),
            "question":json.loads(row["question_json"]),
            "selection":json.loads(row["selection_json"]),
            "result":json.loads(row["result_json"]),
            "retry":self.quiz_retry_status(answer_id),
        }

    def quiz_progress(
        self, mode: str, difficulty: str, limit: int = 20
    ) -> dict[str, Any]:
        _validate_mode_level(mode, difficulty)
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("单题历史查询数量应在1至50之间")
        with self._connect() as db:
            groups = db.execute("""
                SELECT difficulty, COUNT(*) total, SUM(correct) correct
                FROM quiz_attempts WHERE mode=? GROUP BY difficulty
            """, (mode,)).fetchall()
            current = db.execute("""
                SELECT correct FROM quiz_attempts
                WHERE mode=? AND difficulty=?
                ORDER BY created_at DESC,answer_id DESC LIMIT ?
            """, (mode,difficulty,RECENT_WINDOW)).fetchall()
            rows = db.execute("""
                SELECT answer_id,created_at,mode,difficulty,correct,family
                FROM quiz_attempts
                WHERE mode=? ORDER BY created_at DESC,answer_id DESC LIMIT ?
            """, (mode,limit)).fetchall()
            # All difficulties of this mode, last 30 FIRST attempts only.
            errors = db.execute("""
                SELECT result_json FROM quiz_attempts
                WHERE mode=? AND correct=0
                ORDER BY created_at DESC,answer_id DESC LIMIT 30
            """, (mode,)).fetchall()
        level_totals = {
            level:{"total":0,"correct":0,"accuracy":None}
            for level in DIFFICULTIES
        }
        for group in groups:
            total = group["total"]
            good = group["correct"] or 0
            level_totals[group["difficulty"]] = {
                "total":total,"correct":good,"accuracy":good/total,
            }
        completed=len(current)
        correct=sum(x["correct"] for x in current)
        accuracy=correct/completed if completed else None
        ix=DIFFICULTIES.index(difficulty)
        target=difficulty
        decision="insufficient"
        if completed >= MIN_RECOMMENDATION_SAMPLES:
            decision="hold"
            if accuracy >= .8 and ix < len(DIFFICULTIES)-1:
                target=DIFFICULTIES[ix+1]
                decision="promote"
            elif accuracy <= .4 and ix > 0:
                target=DIFFICULTIES[ix-1]
                decision="demote"
        if decision=="insufficient":
            reason=f"当前模式的{difficulty}难度仅完成{completed}题；至少{MIN_RECOMMENDATION_SAMPLES}题后才给升降档建议。"
        elif decision=="promote":
            reason=f"近{completed}题正确率{accuracy:.0%}，达到80%晋级阈值，建议试试下一档。"
        elif decision=="demote":
            reason=f"近{completed}题正确率{accuracy:.0%}，不高于40%，建议返回上一档巩固。"
        else:
            reason=f"近{completed}题正确率{accuracy:.0%}，当前建议保持此难度。"
        counts = {label:0 for label in FOCUS_BY_MODE[mode]}
        other = 0
        for err_row in errors:
            graded=json.loads(err_row["result_json"])
            causes=graded.get("error_types")
            if causes is None:
                causes=diagnose_quiz(mode,graded)  # pre-v0.10 archive
            for cause in set(causes):
                if cause in counts:
                    counts[cause]+=1
                else:
                    other+=1
        order=sorted(counts, key=lambda k:(-counts[k],
              FOCUS_BY_MODE[mode].index(k)))
        weakness={
            "sample_wrong":len(errors),
            "window":30,
            "counts":counts,
            "labels":{key:ERROR_LABELS[key] for key in counts},
            "other_error_count":other,
            "top_focus":order[0] if order and counts[order[0]] else None,
        }
        return {
            "weaknesses":weakness,
            "mode":mode,"difficulty":difficulty,
            "level_totals":level_totals,
            "recent":{"attempts":completed,"correct":correct,"accuracy":accuracy,
                      "window":RECENT_WINDOW},
            "recommendation":{
                "level":target,"decision":decision,
                "reason":reason,"minimum_samples":MIN_RECOMMENDATION_SAMPLES,
            },
            "attempts":[{**dict(row),"correct":bool(row["correct"])} for row in rows],
        }

    def quiz_retry_status(self, answer_id: str) -> dict[str, Any]:
        self._quiz_row(answer_id)
        with self._connect() as db:
            rows = db.execute("""
                SELECT correct FROM quiz_retries WHERE answer_id=?
                ORDER BY retry_id DESC
            """, (answer_id,)).fetchall()
        return {"attempts":len(rows),"latest_correct":bool(rows[0]["correct"]) if rows else None}

    def quiz_retry_question(self, answer_id: str) -> dict[str, Any]:
        row = self._quiz_row(answer_id)
        if row["correct"]:
            raise ValueError("只能重练做错的单题")
        # The user already saw the answer on the original submission;
        # this endpoint itself still returns no correct choice.
        return {
            "question":json.loads(row["question_json"]),
            "retry":self.quiz_retry_status(answer_id),
        }

    def quiz_retry_submit(self, answer_id: str, selection: Any) -> dict[str, Any]:
        row = self._quiz_row(answer_id)
        if row["correct"]:
            raise ValueError("只能重练做错的单题")
        question = json.loads(row["question_json"])
        chosen = _valid_choice(question,selection)
        frozen = json.loads(row["result_json"])
        if question["answer_type"]=="tile_set":
            correct = set(chosen) == set(frozen["correct_tiles"])
        else:
            correct = chosen in frozen["best_actions"]
        result = {
            "correct":correct,"selection":chosen,
            "original_selection":json.loads(row["selection_json"]),
            "original_correct":False,
            "correct_answers":(
                frozen["correct_tiles"] if question["answer_type"]=="tile_set"
                else frozen["best_actions"]
            ),
            "reason":frozen["reason"],
        }
        with self._connect() as db:
            db.execute("""
                INSERT INTO quiz_retries(answer_id,created_at,correct,selection_json)
                VALUES (?,?,?,?)
            """, (answer_id,datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                  int(correct),self._encode(chosen)))
        return {"result":result,"retry":self.quiz_retry_status(answer_id)}

    def delete_quiz_attempt(self, answer_id: str) -> None:
        self._quiz_row(answer_id)
        with self._connect() as db:
            db.execute("DELETE FROM quiz_attempts WHERE answer_id=?", (answer_id,))
