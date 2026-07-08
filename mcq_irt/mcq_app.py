"""
mcq_app.py
Adaptive MCQ system using 1-PL Rasch IRT.

FLOW:
  Student registers → answers 15 adaptive questions per skill (5 skills)
  → θ updates after every answer (b ≈ θ selection)
  → Results: proficiency per skill
  → Leaderboard: overall θ rank + per-skill breakdown

STAGES:
  home      → register
  quiz      → adaptive MCQ (skill by skill)
  results   → per-skill proficiency + overall θ
  leaderboard → overall rank + per-skill tabs
  admin     → load dataset + view DB status
"""

import os
import math
import html as html_module
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

import rasch_engine as irt
import mcq_database as db

QUESTIONS_PER_SKILL = 15
MCQ_DATA_PATH       = "mcq_data.json"


def auto_setup():
    """
    Runs once on startup — initialises DB schema and loads questions
    from mcq_data.json if not already loaded.
    No admin panel needed.
    """
    db.init_db()
    skills = db.get_skills()
    if not skills:
        n, err = db.load_questions_from_json(MCQ_DATA_PATH)
        if err:
            print(f"[Setup] Failed to load questions: {err}")
        else:
            print(f"[Setup] Loaded {n} questions from {MCQ_DATA_PATH}")
    else:
        print(f"[Setup] Questions already loaded: {skills}")

