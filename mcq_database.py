"""
mcq_database.py
───────────────
PostgreSQL database layer for the MCQ module.

Tables managed here:
  mcq_sessions      — one row per MCQ event (admin creates, users join)
  mcq_questions     — questions for a session (same for all users)
  mcq_participants  — one row per user who joins a session
  mcq_answers       — one row per (participant × question) answer

All DB credentials are read from environment variables or Streamlit secrets.
Set these before running:
  POSTGRES_HOST     (default: localhost)
  POSTGRES_PORT     (default: 5432)
  POSTGRES_DB       (default: interview_coach)
  POSTGRES_USER     (default: postgres)
  POSTGRES_PASSWORD (required)

Or add to .streamlit/secrets.toml:
  [postgres]
  host     = "localhost"
  port     = 5432
  dbname   = "interview_coach"
  user     = "postgres"
  password = "yourpassword"
"""

import os
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor


# ─────────────────────────────────────────────────────────────────────────────
# CONNECTION
# ─────────────────────────────────────────────────────────────────────────────

def _get_conn_params() -> dict:
    """
    Read connection params from environment variables.
    Falls back to Streamlit secrets if the env vars are not set.
    """
    try:
        import streamlit as st
        pg = st.secrets.get("postgres", {})
    except Exception:
        pg = {}

    return {
        "host":     os.environ.get("POSTGRES_HOST",     pg.get("host",     "localhost")),
        "port":     int(os.environ.get("POSTGRES_PORT", pg.get("port",     5432))),
        "dbname":   os.environ.get("POSTGRES_DB",       pg.get("dbname",   "interview_coach")),
        "user":     os.environ.get("POSTGRES_USER",     pg.get("user",     "postgres")),
        "password": os.environ.get("POSTGRES_PASSWORD", pg.get("password", "")),
    }


@contextmanager
def get_connection():
    """Context manager — always closes the connection."""
    conn = psycopg2.connect(**_get_conn_params())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA INITIALISATION
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
-- MCQ session: one row = one exam event (admin creates, users join)
CREATE TABLE IF NOT EXISTS mcq_sessions (
    session_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL DEFAULT 'MCQ Round',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    time_limit_mins INTEGER NOT NULL DEFAULT 30,
    skill_tags      JSONB DEFAULT '[]'::JSONB,
    created_by      TEXT DEFAULT 'admin'
);

-- Questions for a session (identical for all participants)
CREATE TABLE IF NOT EXISTS mcq_questions (
    question_id     SERIAL PRIMARY KEY,
    session_id      UUID NOT NULL REFERENCES mcq_sessions(session_id) ON DELETE CASCADE,
    question_order  INTEGER NOT NULL,
    question_text   TEXT NOT NULL,
    option_a        TEXT NOT NULL,
    option_b        TEXT NOT NULL,
    option_c        TEXT NOT NULL,
    option_d        TEXT NOT NULL,
    correct_option  CHAR(1) NOT NULL CHECK (correct_option IN ('a','b','c','d')),
    explanation     TEXT DEFAULT '',
    skill           TEXT DEFAULT '',
    category        TEXT DEFAULT '',
    difficulty      TEXT DEFAULT 'medium',
    UNIQUE (session_id, question_order)
);

