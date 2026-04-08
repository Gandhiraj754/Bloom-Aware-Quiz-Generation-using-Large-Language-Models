# ============================================================
#  database.py  —  SQLite local storage for all research data
#  Every quiz session, score, evaluation result saved here.
#  Data is ALSO pushed to Google Drive when Drive is configured.
# ============================================================

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "bloom_research.db")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist. Safe to call on every startup."""
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS quiz_sessions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at    TEXT    NOT NULL,
            topic         TEXT    NOT NULL,
            model         TEXT    NOT NULL,
            provider      TEXT    NOT NULL,
            bloom_level   INTEGER NOT NULL,
            bloom_name    TEXT    NOT NULL,
            difficulty    TEXT    NOT NULL DEFAULT 'medium',
            num_questions INTEGER NOT NULL,
            latency_sec   REAL,
            questions_json TEXT   NOT NULL,
            drive_link    TEXT,
            pdf_filename  TEXT
        );

        CREATE TABLE IF NOT EXISTS question_scores (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    INTEGER NOT NULL REFERENCES quiz_sessions(id),
            question_id   INTEGER NOT NULL,
            question_text TEXT    NOT NULL,
            bloom_level   INTEGER NOT NULL,
            selected_ans  TEXT,
            correct_ans   TEXT    NOT NULL,
            is_correct    INTEGER NOT NULL,
            time_taken_sec REAL
        );

        CREATE TABLE IF NOT EXISTS evaluation_results (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at     TEXT NOT NULL,
            model          TEXT NOT NULL,
            bloom_level    INTEGER NOT NULL,
            topic          TEXT NOT NULL,
            num_questions  INTEGER NOT NULL,
            latency_sec    REAL,
            classifier_accuracy REAL,
            avg_question_quality REAL,
            raw_json       TEXT,
            drive_link     TEXT
        );

        CREATE TABLE IF NOT EXISTS comparison_runs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at   TEXT NOT NULL,
            topic        TEXT NOT NULL,
            bloom_level  INTEGER NOT NULL,
            difficulty   TEXT NOT NULL,
            models_json  TEXT NOT NULL,
            results_json TEXT NOT NULL,
            drive_link   TEXT
        );
        """)


# ── Sessions ──────────────────────────────────────────────────

