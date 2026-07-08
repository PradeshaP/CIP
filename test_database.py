"""
test_database.py
Database layer for the fixed 10-question MCQ test.
All students get the same questions, ranked by raw score.
"""

import os
import json
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
load_dotenv()


def _get_conn():
    try:
        try:
            import streamlit as st
            cfg = st.secrets.get("postgres", {})
        except Exception:
            cfg = {}
        if cfg:
            return psycopg2.connect(
                host=cfg.get("host", "localhost"),
                port=cfg.get("port", 5432),
                dbname=cfg.get("dbname", "interview_coach"),
                user=cfg.get("user", "postgres"),
                password=cfg.get("password", ""),
            )
        return psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", 5432)),
            dbname=os.environ.get("POSTGRES_DB", "interview_coach"),
            user=os.environ.get("POSTGRES_USER", "postgres"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
        )
    except Exception as e:
        print(f"[Test DB] Connection error: {e}")
        return None


def init_db():
    """Create test tables if they don't already exist."""
    conn = _get_conn()
    if not conn:
        print("[Test DB] init_db: could not connect.")
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS test_questions (
                        question_id    VARCHAR(50) PRIMARY KEY,
                        skill          VARCHAR(100) NOT NULL,
                        question_text  TEXT NOT NULL,
                        option_a       TEXT NOT NULL,
                        option_b       TEXT NOT NULL,
                        option_c       TEXT NOT NULL,
                        option_d       TEXT NOT NULL,
                        correct_option CHAR(1) NOT NULL CHECK (correct_option IN ('a','b','c','d')),
                        explanation    TEXT,
                        display_order  INT NOT NULL,
                        is_active      BOOLEAN DEFAULT TRUE
                    );

                    CREATE TABLE IF NOT EXISTS test_sessions (
                        session_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        student_name   VARCHAR(200) NOT NULL,
                        student_email  VARCHAR(200) NOT NULL,
                        total_score    INT DEFAULT 0,
                        total_correct  INT DEFAULT 0,
                        status         VARCHAR(20) DEFAULT 'active',
                        started_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        completed_at   TIMESTAMP WITH TIME ZONE
                    );

                    CREATE TABLE IF NOT EXISTS test_responses (
                        response_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        session_id      UUID NOT NULL,
                        question_id     VARCHAR(50) NOT NULL,
                        skill           VARCHAR(100) NOT NULL,
                        selected_option CHAR(1),
                        is_correct      BOOLEAN NOT NULL,
                        answered_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );

                    CREATE INDEX IF NOT EXISTS idx_test_responses_session
                        ON test_responses(session_id);
                """)
        print("[Test DB] Tables verified/created.")
    except Exception as e:
        print(f"[Test DB] init_db error: {e}")
    finally:
        conn.close()


def load_test_questions_from_json(filepath: str) -> tuple[int, str]:
    """Load the fixed 10 test questions from a JSON file."""
    conn = _get_conn()
    if not conn:
        return 0, "DB connection failed"
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        inserted = 0
        with conn:
            with conn.cursor() as cur:
                for q in data.get("questions", []):
                    cur.execute("""
                        INSERT INTO test_questions
                            (question_id, skill, question_text,
                             option_a, option_b, option_c, option_d,
                             correct_option, explanation, display_order)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (question_id) DO NOTHING
                    """, (
                        q["question_id"], q["skill"], q["question_text"],
                        q["option_a"], q["option_b"], q["option_c"], q["option_d"],
                        q["correct_option"], q.get("explanation", ""),
                        q["display_order"],
                    ))
                    inserted += cur.rowcount
        return inserted, ""
    except Exception as e:
        return 0, str(e)
    finally:
        conn.close()


def get_test_questions() -> list[dict]:
    """Return all 10 test questions in fixed order."""
    conn = _get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT question_id, skill, question_text,
                       option_a, option_b, option_c, option_d,
                       correct_option, explanation, display_order
                FROM test_questions
                WHERE is_active = TRUE
                ORDER BY display_order
            """)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[Test DB] get_test_questions error: {e}")
        return []
    finally:
        conn.close()


def create_test_session(student_name: str, student_email: str) -> str | None:
    conn = _get_conn()
    if not conn:
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO test_sessions (student_name, student_email)
                    VALUES (%s, %s) RETURNING session_id
                """, (student_name, student_email))
                return str(cur.fetchone()[0])
    except Exception as e:
        print(f"[Test DB] create_test_session error: {e}")
        return None
    finally:
        conn.close()


def save_test_response(session_id: str, question_id: str,
                       skill: str, selected_option: str, is_correct: bool) -> str:
    conn = _get_conn()
    if not conn:
        return "DB connection failed"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO test_responses
                        (session_id, question_id, skill, selected_option, is_correct)
                    VALUES (%s::uuid, %s, %s, %s, %s)
                """, (session_id, question_id, skill, selected_option, is_correct))
        return ""
    except Exception as e:
        return str(e)
    finally:
        conn.close()


def complete_test_session(session_id: str, total_correct: int, total_score: int):
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE test_sessions SET
                        total_correct = %s,
                        total_score   = %s,
                        status        = 'completed',
                        completed_at  = NOW()
                    WHERE session_id = %s::uuid
                """, (total_correct, total_score, session_id))
    except Exception as e:
        print(f"[Test DB] complete_test_session error: {e}")
    finally:
        conn.close()


def get_test_leaderboard() -> list[dict]:
    """Ranked by total_correct DESC, then completed_at ASC (faster wins ties)."""
    conn = _get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    session_id,
                    student_name,
                    total_correct,
                    total_score,
                    completed_at,
                    RANK() OVER (
                        ORDER BY total_correct DESC, completed_at ASC
                    ) AS rank
                FROM test_sessions
                WHERE status = 'completed'
                ORDER BY total_correct DESC, completed_at ASC
            """)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[Test DB] get_test_leaderboard error: {e}")
        return []
    finally:
        conn.close()


def get_skill_breakdown(session_id: str) -> dict:
    """Returns {skill: {correct, total}} for one student."""
    conn = _get_conn()
    if not conn:
        return {}
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT skill,
                       COUNT(*) AS total,
                       SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS correct
                FROM test_responses
                WHERE session_id = %s::uuid
                GROUP BY skill
                ORDER BY skill
            """, (session_id,))
            return {r["skill"]: {"correct": int(r["correct"]), "total": int(r["total"])}
                    for r in cur.fetchall()}
    except Exception as e:
        print(f"[Test DB] get_skill_breakdown error: {e}")
        return {}
    finally:
        conn.close()