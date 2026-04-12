"""
main_app.py  —  Unified Interview Coach + Adaptive MCQ
Merges enhanced_app.py (AI Interview) and mcq_app.py (Adaptive MCQ)
into a single Streamlit application with a mode switcher.

All original logic is preserved — only the entry point and navigation
are changed.  Run with:
    streamlit run main_app.py
"""

import os
import math
import html as html_module
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

# ── AI Interview imports ──────────────────────────────────────────────────────
from enhanced_skill_extractor import EnhancedSkillExtractor
from resume_parser import ResumeParser
from question_generator import QuestionGenerator
from answer_evaluator import AnswerEvaluator, LIKERT_SCALE
import mcq_irt.rasch_engine as irt

# ── MCQ imports ───────────────────────────────────────────────────────────────
import mcq_irt.mcq_database as db

# ── Database imports (unified interview_coach DB) ──────────────────────────────
import open_ended_database as oe_db
import final_database as final_db

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG  (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Interview Coach",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# MCQ AUTO-SETUP (runs once — loads question bank if empty)
# ─────────────────────────────────────────────────────────────────────────────

MCQ_DATA_PATH       = "mcq_irt/mcq_data.json"
QUESTIONS_PER_SKILL = 3

def _mcq_auto_setup():
    db.init_db()
    skills = db.get_skills()
    if not skills:
        n, err = db.load_questions_from_json(MCQ_DATA_PATH)
        if err:
            print(f"[MCQ Setup] Failed to load: {err}")
        else:
            print(f"[MCQ Setup] Loaded {n} questions from {MCQ_DATA_PATH}")

_mcq_auto_setup()

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
.stApp { background: #f0f4ff; }

section[data-testid="stSidebar"] { background: #1e1b4b !important; border-right: none; }
section[data-testid="stSidebar"] * { color: #c7d2fe !important; }
section[data-testid="stSidebar"] .stButton button {
    background: #4f46e5 !important; color: white !important;
    border: none !important; border-radius: 8px !important; }
.main .block-container { background: transparent; padding: 2rem 2.5rem; max-width: 1000px; }

/* ── Mode switcher ── */
.mode-switcher {
    display: flex; gap: 10px; margin-bottom: 1.6rem;
    background: white; border-radius: 14px; padding: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(79,70,229,0.07);
}
.mode-btn-active {
    flex: 1; text-align: center; padding: 12px 20px; border-radius: 10px;
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
    color: white !important; font-weight: 700; font-size: 0.95rem;
    cursor: default;
}
.mode-btn-inactive {
    flex: 1; text-align: center; padding: 12px 20px; border-radius: 10px;
    background: #f1f5f9; color: #64748b !important; font-weight: 600;
    font-size: 0.95rem; cursor: pointer;
}

/* ── Shared cards ── */
.page-banner {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%);
    border-radius: 16px; padding: 2rem 2.4rem; margin-bottom: 1.5rem; color: white; }
.page-banner-mcq {
    background: linear-gradient(135deg, #1e1b4b 0%, #4f46e5 60%, #7c3aed 100%);
    border-radius: 16px; padding: 2rem 2.4rem; margin-bottom: 1.5rem; color: white; }
.page-banner h1, .page-banner-mcq h1 {
    margin: 0 0 0.3rem; font-size: 1.7rem; font-weight: 800;
    letter-spacing: -0.02em; color: white; }
.page-banner p, .page-banner-mcq p {
    margin: 0; font-size: 0.92rem; opacity: 0.85; color: white; }

.content-card {
    background: white; border-radius: 16px; padding: 1.8rem 2rem; margin-bottom: 1.2rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(79,70,229,0.07); }
.card {
    background: white; border-radius: 16px; padding: 1.6rem 2rem; margin-bottom: 1.2rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(79,70,229,0.07); }
.section-label {
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #6366f1; margin-bottom: 0.7rem; }
.section-divider { border: none; border-top: 1.5px solid #e0e7ff; margin: 1.2rem 0; }

/* ── AI Interview: skill pills ── */
.skill-pill {
    display: inline-block; padding: 4px 13px; margin: 3px; border-radius: 999px;
    font-size: 0.78rem; font-weight: 600; background: #eef2ff;
    color: #4338ca; border: 1px solid #c7d2fe; }
.skill-pill-semantic {
    display: inline-block; padding: 4px 13px; margin: 3px; border-radius: 999px;
    font-size: 0.78rem; font-weight: 600; background: #fdf4ff;
    color: #7e22ce; border: 1px dashed #d8b4fe; }
.skill-pill-cat {
    display: inline-block; padding: 2px 10px; margin: 2px; border-radius: 4px;
    font-size: 0.68rem; font-weight: 700; background: #f0fdf4;
    color: #16a34a; border: 1px solid #bbf7d0; text-transform: uppercase; }
.skill-pill-project {
    display: inline-block; padding: 2px 10px; margin: 2px; border-radius: 4px;
    font-size: 0.68rem; font-weight: 700; background: #fff7ed;
    color: #c2410c; border: 1px solid #fdba74; text-transform: uppercase; }

/* ── AI Interview: question card ── */
.q-card {
    background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
    border: 1.5px solid #c7d2fe; border-radius: 14px;
    padding: 1.4rem 1.6rem; margin-bottom: 0.6rem; }
.q-meta { display: flex; gap: 8px; flex-wrap: wrap; font-size: 0.72rem; margin-bottom: 0.8rem; }
.q-meta span { padding: 3px 10px; border-radius: 999px; font-weight: 600; }
.q-num  { background: #4f46e5; color: white; }
.q-skill { background: #7c3aed; color: white; }
.q-text { font-size: 1.05rem; color: #1e1b4b; font-weight: 600; line-height: 1.65; }

/* ── Confidence badge ── */
.confidence-badge {
    border-radius: 8px; padding: 8px 14px; margin-bottom: 1rem;
    font-size: 0.82rem; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.confidence-high   { background: #f0fdf4; border: 1px solid #bbf7d0; color: #16a34a; }
.confidence-medium { background: #fffbeb; border: 1px solid #fde68a; color: #d97706; }
.confidence-low    { background: #fef2f2; border: 1px solid #fecaca; color: #dc2626; }

/* ── Progress ── */
.progress-bar-wrap { background: #e0e7ff; border-radius: 999px; height: 6px;
    margin-bottom: 1.2rem; overflow: hidden; }
.progress-bar-fill { background: linear-gradient(90deg, #4f46e5, #a855f7);
    height: 6px; border-radius: 999px; }
.q-counter { font-size: 0.8rem; font-weight: 600; color: #6366f1; margin-bottom: 0.4rem; }
.prog-wrap { background: #e0e7ff; border-radius: 99px; height: 6px;
    overflow: hidden; margin: 0.4rem 0 1.2rem; }
.prog-fill  { height: 100%; border-radius: 99px;
    background: linear-gradient(90deg, #4f46e5, #7c3aed); }

/* ── Score / grade ── */
.score-wrap { text-align: center; padding: 1rem 0.5rem; }
.score-ring {
    width: 110px; height: 110px; border-radius: 50%;
    display: inline-flex; flex-direction: column;
    align-items: center; justify-content: center; margin-bottom: 0.5rem; }
.score-num { font-size: 2.2rem; font-weight: 800; letter-spacing: -0.04em; line-height: 1; }
.score-denom { font-size: 0.72rem; color: #94a3b8; }
.grade-badge {
    display: inline-block; padding: 4px 16px; border-radius: 999px;
    font-size: 0.78rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }

/* ── Rubric rows ── */
.rubric-row { margin-bottom: 12px; }
.rubric-label { display: flex; justify-content: space-between;
    font-size: 0.8rem; color: #475569; margin-bottom: 4px; font-weight: 500; }
.rubric-track { background: #e2e8f0; border-radius: 999px; height: 8px; overflow: hidden; }
.rubric-fill { height: 8px; border-radius: 999px; }

/* ── Feedback ── */
.fb-strength {
    display: flex; align-items: flex-start; gap: 8px;
    background: #f0fdf4; border: 1px solid #bbf7d0;
    padding: 9px 13px; margin: 5px 0; border-radius: 10px;
    font-size: 0.84rem; color: #166534; font-weight: 500; }
.fb-improve {
    display: flex; align-items: flex-start; gap: 8px;
    background: #fffbeb; border: 1px solid #fde68a;
    padding: 9px 13px; margin: 5px 0; border-radius: 10px;
    font-size: 0.84rem; color: #92400e; font-weight: 500; }
.hint-box {
    background: #fffbeb; border: 1.5px dashed #fbbf24;
    border-radius: 10px; padding: 12px 16px;
    font-size: 0.84rem; color: #78350f; margin-top: 8px; }

/* ── Metric cards ── */
.metric-card {
    background: white; border-radius: 14px; padding: 1.3rem 1rem; text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 12px rgba(79,70,229,0.08);
    border-top: 4px solid; }
.metric-val { font-size: 1.9rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1; margin-bottom: 4px; }
.metric-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.08em; color: #94a3b8; }

/* ── Category bars ── */
.cat-row { margin-bottom: 14px; }
.cat-row-label { display: flex; justify-content: space-between;
    font-size: 0.85rem; font-weight: 600; color: #1e1b4b; margin-bottom: 5px; }
.cat-track { background: #e0e7ff; border-radius: 999px; height: 10px; overflow: hidden; }
.cat-fill { height: 10px; border-radius: 999px; }

/* ── Legend ── */
.legend-box {
    display:flex; gap:16px; flex-wrap:wrap; align-items:center;
    font-size:0.76rem; color:#475569; margin-bottom:1rem;
    background:#f8fafc; border-radius:10px; padding:10px 14px;
    border:1px solid #e2e8f0; }

/* ── IRT calibration ── */
.calibration-accurate   { background: #f0fdf4; border: 1.5px solid #86efac; color: #15803d; }
.calibration-over       { background: #fff7ed; border: 1.5px solid #fdba74; color: #c2410c; }
.calibration-under      { background: #eff6ff; border: 1.5px solid #93c5fd; color: #1d4ed8; }
.calibration-default    { background: #f8fafc; border: 1.5px solid #e2e8f0; color: #475569; }

/* ── MCQ styles ── */
.skill-tab-active  { background: #4f46e5; color: white; border-radius: 8px;
    padding: 6px 16px; font-weight: 700; font-size: 0.82rem; display:inline-block; }
.skill-tab-done    { background: #dcfce7; color: #15803d; border-radius: 8px;
    padding: 6px 16px; font-weight: 700; font-size: 0.82rem; display:inline-block; }
.skill-tab-pending { background: #f1f5f9; color: #64748b; border-radius: 8px;
    padding: 6px 16px; font-weight: 600; font-size: 0.82rem; display:inline-block; }
.prof-pill {
    display: inline-block; border-radius: 99px;
    padding: 4px 18px; font-weight: 700; font-size: 0.82rem; }
.lb-row { display: flex; align-items: center; gap: 14px;
    padding: 0.8rem 1.2rem; border-radius: 12px;
    background: white; border: 1px solid #e0e7ff; margin-bottom: 6px; }
.lb-row.gold   { border-color: #f59e0b; background: #fffbeb; }
.lb-row.silver { border-color: #9ca3af; background: #f9fafb; }
.lb-row.bronze { border-color: #d97706; background: #fefce8; }
.lb-row.is-me  { border-color: #4f46e5; border-width: 2px; }
.lb-name  { font-weight: 700; color: #1e1b4b; }
.lb-score { font-family: 'DM Mono', monospace; color: #4f46e5; font-weight: 600; }
.lb-you   { background: #eef2ff; color: #4f46e5; border-radius: 4px;
    padding: 2px 8px; font-size: 0.7rem; font-weight: 700; margin-left: 6px; }
.expl-box { background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 10px;
    padding: 0.8rem 1rem; font-size: 0.87rem; color: #3730a3; margin-top: 0.6rem; }
.theta-display { font-family: 'DM Mono', monospace; font-size: 0.78rem;
    color: #64748b; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CACHED RESOURCE LOADERS
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def load_interview_tools():
    return EnhancedSkillExtractor(), ResumeParser(), QuestionGenerator(), AnswerEvaluator()

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE DEFAULTS
# ─────────────────────────────────────────────────────────────────────────────

# Shared
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "interview"   # "interview" | "mcq"

# ── AI Interview defaults ─────────────────────────────────────────────────────
_interview_defaults = {
    "stage":              "upload",
    "skills_data":        None,
    "answers_per_skill":  9,
    "questions":          [],
    "answers":            {},
    "evaluations":        {},
    "q_index":            0,
    "resume_text":        "",
    "last_uploaded_file": None,
    "current_q_irt":      None,
    "current_cat_irt":    None,
}
for k, v in _interview_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── MCQ defaults ──────────────────────────────────────────────────────────────
_mcq_defaults = {
    "mcq_stage":           "home",
    "student_name":        "",
    "student_email":       "",
    "session_id":          None,
    "skills":              [],
    "skill_pools":         {},
    "skill_index":         0,
    "skill_thetas":        {},
    "skill_responses":     {},
    "skill_asked":         {},
    "skill_last_correct":  {},
    "skill_profiles":      {},
    "q_count":             0,
    "current_q":           None,
    "questions_per_skill": 15,
}
for k, v in _mcq_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS — AI Interview
# ─────────────────────────────────────────────────────────────────────────────

GRADE = {
    "Excellent":         ("#16a34a", "#dcfce7", "#bbf7d0"),
    "Good":              ("#4f46e5", "#eef2ff", "#c7d2fe"),
    "Average":           ("#d97706", "#fffbeb", "#fde68a"),
    "Needs Improvement": ("#dc2626", "#fef2f2", "#fecaca"),
    "Error":             ("#64748b", "#f8fafc", "#e2e8f0"),
}

def grade_colors(grade):
    return GRADE.get(grade, GRADE["Error"])

def diff_badge(d):
    return {"easy":   ("#16a34a","#f0fdf4","#bbf7d0"),
            "medium": ("#d97706","#fffbeb","#fde68a"),
            "hard":   ("#dc2626","#fef2f2","#fecaca")}.get(d, ("#64748b","#f8fafc","#e2e8f0"))

def render_confidence_badge(q: dict):
    if q.get("type") == "project":
        return
    confidence = q.get("confidence", "high")
    similarity = q.get("similarity", 1.0)
    conf_map = {
        "high":   ("✅", "confidence-high",   "Both AI models agree — answer is reliable"),
        "medium": ("⚠️", "confidence-medium", "Models partially agreed — verify key points"),
        "low":    ("🔴", "confidence-low",    "Models disagreed — verify with your textbook"),
    }
    icon, css, message = conf_map.get(confidence, conf_map["high"])
    st.markdown(
        f'<div class="confidence-badge {css}">'
        f'{icon}&nbsp;<b>Answer confidence: {confidence.upper()}</b>'
        f'&nbsp;·&nbsp;Agreement score: {similarity}'
        f'&nbsp;·&nbsp;{message}</div>',
        unsafe_allow_html=True)

def render_score(score, grade):
    c, bg, border = grade_colors(grade)
    st.markdown(f"""
    <div class="score-wrap">
        <div class="score-ring" style="background:{bg};border:3px solid {border}">
            <div class="score-num" style="color:{c}">{score}</div>
            <div class="score-denom">/ 100</div>
        </div><br>
        <span class="grade-badge" style="background:{bg};color:{c};border:1px solid {border}">
            {grade}
        </span>
    </div>""", unsafe_allow_html=True)

def interview_progress_bar(current, total):
    pct = int(((current) / total) * 100) if total else 0
    st.markdown(f"""
    <div class="q-counter">Question {current + 1} of {total}</div>
    <div class="progress-bar-wrap">
        <div class="progress-bar-fill" style="width:{pct}%"></div>
    </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS — MCQ
# ─────────────────────────────────────────────────────────────────────────────

PROF_COLORS = {
    "Expert":       ("#534AB7", "#ede9fe"),
    "Advanced":     ("#1D9E75", "#dcfce7"),
    "Intermediate": ("#378ADD", "#dbeafe"),
    "Beginner":     ("#d97706", "#fef3c7"),
    "Novice":       ("#dc2626", "#fee2e2"),
}
MEDALS  = {1: "🥇", 2: "🥈", 3: "🥉"}
ROW_CLS = {1: "gold", 2: "silver", 3: "bronze"}

def prof_pill(label: str) -> str:
    color, bg = PROF_COLORS.get(label, ("#64748b", "#f1f5f9"))
    return (f'<span class="prof-pill" style="background:{bg};color:{color}">{label}</span>')

def render_lb_rows(rows: list, current_sid: str = None):
    st.markdown('<div>', unsafe_allow_html=True)
    for r in rows:
        rank    = int(r.get("overall_rank") or r.get("skill_rank") or 1)
        medal   = MEDALS.get(rank, "")
        row_cls = ROW_CLS.get(rank, "")
        is_me   = current_sid and str(r.get("session_id","")) == current_sid
        theta   = float(r.get("theta_final") or r.get("theta_overall") or 0)
        prof    = r.get("proficiency_label", "")
        name    = html_module.escape(str(r.get("student_name","")))
        you     = '<span class="lb-you">you</span>' if is_me else ""
        correct = r.get("questions_correct", r.get("total_correct", 0))
        total   = r.get("questions_answered", r.get("total_answered", 0))
        color, bg = PROF_COLORS.get(prof, ("#64748b","#f1f5f9"))
        me_cls  = " is-me" if is_me else ""
        st.markdown(f"""
        <div class="lb-row {row_cls}{me_cls}">
            <div style="font-size:1.2rem;min-width:28px">{medal}</div>
            <div style="font-family:'DM Mono',monospace;font-size:0.78rem;
                        color:#94a3b8;min-width:26px">#{rank}</div>
            <div style="flex:1">
                <div class="lb-name">{name}{you}</div>
                <div class="theta-display">θ = {theta:+.3f}</div>
            </div>
            <div style="text-align:right">
                <span class="prof-pill" style="background:{bg};color:{color}">{prof}</span>
                <div style="font-size:0.75rem;color:#94a3b8;margin-top:2px">
                    {correct}/{total} correct</div>
            </div>
        </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def reset_mcq_session():
    dynamic_keys = [k for k in st.session_state if k.startswith("skill_session_")]
    for k in dynamic_keys:
        del st.session_state[k]
    for k, v in _mcq_defaults.items():
        st.session_state[k] = v


def require_profile() -> bool:
    if not st.session_state.student_name or not st.session_state.student_email:
        st.warning("Please enter your name and email in the sidebar before continuing.")
        return False
    return True

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style="padding:0.5rem 0 1.2rem">
        <div style="font-size:1.3rem;font-weight:800;color:white;letter-spacing:-0.02em">
            🚀 Interview Coach
        </div>
        <div style="font-size:0.75rem;color:#a5b4fc;margin-top:3px">AI-powered interview platform</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom:0.5rem;font-size:0.72rem;font-weight:700;"
                "letter-spacing:0.1em;text-transform:uppercase;color:#a5b4fc'>Profile</div>",
                unsafe_allow_html=True)
    if st.session_state.student_name and st.session_state.student_email:
        st.markdown(f"**{st.session_state.student_name}**")
        st.markdown(f"<span style='font-size:0.85rem;color:#c7d2fe'>{st.session_state.student_email}</span>", unsafe_allow_html=True)
        if st.button("Edit Profile", use_container_width=True):
            st.session_state.student_name = ""
            st.session_state.student_email = ""
            st.experimental_rerun()
    else:
        name = st.text_input("Full Name", value=st.session_state.get("sidebar_name", ""), key="sidebar_name")
        email = st.text_input("Email", value=st.session_state.get("sidebar_email", ""), key="sidebar_email")
        if st.button("Save Profile", use_container_width=True):
            if not name.strip() or "@" not in email:
                st.warning("Enter a valid name and email to continue.")
            else:
                st.session_state.student_name = name.strip()
                st.session_state.student_email = email.strip()
                st.success("Profile saved. Select a mode to continue.")

    st.markdown("<hr style='border-color:#312e81;margin:1rem 0'>", unsafe_allow_html=True)
    
    # ── Mode switcher in sidebar ──────────────────────────────────────────
    st.markdown("<div style='margin-bottom:0.5rem;font-size:0.72rem;font-weight:700;"
                "letter-spacing:0.1em;text-transform:uppercase;color:#a5b4fc'>Mode</div>",
                unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🎤 AI Interview",
                     use_container_width=True,
                     type="primary" if st.session_state.app_mode == "interview" else "secondary"):
            st.session_state.app_mode = "interview"
            st.rerun()
    with col_b:
        if st.button("🎯 MCQ Quiz",
                     use_container_width=True,
                     type="primary" if st.session_state.app_mode == "mcq" else "secondary"):
            st.session_state.app_mode = "mcq"
            st.rerun()

    st.markdown("<hr style='border-color:#312e81;margin:1rem 0'>", unsafe_allow_html=True)

    # ── Mode-specific sidebar content ──────────────────────────────────────
    if st.session_state.app_mode == "interview":
        steps = [("upload","1","Upload Resume"),("configure","2","Configure"),
                 ("interview","3","Interview"),("results","4","Results")]
        cur = st.session_state.stage
        for stage, num, label in steps:
            if stage == cur:
                st.markdown(f"""
                <div style="background:#4f46e5;border-radius:10px;padding:10px 14px;
                            margin-bottom:6px;display:flex;align-items:center;gap:10px">
                    <div style="background:white;color:#4f46e5;width:22px;height:22px;
                                border-radius:50%;display:flex;align-items:center;
                                justify-content:center;font-size:0.72rem;font-weight:800;
                                flex-shrink:0">{num}</div>
                    <span style="color:white;font-weight:700;font-size:0.88rem">{label}</span>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="padding:10px 14px;margin-bottom:6px;
                            display:flex;align-items:center;gap:10px">
                    <div style="background:#312e81;color:#a5b4fc;width:22px;height:22px;
                                border-radius:50%;display:flex;align-items:center;
                                justify-content:center;font-size:0.72rem;font-weight:700;
                                flex-shrink:0">{num}</div>
                    <span style="color:#a5b4fc;font-size:0.85rem">{label}</span>
                </div>""", unsafe_allow_html=True)

        if st.session_state.stage == "interview" and st.session_state.questions:
            total = len(st.session_state.questions)
            done  = len(st.session_state.evaluations)
            pct   = int(done / total * 100)
            st.markdown(f"""
            <div style="margin:0.8rem 0">
                <div style="display:flex;justify-content:space-between;
                            font-size:0.76rem;color:#a5b4fc;margin-bottom:6px">
                    <span>Progress</span><span>{done}/{total} answered</span>
                </div>
                <div style="background:#312e81;border-radius:999px;height:6px">
                    <div style="width:{pct}%;background:#a5b4fc;height:6px;border-radius:999px"></div>
                </div>
            </div>""", unsafe_allow_html=True)

        if st.button("↺  Start Over", use_container_width=True):
            for k, v in _interview_defaults.items():
                st.session_state[k] = v
            st.rerun()

    else:  # MCQ sidebar
        for label, stage in [("🏠 Home","home"),("🏆 Leaderboard","leaderboard")]:
            if st.button(label, use_container_width=True):
                st.session_state.mcq_stage = stage
                st.rerun()
        st.markdown("<hr style='border-color:#312e81;margin:1rem 0'>", unsafe_allow_html=True)
        ok, msg = db.test_connection()
        if ok:
            st.success("🟢 DB connected")
        else:
            st.error(f"🔴 DB error\n{msg[:60]}")
        if st.session_state.get("student_name", ""):
            st.markdown(f"**👤 {st.session_state.student_name}**")
            if st.button("🔄 Switch Student", use_container_width=True):
                reset_mcq_session()
                st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# MAIN CONTENT — MODE SWITCHER BANNER
# ─────────────────────────────────────────────────────────────────────────────

mode = st.session_state.app_mode

ai_active   = "mode-btn-active"   if mode == "interview" else "mode-btn-inactive"
mcq_active  = "mode-btn-active"   if mode == "mcq"       else "mode-btn-inactive"

st.markdown(f"""
<div class="mode-switcher">
    <div class="{ai_active}">🎤 AI Interview Coach</div>
    <div class="{mcq_active}">🎯 Adaptive MCQ Quiz</div>
</div>""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
#  AI INTERVIEW MODE
# ═════════════════════════════════════════════════════════════════════════════

if mode == "interview":

    try:
        skill_extractor, resume_parser, question_gen, answer_eval = load_interview_tools()
    except Exception as e:
        st.error(f"Failed to load AI tools: {e}")
        st.stop()

    if not require_profile():
        st.stop()

    # ── STAGE 1: UPLOAD ───────────────────────────────────────────────────────
    if st.session_state.stage == "upload":
        st.markdown("""
        <div class="page-banner">
            <h1>AI Interview Coach</h1>
            <p>Upload your resume · Skills + projects extracted · AI asks tough questions · You get scored</p>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Step 1 — Upload Resume</div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("PDF, DOCX or TXT", type=["pdf","docx","txt"])

        if uploaded_file:
            file_identity = (uploaded_file.name, uploaded_file.size)
            if st.session_state.last_uploaded_file != file_identity:
                st.session_state.questions    = []
                st.session_state.answers      = {}
                st.session_state.evaluations  = {}
                st.session_state.q_index      = 0
                st.session_state.last_uploaded_file = file_identity

            st.markdown(f"""
            <div style="background:#eef2ff;border:1.5px solid #c7d2fe;border-radius:10px;
                        padding:12px 16px;margin:10px 0;display:flex;
                        justify-content:space-between;align-items:center">
                <span style="font-weight:600;color:#3730a3">📄 {uploaded_file.name}</span>
                <span style="font-size:0.8rem;color:#6366f1;background:white;
                             padding:2px 10px;border-radius:999px;border:1px solid #c7d2fe">
                    {uploaded_file.size/1024:.1f} KB
                </span>
            </div>""", unsafe_allow_html=True)

            st.write("")
            if st.button("Extract Skills →", type="primary", use_container_width=True):
                with st.spinner("Analysing resume with NLP + semantic matching…"):
                    temp_dir  = "temp_uploads"
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    try:
                        text = resume_parser.extract_text(temp_path)
                        if not text:
                            st.error("Could not extract text. Try a different file.")
                        else:
                            skills_data = skill_extractor.extract_all_skills(text)
                            st.session_state.skills_data = skills_data
                            st.session_state.resume_text = text
                            st.session_state.stage       = "configure"
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── STAGE 2: CONFIGURE ────────────────────────────────────────────────────
    elif st.session_state.stage == "configure":
        st.markdown("""
        <div class="page-banner">
            <h1>Skills Detected</h1>
            <p>Review what LLaMA extracted from your resume, then configure your session</p>
        </div>""", unsafe_allow_html=True)

        skills_data  = st.session_state.skills_data
        total_skills = skills_data["total_skills"]

        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Skills Found</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="legend-box">
            <span><span class="skill-pill">Skill</span> &nbsp;extracted by LLaMA from resume</span>
            <span><span class="skill-pill-semantic">Skill</span> &nbsp;keyword fallback</span>
        </div>""", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:0.9rem;color:#475569;margin-bottom:1rem'>"
                    f"<b style='color:#1e1b4b'>{total_skills} skills</b> detected</p>",
                    unsafe_allow_html=True)

        for category, skills_list in skills_data["categories"].items():
            if skills_list:
                pills = ""
                for s in skills_list:
                    css_class = "skill-pill-semantic" if s.get("source") == "fallback" else "skill-pill"
                    pills += f'<span class="{css_class}">{s["name"]}</span> '
                st.markdown(
                    f'<div style="margin-bottom:0.9rem">'
                    f'<span class="skill-pill-cat">{category}</span>'
                    f'<div style="margin-top:6px">{pills}</div></div>',
                    unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Interview Settings</div>', unsafe_allow_html=True)
        q_per_level = 5
        answers_per_skill = st.slider(
            "Questions per skill", min_value=5, max_value=15, value=9, step=1,
            help="IRT adaptively picks from a pool of 15 questions per skill.")
        include_projects = st.checkbox(
            "🗂️  Include project-based questions", value=True)

        pool_size = total_skills * 15
        estimated = total_skills * answers_per_skill
        proj_note = " + project questions" if include_projects else ""
        st.markdown(f"""
        <div style="background:#eef2ff;border:1.5px solid #c7d2fe;border-radius:10px;
                    padding:12px 18px;margin:1rem 0;display:flex;align-items:center;gap:10px">
            <span style="font-size:1.2rem">📋</span>
            <span style="font-size:0.9rem;color:#3730a3">
                <b>Pool: {pool_size} questions generated</b> · <b>Student answers: {estimated}</b> (IRT adaptive){proj_note}
            </span>
        </div>""", unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("← Back", use_container_width=True):
                st.session_state.stage = "upload"; st.rerun()
        with col_b:
            if st.button("Generate Questions →", type="primary", use_container_width=True):
                if total_skills == 0:
                    st.warning("No skills found. Upload a more detailed resume.")
                else:
                    with st.spinner("AI is generating and validating questions…"):
                        resume_text_for_projects = (
                            st.session_state.resume_text if include_projects else "")
                        questions  = []
                        gen_error  = None
                        try:
                            questions = question_gen.generate_questions(
                                skills_data, questions_per_skill=q_per_level,
                                resume_text=resume_text_for_projects)
                        except RuntimeError as e:
                            gen_error = str(e)
                        except Exception as e:
                            gen_error = f"Unexpected error: {e}"

                    if gen_error:
                        st.error(f"❌ Question generation failed:\n\n{gen_error}")
                    elif questions:
                        cat_pool = {}
                        for q in questions:
                            cat = q.get("category", "Other")
                            cat_pool.setdefault(cat, []).append(q)

                        oe_session_id = None
                        oe_question_map = {}
                        try:
                            skills_tested = [skill["name"] for category, skills_list in skills_data.get("categories", {}).items() for skill in skills_list]
                            oe_session_id = oe_db.create_oe_session(
                                st.session_state.student_name,
                                st.session_state.student_email,
                                skills_tested,
                                mode="open_ended"
                            )
                            if oe_session_id:
                                stored_questions = oe_db.store_oe_questions(oe_session_id, questions)
                                oe_question_map = {
                                    item["question_id"]: item["session_question_id"]
                                    for item in stored_questions
                                    if item.get("question_id")
                                }
                        except Exception as e:
                            st.warning(f"⚠️ Open-ended session persistence failed: {e}")

                        st.session_state.questions        = questions
                        st.session_state.q_index          = 0
                        st.session_state.answers          = {}
                        st.session_state.evaluations      = {}
                        st.session_state.cat_pool         = cat_pool
                        st.session_state.category_thetas  = {
                            cat: irt.THETA_INIT for cat in cat_pool}
                        st.session_state.category_asked   = {
                            cat: set() for cat in cat_pool}
                        st.session_state.category_responses = {
                            cat: [] for cat in cat_pool}
                        st.session_state.answers_per_skill = answers_per_skill
                        st.session_state.stage            = "interview"
                        st.session_state.oe_session_id    = oe_session_id
                        st.session_state.oe_question_map  = oe_question_map
                        st.session_state.oe_completed     = False
                        st.rerun()
                    else:
                        st.error("❌ No questions were generated.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── STAGE 3: INTERVIEW ────────────────────────────────────────────────────
    elif st.session_state.stage == "interview":
        questions         = st.session_state.questions
        q_index           = st.session_state.q_index
        answers_per_skill = st.session_state.get("answers_per_skill", 9)
        cat_pool          = st.session_state.get("cat_pool", {})
        cat_thetas        = st.session_state.get("category_thetas", {})
        cat_asked         = st.session_state.get("category_asked", {})
        total             = len(cat_pool) * answers_per_skill

        if not questions:
            st.warning("No questions available."); st.stop()

        answered_count = len(st.session_state.evaluations)
        cats_list      = list(cat_pool.keys())
        n_cats         = len(cats_list)

        cat_answer_counts = {}
        q_uid_to_cat = {
            q.get("question_id", str(i)): q.get("category", "Other")
            for i, q in enumerate(questions)}
        for q_uid_key in st.session_state.evaluations:
            cat_of_q = q_uid_to_cat.get(q_uid_key, "Other")
            cat_answer_counts[cat_of_q] = cat_answer_counts.get(cat_of_q, 0) + 1

        stored_q   = st.session_state.get("current_q_irt")
        stored_cat = st.session_state.get("current_cat_irt")

        if stored_q and stored_q.get("question_id") not in st.session_state.evaluations:
            q           = stored_q
            current_cat = stored_cat
        else:
            q = None
            for offset in range(n_cats):
                try_cat = cats_list[(answered_count + offset) % n_cats]
                if cat_answer_counts.get(try_cat, 0) >= answers_per_skill:
                    continue
                pool      = cat_pool.get(try_cat, [])
                theta     = cat_thetas.get(try_cat, 0.0)
                asked_ids = cat_asked.get(try_cat, set())
                selected  = irt.select_question(pool, theta, asked_ids, None)
                if selected:
                    q           = selected
                    current_cat = try_cat
                    st.session_state.current_q_irt   = q
                    st.session_state.current_cat_irt = current_cat
                    break

        if q is None:
            st.session_state.stage = "results"; st.rerun()

        st.markdown("""
        <div class="page-banner">
            <h1>Technical Interview</h1>
            <p>Answer each question thoroughly — you'll get instant AI feedback after each submission</p>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        interview_progress_bar(answered_count, total)

        dc, dc_bg, dc_border = diff_badge(q.get("difficulty","medium"))
        type_icon = {"conceptual":"💡","practical":"🔧","scenario":"🎬","project":"🗂️"}.get(q.get("type",""),"❓")
        card_bg    = "#fff7ed" if q.get("type") == "project" else "linear-gradient(135deg,#eef2ff 0%,#f5f3ff 100%)"
        card_border= "#fdba74" if q.get("type") == "project" else "#c7d2fe"

        st.markdown(f"""
        <div class="q-card" style="background:{card_bg};border-color:{card_border}">
            <div class="q-meta">
                <span class="q-num">Q{answered_count+1}</span>
                <span class="q-skill">{q.get('skill','')}</span>
                <span style="background:{dc_bg};color:{dc};border:1px solid {dc_border};
                             padding:3px 10px;border-radius:999px;font-weight:600">
                    {q.get('difficulty','').capitalize()}
                </span>
                <span style="background:#fff7ed;color:#c2410c;border:1px solid #fdba74;
                             padding:3px 10px;border-radius:999px;font-weight:600">
                    {type_icon} {q.get('type','').capitalize()}
                </span>
            </div>
            <div class="q-text">{q.get('question','')}</div>
        </div>""", unsafe_allow_html=True)

        render_confidence_badge(q)

        if q.get("hints"):
            if st.checkbox("💡 Show a hint", key=f"hint_{q.get('question_id', q_index)}"):
                hints_html = "".join(f"<li style='margin-bottom:4px'>{h}</li>" for h in q["hints"])
                st.markdown(
                    f'<div class="hint-box"><b>Hints:</b>'
                    f'<ul style="margin:6px 0 0;padding-left:1.3rem">{hints_html}</ul></div>',
                    unsafe_allow_html=True)

        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
        q_uid       = q.get("question_id", str(q_index))
        prev_answer = st.session_state.answers.get(q_uid, "")
        answer      = st.text_area("Your Answer", value=prev_answer, height=180,
                                   placeholder="Write your answer here — be as detailed as possible…",
                                   key=f"ans_{q_uid}")

        col_prev, col_submit, col_next = st.columns([1, 2, 1])
        with col_prev:
            if answered_count > 0:
                if st.button("← Previous", use_container_width=True):
                    st.session_state.q_index -= 1; st.rerun()
        with col_submit:
            already_done = q_uid in st.session_state.evaluations
            lbl = "Re-evaluate ↺" if already_done else "Submit & Evaluate →"
            if st.button(lbl, type="primary", use_container_width=True):
                if not answer.strip():
                    st.warning("Please write an answer first.")
                else:
                    st.session_state.answers[q_uid] = answer
                    with st.spinner("AI is evaluating your answer…"):
                        result = answer_eval.evaluate_answer(
                            question=q["question"], user_answer=answer,
                            model_answer=q.get("model_answer",""), skill=q.get("skill",""))
                    st.session_state.evaluations[q_uid] = result

                    try:
                        oe_session_id = st.session_state.get("oe_session_id")
                        oe_question_map = st.session_state.get("oe_question_map", {})
                        if oe_session_id and q.get("question_id"):
                            session_question_id = oe_question_map.get(q["question_id"])
                            if session_question_id:
                                confidence = int(result.get("likert", 0))
                                feedback = result.get("detailed_feedback", "")
                                oe_db.save_oe_response(
                                    session_id=oe_session_id,
                                    session_question_id=session_question_id,
                                    skill=q.get("skill", ""),
                                    answer_text=answer,
                                    confidence=confidence,
                                    score=float(result.get("total_score", 0.0)),
                                    feedback=feedback,
                                    evaluator_model="groq"
                                )
                    except Exception as e:
                        print(f"[OE DB] save response failed: {e}")

                    cat        = current_cat or q.get("category", "Other")
                    b_param    = float(q.get("b_param", 0.0))
                    score      = result.get("total_score", 0)
                    frac_correct = score / 100.0

                    if cat in st.session_state.get("category_thetas", {}):
                        theta_before = st.session_state.category_thetas[cat]
                        p_pred       = irt.p_correct(theta_before, b_param)
                        surprise     = frac_correct - p_pred
                        theta_after  = float(max(irt.THETA_MIN, min(irt.THETA_MAX,
                                            theta_before + irt.ALPHA * surprise)))
                        st.session_state.category_thetas[cat] = theta_after
                        st.session_state.category_responses[cat].append({
                            "theta_before": theta_before, "b_used": b_param,
                            "frac_correct": frac_correct, "surprise": surprise,
                            "theta_after":  theta_after})
                        st.session_state.category_asked[cat].add(q_uid)
                        result["irt"] = {
                            "theta_before":  round(theta_before, 3),
                            "theta_after":   round(theta_after, 3),
                            "b_param":       b_param,
                            "p_correct_irt": round(p_pred, 3),
                            "surprise":      round(surprise, 3),
                            "proficiency":   irt.theta_to_proficiency(theta_after),
                            "se":            irt.se_theta(st.session_state.category_responses[cat]),
                        }
                        st.session_state.evaluations[q_uid] = result

        with col_next:
            if st.button("Next Question →", use_container_width=True,
                         type="primary" if q_uid in st.session_state.evaluations else "secondary"):
                st.session_state.current_q_irt   = None
                st.session_state.current_cat_irt = None
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        if q_uid in st.session_state.evaluations:
            ev     = st.session_state.evaluations[q_uid]
            likert = ev.get("likert", 0)
            emoji  = ev.get("likert_emoji", "")
            label  = ev.get("likert_label", "")
            color  = ev.get("likert_color", "#64748b")
            score  = ev.get("total_score", 0)

            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-label">Your Feedback</div>', unsafe_allow_html=True)

            st.markdown(f'''
            <div style="display:flex;align-items:center;gap:20px;
                        background:#f8fafc;border-radius:12px;padding:1rem 1.4rem;
                        border:2px solid {color};margin-bottom:1rem">
                <div style="font-size:2.5rem">{emoji}</div>
                <div>
                    <div style="font-size:0.75rem;color:#64748b;font-weight:600;
                                letter-spacing:0.08em;text-transform:uppercase">AI Rating</div>
                    <div style="font-size:1.4rem;font-weight:800;color:{color}">
                        {likert}/5 — {label}</div>
                    <div style="font-size:0.82rem;color:#64748b;margin-top:2px">Score: {score}/100</div>
                </div>
                <div style="margin-left:auto;display:flex;gap:6px">
                    {" ".join([f'<span style="font-size:1.4rem;opacity:{1.0 if i <= likert else 0.2}">⭐</span>' for i in range(1, 6)])}
                </div>
            </div>''', unsafe_allow_html=True)

            st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
            col_s, col_i = st.columns(2)
            with col_s:
                st.markdown('<div class="section-label">💪 Strengths</div>', unsafe_allow_html=True)
                for s in ev.get("strengths", []):
                    st.markdown(f'<div class="fb-strength"><span>✓</span> {s}</div>', unsafe_allow_html=True)
            with col_i:
                st.markdown('<div class="section-label">📈 To Improve</div>', unsafe_allow_html=True)
                for imp in ev.get("improvements", []):
                    st.markdown(f'<div class="fb-improve"><span>→</span> {imp}</div>', unsafe_allow_html=True)

            with st.expander("📝 Read detailed feedback"):
                st.write(ev.get("detailed_feedback", ""))
                if ev.get("correct_answer_summary"):
                    st.markdown(f"""
                    <div style="background:#eef2ff;border:1.5px solid #c7d2fe;
                                border-radius:10px;padding:12px 16px;margin-top:10px">
                        <b style="color:#4338ca">Ideal Answer:</b>
                        <span style="color:#1e1b4b"> {ev['correct_answer_summary']}</span>
                    </div>""", unsafe_allow_html=True)

            irt_data = ev.get("irt")
            if irt_data:
                tb    = irt_data["theta_before"]
                ta    = irt_data["theta_after"]
                dth   = ta - tb
                prof  = irt_data["proficiency"]
                se    = irt_data["se"]
                arrow = "↑" if dth >= 0 else "↓"
                color = prof["color"]
                st.markdown(f"""
                <div style="background:#f8fafc;border-radius:10px;
                            padding:0.8rem 1.2rem;border-left:3px solid {color};
                            margin-top:0.5rem;font-size:0.85rem">
                    <b style="color:{color}">🧠 Ability Update (IRT)</b><br>
                    θ: <code>{tb:+.3f}</code> → <code>{ta:+.3f}</code>
                    <span style="color:{color};font-weight:700">{arrow} {abs(dth):.3f}</span>
                    &nbsp;·&nbsp;
                    <span style="background:{color};color:white;border-radius:4px;
                                 padding:1px 8px;font-size:0.78rem">{prof['label']}</span>
                    &nbsp;·&nbsp; SE(θ) = {se:.3f}
                    &nbsp;·&nbsp; b = {irt_data['b_param']:+.2f}
                    &nbsp;·&nbsp; P(correct) = {irt_data['p_correct_irt']:.1%}
                </div>""", unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

        n_answered = len(st.session_state.evaluations)
        if n_answered > 0:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown(f"""
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px">
                <div>
                    <div style="font-weight:700;color:#1e1b4b">Ready to see your results?</div>
                    <div style="font-size:0.82rem;color:#6b7280">{n_answered} of {total} questions answered</div>
                </div>
            </div>""", unsafe_allow_html=True)
            if st.button(f"View Full Results ({n_answered}/{total}) →", type="primary", use_container_width=True):
                st.session_state.stage = "results"; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # ── STAGE 4: RESULTS ──────────────────────────────────────────────────────
    elif st.session_state.stage == "results":
        questions   = st.session_state.questions
        evaluations = st.session_state.evaluations

        if not evaluations:
            st.info("No answers evaluated yet."); st.stop()

        ev_list   = list(evaluations.values())
        q_uid_to_q = {q.get("question_id", str(i)): q for i, q in enumerate(questions)}
        q_list    = [q_uid_to_q.get(uid, {}) for uid in evaluations.keys()]
        summary   = answer_eval.compute_session_summary(ev_list, q_list)

        if not st.session_state.get("oe_completed") and st.session_state.get("oe_session_id"):
            try:
                oe_session_id = st.session_state.oe_session_id
                total = len(st.session_state.questions)
                answered = len(evaluations)
                avg = summary["average_score"]
                grade = summary["overall_grade"]
                oe_db.update_oe_session_stats(
                    session_id=oe_session_id,
                    total_questions=total,
                    total_answered=answered,
                    total_score=avg,
                )
                oe_db.complete_oe_session(oe_session_id, avg, grade)

                if not st.session_state.get("oe_final_session_id"):
                    final_session_id = final_db.create_final_session(
                        student_name=st.session_state.student_name,
                        student_email=st.session_state.student_email,
                        mode="open_ended",
                        oe_session_id=oe_session_id,
                    )
                    if final_session_id:
                        final_db.complete_final_session(
                            final_session_id=final_session_id,
                            total_questions=total,
                            total_answered=answered,
                            final_score=avg,
                            overall_label=grade,
                        )
                        st.session_state.oe_final_session_id = final_session_id

                st.session_state.oe_completed = True
            except Exception as e:
                print(f"[OE DB] complete open-ended session failed: {e}")

        avg   = summary["average_score"]
        grade = summary["overall_grade"]
        gc, gbg, gborder = grade_colors(grade)

        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#1e1b4b 0%,#3730a3 100%);
                    border-radius:16px;padding:2rem 2.4rem;margin-bottom:1.5rem">
            <div style="font-size:0.7rem;letter-spacing:0.12em;text-transform:uppercase;
                        color:#a5b4fc;margin-bottom:0.4rem">Session Complete</div>
            <div style="font-size:1.7rem;font-weight:800;letter-spacing:-0.02em;
                        margin-bottom:0.6rem;color:white">Your Interview Results</div>
            <div style="display:inline-flex;align-items:center;gap:10px;
                        background:rgba(255,255,255,0.1);border-radius:999px;padding:6px 18px">
                <span style="font-size:1.6rem;font-weight:800;color:white">{avg:.0f}</span>
                <span style="font-size:0.8rem;color:#c7d2fe">/ 100 average score</span>
                <span style="background:{gbg};color:{gc};padding:3px 12px;border-radius:999px;
                             font-size:0.75rem;font-weight:700">{grade}</span>
            </div>
        </div>""", unsafe_allow_html=True)

        ACCENTS = ["#4f46e5","#7c3aed","#16a34a","#d97706"]
        metrics = [
            (f"{avg:.0f}/100","Average Score"),
            (grade,"Overall Grade"),
            (str(summary["total_questions"]),"Answered"),
            (f"{summary['highest_score']}/100","Best Score"),
        ]
        cols = st.columns(4)
        for col, (val, label), color in zip(cols, metrics, ACCENTS):
            with col:
                st.markdown(f"""
                <div class="metric-card" style="border-top-color:{color}">
                    <div class="metric-val" style="color:{color}">{val}</div>
                    <div class="metric-label">{label}</div>
                </div>""", unsafe_allow_html=True)

        st.write("")
        cat_thetas    = st.session_state.get("category_thetas", {})
        cat_responses = st.session_state.get("category_responses", {})
        if cat_thetas:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-label">🧠 Skill Proficiency (IRT)</div>', unsafe_allow_html=True)
            overall_theta = irt.compute_overall_theta(cat_thetas)
            overall_prof  = irt.theta_to_proficiency(overall_theta)
            oc            = overall_prof["color"]
            st.markdown(f"""
            <div style="background:#f0f4ff;border-radius:10px;
                        padding:0.8rem 1.2rem;margin-bottom:1rem;border-left:4px solid {oc}">
                <b>Overall θ = {overall_theta:+.3f}</b> →
                <span style="background:{oc};color:white;border-radius:4px;
                             padding:2px 10px;font-size:0.82rem;font-weight:700">
                    {overall_prof['label']}
                </span>
                &nbsp;·&nbsp;
                <span style="font-size:0.82rem;color:#64748b">{overall_prof['score']:.1f}% proficiency</span>
            </div>""", unsafe_allow_html=True)

            prof_cols = st.columns(min(len(cat_thetas), 4))
            for col, (cat, theta) in zip(prof_cols, cat_thetas.items()):
                prof      = irt.theta_to_proficiency(theta)
                responses = cat_responses.get(cat, [])
                se        = irt.se_theta(responses)
                n_ans     = len(responses)
                color     = prof["color"]
                with col:
                    st.markdown(f"""
                    <div style="background:white;border-radius:12px;padding:1rem;
                                border-top:3px solid {color};text-align:center;
                                box-shadow:0 1px 6px rgba(0,0,0,0.06)">
                        <div style="font-size:0.82rem;font-weight:700;color:#1e1b4b;margin-bottom:6px">
                            {cat.split()[0]}</div>
                        <div style="font-size:1.4rem;font-weight:800;color:{color}">{prof['score']:.0f}%</div>
                        <div style="background:{color};color:white;border-radius:4px;
                                    padding:2px 8px;font-size:0.72rem;font-weight:700;
                                    display:inline-block;margin:4px 0">{prof['label']}</div>
                        <div style="font-size:0.72rem;color:#94a3b8;margin-top:4px">
                            θ = {theta:+.3f} · SE = {se:.2f}</div>
                        <div style="font-size:0.72rem;color:#94a3b8">{n_ans} question(s)</div>
                    </div>""", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        if summary.get("category_averages"):
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-label">Score by Category</div>', unsafe_allow_html=True)
            for cat, avg_cat in summary["category_averages"].items():
                pct = int(avg_cat)
                c_color = "#16a34a" if pct >= 70 else ("#d97706" if pct >= 50 else "#dc2626")
                st.markdown(f"""
                <div class="cat-row">
                    <div class="cat-row-label">
                        <span>{cat}</span>
                        <span style="color:{c_color};font-weight:700">{avg_cat:.0f}/100</span>
                    </div>
                    <div class="cat-track">
                        <div class="cat-fill" style="width:{pct}%;background:{c_color}"></div>
                    </div>
                </div>""", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        col_s, col_i = st.columns(2)
        with col_s:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-label">💪 Top Strengths</div>', unsafe_allow_html=True)
            for s in summary.get("top_strengths", [])[:4]:
                st.markdown(f'<div class="fb-strength"><span>✓</span> {s}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with col_i:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-label">📈 Areas to Improve</div>', unsafe_allow_html=True)
            for imp in summary.get("top_improvements", [])[:4]:
                st.markdown(f'<div class="fb-improve"><span>→</span> {imp}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Question-by-Question Review</div>', unsafe_allow_html=True)
        for idx, (ev, q) in enumerate(zip(ev_list, q_list)):
            type_icon  = {"conceptual":"💡","practical":"🔧","scenario":"🎬","project":"🗂️"}.get(q.get("type",""),"❓")
            confidence = q.get("confidence", "high")
            conf_icon  = {"high":"✅","medium":"⚠️","low":"🔴"}.get(confidence, "✅")
            q_uid_r    = q.get("question_id", str(idx))
            with st.expander(
                f"{type_icon} Q{idx+1}  ·  {q.get('skill','')}  ·  "
                f"{ev['total_score']}/100  ·  {ev.get('grade','')}  ·  "
                f"{conf_icon} {confidence.capitalize()} confidence"):
                st.markdown(f"**Question:** {q.get('question','')}")
                st.markdown(f"**Your Answer:** {st.session_state.answers.get(q_uid_r,'—')}")
                st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
                lk     = ev.get("likert", 0)
                lcolor = ev.get("likert_color", "#64748b")
                lemoji = ev.get("likert_emoji", "")
                llabel = ev.get("likert_label", "")
                lscore = ev.get("total_score", 0)
                stars  = " ".join([
                    f'<span style="opacity:{1.0 if i<=lk else 0.2}">⭐</span>'
                    for i in range(1, 6)])
                st.markdown(f'''
                <div style="display:flex;align-items:center;gap:12px;
                            background:#f8fafc;border-radius:10px;
                            padding:0.8rem 1rem;border:1.5px solid {lcolor}">
                    <div style="font-size:1.8rem">{lemoji}</div>
                    <div>
                        <div style="font-weight:700;color:{lcolor}">{lk}/5 — {llabel}</div>
                        <div style="font-size:0.78rem;color:#64748b">Score: {lscore}/100</div>
                    </div>
                    <div style="margin-left:auto">{stars}</div>
                </div>''', unsafe_allow_html=True)
                col_a2, col_b2 = st.columns(2)
                with col_a2:
                    for s in ev.get("strengths", []):
                        st.markdown(f'<div class="fb-strength"><span>✓</span> {s}</div>', unsafe_allow_html=True)
                with col_b2:
                    for imp in ev.get("improvements", []):
                        st.markdown(f'<div class="fb-improve"><span>→</span> {imp}</div>', unsafe_allow_html=True)
                if ev.get("correct_answer_summary"):
                    st.markdown(f"""
                    <div style="background:#eef2ff;border:1.5px solid #c7d2fe;border-radius:10px;
                                padding:11px 15px;margin-top:10px;font-size:0.87rem">
                        <b style="color:#4338ca">Ideal Answer:</b>
                        <span style="color:#1e1b4b"> {ev['correct_answer_summary']}</span>
                    </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.write("")
        if st.button("↺  Start a New Interview", type="primary", use_container_width=True):
            for k, v in _interview_defaults.items():
                st.session_state[k] = v
            st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
#  MCQ MODE
# ═════════════════════════════════════════════════════════════════════════════

elif mode == "mcq":

    mcq_stage = st.session_state.mcq_stage

    # ── MCQ HOME ──────────────────────────────────────────────────────────────
    if mcq_stage == "home":
        st.markdown("""
        <div class="page-banner-mcq">
            <h1>🎯 Adaptive MCQ Assessment</h1>
            <p>Questions adapt to your ability · Rasch IRT scoring · Skill-wise leaderboard</p>
        </div>""", unsafe_allow_html=True)

        skills_available = db.get_skills()
        if not skills_available:
            st.warning("⚠️ No questions loaded. Check that mcq_data.json is present and DB is connected.")
            st.stop()

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Register to Start</div>', unsafe_allow_html=True)
        if not st.session_state.student_name or not st.session_state.student_email:
            st.info("Please save your profile in the sidebar first.")
            name = st.text_input("Full Name *", value=st.session_state.student_name, placeholder="e.g. Priya S")
            email = st.text_input("Email *", value=st.session_state.student_email, placeholder="e.g. priya@email.com")
        else:
            name = st.session_state.student_name
            email = st.session_state.student_email
            st.markdown(f"<div style='margin-bottom:0.75rem'><strong>{html_module.escape(name)}</strong><br><span style='color:#64748b'>{html_module.escape(email)}</span></div>", unsafe_allow_html=True)

        max_qs = min(15, min(len(db.get_questions_for_skill(sk)) for sk in skills_available))
        if max_qs > 7:
            st.markdown("**Number of questions per skill:**")
            q_per_skill = st.slider(
                "Questions per skill", min_value=7, max_value=max_qs, value=7, step=1,
                help="Fewer = faster but less accurate θ estimate.")
        else:
            q_per_skill = max_qs

        total_qs = len(skills_available) * q_per_skill
        col1, col2, col3 = st.columns(3)
        col1.metric("📚 Skills", len(skills_available))
        col2.metric("❓ Per skill", q_per_skill)
        col3.metric("📋 Total", total_qs)

        st.markdown("**Skills you will be assessed on:**")
        cols = st.columns(len(skills_available))
        for col, sk in zip(cols, skills_available):
            col.markdown(f'<div style="background:#eef2ff;border-radius:8px;padding:8px 12px;'
                         f'text-align:center;font-weight:700;color:#4f46e5;font-size:0.85rem">'
                         f'{sk}</div>', unsafe_allow_html=True)

        with st.expander("📖 How it works"):
            st.markdown(f"""
- Answer **{q_per_skill} questions per skill** ({len(skills_available)} skills · {total_qs} total)
- Questions **adapt to your ability** — get one right and the next is harder
- Scored using **Rasch IRT** — harder correct answers count more
- Ranked against all other students skill-by-skill
            """)

        email_ok = bool(email.strip() and "@" in email and "." in email.split("@")[-1])
        agreed   = st.checkbox("I understand the assessment rules")
        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("🚀 Start Assessment", type="primary", use_container_width=True,
                     disabled=not (name.strip() and email_ok and agreed)):
            pools = {sk: db.get_questions_for_skill(sk) for sk in skills_available}
            empty = [sk for sk, qs in pools.items() if not qs]
            if empty:
                st.error(f"No questions found for: {', '.join(empty)}"); st.stop()

            sid = db.create_session(name.strip(), email.strip(), skills_available)
            if not sid:
                st.error("Failed to create session. Check DB connection."); st.stop()

            st.session_state.student_name        = name.strip()
            st.session_state.student_email       = email.strip()
            st.session_state.session_id          = sid
            st.session_state.skills              = skills_available
            st.session_state.skill_pools         = pools
            st.session_state.skill_index         = 0
            st.session_state.skill_thetas        = {sk: irt.THETA_INIT for sk in skills_available}
            st.session_state.skill_responses     = {sk: [] for sk in skills_available}
            st.session_state.skill_asked         = {sk: set() for sk in skills_available}
            st.session_state.skill_last_correct  = {sk: None for sk in skills_available}
            st.session_state.skill_profiles      = {}
            st.session_state.q_count             = 0
            st.session_state.current_q           = None
            st.session_state.questions_per_skill = q_per_skill
            st.session_state.mcq_stage           = "quiz"
            st.rerun()

    # ── MCQ QUIZ ──────────────────────────────────────────────────────────────
    elif mcq_stage == "quiz":
        skills    = st.session_state.skills
        skill_idx = st.session_state.skill_index

        if skill_idx >= len(skills):
            st.session_state.mcq_stage = "results"; st.rerun()

        current_skill = skills[skill_idx]
        pool    = st.session_state.skill_pools[current_skill]
        q_count = st.session_state.q_count

        sess_key = f"skill_session_{current_skill}"
        if sess_key not in st.session_state:
            st.session_state[sess_key] = irt.SkillSession(
                current_skill, st.session_state.get("questions_per_skill", QUESTIONS_PER_SKILL))
        skill_sess = st.session_state[sess_key]

        theta = skill_sess.theta
        prof  = skill_sess.proficiency

        tabs_html = ""
        for i, sk in enumerate(skills):
            if i < skill_idx:
                tabs_html += f'<span class="skill-tab-done">✓ {sk}</span> '
            elif i == skill_idx:
                tabs_html += f'<span class="skill-tab-active">▶ {sk}</span> '
            else:
                tabs_html += f'<span class="skill-tab-pending">{sk}</span> '
        st.markdown(f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:1rem">'
                    f'{tabs_html}</div>', unsafe_allow_html=True)

        qps = st.session_state.get("questions_per_skill", QUESTIONS_PER_SKILL)
        pct = int((q_count / qps) * 100)
        st.markdown(
            f"**{current_skill}** · Q {q_count+1}/{qps} · "
            f"θ = {theta:+.3f} · {prof['label']}")
        st.markdown(
            f'<div class="prog-wrap"><div class="prog-fill" style="width:{pct}%"></div></div>',
            unsafe_allow_html=True)

        if skill_sess.done:
            summary = skill_sess.summary()
            db.save_skill_profile(
                session_id=st.session_state.session_id,
                student_name=st.session_state.student_name,
                student_email=st.session_state.student_email,
                skill=current_skill,
                theta_final=summary["theta_final"],
                proficiency_score=summary["proficiency_score"],
                proficiency_label=summary["proficiency_label"],
                questions_answered=summary["questions_answered"],
                questions_correct=summary["questions_correct"],
            )
            st.session_state.skill_profiles[current_skill] = {
                "theta":       summary["theta_final"],
                "proficiency": irt.theta_to_proficiency(summary["theta_final"]),
                "answered":    summary["questions_answered"],
                "correct":     summary["questions_correct"],
                "se":          summary["theta_se"],
            }
            st.session_state.skill_thetas[current_skill] = summary["theta_final"]
            st.session_state.skill_index += 1
            st.session_state.q_count      = 0
            st.session_state.current_q    = None

            if st.session_state.skill_index >= len(skills):
                skill_thetas  = st.session_state.skill_thetas
                overall_theta = irt.compute_overall_theta(skill_thetas)
                overall_prof  = irt.theta_to_proficiency(overall_theta)
                total_ans = sum(p["answered"] for p in st.session_state.skill_profiles.values())
                total_cor = sum(p["correct"]  for p in st.session_state.skill_profiles.values())
                db.complete_session(
                    session_id=st.session_state.session_id,
                    theta_overall=overall_theta,
                    proficiency_label=overall_prof["label"],
                    proficiency_score=overall_prof["score"],
                    total_answered=total_ans,
                    total_correct=total_cor,
                )
                st.session_state.mcq_stage = "results"
            st.rerun()

        if st.session_state.current_q is None:
            q = skill_sess.next_question(pool)
            if q is None:
                skill_sess.quiz_length = len(skill_sess.responses); st.rerun()
            st.session_state.current_q = q

        q = st.session_state.current_q
        if q is None:
            st.rerun()

        diff_colors = {"easy": "#16a34a", "medium": "#d97706", "hard": "#dc2626"}
        diff        = q.get("difficulty_tier", "medium")
        diff_color  = diff_colors.get(diff, "#6366f1")

        st.markdown(f"""
        <div style="background:white;border-radius:14px;padding:1.6rem 2rem;
                    border-left:4px solid #4f46e5;margin-bottom:1rem;
                    box-shadow:0 2px 12px rgba(79,70,229,0.08)">
            <div style="font-size:0.72rem;font-weight:600;color:#6366f1;
                        letter-spacing:0.1em;text-transform:uppercase;margin-bottom:0.5rem">
                Question {q_count+1} of {qps} &nbsp;·&nbsp;
                <span style="color:{diff_color}">{diff.upper()}</span>
                &nbsp;·&nbsp; b = {q['b_param']:+.2f}
                &nbsp;·&nbsp; θ = {theta:+.3f}
            </div>
            <div style="font-size:1.05rem;font-weight:600;color:#1e1b4b;line-height:1.6">
                {html_module.escape(q['question_text'])}
            </div>
        </div>""", unsafe_allow_html=True)

        option_map = {
            "a": q["option_a"], "b": q["option_b"],
            "c": q["option_c"], "d": q["option_d"],
        }
        choice = st.radio(
            "Select your answer:",
            options=list(option_map.keys()),
            format_func=lambda k: f"{k.upper()}.  {option_map[k]}",
            index=None,
            key=f"radio_{q['question_id']}",
            label_visibility="collapsed",
        )

        if st.button("Submit Answer →", type="primary",
                     use_container_width=True, disabled=choice is None):
            rec = skill_sess.record_answer(q, choice)
            db_err = db.save_response(
                session_id=st.session_state.session_id,
                question_id=rec["question_id"],
                skill=current_skill,
                selected_option=rec["selected_option"],
                is_correct=rec["is_correct"],
                b_used=rec["b_used"],
                theta_before=rec["theta_before"],
                theta_after=rec["theta_after"],
                p_correct_irt=rec["p_correct_irt"],
                surprise=rec["surprise"],
                proficiency_before=rec["proficiency_before"],
                proficiency_after=rec["proficiency_after"],
            )
            if db_err:
                st.warning(f"⚠️ DB save error: {db_err}")
            db.update_question_b(rec["question_id"], rec["b_final"],
                                 rec["is_correct"], rec["b_source"])

            st.session_state.skill_thetas[current_skill] = skill_sess.theta
            st.session_state.q_count  += 1
            st.session_state.current_q = None

            dtheta = rec["theta_after"] - rec["theta_before"]
            if rec["is_correct"]:
                st.success("✅ Correct!")
            else:
                co       = rec["correct_option"]
                opt_text = q.get(f"option_{co}", co.upper())
                st.error(f"❌ Wrong. Correct answer: **{co.upper()}. {opt_text}**")

            col_s1, col_s2, col_s3 = st.columns(3)
            col_s1.metric("P(correct) predicted", f"{rec['p_correct_irt']:.1%}")
            col_s2.metric("Surprise (y−P)",        f"{rec['surprise']:+.3f}")
            col_s3.metric("θ change",
                          f"{rec['theta_after']:+.3f}", f"{dtheta:+.3f}")
            if rec.get("explanation"):
                st.markdown(
                    f'<div class="expl-box">💡 {html_module.escape(rec["explanation"])}</div>',
                    unsafe_allow_html=True)
            st.button("Next Question →", on_click=st.rerun)

    # ── MCQ RESULTS ───────────────────────────────────────────────────────────
    elif mcq_stage == "results":
        profiles = st.session_state.skill_profiles
        if not profiles:
            db_profiles = db.get_session_skill_profiles(st.session_state.session_id)
            profiles    = {p["skill"]: {
                "theta":       p["theta_final"],
                "proficiency": irt.theta_to_proficiency(p["theta_final"]),
                "answered":    p["questions_answered"],
                "correct":     p["questions_correct"],
            } for p in db_profiles}

        skill_thetas  = {sk: p["theta"] for sk, p in profiles.items()}
        overall_theta = irt.compute_overall_theta(skill_thetas)
        overall_prof  = irt.theta_to_proficiency(overall_theta)
        oc, obg       = PROF_COLORS.get(overall_prof["label"], ("#4f46e5","#eef2ff"))

        st.markdown(f"""
        <div class="page-banner-mcq">
            <div style="font-size:0.75rem;letter-spacing:0.12em;opacity:0.7;margin-bottom:0.4rem">
                ASSESSMENT COMPLETE
            </div>
            <h1>{st.session_state.student_name}</h1>
            <div style="display:inline-flex;align-items:center;gap:12px;
                        background:rgba(255,255,255,0.12);border-radius:999px;
                        padding:8px 20px;margin-top:0.6rem">
                <span style="font-size:2rem;font-weight:800">θ = {overall_theta:+.3f}</span>
                <span style="background:{obg};color:{oc};border-radius:999px;
                             padding:4px 16px;font-weight:700;font-size:0.9rem">
                    {overall_prof['label']}
                </span>
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div class="section-label">Per-Skill Proficiency</div>', unsafe_allow_html=True)
        cols = st.columns(len(profiles))
        for col, (skill, p) in zip(cols, profiles.items()):
            prof      = p["proficiency"]
            color, bg = PROF_COLORS.get(prof["label"], ("#4f46e5","#eef2ff"))
            acc       = round(p["correct"] / p["answered"] * 100) if p["answered"] else 0
            with col:
                st.markdown(f"""
                <div class="metric-card" style="border-top-color:{color}">
                    <div style="font-weight:800;font-size:0.95rem;color:#1e1b4b;margin-bottom:6px">{skill}</div>
                    <div class="metric-val" style="color:{color}">{prof['score']:.1f}%</div>
                    <div style="margin:6px 0">
                        <span class="prof-pill" style="background:{bg};color:{color}">{prof['label']}</span>
                    </div>
                    <div class="theta-display">θ = {p['theta']:+.3f}</div>
                    <div style="font-size:0.75rem;color:#94a3b8;margin-top:4px">
                        {p['correct']}/{p['answered']} correct ({acc}%)</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🏆 View Leaderboard", type="primary", use_container_width=True):
                st.session_state.mcq_stage = "leaderboard"; st.rerun()
        with col_b:
            if st.button("↺ Start New Session", use_container_width=True):
                reset_mcq_session(); st.rerun()

    # ── MCQ LEADERBOARD ───────────────────────────────────────────────────────
    elif mcq_stage == "leaderboard":
        st.markdown("""
        <div class="page-banner-mcq">
            <h1>🏆 Leaderboard</h1>
            <p>Ranked by Rasch θ · Accounts for question difficulty · Fair cross-student comparison</p>
        </div>""", unsafe_allow_html=True)

        col_ref, col_btn = st.columns([5, 1])
        with col_btn:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()

        current_sid  = st.session_state.session_id
        overall_lb   = db.get_overall_leaderboard()
        skill_lb_all = db.get_all_skills_leaderboard()
        skills       = db.get_skills()

        if not overall_lb:
            st.info("No completed sessions yet. Be the first to take the assessment!")
            st.stop()

        thetas = [float(r["theta_overall"]) for r in overall_lb]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("👥 Students",  len(overall_lb))
        c2.metric("📊 Avg θ",    f"{sum(thetas)/len(thetas):+.3f}")
        c3.metric("🥇 Best θ",   f"{max(thetas):+.3f}")
        c4.metric("📉 Lowest θ", f"{min(thetas):+.3f}")

        st.markdown("---")
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Overall Ranking</div>', unsafe_allow_html=True)
        render_lb_rows(overall_lb, current_sid)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-label">Skill-wise Ranking</div>', unsafe_allow_html=True)
        skill_tabs = st.tabs(skills)
        for tab, skill in zip(skill_tabs, skills):
            with tab:
                rows = skill_lb_all.get(skill, [])
                if not rows:
                    st.info(f"No submissions for {skill} yet.")
                else:
                    my_row = next(
                        (r for r in rows if str(r.get("session_id","")) == str(current_sid or "")),
                        None)
                    if my_row:
                        mcolor, mbg = PROF_COLORS.get(my_row["proficiency_label"], ("#4f46e5","#eef2ff"))
                        st.markdown(
                            f'<div style="background:{mbg};border-radius:10px;'
                            f'padding:10px 16px;margin-bottom:12px;color:{mcolor};font-weight:700">'
                            f'Your rank in {skill}: #{my_row["skill_rank"]} · '
                            f'θ = {my_row["theta_final"]:+.3f} · {my_row["proficiency_label"]}'
                            f'</div>', unsafe_allow_html=True)
                    render_lb_rows(rows)

