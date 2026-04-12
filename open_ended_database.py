"""
open_ended_database.py
Database layer for open-ended interview questions and responses.

Tables:
  oe_sessions           — one row per student open-ended session
  oe_session_questions  — questions generated for that session
  oe_responses          — student answers + AI evaluation
"""

import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
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
        print(f"[OE DB] Connection error: {e}")
        return None


def test_connection() -> tuple[bool, str]:
    """Test database connection."""
    conn = _get_conn()
    if not conn:
        return False, "Cannot connect to PostgreSQL"
    conn.close()
    return True, "Connected"


# ─────────────────────────────────────────────────────────────────────────────
# SESSION MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def create_oe_session(student_name: str, student_email: str, 
                      skills_tested: list[str], mode: str = "open_ended") -> str | None:
    """Create a new open-ended session. Returns session_id (UUID string)."""
    conn = _get_conn()
    if not conn:
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO oe_sessions (student_name, student_email, skills_tested, mode)
                    VALUES (%s, %s, %s, %s)
                    RETURNING session_id
                """, (student_name, student_email, skills_tested, mode))
                return str(cur.fetchone()[0])
    except Exception as e:
        print(f"[OE DB] create_oe_session error: {e}")
        return None
    finally:
        conn.close()


def complete_oe_session(session_id: str, total_score: float, overall_label: str):
    """Mark open-ended session as completed."""
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE oe_sessions SET
                        total_score = %s,
                        overall_label = %s,
                        status = 'completed',
                        completed_at = NOW()
                    WHERE session_id = %s::uuid
                """, (total_score, overall_label, session_id))
    except Exception as e:
        print(f"[OE DB] complete_oe_session error: {e}")
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# QUESTION STORAGE (per session)
# ─────────────────────────────────────────────────────────────────────────────

def store_oe_questions(session_id: str, questions: list[dict]) -> list[dict]:
    """
    Store questions generated for a session.
    Returns list of stored question references:
      [{"session_question_id": str, "question_id": str|None}, ...]
    """
    conn = _get_conn()
    if not conn:
        return []
    try:
        stored_questions = []
        with conn:
            with conn.cursor() as cur:
                for q in questions:
                    cur.execute("""
                        INSERT INTO oe_session_questions
                            (session_id, skill, category, question_text,
                             difficulty, b_param, type, model_answer, hints, source)
                        VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING session_question_id
                    """, (
                        session_id,
                        q.get("skill", ""),
                        q.get("category", ""),
                        q["question_text"],
                        q.get("difficulty", "medium"),
                        q.get("b_param", 0.0),
                        q.get("type", "conceptual"),
                        q.get("model_answer", ""),
                        q.get("hints", []),
                        q.get("source", "llm"),
                    ))
                    row = cur.fetchone()
                    if row:
                        stored_questions.append({
                            "session_question_id": str(row[0]),
                            "question_id": q.get("question_id"),
                        })
        return stored_questions
    except Exception as e:
        print(f"[OE DB] store_oe_questions error: {e}")
        return []
    finally:
        conn.close()


def get_oe_session_questions(session_id: str) -> list[dict]:
    """Get all questions for a session."""
    conn = _get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT session_question_id, question_text, skill, difficulty,
                       b_param, type, model_answer, hints
                FROM oe_session_questions
                WHERE session_id = %s::uuid
                ORDER BY created_at
            """, (session_id,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[OE DB] get_oe_session_questions error: {e}")
        return []
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE STORAGE
# ─────────────────────────────────────────────────────────────────────────────

def save_oe_response(session_id: str, session_question_id: str, skill: str,
                     answer_text: str, confidence: int, score: float,
                     feedback: str, evaluator_model: str = "groq") -> bool:
    """Save one open-ended answer + AI evaluation."""
    conn = _get_conn()
    if not conn:
        return False
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO oe_responses
                        (session_id, session_question_id, skill, answer_text,
                         confidence, score, feedback, evaluator_model)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)
                """, (session_id, session_question_id, skill, answer_text,
                      confidence, score, feedback, evaluator_model))
        return True
    except Exception as e:
        print(f"[OE DB] save_oe_response error: {e}")
        return False
    finally:
        conn.close()


def get_oe_session_responses(session_id: str) -> list[dict]:
    """Get all responses for a session."""
    conn = _get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT response_id, session_question_id, skill, answer_text,
                       confidence, score, feedback, evaluated_at
                FROM oe_responses
                WHERE session_id = %s::uuid
                ORDER BY evaluated_at
            """, (session_id,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[OE DB] get_oe_session_responses error: {e}")
        return []
    finally:
        conn.close()


def update_oe_session_stats(session_id: str, total_questions: int, 
                             total_answered: int, total_score: float):
    """Update session stats after all questions answered."""
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE oe_sessions SET
                        total_questions = %s,
                        total_answered = %s,
                        total_score = %s
                    WHERE session_id = %s::uuid
                """, (total_questions, total_answered, total_score, session_id))
    except Exception as e:
        print(f"[OE DB] update_oe_session_stats error: {e}")
    finally:
        conn.close()