-- Each user who participates in a session
CREATE TABLE IF NOT EXISTS mcq_participants (
    participant_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES mcq_sessions(session_id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    email               TEXT DEFAULT '',
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at        TIMESTAMPTZ,
    score               NUMERIC(5,2),         -- percentage 0-100
    correct_count       INTEGER DEFAULT 0,
    total_questions     INTEGER DEFAULT 0,
    time_taken_seconds  INTEGER,
    UNIQUE (session_id, email)                -- one entry per email per session
);

-- Individual answers
CREATE TABLE IF NOT EXISTS mcq_answers (
    answer_id       SERIAL PRIMARY KEY,
    participant_id  UUID NOT NULL REFERENCES mcq_participants(participant_id) ON DELETE CASCADE,
    question_id     INTEGER NOT NULL REFERENCES mcq_questions(question_id) ON DELETE CASCADE,
    selected_option CHAR(1) CHECK (selected_option IN ('a','b','c','d')),
    is_correct      BOOLEAN NOT NULL DEFAULT FALSE,
    answered_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (participant_id, question_id)
);

-- Index for fast leaderboard queries
CREATE INDEX IF NOT EXISTS idx_participants_session_score
    ON mcq_participants (session_id, score DESC NULLS LAST, time_taken_seconds ASC);

CREATE INDEX IF NOT EXISTS idx_questions_session_order
    ON mcq_questions (session_id, question_order);
"""


def init_db() -> bool:
    """
    Create all tables if they don't exist.
    Returns True on success, False on failure.
    Call this once at app startup.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
        print("[MCQ DB] Schema initialised successfully.")
        return True
    except Exception as e:
        print(f"[MCQ DB] Schema init failed: {e}")
        return False


def test_connection() -> tuple[bool, str]:
    """Ping the database. Returns (success, message)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                ver = cur.fetchone()[0]
        return True, f"Connected — {ver}"
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# SESSION OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

def create_session(
    title:           str  = "MCQ Round",
    time_limit_mins: int  = 30,
    skill_tags:      list = None,
    created_by:      str  = "admin",
) -> str:
    """
    Create a new MCQ session and deactivate all previous ones.
    Returns the new session_id (UUID string).
    """
    import json
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Deactivate all previous sessions
            cur.execute("UPDATE mcq_sessions SET is_active = FALSE")
            # Create new session
            cur.execute(
                """
                INSERT INTO mcq_sessions
                    (title, time_limit_mins, skill_tags, created_by)
                VALUES (%s, %s, %s::JSONB, %s)
                RETURNING session_id
                """,
                (title, time_limit_mins,
                 json.dumps(skill_tags or []), created_by)
            )
            return str(cur.fetchone()[0])


def get_active_session() -> Optional[dict]:
    """
    Returns the currently active session as a dict, or None.
    Dict keys: session_id, title, created_at, time_limit_mins, skill_tags, question_count
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT s.*,
                       COUNT(q.question_id) AS question_count
                FROM   mcq_sessions s
                LEFT JOIN mcq_questions q USING (session_id)
                WHERE  s.is_active = TRUE
                GROUP  BY s.session_id
                ORDER  BY s.created_at DESC
                LIMIT  1
                """)
            row = cur.fetchone()
            return dict(row) if row else None


def get_session_by_id(session_id: str) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM mcq_sessions WHERE session_id = %s",
                (session_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None


def list_sessions() -> list[dict]:
    """Return all sessions (newest first) with question + participant counts."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT s.*,
                       COUNT(DISTINCT q.question_id) AS question_count,
                       COUNT(DISTINCT p.participant_id) AS participant_count
                FROM   mcq_sessions s
                LEFT JOIN mcq_questions q USING (session_id)
                LEFT JOIN mcq_participants p USING (session_id)
                GROUP  BY s.session_id
                ORDER  BY s.created_at DESC
                """
            )
            return [dict(r) for r in cur.fetchall()]


# ─────────────────────────────────────────────────────────────────────────────
# QUESTION OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

def insert_questions(session_id: str, questions: list[dict]) -> int:
    """
    Bulk-insert questions for a session.
    Each dict in `questions` must have:
        question_text, option_a, option_b, option_c, option_d,
        correct_option, explanation, skill, category, difficulty
    Returns count of rows inserted.
    """
    if not questions:
        return 0

    rows = []
    for i, q in enumerate(questions, start=1):
        rows.append((
            session_id,
            i,
            q["question_text"],
            q["option_a"],
            q["option_b"],
            q["option_c"],
            q["option_d"],
            q["correct_option"].lower(),
            q.get("explanation", ""),
            q.get("skill", ""),
            q.get("category", ""),
            q.get("difficulty", "medium"),
        ))

    with get_connection() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO mcq_questions
                    (session_id, question_order, question_text,
                     option_a, option_b, option_c, option_d,
                     correct_option, explanation, skill, category, difficulty)
                VALUES %s
                ON CONFLICT (session_id, question_order) DO NOTHING
                """,
                rows,
            )
            return cur.rowcount


def get_questions(session_id: str) -> list[dict]:
    """
    Return all questions for a session in display order.
    Correct option is intentionally included — it is used server-side for scoring.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM mcq_questions
                WHERE  session_id = %s
                ORDER  BY question_order
                """,
                (session_id,)
            )
            return [dict(r) for r in cur.fetchall()]


# ─────────────────────────────────────────────────────────────────────────────
# PARTICIPANT OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

