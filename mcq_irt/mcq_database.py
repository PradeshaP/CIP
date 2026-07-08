"""
mcq_database.py
PostgreSQL database layer for the MCQ + Rasch adaptive quiz system.

TABLES:
  mcq_questions        — question pool per skill with b_param
  mcq_sessions         — one row per student (overall session)
  mcq_responses        — one row per answer (full Rasch state captured)
  mcq_skill_profiles   — final θ per skill per student (leaderboard source)
"""

import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()


def _get_conn():
    try:
        cfg = st_secrets = None
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
        print(f"[MCQ DB] Connection error: {e}")
        return None


def test_connection() -> tuple[bool, str]:
    conn = _get_conn()
    if not conn:
        return False, "Cannot connect to PostgreSQL"
    conn.close()
    return True, "Connected"


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA VERIFICATION (tables already created via db_schema.sql)
# ─────────────────────────────────────────────────────────────────────────────

def init_db() -> bool:
    """Verify MCQ tables exist in interview_coach database."""
    conn = _get_conn()
    if not conn:
        return False
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema='public' AND table_name='mcq_questions'
                """)
                exists = cur.fetchone()[0] > 0
        if exists:
            print("[MCQ DB] Tables verified in interview_coach database.")
        else:
            print("[MCQ DB] WARNING: MCQ tables not found. Run db_schema.sql first.")
        return exists
    except Exception as e:
        print(f"[MCQ DB] init_db error: {e}")
        return False
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# LOAD QUESTION DATASET
# ─────────────────────────────────────────────────────────────────────────────

def load_questions_from_json(filepath: str) -> tuple[int, str]:
    """
    Load questions from mcq_data.json into mcq_questions table.
    Skips questions that already exist (by question_id).
    Returns (count_inserted, error_message)
    """
    conn = _get_conn()
    if not conn:
        return 0, "DB connection failed"
    try:
        with open(filepath, "r") as f:
            data = json.load(f)

        inserted = 0
        with conn:
            with conn.cursor() as cur:
                for skill_block in data.get("skills", []):
                    skill    = skill_block["skill"]
                    category = skill_block.get("category", "")
                    for q in skill_block.get("questions", []):
                        cur.execute("""
                            INSERT INTO mcq_questions
                                (question_id, skill, category, question_text,
                                 option_a, option_b, option_c, option_d,
                                 correct_option, explanation, b_param)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (question_id) DO NOTHING
                        """, (
                            q["question_id"], skill, category,
                            q["question_text"],
                            q["option_a"], q["option_b"],
                            q["option_c"], q["option_d"],
                            q["correct_option"], q.get("explanation",""),
                            q["b_param"],
                        ))
                        inserted += cur.rowcount
        return inserted, ""
    except Exception as e:
        return 0, str(e)
    finally:
        conn.close()


def get_skills() -> list[str]:
    """Return list of distinct skills available in the question pool."""
    conn = _get_conn()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT skill FROM mcq_questions WHERE is_active=TRUE ORDER BY skill")
            return [r[0] for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def get_questions_for_skill(skill: str) -> list[dict]:
    """Return all active questions for a skill as list of dicts."""
    conn = _get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT question_id, skill, category, question_text,
                       option_a, option_b, option_c, option_d,
                       correct_option, explanation, b_param, difficulty_tier
                FROM mcq_questions
                WHERE skill = %s AND is_active = TRUE
                ORDER BY b_param
            """, (skill,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[MCQ DB] get_questions_for_skill error: {e}")
        return []
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# SESSION MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def create_session(student_name: str, student_email: str,
                   skills_tested: list[str]) -> str | None:
    """Create a new quiz session. Returns session_id (UUID string)."""
    conn = _get_conn()
    if not conn:
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO mcq_sessions (student_name, student_email, skills_tested)
                    VALUES (%s, %s, %s)
                    RETURNING session_id
                """, (student_name, student_email, skills_tested))
                return str(cur.fetchone()[0])
    except Exception as e:
        print(f"[MCQ DB] create_session error: {e}")
        return None
    finally:
        conn.close()


def save_response(session_id: str, question_id: str, skill: str,
                  selected_option: str, is_correct: bool,
                  b_used: float, theta_before: float, theta_after: float,
                  p_correct_irt: float, surprise: float,
                  proficiency_before: float, proficiency_after: float) -> str:
    """Save one answer + Rasch state to mcq_responses. Returns error string or empty string."""
    conn = _get_conn()
    if not conn:
        return "DB connection failed"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO mcq_responses
                        (session_id, question_id, skill, selected_option,
                         is_correct, b_used, theta_before, theta_after,
                         p_correct_irt, surprise,
                         proficiency_before, proficiency_after)
                    VALUES (%s::uuid,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (session_id, question_id, skill, selected_option,
                      is_correct, b_used, theta_before, theta_after,
                      p_correct_irt, surprise,
                      proficiency_before, proficiency_after))
        return ""
    except Exception as e:
        print(f"[MCQ DB] save_response error: {e}")
        return str(e)
    finally:
        conn.close()


def save_skill_profile(session_id: str, student_name: str,
                       student_email: str, skill: str,
                       theta_final: float, proficiency_score: float,
                       proficiency_label: str, questions_answered: int,
                       questions_correct: int):
    """Save final θ for one skill at end of skill section."""
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO mcq_skill_profiles
                        (session_id, student_name, student_email, skill,
                         theta_final, proficiency_score, proficiency_label,
                         questions_answered, questions_correct)
                    VALUES (%s::uuid,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (session_id, skill) DO UPDATE SET
                        theta_final       = EXCLUDED.theta_final,
                        proficiency_score = EXCLUDED.proficiency_score,
                        proficiency_label = EXCLUDED.proficiency_label,
                        questions_answered = EXCLUDED.questions_answered,
                        questions_correct  = EXCLUDED.questions_correct,
                        completed_at       = NOW()
                """, (session_id, student_name, student_email, skill,
                      theta_final, proficiency_score, proficiency_label,
                      questions_answered, questions_correct))
    except Exception as e:
        print(f"[MCQ DB] save_skill_profile error: {e}")
        return str(e)
    finally:
        conn.close()