auto_setup()

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG + CSS
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Adaptive MCQ — IRT",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
.stApp { background: #f0f4ff; }

section[data-testid="stSidebar"] { background: #1e1b4b !important; }
section[data-testid="stSidebar"] * { color: #c7d2fe !important; }
section[data-testid="stSidebar"] .stButton button {
    background: #4f46e5 !important; color: white !important;
    border: none !important; border-radius: 8px !important; }

.card {
    background: white; border-radius: 16px; padding: 1.6rem 2rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(79,70,229,0.07); }

.page-banner {
    background: linear-gradient(135deg, #1e1b4b 0%, #4f46e5 60%, #7c3aed 100%);
    border-radius: 16px; padding: 2rem 2.4rem; margin-bottom: 1.5rem; color: white; }
.page-banner h1 { margin: 0 0 0.3rem; font-size: 1.7rem; font-weight: 800;
    letter-spacing: -0.02em; color: white; }
.page-banner p  { margin: 0; font-size: 0.92rem; opacity: 0.85; color: white; }

.q-card {
    background: white; border-radius: 14px; padding: 1.6rem 2rem;
    border-left: 4px solid #4f46e5; margin-bottom: 1rem;
    box-shadow: 0 2px 12px rgba(79,70,229,0.08); }
.q-meta { font-size: 0.72rem; font-weight: 600; color: #6366f1;
    letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 0.5rem; }
.q-text { font-size: 1.05rem; font-weight: 600; color: #1e1b4b; line-height: 1.6; }

.prog-wrap { background: #e0e7ff; border-radius: 99px; height: 6px;
    overflow: hidden; margin: 0.4rem 0 1.2rem; }
.prog-fill  { height: 100%; border-radius: 99px;
    background: linear-gradient(90deg, #4f46e5, #7c3aed); }

.skill-tab-active   { background: #4f46e5; color: white; border-radius: 8px;
    padding: 6px 16px; font-weight: 700; font-size: 0.82rem; display:inline-block; }
.skill-tab-done     { background: #dcfce7; color: #15803d; border-radius: 8px;
    padding: 6px 16px; font-weight: 700; font-size: 0.82rem; display:inline-block; }
.skill-tab-pending  { background: #f1f5f9; color: #64748b; border-radius: 8px;
    padding: 6px 16px; font-weight: 600; font-size: 0.82rem; display:inline-block; }

.prof-pill {
    display: inline-block; border-radius: 99px;
    padding: 4px 18px; font-weight: 700; font-size: 0.82rem; }

.metric-card { background: white; border-radius: 12px; padding: 1.2rem;
    border-top: 3px solid #4f46e5; text-align: center;
    box-shadow: 0 1px 6px rgba(0,0,0,0.06); }
.metric-val   { font-size: 1.6rem; font-weight: 800; color: #1e1b4b; }
.metric-label { font-size: 0.78rem; color: #64748b; margin-top: 4px; }

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

.section-label { font-size: 0.72rem; font-weight: 700; color: #6366f1;
    letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 0.8rem; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────

DEFAULTS = {
    "stage":           "home",
    "student_name":    "",
    "student_email":   "",
    "session_id":      None,
    "skills":          [],           # list of skill names to test
    "skill_pools":     {},           # { skill: [question dicts] }
    "skill_index":     0,            # which skill we're on (0-4)
    "skill_thetas":    {},           # { skill: current θ }
    "skill_responses": {},           # { skill: [response dicts] }
    "skill_asked":     {},           # { skill: set of asked question_ids }
    "skill_last_correct": {},        # { skill: True/False/None }
    "skill_profiles":  {},           # { skill: final profile dict }
    "q_count":         0,            # questions answered in current skill
    "current_q":       None,         # current question dict
    "questions_per_skill": 15,          # user chosen
}

for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def reset_session():
    # Clear dynamic skill_session_* keys first
    dynamic_keys = [k for k in st.session_state
                    if k.startswith("skill_session_")]
    for k in dynamic_keys:
        del st.session_state[k]
    # Reset all default keys
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

PROF_COLORS = {
    "Expert":       ("#534AB7", "#ede9fe"),
    "Advanced":     ("#1D9E75", "#dcfce7"),
    "Intermediate": ("#378ADD", "#dbeafe"),
    "Beginner":     ("#d97706", "#fef3c7"),
    "Novice":       ("#dc2626", "#fee2e2"),
}
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
ROW_CLS = {1: "gold", 2: "silver", 3: "bronze"}

def prof_pill(label: str) -> str:
    color, bg = PROF_COLORS.get(label, ("#64748b", "#f1f5f9"))
    return (f'<span class="prof-pill" '
            f'style="background:{bg};color:{color}">{label}</span>')


def render_lb_rows(rows: list[dict], current_sid: str = None):
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
                    {correct}/{total} correct
                </div>
            </div>
        </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown('<p style="font-family:Plus Jakarta Sans;font-size:1.1rem;'
                'font-weight:800;margin-bottom:1rem">🎯 Adaptive MCQ</p>',
                unsafe_allow_html=True)
    st.markdown("---")
    for label, stage in [("🏠 Home","home"),("🏆 Leaderboard","leaderboard")]:
        if st.button(label, use_container_width=True):
            st.session_state.stage = stage
            st.rerun()
    st.markdown("---")
    ok, msg = db.test_connection()
    # ── FIXED: use if/else instead of ternary to avoid DeltaGenerator leak ──
    if ok:
        st.success("🟢 DB connected")
    else:
        st.error(f"🔴 DB error\n{msg[:60]}")
    st.markdown("---")
    if st.session_state.get("student_name", ""):
        st.markdown(f"**👤 {st.session_state.student_name}**")
        if st.button("🔄 Switch Student", use_container_width=True):
            reset_session()
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# HOME
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.stage == "home":
    st.markdown("""
    <div class="page-banner">
        <h1>🎯 Adaptive MCQ Assessment</h1>
        <p>Questions adapt to your ability · Rasch IRT scoring · Skill-wise leaderboard</p>
    </div>""", unsafe_allow_html=True)

    skills_available = db.get_skills()
    if not skills_available:
        st.warning("⚠️ No questions loaded yet. Go to Admin panel to load the dataset.")
        st.stop()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Register to Start</div>', unsafe_allow_html=True)
    name  = st.text_input("Full Name *", placeholder="e.g. Priya S")
    email = st.text_input("Email *",     placeholder="e.g. priya@email.com")

    max_qs = min(15, min(len(db.get_questions_for_skill(sk)) for sk in skills_available))
    if max_qs > 7:
        st.markdown("**Number of questions per skill:**")
        q_per_skill = st.slider(
            "Questions per skill", min_value=7, max_value=max_qs, value=7, step=1,
            help="Fewer questions = faster but less accurate θ estimate. 15 = most accurate."
        )
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
- You will answer **{q_per_skill} questions per skill** ({len(skills_available)} skills · {total_qs} total)
- Questions **adapt to your ability** — get one right and the next is harder
- Scoring uses **Rasch IRT** — getting harder questions right counts more
- Final score is your **θ (ability estimate)** per skill
- You are ranked against all other students skill-by-skill
        """)
    email_ok = bool(email.strip() and "@" in email and "." in email.split("@")[-1])
    agreed   = st.checkbox("I understand the assessment rules")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 Start Assessment", type="primary", use_container_width=True,
                 disabled=not (name.strip() and email_ok and agreed)):
        # Load question pools for all skills
        pools = {sk: db.get_questions_for_skill(sk) for sk in skills_available}
        empty = [sk for sk, qs in pools.items() if not qs]
        if empty:
            st.error(f"No questions found for: {', '.join(empty)}")
            st.stop()

        sid = db.create_session(name.strip(), email.strip(), skills_available)
        if not sid:
            st.error("Failed to create session. Check DB connection.")
            st.stop()

        st.session_state.student_name       = name.strip()
        st.session_state.student_email      = email.strip()
        st.session_state.session_id         = sid
        st.session_state.skills             = skills_available
        st.session_state.skill_pools        = pools
        st.session_state.skill_index        = 0
        st.session_state.skill_thetas       = {sk: irt.THETA_INIT for sk in skills_available}
        st.session_state.skill_responses    = {sk: [] for sk in skills_available}
        st.session_state.skill_asked        = {sk: set() for sk in skills_available}
        st.session_state.skill_last_correct = {sk: None for sk in skills_available}
        st.session_state.skill_profiles     = {}
        st.session_state.q_count            = 0
        st.session_state.current_q          = None
        st.session_state.questions_per_skill = q_per_skill
        st.session_state.stage              = "quiz"
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# QUIZ
# ─────────────────────────────────────────────────────────────────────────────

elif st.session_state.stage == "quiz":
    skills    = st.session_state.skills
    skill_idx = st.session_state.skill_index

    # Check if all skills done
    if skill_idx >= len(skills):
        st.session_state.stage = "results"
        st.rerun()

    current_skill = skills[skill_idx]
    pool    = st.session_state.skill_pools[current_skill]
    q_count = st.session_state.q_count

    # ── Get or create SkillSession — MUST be before any skill_sess usage ──
    sess_key = f"skill_session_{current_skill}"
    if sess_key not in st.session_state:
        st.session_state[sess_key] = irt.SkillSession(current_skill, st.session_state.get("questions_per_skill", QUESTIONS_PER_SKILL))
    skill_sess = st.session_state[sess_key]

    theta = skill_sess.theta
    prof  = skill_sess.proficiency

    # ── Skill progress tabs ───────────────────────────────────────────────
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

    # ── Progress bar ──────────────────────────────────────────────────────
    qps  = st.session_state.get("questions_per_skill", QUESTIONS_PER_SKILL)
    pct = int((q_count / qps) * 100)
    st.markdown(
        f"**{current_skill}** · Q {q_count+1}/{qps} · "
        f"θ = {theta:+.3f} · {prof['label']}"
    )
    st.markdown(
        f'<div class="prog-wrap"><div class="prog-fill" style="width:{pct}%"></div></div>',
        unsafe_allow_html=True
    )

    # ── Check if skill is complete ────────────────────────────────────────
    if skill_sess.done:
        summary = skill_sess.summary()
        db.save_skill_profile(
            session_id         = st.session_state.session_id,
            student_name       = st.session_state.student_name,
            student_email      = st.session_state.student_email,
            skill              = current_skill,
            theta_final        = summary["theta_final"],
            proficiency_score  = summary["proficiency_score"],
            proficiency_label  = summary["proficiency_label"],
            questions_answered = summary["questions_answered"],
            questions_correct  = summary["questions_correct"],
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
                session_id        = st.session_state.session_id,
                theta_overall     = overall_theta,
                proficiency_label = overall_prof["label"],
                proficiency_score = overall_prof["score"],
                total_answered    = total_ans,
                total_correct     = total_cor,
            )
            st.session_state.stage = "results"
        st.rerun()

    # ── Select next question ──────────────────────────────────────────────
    if st.session_state.current_q is None:
        q = skill_sess.next_question(pool)
        if q is None:
            skill_sess.quiz_length = len(skill_sess.responses)
            st.rerun()
        st.session_state.current_q = q

    q = st.session_state.current_q
    if q is None:
        st.rerun()

    # ── Render question ───────────────────────────────────────────────────
    diff_colors = {"easy": "#16a34a", "medium": "#d97706", "hard": "#dc2626"}
    diff        = q.get("difficulty_tier", "medium")
    diff_color  = diff_colors.get(diff, "#6366f1")

    st.markdown(f"""
    <div class="q-card">
        <div class="q-meta">
            Question {q_count+1} of {QUESTIONS_PER_SKILL} &nbsp;·&nbsp;
            <span style="color:{diff_color}">{diff.upper()}</span>
            &nbsp;·&nbsp; b = {q['b_param']:+.2f}
            &nbsp;·&nbsp; θ = {theta:+.3f}
        </div>
        <div class="q-text">{html_module.escape(q['question_text'])}</div>
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

    col_prev, col_submit = st.columns([1, 3])
    with col_submit:
        if st.button("Submit Answer →", type="primary",
                     use_container_width=True, disabled=choice is None):

            rec = skill_sess.record_answer(q, choice)

            # Save to DB
            db_err = db.save_response(
                session_id         = st.session_state.session_id,
                question_id        = rec["question_id"],
                skill              = current_skill,
                selected_option    = rec["selected_option"],
                is_correct         = rec["is_correct"],
                b_used             = rec["b_used"],
                theta_before       = rec["theta_before"],
                theta_after        = rec["theta_after"],
                p_correct_irt      = rec["p_correct_irt"],
                surprise           = rec["surprise"],
                proficiency_before = rec["proficiency_before"],
                proficiency_after  = rec["proficiency_after"],
            )
            if db_err:
                st.warning(f"⚠️ DB save error: {db_err}")
            db.update_question_b(rec["question_id"], rec["b_final"],
                                 rec["is_correct"], rec["b_source"])

            st.session_state.skill_thetas[current_skill] = skill_sess.theta
            st.session_state.q_count   += 1
            st.session_state.current_q  = None

            # Feedback
            dtheta = rec["theta_after"] - rec["theta_before"]
            db_val = rec["b_final"] - rec["b_used"]

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
                          f"{rec['theta_after']:+.3f}",
                          f"{dtheta:+.3f}")
            
            if rec.get("explanation"):
                st.markdown(
                    f'<div class="expl-box">💡 {html_module.escape(rec["explanation"])}</div>',
                    unsafe_allow_html=True
                )
            st.button("Next Question →", on_click=st.rerun)


# ─────────────────────────────────────────────────────────────────────────────
# RESULTS
# ─────────────────────────────────────────────────────────────────────────────

elif st.session_state.stage == "results":
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
    <div class="page-banner">
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

    # Per-skill cards
    st.markdown('<div class="section-label">Per-Skill Proficiency</div>', unsafe_allow_html=True)
    cols = st.columns(len(profiles))
    for col, (skill, p) in zip(cols, profiles.items()):
        prof   = p["proficiency"]
        color, bg = PROF_COLORS.get(prof["label"], ("#4f46e5","#eef2ff"))
        acc    = round(p["correct"] / p["answered"] * 100) if p["answered"] else 0
        with col:
            st.markdown(f"""
            <div class="metric-card" style="border-top-color:{color}">
                <div style="font-weight:800;font-size:0.95rem;color:#1e1b4b;margin-bottom:6px">
                    {skill}
                </div>
                <div class="metric-val" style="color:{color}">{prof['score']:.1f}%</div>
                <div style="margin:6px 0">
                    <span class="prof-pill" style="background:{bg};color:{color}">
                        {prof['label']}
                    </span>
                </div>
                <div class="theta-display">θ = {p['theta']:+.3f}</div>
                <div style="font-size:0.75rem;color:#94a3b8;margin-top:4px">
                    {p['correct']}/{p['answered']} correct ({acc}%)
                </div>
            </div>""", unsafe_allow_html=True)

    st.markdown("")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🏆 View Leaderboard", type="primary", use_container_width=True):
            st.session_state.stage = "leaderboard"
            st.rerun()
    with col_b:
        if st.button("↺ Start New Session", use_container_width=True):
            reset_session()
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# LEADERBOARD
# ─────────────────────────────────────────────────────────────────────────────

elif st.session_state.stage == "leaderboard":
    st.markdown("""
    <div class="page-banner">
        <h1>🏆 Leaderboard</h1>
        <p>Ranked by Rasch θ · Accounts for question difficulty · Fair cross-student comparison</p>
    </div>""", unsafe_allow_html=True)

    col_ref, col_btn = st.columns([5,1])
    with col_btn:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    current_sid = st.session_state.session_id

    overall_lb    = db.get_overall_leaderboard()
    skill_lb_all  = db.get_all_skills_leaderboard()
    skills        = db.get_skills()

    if not overall_lb:
        st.info("No completed sessions yet. Be the first to take the assessment!")
        st.stop()

    # ── Overall summary metrics ──────────────────────────────────────────
    thetas = [float(r["theta_overall"]) for r in overall_lb]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("👥 Students", len(overall_lb))
    c2.metric("📊 Avg θ",    f"{sum(thetas)/len(thetas):+.3f}")
    c3.metric("🥇 Best θ",   f"{max(thetas):+.3f}")
    c4.metric("📉 Lowest θ", f"{min(thetas):+.3f}")

    st.markdown("---")

    # ── Overall rank ──────────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Overall Ranking (by average θ across all skills)</div>',
                unsafe_allow_html=True)
    render_lb_rows(overall_lb, current_sid)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Per-skill breakdown ───────────────────────────────────────────────
    st.markdown('<div class="section-label">Skill-wise Ranking</div>', unsafe_allow_html=True)
    skill_tabs = st.tabs(skills)
    for tab, skill in zip(skill_tabs, skills):
        with tab:
            rows = skill_lb_all.get(skill, [])
            if not rows:
                st.info(f"No submissions for {skill} yet.")
            else:
                # Find current student's skill rank
                my_row = next(
                    (r for r in rows
                     if str(r.get("session_id","")) == str(current_sid or "")),
                    None
                )
                if my_row:
                    mcolor, mbg = PROF_COLORS.get(my_row["proficiency_label"],
                                                   ("#4f46e5","#eef2ff"))
                    st.markdown(
                        f'<div style="background:{mbg};border-radius:10px;'
                        f'padding:10px 16px;margin-bottom:12px;color:{mcolor};font-weight:700">'
                        f'Your rank in {skill}: #{my_row["skill_rank"]} · '
                        f'θ = {my_row["theta_final"]:+.3f} · {my_row["proficiency_label"]}'
                        f'</div>', unsafe_allow_html=True
                    )
                render_lb_rows(rows)