def register_participant(
    session_id: str,
    name:       str,
    email:      str = "",
) -> tuple[Optional[str], str]:
    """
    Register a user for a session.
    Returns (participant_id, error_message).
    Returns error if email already used in this session.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Check for duplicate email in this session
                if email:
                    cur.execute(
                        """
                        SELECT participant_id, name
                        FROM   mcq_participants
                        WHERE  session_id = %s AND email = %s
                        """,
                        (session_id, email)
                    )
                    existing = cur.fetchone()
                    if existing:
                        return None, (
                            f"Email '{email}' already registered in this session "
                            f"(as '{existing[1]}'). Use a different email."
                        )

                cur.execute(
                    """
                    INSERT INTO mcq_participants (session_id, name, email)
                    VALUES (%s, %s, %s)
                    RETURNING participant_id
                    """,
                    (session_id, name.strip(), email.strip())
                )
                pid = str(cur.fetchone()[0])
                return pid, ""
    except Exception as e:
        return None, str(e)


def get_participant(participant_id: str) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM mcq_participants WHERE participant_id = %s",
                (participant_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None


def save_answer(
    participant_id: str,
    question_id:    int,
    selected_option: Optional[str],
    is_correct:     bool,
) -> bool:
    """
    Upsert a single answer (allows changing answer before final submit).
    Returns True on success.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mcq_answers
                        (participant_id, question_id, selected_option, is_correct)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (participant_id, question_id)
                    DO UPDATE SET
                        selected_option = EXCLUDED.selected_option,
                        is_correct      = EXCLUDED.is_correct,
                        answered_at     = NOW()
                    """,
                    (participant_id, question_id, selected_option, is_correct)
                )
        return True
    except Exception as e:
        print(f"[MCQ DB] save_answer error: {e}")
        return False


def submit_participant(
    participant_id:     str,
    started_at:         datetime,
    answers:            dict,  # {question_id: selected_option}
    questions:          list[dict],
) -> dict:
    """
    Finalise a participant's submission:
      1. Calculates score from provided answers
      2. Bulk-saves all answers
      3. Updates participant row with score + timing
    Returns result dict: {score, correct_count, total, time_taken_seconds, already_submitted}
    """
    # Check if already submitted
    participant = get_participant(participant_id)
    if participant and participant.get("submitted_at"):
        return {
            "score":             float(participant["score"] or 0),
            "correct_count":     participant["correct_count"],
            "total":             participant["total_questions"],
            "time_taken_seconds": participant["time_taken_seconds"],
            "already_submitted": True,
        }

    # Build lookup: question_id → correct_option
    correct_map = {q["question_id"]: q["correct_option"] for q in questions}
    total       = len(questions)

    # Score calculation
    answer_rows    = []
    correct_count  = 0

    for q in questions:
        qid      = q["question_id"]
        selected = answers.get(qid)             # None if skipped
        is_correct = (
            selected is not None
            and selected.lower() == correct_map[qid].lower()
        )
        if is_correct:
            correct_count += 1
        answer_rows.append((
            participant_id,
            qid,
            selected,
            is_correct,
        ))

    score           = round((correct_count / total) * 100, 2) if total else 0

    # ✅ FIX: use timezone-aware UTC datetime to match started_at
    now             = datetime.now(timezone.utc)

    # ✅ FIX: ensure started_at is timezone-aware before subtracting
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    time_taken_secs = int((now - started_at).total_seconds())

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Bulk upsert all answers
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO mcq_answers
                    (participant_id, question_id, selected_option, is_correct)
                VALUES %s
                ON CONFLICT (participant_id, question_id)
                DO UPDATE SET
                    selected_option = EXCLUDED.selected_option,
                    is_correct      = EXCLUDED.is_correct,
                    answered_at     = NOW()
                """,
                answer_rows,
            )
            # Update participant record
            cur.execute(
                """
                UPDATE mcq_participants
                SET    submitted_at       = NOW(),
                       score              = %s,
                       correct_count      = %s,
                       total_questions    = %s,
                       time_taken_seconds = %s
                WHERE  participant_id = %s
                """,
                (score, correct_count, total, time_taken_secs, participant_id)
            )

    return {
        "score":              score,
        "correct_count":      correct_count,
        "total":              total,
        "time_taken_seconds": time_taken_secs,
        "already_submitted":  False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# LEADERBOARD
# ─────────────────────────────────────────────────────────────────────────────

def get_leaderboard(session_id: str) -> list[dict]:
    """
    Returns all submitted participants for a session, ranked by:
      Primary   : score DESC
      Tiebreaker: time_taken_seconds ASC (faster = better rank)

    Each row dict:
      rank, participant_id, name, email, score, correct_count,
      total_questions, time_taken_seconds, submitted_at
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    RANK() OVER (
                        ORDER BY score DESC,
                                 time_taken_seconds ASC
                    )                         AS rank,
                    participant_id,
                    name,
                    email,
                    score,
                    correct_count,
                    total_questions,
                    time_taken_seconds,
                    submitted_at
                FROM   mcq_participants
                WHERE  session_id  = %s
                  AND  submitted_at IS NOT NULL
                ORDER  BY rank, submitted_at
                """,
                (session_id,)
            )
            return [dict(r) for r in cur.fetchall()]


def get_participant_rank(participant_id: str, session_id: str) -> Optional[int]:
    """Returns the rank of a specific participant, or None if not submitted."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH ranked AS (
                    SELECT participant_id,
                           RANK() OVER (
                               ORDER BY score DESC, time_taken_seconds ASC
                           ) AS rnk
                    FROM   mcq_participants
                    WHERE  session_id   = %s
                      AND  submitted_at IS NOT NULL
                )
                SELECT rnk FROM ranked WHERE participant_id = %s
                """,
                (session_id, participant_id)
            )
            row = cur.fetchone()
            return row[0] if row else None


def get_participant_answers(participant_id: str) -> list[dict]:
    """
    Returns all answers with question text and correctness — used for result review.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    q.question_order,
                    q.question_text,
                    q.option_a, q.option_b, q.option_c, q.option_d,
                    q.correct_option,
                    q.explanation,
                    q.skill,
                    a.selected_option,
                    a.is_correct
                FROM   mcq_answers a
                JOIN   mcq_questions q USING (question_id)
                WHERE  a.participant_id = %s
                ORDER  BY q.question_order
                """,
                (participant_id,)
            )
            return [dict(r) for r in cur.fetchall()]