def complete_session(session_id: str, theta_overall: float,
                     proficiency_label: str, proficiency_score: float,
                     total_answered: int, total_correct: int):
    """
    Mark MCQ session as completed and store final overall θ.
    Also updates final_sessions via final_database.
    """
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                # Update MCQ session
                cur.execute("""
                    UPDATE mcq_sessions SET
                        theta_overall     = %s,
                        proficiency_label = %s,
                        proficiency_score = %s,
                        total_answered    = %s,
                        total_correct     = %s,
                        status            = 'completed',
                        completed_at      = NOW()
                    WHERE session_id = %s::uuid
                """, (theta_overall, proficiency_label, proficiency_score,
                      total_answered, total_correct, session_id))
                
                # Get student info for final session update
                cur.execute("""
                    SELECT student_name, student_email FROM mcq_sessions 
                    WHERE session_id = %s::uuid
                """, (session_id,))
                row = cur.fetchone()
                if row:
                    student_name, student_email = row
                    try:
                        import final_database as fdb
                        final_sid = fdb.create_final_session(
                            student_name, student_email, "mcq",
                            mcq_session_id=session_id
                        )
                        if final_sid:
                            fdb.complete_final_session(
                                final_sid,
                                total_questions=total_answered,
                                total_answered=total_answered,
                                final_score=proficiency_score,
                                overall_label=proficiency_label,
                                total_correct=total_correct,
                                proficiency_score=proficiency_score,
                                proficiency_label=proficiency_label,
                            )
                    except Exception as e:
                        print(f"[MCQ DB] Failed to update final tables: {e}")
    except Exception as e:
        print(f"[MCQ DB] complete_session error: {e}")
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# LEADERBOARD QUERIES
# ─────────────────────────────────────────────────────────────────────────────

def get_overall_leaderboard() -> list[dict]:
    """
    Overall leaderboard — ranked by average θ across all skills.
    One row per student session.
    """
    conn = _get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    s.session_id,
                    s.student_name,
                    s.student_email,
                    s.theta_overall,
                    s.proficiency_label,
                    s.proficiency_score,
                    s.total_answered,
                    s.total_correct,
                    s.completed_at,
                    RANK() OVER (ORDER BY s.theta_overall DESC) AS overall_rank
                FROM mcq_sessions s
                WHERE s.status = 'completed'
                ORDER BY s.theta_overall DESC
            """)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[MCQ DB] get_overall_leaderboard error: {e}")
        return []
    finally:
        conn.close()


def get_skill_leaderboard(skill: str) -> list[dict]:
    """
    Leaderboard for one specific skill — ranked by θ for that skill.
    """
    conn = _get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    sp.student_name,
                    sp.student_email,
                    sp.skill,
                    sp.theta_final,
                    sp.proficiency_score,
                    sp.proficiency_label,
                    sp.questions_answered,
                    sp.questions_correct,
                    RANK() OVER (ORDER BY sp.theta_final DESC) AS skill_rank
                FROM mcq_skill_profiles sp
                WHERE sp.skill = %s
                ORDER BY sp.theta_final DESC
            """, (skill,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[MCQ DB] get_skill_leaderboard error: {e}")
        return []
    finally:
        conn.close()


def get_all_skills_leaderboard() -> dict[str, list[dict]]:
    """Return leaderboard for every skill in one call."""
    skills = get_skills()
    return {skill: get_skill_leaderboard(skill) for skill in skills}


def get_session_skill_profiles(session_id: str) -> list[dict]:
    """Get all skill profiles for one student session (results page)."""
    conn = _get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT skill, theta_final, proficiency_score,
                       proficiency_label, questions_answered, questions_correct
                FROM mcq_skill_profiles
                WHERE session_id = %s::uuid
                ORDER BY theta_final DESC
            """, (session_id,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[MCQ DB] get_session_skill_profiles error: {e}")
        return []
    finally:
        conn.close()


def update_question_b(question_id: str, b_final: float,
                      is_correct: bool, b_source: str):
    """
    Update b_param in DB after every answer — mirrors senior's QB write-back.
    Also increments response_count and correct_count for calibration.
    """
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE mcq_questions SET
                        b_param        = %s,
                        response_count = response_count + 1,
                        correct_count  = correct_count + %s
                    WHERE question_id = %s
                """, (b_final, 1 if is_correct else 0, question_id))
    except Exception as e:
        print(f"[MCQ DB] update_question_b error: {e}")
    finally:
        conn.close()