def save_session(data: dict) -> int:
    """Insert a quiz session. Returns new row ID."""
    with _conn() as c:
        cur = c.execute("""
            INSERT INTO quiz_sessions
              (created_at, topic, model, provider, bloom_level, bloom_name,
               difficulty, num_questions, latency_sec, questions_json, drive_link, pdf_filename)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            datetime.now().isoformat(),
            data.get("topic", ""),
            data.get("model", ""),
            data.get("provider", ""),
            data.get("bloom_level", 1),
            data.get("bloom_level_name", ""),
            data.get("difficulty", "medium"),
            len(data.get("questions", [])),
            data.get("latency_sec"),
            json.dumps(data.get("questions", [])),
            data.get("drive_link"),
            data.get("pdf_filename"),
        ))
        return cur.lastrowid


def save_scores(session_id: int, scores: list):
    """Bulk insert question scores for a session."""
    with _conn() as c:
        c.executemany("""
            INSERT INTO question_scores
              (session_id, question_id, question_text, bloom_level,
               selected_ans, correct_ans, is_correct, time_taken_sec)
            VALUES (?,?,?,?,?,?,?,?)
        """, [
            (
                session_id,
                s.get("question_id", 0),
                s.get("question_text", ""),
                s.get("bloom_level", 1),
                s.get("selected_ans"),
                s.get("correct_ans", ""),
                1 if s.get("is_correct") else 0,
                s.get("time_taken_sec"),
            )
            for s in scores
        ])


def get_all_sessions(limit: int = 100) -> list:
    with _conn() as c:
        rows = c.execute("""
            SELECT s.*, 
                   COUNT(sc.id) as answered,
                   SUM(sc.is_correct) as correct
            FROM quiz_sessions s
            LEFT JOIN question_scores sc ON sc.session_id = s.id
            GROUP BY s.id
            ORDER BY s.created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_session_detail(session_id: int) -> Optional[dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM quiz_sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["questions"] = json.loads(result["questions_json"])
        scores = c.execute(
            "SELECT * FROM question_scores WHERE session_id=?", (session_id,)
        ).fetchall()
        result["scores"] = [dict(s) for s in scores]
        return result


# ── Evaluation results ────────────────────────────────────────

def save_evaluation(data: dict) -> int:
    with _conn() as c:
        cur = c.execute("""
            INSERT INTO evaluation_results
              (created_at, model, bloom_level, topic, num_questions,
               latency_sec, classifier_accuracy, avg_question_quality, raw_json, drive_link)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            datetime.now().isoformat(),
            data.get("model", ""),
            data.get("bloom_level", 1),
            data.get("topic", ""),
            data.get("num_questions", 0),
            data.get("latency_sec"),
            data.get("classifier_accuracy"),
            data.get("avg_question_quality"),
            json.dumps(data),
            data.get("drive_link"),
        ))
        return cur.lastrowid


def get_evaluation_table() -> list:
    """Return LLM × Bloom level summary — the research headline table."""
    with _conn() as c:
        rows = c.execute("""
            SELECT model, bloom_level,
                   COUNT(*)                        AS runs,
                   AVG(latency_sec)                AS avg_latency,
                   AVG(classifier_accuracy)        AS avg_classifier_acc,
                   AVG(avg_question_quality)       AS avg_quality
            FROM evaluation_results
            GROUP BY model, bloom_level
            ORDER BY model, bloom_level
        """).fetchall()
        return [dict(r) for r in rows]


# ── Comparison runs ───────────────────────────────────────────

def save_comparison(data: dict) -> int:
    with _conn() as c:
        cur = c.execute("""
            INSERT INTO comparison_runs
              (created_at, topic, bloom_level, difficulty, models_json, results_json, drive_link)
            VALUES (?,?,?,?,?,?,?)
        """, (
            datetime.now().isoformat(),
            data.get("topic", ""),
            data.get("bloom_level", 1),
            data.get("difficulty", "medium"),
            json.dumps(data.get("models", [])),
            json.dumps(data.get("results", {})),
            data.get("drive_link"),
        ))
        return cur.lastrowid


def get_analytics_summary() -> dict:
    """All numbers needed for the analytics dashboard."""
    with _conn() as c:
        total_sessions = c.execute("SELECT COUNT(*) FROM quiz_sessions").fetchone()[0]
        total_questions = c.execute("SELECT COUNT(*) FROM question_scores").fetchone()[0]
        total_correct   = c.execute("SELECT SUM(is_correct) FROM question_scores").fetchone()[0] or 0

        by_level = c.execute("""
            SELECT bloom_level, COUNT(*) as count, AVG(latency_sec) as avg_latency
            FROM quiz_sessions GROUP BY bloom_level ORDER BY bloom_level
        """).fetchall()

        by_model = c.execute("""
            SELECT model, COUNT(*) as sessions, AVG(latency_sec) as avg_latency
            FROM quiz_sessions GROUP BY model ORDER BY sessions DESC
        """).fetchall()

        accuracy_by_level = c.execute("""
            SELECT bloom_level,
                   COUNT(*) as total,
                   SUM(is_correct) as correct,
                   ROUND(100.0 * SUM(is_correct) / COUNT(*), 1) as accuracy_pct
            FROM question_scores GROUP BY bloom_level ORDER BY bloom_level
        """).fetchall()

        return {
            "total_sessions":   total_sessions,
            "total_questions":  total_questions,
            "total_correct":    total_correct,
            "overall_accuracy": round(100 * total_correct / total_questions, 1) if total_questions else 0,
            "by_level":         [dict(r) for r in by_level],
            "by_model":         [dict(r) for r in by_model],
            "accuracy_by_level":[dict(r) for r in accuracy_by_level],
        }
