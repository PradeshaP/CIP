"""
final_database.py
Database layer for final session summaries.

Tables:
  final_sessions — one row per MCQ or open-ended session summary.
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def _get_conn():
    """Get PostgreSQL connection to interview_coach database."""
    try:
        cfg = None
        try:
            import streamlit as st
            cfg = st.secrets.get("postgres", {})
        except Exception:
            pass

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
        print(f"[FINAL DB] Connection error: {e}")
        return None


def test_connection() -> tuple[bool, str]:
    """Test database connection."""
    conn = _get_conn()
    if not conn:
        return False, "Cannot connect to PostgreSQL"
    conn.close()
    return True, "Connected"


# ─────────────────────────────────────────────────────────────────────────────
# FINAL SESSION MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def create_final_session(student_name: str, student_email: str,
                         mode: str, oe_session_id: str | None = None,
                         mcq_session_id: str | None = None) -> str | None:
    """Create a final session summary record."""
    conn = _get_conn()
    if not conn:
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO final_sessions
                        (student_name, student_email, mode, oe_session_id, mcq_session_id)
                    VALUES (%s, %s, %s, %s::uuid, %s::uuid)
                    RETURNING final_session_id
                """, (student_name, student_email, mode, oe_session_id, mcq_session_id))
                row = cur.fetchone()
                return str(row[0]) if row else None
    except Exception as e:
        print(f"[FINAL DB] create_final_session error: {e}")
        return None
    finally:
        conn.close()


def complete_final_session(final_session_id: str, total_questions: int,
                           total_answered: int, final_score: float,
                           overall_label: str, total_correct: int | None = None,
                           proficiency_score: float | None = None,
                           proficiency_label: str | None = None) -> bool:
    """Mark a final session summary as completed."""
    conn = _get_conn()
    if not conn:
        return False
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE final_sessions SET
                        total_questions = %s,
                        total_answered = %s,
                        total_correct = %s,
                        final_score = %s,
                        overall_label = %s,
                        proficiency_score = %s,
                        proficiency_label = %s,
                        status = 'completed',
                        completed_at = NOW()
                    WHERE final_session_id = %s::uuid
                """, (total_questions, total_answered, total_correct,
                      final_score, overall_label, proficiency_score,
                      proficiency_label, final_session_id))
        return True
    except Exception as e:
        print(f"[FINAL DB] complete_final_session error: {e}")
        return False
    finally:
        conn.close()


def get_final_session(final_session_id: str) -> dict | None:
    """Get a final session summary record."""
    conn = _get_conn()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT *
                FROM final_sessions
                WHERE final_session_id = %s::uuid
            """, (final_session_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"[FINAL DB] get_final_session error: {e}")
        return None
    finally:
        conn.close()


def get_final_sessions_for_student(student_email: str, limit: int = 50) -> list[dict]:
    """Get recent final session summaries for a student."""
    conn = _get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT *
                FROM final_sessions
                WHERE student_email = %s
                ORDER BY completed_at DESC NULLS LAST, created_at DESC
                LIMIT %s
            """, (student_email, limit))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[FINAL DB] get_final_sessions_for_student error: {e}")
        return []
    finally:
        conn.close()
