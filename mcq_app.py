"""
mcq_app.py
──────────
Streamlit MCQ application — three modes in one file:

  USER MODE   → Register → Take MCQ → See score + rank + answer review
  ADMIN MODE  → Generate MCQ set → View live leaderboard → Manage sessions
  LEADERBOARD → Public read-only leaderboard (no login needed)

Run:
  streamlit run mcq_app.py

Required env vars (or .streamlit/secrets.toml):
  GROQ_API_KEY, POSTGRES_HOST, POSTGRES_PORT,
  POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
  MCQ_ADMIN_PASSWORD   (default: "admin123" — change this!)
"""

import time
import html as html_module
import streamlit as st
from datetime import datetime, timezone

import mcq_database as db
import mcq_generator as gen

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Interview MCQ",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

ADMIN_PASSWORD = st.secrets.get("MCQ_ADMIN_PASSWORD", "admin123")

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS  — Redesigned: Dark editorial with amber accent
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700&display=swap');

:root {
  --bg:        #0a0a0f;
  --surface:   #111118;
  --surface2:  #18181f;
  --border:    #222230;
  --border2:   #2e2e40;
  --amber:     #f5a623;
  --amber-dim: rgba(245,166,35,0.12);
  --amber-glow:rgba(245,166,35,0.06);
  --blue:      #4f8ef7;
  --blue-dim:  rgba(79,142,247,0.12);
  --green:     #3ecf8e;
  --green-dim: rgba(62,207,142,0.12);
  --red:       #f06565;
  --red-dim:   rgba(240,101,101,0.10);
  --text:      #e8e8f0;
  --text-muted:#7a7a9a;
  --text-dim:  #3e3e58;
}

html, body, [class*="css"] {
  font-family: 'Manrope', sans-serif;
  background: var(--bg) !important;
  color: var(--text);
}

/* ── HEADER ── */
.mcq-header {
  position: relative;
  overflow: hidden;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 2.4rem 2.8rem 2rem;
  margin-bottom: 2rem;
}
.mcq-header::before {
  content: '';
  position: absolute;
  top: -80px; right: -80px;
  width: 320px; height: 320px;
  background: radial-gradient(circle, rgba(245,166,35,0.08) 0%, transparent 65%);
  border-radius: 50%;
  pointer-events: none;
}
.mcq-header::after {
  content: '';
  position: absolute;
  bottom: -40px; left: 10%;
  width: 200px; height: 200px;
  background: radial-gradient(circle, rgba(79,142,247,0.05) 0%, transparent 65%);
  border-radius: 50%;
  pointer-events: none;
}
.mcq-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--amber-dim);
  color: var(--amber);
  border: 1px solid rgba(245,166,35,0.25);
  border-radius: 99px;
  padding: 3px 14px;
  font-family: 'DM Mono', monospace;
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-bottom: 0.85rem;
}
.mcq-header h1 {
  font-family: 'Syne', sans-serif;
  color: var(--text);
  font-size: 2rem;
  font-weight: 800;
  margin: 0 0 0.4rem;
  letter-spacing: -0.02em;
}
.mcq-header p {
  color: var(--text-muted);
  font-size: 0.92rem;
  margin: 0;
}

/* ── CARDS ── */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 1.6rem 1.8rem;
  margin-bottom: 1.2rem;
}
.card-title {
  font-family: 'Syne', sans-serif;
  color: var(--text);
  font-size: 1rem;
  font-weight: 700;
  margin-bottom: 1rem;
  letter-spacing: -0.01em;
}

/* ── QUESTION CARD ── */
.question-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--amber);
  border-radius: 14px;
  padding: 1.6rem 1.8rem 1.2rem;
  margin-bottom: 1.4rem;
  position: relative;
}
.q-num {
  font-family: 'DM Mono', monospace;
  font-size: 0.68rem;
  font-weight: 500;
  color: var(--amber);
  letter-spacing: 0.15em;
  text-transform: uppercase;
  margin-bottom: 0.6rem;
}
.q-text {
  color: var(--text);
  font-size: 1.02rem;
  font-weight: 500;
  line-height: 1.6;
  margin: 0;
}
.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--blue-dim);
  color: var(--blue);
  border-radius: 6px;
  padding: 2px 10px;
  font-size: 0.7rem;
  font-weight: 600;
  margin-top: 0.75rem;
  font-family: 'DM Mono', monospace;
}
.tag-easy   { background: var(--green-dim); color: var(--green); }
.tag-medium { background: var(--amber-dim); color: var(--amber); }
.tag-hard   { background: var(--red-dim);   color: var(--red); }

/* ── TIMER ── */
.timer-box {
  background: var(--surface);
  border: 1px solid var(--border2);
  border-radius: 12px;
  padding: 0.65rem 1.2rem;
  text-align: center;
  font-family: 'DM Mono', monospace;
  font-size: 1.45rem;
  font-weight: 500;
  color: var(--green);
  letter-spacing: 0.08em;
}
.timer-warning {
  color: var(--red) !important;
  border-color: var(--red) !important;
  box-shadow: 0 0 20px rgba(240,101,101,0.15);
}

/* ── PROGRESS ── */
.prog-wrap {
  background: var(--surface2);
  border-radius: 99px;
  height: 5px;
  overflow: hidden;
  margin: 0.4rem 0 1.4rem;
}
.prog-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, var(--amber), #f7c948);
  transition: width 0.4s ease;
}

/* ── SCORE HERO ── */
.score-hero {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 2.8rem 2rem;
  text-align: center;
  margin-bottom: 1.6rem;
  position: relative;
  overflow: hidden;
}
.score-hero::before {
  content: '';
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%,-50%);
  width: 280px; height: 280px;
  background: radial-gradient(circle, rgba(245,166,35,0.07) 0%, transparent 65%);
  border-radius: 50%;
  pointer-events: none;
}
.score-num {
  font-family: 'Syne', sans-serif;
  font-size: 5rem;
  font-weight: 800;
  color: var(--amber);
  line-height: 1;
  letter-spacing: -0.04em;
}
.score-sub {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-top: 0.3rem;
}
.rank-pill {
  display: inline-block;
  background: var(--amber);
  color: #000;
  border-radius: 99px;
  padding: 5px 24px;
  font-family: 'Syne', sans-serif;
  font-weight: 800;
  font-size: 1rem;
  margin-top: 1.2rem;
  letter-spacing: 0.01em;
}

/* ── LEADERBOARD ── */
.lb-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.lb-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0.85rem 1.2rem;
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  transition: border-color 0.2s, transform 0.15s;
}
.lb-row:hover {
  border-color: var(--border2);
  transform: translateX(2px);
}
.lb-row.gold   { border-color: #f5a623; background: rgba(245,166,35,0.05); }
.lb-row.silver { border-color: #9ca3af; background: rgba(156,163,175,0.04); }
.lb-row.bronze { border-color: #b87333; background: rgba(184,115,51,0.04); }
.lb-row.is-me  { border-color: var(--blue) !important; }
.lb-medal {
  font-size: 1.15rem;
  min-width: 28px;
  text-align: center;
}
.lb-rank-num {
  font-family: 'DM Mono', monospace;
  font-size: 0.8rem;
  color: var(--text-muted);
  min-width: 28px;
}
.lb-info { flex: 1; min-width: 0; }
.lb-name {
  font-weight: 600;
  color: var(--text);
  font-size: 0.95rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.lb-email {
  font-size: 0.75rem;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.lb-right { text-align: right; }
.lb-score {
  font-family: 'DM Mono', monospace;
  color: var(--amber);
  font-weight: 500;
  font-size: 1rem;
}
.lb-correct {
  font-size: 0.75rem;
  color: var(--text-muted);
}
.lb-time {
  font-family: 'DM Mono', monospace;
  font-size: 0.78rem;
  color: var(--text-dim);
  margin-top: 1px;
}
.lb-you {
  font-size: 0.68rem;
  background: var(--blue-dim);
  color: var(--blue);
  border-radius: 4px;
  padding: 1px 7px;
  font-family: 'DM Mono', monospace;
  font-weight: 500;
  margin-left: 6px;
  vertical-align: middle;
}

/* ── ANSWER REVIEW ── */
.rev-correct { border-left-color: var(--green) !important; }
.rev-wrong   { border-left-color: var(--red) !important; }
.rev-skipped { border-left-color: var(--text-dim) !important; }
.rev-label-correct { color: var(--green); font-weight: 600; font-size: 0.84rem; }
.rev-label-wrong   { color: var(--red);   font-weight: 600; font-size: 0.84rem; }
.expl-box {
  background: rgba(79,142,247,0.06);
  border: 1px solid rgba(79,142,247,0.15);
  border-radius: 10px;
  padding: 0.8rem 1.1rem;
  color: var(--text-muted);
  font-size: 0.87rem;
  margin-top: 0.75rem;
  line-height: 1.55;
}

/* ── SIDEBAR ── */
section[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] * { color: var(--text) !important; }
section[data-testid="stSidebar"] .stButton > button {
  background: var(--surface2) !important;
  border: 1px solid var(--border2) !important;
  color: var(--text) !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
  border-color: var(--amber) !important;
  color: var(--amber) !important;
}

/* ── STREAMLIT OVERRIDES ── */
.stButton > button {
  border-radius: 10px !important;
  font-weight: 600 !important;
  font-family: 'Manrope', sans-serif !important;
  background: var(--surface2) !important;
  border: 1px solid var(--border2) !important;
  color: var(--text) !important;
  transition: all 0.2s !important;
}
.stButton > button:hover {
  border-color: var(--amber) !important;
  color: var(--amber) !important;
}
.stButton > button[kind="primary"] {
  background: var(--amber) !important;
  border-color: var(--amber) !important;
  color: #000 !important;
}
.stButton > button[kind="primary"]:hover {
  background: #f7c948 !important;
  color: #000 !important;
}
.stRadio label { color: var(--text-muted) !important; cursor: pointer; }
.stTextInput input, .stNumberInput input {
  background: var(--surface) !important;
  border: 1px solid var(--border2) !important;
  color: var(--text) !important;
  border-radius: 10px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
  border-color: var(--amber) !important;
  box-shadow: 0 0 0 2px rgba(245,166,35,0.15) !important;
}
.stSelectbox > div > div {
  background: var(--surface) !important;
  border: 1px solid var(--border2) !important;
  border-radius: 10px !important;
  color: var(--text) !important;
}
div[data-testid="metric-container"] {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1rem 1.2rem;
}
div[data-testid="metric-container"] [data-testid="stMetricLabel"] {
  color: var(--text-muted) !important;
  font-size: 0.78rem !important;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
  color: var(--text) !important;
  font-family: 'Syne', sans-serif !important;
}
.stAlert {
  border-radius: 12px !important;
  border: 1px solid var(--border2) !important;
}
.stTabs [data-baseweb="tab-list"] {
  background: var(--surface) !important;
  border-radius: 12px !important;
  padding: 4px !important;
  gap: 4px !important;
}
.stTabs [data-baseweb="tab"] {
  border-radius: 8px !important;
  color: var(--text-muted) !important;
  font-weight: 600 !important;
}
.stTabs [aria-selected="true"] {
  background: var(--surface2) !important;
  color: var(--amber) !important;
}
.stCheckbox label { color: var(--text-muted) !important; }
.stSlider [data-testid="stTickBarMin"],
.stSlider [data-testid="stTickBarMax"] { color: var(--text-muted) !important; }
.stTextArea textarea {
  background: var(--surface) !important;
  border: 1px solid var(--border2) !important;
  color: var(--text) !important;
  border-radius: 10px !important;
}
.stDataFrame { border-radius: 12px !important; overflow: hidden; }
.stExpander {
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  background: var(--surface) !important;
}

/* dots nav */
.dot-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  justify-content: center;
  padding: 4px 0;
}
.dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  display: inline-block;
}

/* divider */
.divider {
  border: none;
  border-top: 1px solid var(--border);
  margin: 1.4rem 0;
}

/* ── SESSION META BAR ── */
.session-meta-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 0.75rem 1.2rem;
  margin: 0.8rem 0 1.2rem;
}
.smb-title {
  font-family: 'Syne', sans-serif;
  font-weight: 700;
  font-size: 0.95rem;
  color: var(--text);
  margin-right: 4px;
}
.smb-chip {
  background: var(--surface2);
  border: 1px solid var(--border2);
  border-radius: 99px;
  padding: 2px 12px;
  font-size: 0.75rem;
  color: var(--text-muted);
  font-family: 'DM Mono', monospace;
  white-space: nowrap;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "mode":            "home",
        "participant_id":  None,
        "session_id":      None,
        "questions":       [],
        "answers":         {},
        "started_at":      None,
        "result":          None,
        "admin_auth":      False,
        "current_q":       0,
        "show_review":     False,
        "lb_session_idx":  0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


def _switch_user():
    """Clear all participant-specific state so the next person can register."""
    st.session_state.participant_id = None
    st.session_state.session_id     = None
    st.session_state.questions      = []
    st.session_state.answers        = {}
    st.session_state.started_at     = None
    st.session_state.result         = None
    st.session_state.current_q      = 0
    st.session_state.show_review    = False
    st.session_state.mode           = "home"


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

def _render_sidebar():
    with st.sidebar:
        st.markdown(
            '<p style="font-family:Syne,sans-serif;font-size:1.1rem;'
            'font-weight:800;letter-spacing:-0.01em;margin-bottom:1rem">🎯 Interview MCQ</p>',
            unsafe_allow_html=True
        )
        st.markdown("---")

        nav_items = [
            ("🏠", "Home",        "home"),
            ("📋", "Take MCQ",    "home"),
            ("🏆", "Leaderboard", "leaderboard"),
            ("⚙️", "Admin Panel", "admin"),
        ]
        for icon, label, target in nav_items:
            if st.button(f"{icon}  {label}", use_container_width=True):
                st.session_state.mode = target
                st.rerun()

        st.markdown("---")
        ok, msg = db.test_connection()
        if ok:
            st.success("🟢 DB connected")
        else:
            st.error(f"🔴 DB error\n{msg[:60]}")

        if st.session_state.participant_id:
            p = db.get_participant(st.session_state.participant_id)
            if p:
                st.markdown(
                    f'<div style="background:var(--surface2);border:1px solid var(--border2);'
                    f'border-radius:10px;padding:0.65rem 0.9rem;margin-top:0.5rem">'
                    f'<div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:2px">Current user</div>'
                    f'<div style="font-weight:700;font-size:0.92rem">👤 {html_module.escape(p["name"])}</div>'
                    + (f'<div style="font-size:0.75rem;color:var(--text-muted)">{html_module.escape(p.get("email",""))}</div>' if p.get("email") else "")
                    + (f'<div style="font-size:0.75rem;color:var(--amber);margin-top:2px">Score: {p["score"]:.1f}%</div>' if p.get("submitted_at") else "")
                    + '</div>',
                    unsafe_allow_html=True
                )
                st.markdown("")
                if st.button("🔄 Switch User", use_container_width=True):
                    _switch_user()
                    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# HOME PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _render_home():
    st.markdown("""
    <div class="mcq-header">
        <div class="mcq-badge">● Campus Placement Prep</div>
        <h1>Interview MCQ Round</h1>
        <p>Same questions · Timed · Auto-scored · Live leaderboard</p>
    </div>
    """, unsafe_allow_html=True)

    session = db.get_active_session()
    if not session or int(session.get("question_count", 0)) == 0:
        st.warning(
            "⚠️ No active MCQ session. Ask the admin to generate questions first.",
            icon=None
        )
        st.info("👉 Open **Admin Panel** from the sidebar to create a session.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("📝 Questions",  session["question_count"])
    col2.metric("⏱️ Time Limit", f"{session['time_limit_mins']} min")
    col3.metric("📅 Session",    session["title"])

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    if st.session_state.participant_id:
        p = db.get_participant(st.session_state.participant_id)
        if p and p.get("submitted_at"):
            st.success("✅ You have already submitted this MCQ round.")
            col_a, col_b = st.columns(2)
            if col_a.button("📊 View My Result", use_container_width=True):
                st.session_state.mode = "result"
                st.rerun()
            if col_b.button("🏆 View Leaderboard", use_container_width=True):
                st.session_state.mode = "leaderboard"
                st.rerun()
            return
        if p and not p.get("submitted_at"):
            st.info(f"👋 Welcome back, **{p['name']}**! Your quiz is in progress.")
            if st.button("▶️ Resume Quiz", use_container_width=True, type="primary"):
                st.session_state.mode       = "quiz"
                st.session_state.session_id = str(p["session_id"])
                st.session_state.questions  = db.get_questions(str(p["session_id"]))
                if not st.session_state.started_at:
                    st.session_state.started_at = p["started_at"]
                st.rerun()
            return

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Register to Start</div>', unsafe_allow_html=True)

    name  = st.text_input("Full Name *", placeholder="e.g. Pradesha P")
    email = st.text_input("Email Address *", placeholder="e.g. pradesha@email.com")
    if email and "@" not in email:
        st.markdown(
            '<span style="color:var(--red);font-size:0.82rem">⚠ Enter a valid email address</span>',
            unsafe_allow_html=True
        )

    rules = f"""
**Before you start:**
- You have **{session['time_limit_mins']} minutes** once you begin.
- There are **{session['question_count']} questions** — same for all participants.
- Navigate freely between questions before submitting.
- Once submitted, answers **cannot** be changed.
- Ranking: score first (higher = better), then time (lower = better).
    """
    with st.expander("📖 Read the rules before starting"):
        st.markdown(rules)

    agree = st.checkbox("I have read and understood the rules")
    st.markdown("</div>", unsafe_allow_html=True)

    email_valid = bool(email.strip() and "@" in email and "." in email.split("@")[-1])

    if st.button("🚀 Start MCQ", type="primary", use_container_width=True,
                 disabled=not (name.strip() and email_valid and agree)):
        pid, err = db.register_participant(
            session_id=str(session["session_id"]),
            name=name.strip(),
            email=email.strip(),
        )
        if err:
            st.error(f"❌ {err}")
        else:
            st.session_state.participant_id = pid
            st.session_state.session_id     = str(session["session_id"])
            st.session_state.questions      = db.get_questions(str(session["session_id"]))
            st.session_state.answers        = {}
            st.session_state.started_at     = datetime.now(timezone.utc)
            st.session_state.current_q      = 0
            st.session_state.mode           = "quiz"
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# QUIZ PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _render_quiz():
    questions  = st.session_state.questions
    answers    = st.session_state.answers
    started_at = st.session_state.started_at
    session_id = st.session_state.session_id

    if not questions:
        st.error("No questions loaded. Please go back home.")
        if st.button("🏠 Back to Home"):
            st.session_state.mode = "home"
            st.rerun()
        return

    session    = db.get_session_by_id(session_id)
    time_limit = (session["time_limit_mins"] if session else 30) * 60

    total_q     = len(questions)
    current_idx = st.session_state.current_q

    # ── Timer ──────────────────────────────────────────────────────────────
    if started_at:
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        elapsed    = int((datetime.now(timezone.utc) - started_at).total_seconds())
        remaining  = max(0, time_limit - elapsed)
        mins, secs = divmod(remaining, 60)
        timer_cls  = "timer-warning" if remaining < 120 else ""

        top_left, top_right = st.columns([4, 1])
        with top_right:
            st.markdown(
                f'<div class="timer-box {timer_cls}">{mins:02d}:{secs:02d}</div>',
                unsafe_allow_html=True
            )
        if remaining == 0:
            _do_submit()
            return
    else:
        top_left, _ = st.columns([4, 1])

    with top_left:
        answered_count = len([v for v in answers.values() if v])
        pct = int((answered_count / total_q) * 100)
        st.markdown(
            f"**Q {current_idx + 1} / {total_q}** · "
            f"{answered_count} answered · {total_q - answered_count} remaining"
        )
        st.markdown(
            f'<div class="prog-wrap"><div class="prog-fill" style="width:{pct}%"></div></div>',
            unsafe_allow_html=True
        )

    # ── Current Question ───────────────────────────────────────────────────
    q          = questions[current_idx]
    qid        = q["question_id"]
    diff       = q.get("difficulty", "medium")
    diff_class = f"tag-{diff}"

    # Escape HTML entities in question text to prevent rendering issues
    q_text_safe = html_module.escape(q["question_text"])
    skill_safe  = html_module.escape(q.get("skill", ""))

    st.markdown(
        f"""
        <div class="question-card">
            <div class="q-num">Question {current_idx + 1} of {total_q}</div>
            <p class="q-text">{q_text_safe}</p>
            <span class="tag">{skill_safe}</span>
            <span class="tag {diff_class}" style="margin-left:6px">{diff}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    option_labels = {
        "a": q["option_a"],
        "b": q["option_b"],
        "c": q["option_c"],
        "d": q["option_d"],
    }
    current_answer = answers.get(qid)
    current_index  = (
        list(option_labels.keys()).index(current_answer)
        if current_answer in option_labels else None
    )

    choice = st.radio(
        "Select your answer:",
        options=list(option_labels.keys()),
        format_func=lambda k: f"{k.upper()}.  {option_labels[k]}",
        index=current_index,
        key=f"radio_{qid}",
        label_visibility="collapsed",
    )
    if choice:
        st.session_state.answers[qid] = choice

    # ── Navigation ─────────────────────────────────────────────────────────
    st.markdown("")
    nav_l, nav_c, nav_r = st.columns([1, 2, 1])

    with nav_l:
        if current_idx > 0:
            if st.button("← Prev", use_container_width=True):
                st.session_state.current_q -= 1
                st.rerun()
    with nav_r:
        if current_idx < total_q - 1:
            if st.button("Next →", use_container_width=True, type="primary"):
                st.session_state.current_q += 1
                st.rerun()
    with nav_c:
        dot_html = '<div class="dot-nav">'
        for i, qobj in enumerate(questions):
            qid_dot = qobj["question_id"]
            if i == current_idx:
                color = "#f5a623"
            elif answers.get(qid_dot):
                color = "#3ecf8e"
            else:
                color = "#2e2e40"
            dot_html += f'<div class="dot" style="background:{color}"></div>'
        dot_html += "</div>"
        st.markdown(dot_html, unsafe_allow_html=True)

    # ── Submit ──────────────────────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    unanswered = total_q - len([v for v in answers.values() if v])
    if unanswered > 0:
        st.warning(f"⚠️  {unanswered} question(s) still unanswered — you can still submit.")

    if st.button("✅ Submit MCQ", type="primary", use_container_width=True):
        _do_submit()


def _do_submit():
    result = db.submit_participant(
        participant_id=st.session_state.participant_id,
        started_at=st.session_state.started_at,
        answers=st.session_state.answers,
        questions=st.session_state.questions,
    )
    st.session_state.result = result
    st.session_state.mode   = "result"
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# RESULT PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _render_result():
    result = st.session_state.result
    if not result:
        p = db.get_participant(st.session_state.participant_id)
        if p and p.get("submitted_at"):
            result = {
                "score":              float(p["score"] or 0),
                "correct_count":      p["correct_count"],
                "total":              p["total_questions"],
                "time_taken_seconds": p["time_taken_seconds"],
                "already_submitted":  True,
            }
            st.session_state.result = result
        else:
            st.error("No result found. Please complete the quiz.")
            st.session_state.mode = "home"
            st.rerun()
            return

    score   = result["score"]
    correct = result["correct_count"]
    total   = result["total"]
    t_secs  = result["time_taken_seconds"] or 0
    mins, s = divmod(t_secs, 60)

    rank = db.get_participant_rank(
        st.session_state.participant_id,
        st.session_state.session_id
    )

    if   score >= 80: verdict, emoji = "Excellent!", "🏆"
    elif score >= 60: verdict, emoji = "Good Job!",  "👍"
    elif score >= 40: verdict, emoji = "Keep Going", "💪"
    else:             verdict, emoji = "Keep Practising", "📚"

    p    = db.get_participant(st.session_state.participant_id)
    name = html_module.escape(p["name"]) if p else "Participant"

    rank_html = f'<div class="rank-pill">🥇 Rank #{rank}</div>' if rank else ""

    st.markdown(
        f"""
        <div class="score-hero">
            <div style="color:var(--text-muted);font-size:0.9rem;margin-bottom:0.5rem">
                {emoji} {name}
            </div>
            <div class="score-num">{score:.1f}%</div>
            <div class="score-sub">{correct} correct out of {total} questions</div>
            {rank_html}
            <div style="color:var(--text-muted);font-size:0.85rem;margin-top:0.9rem">
                {verdict} &nbsp;·&nbsp; Time: {mins}m {s}s
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Score",   f"{score:.1f}%")
    c2.metric("Correct", f"{correct}/{total}")
    c3.metric("Time",    f"{mins}m {s}s")
    c4.metric("Rank",    f"#{rank}" if rank else "—")

    col_a, col_b = st.columns(2)
    if col_a.button("🏆 Leaderboard", use_container_width=True, type="primary"):
        st.session_state.mode = "leaderboard"
        st.rerun()
    review_open = col_b.button("📖 Review Answers", use_container_width=True)

    # ── Next candidate handoff ─────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown(
        '<div style="background:var(--surface);border:1px solid var(--border2);'
        'border-radius:14px;padding:1.2rem 1.4rem;margin-bottom:1rem">'
        '<div style="font-family:Syne,sans-serif;font-weight:700;font-size:0.95rem;'
        'margin-bottom:0.3rem">👥 Next candidate on this device?</div>'
        '<div style="color:var(--text-muted);font-size:0.85rem">'
        'Hand the device to the next person and click the button below. '
        'Their session will start fresh.</div>'
        '</div>',
        unsafe_allow_html=True
    )
    if st.button("➡️ Next Candidate — Start Fresh", use_container_width=True):
        _switch_user()
        st.rerun()

    if review_open or st.session_state.get("show_review"):
        st.session_state["show_review"] = True
        _render_answer_review()


def _render_answer_review():
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown(
        '<p style="font-family:Syne,sans-serif;font-size:1.2rem;'
        'font-weight:800;letter-spacing:-0.01em">📖 Answer Review</p>',
        unsafe_allow_html=True
    )

    detail_answers = db.get_participant_answers(st.session_state.participant_id)
    if not detail_answers:
        st.info("No detailed answers available.")
        return

    option_map = {"a": "A", "b": "B", "c": "C", "d": "D"}

    for a in detail_answers:
        selected = a.get("selected_option")
        correct  = a["correct_option"]
        is_corr  = a["is_correct"]

        if not selected:
            row_class, label = "rev-skipped", "⬜ Skipped"
        elif is_corr:
            row_class, label = "rev-correct", "✅ Correct"
        else:
            row_class, label = "rev-wrong", "❌ Wrong"

        correct_text  = a.get(f"option_{correct}", correct)
        selected_text = a.get(f"option_{selected}", "—") if selected else "—"
        q_preview     = html_module.escape(a["question_text"][:80])

        with st.expander(f"Q{a['question_order']}. {q_preview}... — {label}", expanded=False):
            q_full_safe = html_module.escape(a["question_text"])
            st.markdown(
                f'<div class="question-card {row_class}">'
                f'<p class="q-text">{q_full_safe}</p>'
                f'</div>',
                unsafe_allow_html=True
            )
            sub1, sub2 = st.columns(2)
            with sub1:
                if selected:
                    css = "rev-label-correct" if is_corr else "rev-label-wrong"
                    sel_safe = html_module.escape(selected_text)
                    st.markdown(
                        f'<span class="{css}">Your answer: '
                        f'{option_map.get(selected,"?")}. {sel_safe}</span>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        '<span style="color:var(--text-muted)">Skipped</span>',
                        unsafe_allow_html=True
                    )
            with sub2:
                if not is_corr:
                    corr_safe = html_module.escape(correct_text)
                    st.markdown(
                        f'<span class="rev-label-correct">✅ Correct: '
                        f'{option_map.get(correct,"?")}. {corr_safe}</span>',
                        unsafe_allow_html=True
                    )
            if a.get("explanation"):
                expl_safe = html_module.escape(a["explanation"])
                st.markdown(
                    f'<div class="expl-box">💡 {expl_safe}</div>',
                    unsafe_allow_html=True
                )


# ─────────────────────────────────────────────────────────────────────────────
# LEADERBOARD PAGE  — session-wise
# ─────────────────────────────────────────────────────────────────────────────

def _render_lb_rows(leaderboard: list, current_pid: str | None):
    """Render the ranked rows for a given leaderboard list."""
    medals      = {1: "🥇", 2: "🥈", 3: "🥉"}
    row_classes = {1: "gold", 2: "silver", 3: "bronze"}

    st.markdown('<div class="lb-wrap">', unsafe_allow_html=True)
    for entry in leaderboard:
        rank    = int(entry["rank"])
        row_cls = row_classes.get(rank, "")
        medal   = medals.get(rank, "")
        t_secs  = entry["time_taken_seconds"] or 0
        mins, s = divmod(t_secs, 60)
        is_me   = current_pid and str(entry.get("participant_id", "")) == current_pid

        name_safe  = html_module.escape(str(entry["name"]))
        email_safe = html_module.escape(str(entry.get("email") or ""))
        score_val  = float(entry["score"])
        corr       = entry["correct_count"]
        tot        = entry["total_questions"]

        you_badge  = '<span class="lb-you">you</span>' if is_me else ""
        rank_num   = f"#{rank}" if rank > 3 else ""
        email_html = f'<div class="lb-email">{email_safe}</div>' if email_safe else ""

        st.markdown(
            f"""
            <div class="lb-row {row_cls}{'  is-me' if is_me else ''}">
                <div class="lb-medal">{medal}</div>
                <div class="lb-rank-num">{rank_num}</div>
                <div class="lb-info">
                    <div class="lb-name">{name_safe}{you_badge}</div>
                    {email_html}
                </div>
                <div class="lb-right">
                    <div class="lb-score">{score_val:.1f}%</div>
                    <div class="lb-correct">{corr}/{tot} correct</div>
                    <div class="lb-time">{mins}m {s}s</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    st.markdown('</div>', unsafe_allow_html=True)


def _render_leaderboard():
    st.markdown("""
    <div class="mcq-header">
        <div class="mcq-badge">● Live Rankings</div>
        <h1>Leaderboard</h1>
        <p>Ranked by score · Tiebreaker: time taken (lower = better)</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Load all sessions ──────────────────────────────────────────────────
    all_sessions = db.list_sessions()
    if not all_sessions:
        st.warning("No sessions found. Ask the admin to create one.")
        return

    current_pid = str(st.session_state.participant_id) if st.session_state.participant_id else None

    # ── Session picker ─────────────────────────────────────────────────────
    # Build label map: "🟢 Campus MCQ Round 1 · 20 Qs · 30 min"
    session_labels = []
    for s in all_sessions:
        status  = "🟢" if s["is_active"] else "⚪"
        label   = (
            f"{status} {s['title']} "
            f"· {s['question_count']} Qs "
            f"· {s['time_limit_mins']} min"
            f"  [{s['participant_count']} submitted]"
        )
        session_labels.append(label)

    # Default to the active session if present
    active_idx = next(
        (i for i, s in enumerate(all_sessions) if s["is_active"]), 0
    )

    # Store chosen index in session state so it survives reruns
    if "lb_session_idx" not in st.session_state:
        st.session_state.lb_session_idx = active_idx

    col_sel, col_btn = st.columns([5, 1])
    with col_sel:
        chosen_label = st.selectbox(
            "Select session to view",
            options=session_labels,
            index=st.session_state.lb_session_idx,
            label_visibility="collapsed",
        )
    with col_btn:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    # Resolve chosen session
    chosen_idx = session_labels.index(chosen_label)
    st.session_state.lb_session_idx = chosen_idx
    chosen_session = all_sessions[chosen_idx]
    sid            = str(chosen_session["session_id"])

    # ── Session meta strip ─────────────────────────────────────────────────
    is_active   = chosen_session["is_active"]
    status_text = "🟢 Active" if is_active else "⚪ Past session"
    import datetime as _dt
    created_str = ""
    try:
        created_at  = chosen_session.get("created_at")
        if created_at:
            if hasattr(created_at, "strftime"):
                created_str = created_at.strftime("%d %b %Y, %H:%M")
            else:
                created_str = str(created_at)[:16]
    except Exception:
        pass

    st.markdown(
        f"""
        <div class="session-meta-bar">
            <span class="smb-title">{html_module.escape(chosen_session['title'])}</span>
            <span class="smb-chip">{status_text}</span>
            <span class="smb-chip">{chosen_session['question_count']} questions</span>
            <span class="smb-chip">⏱ {chosen_session['time_limit_mins']} min</span>
            {'<span class="smb-chip">📅 ' + created_str + '</span>' if created_str else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Leaderboard data ───────────────────────────────────────────────────
    leaderboard = db.get_leaderboard(sid)

    if not leaderboard:
        st.info("No submissions yet for this session.")
        return

    scores    = [float(r["score"]) for r in leaderboard]
    avg_score = sum(scores) / len(scores)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("👥 Submitted",    len(leaderboard))
    m2.metric("📊 Average",      f"{avg_score:.1f}%")
    m3.metric("🥇 Top Score",    f"{max(scores):.1f}%")
    m4.metric("📉 Lowest Score", f"{min(scores):.1f}%")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Score distribution mini chart ──────────────────────────────────────
    with st.expander("📊 Score Distribution", expanded=False):
        import pandas as pd
        df_scores = pd.DataFrame({"Score (%)": scores})
        st.bar_chart(df_scores, x_label="Participant (by rank)", y_label="Score (%)", height=200)

    # ── Rows ───────────────────────────────────────────────────────────────
    _render_lb_rows(leaderboard, current_pid)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN PANEL
# ─────────────────────────────────────────────────────────────────────────────

def _render_admin():
    st.markdown("""
    <div class="mcq-header">
        <div class="mcq-badge">● Admin</div>
        <h1>Admin Panel</h1>
        <p>Generate MCQ sessions · Monitor participants · View full results</p>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.admin_auth:
        col, _ = st.columns([1, 2])
        with col:
            pwd = st.text_input("Admin Password", type="password")
            if st.button("Login", type="primary"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state.admin_auth = True
                    st.rerun()
                else:
                    st.error("❌ Wrong password")
        return

    with st.expander("🗄️ Database Setup"):
        if st.button("Initialise / Verify Database Schema"):
            ok = db.init_db()
            if ok:
                st.success("✅ Schema is ready.")
            else:
                st.error("❌ DB init failed. Check credentials.")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["🆕 Create Session", "📊 Active Session", "📁 All Sessions"])

    with tab1:
        st.markdown("#### Generate a new MCQ set")
        st.warning(
            "⚠️ Creating a new session deactivates the current one. "
            "Existing submissions are preserved."
        )
        session_title  = st.text_input("Session Title", value="Campus MCQ Round 1")
        time_limit     = st.number_input("Time Limit (minutes)", min_value=5, max_value=120, value=30)
        n_questions    = st.slider("Number of Questions", min_value=5, max_value=30, value=20)
        difficulty_opt = st.selectbox("Difficulty", ["mixed", "easy", "medium", "hard"])

        st.markdown("**Skills to cover** (JSON — leave blank for general CS):")
        skills_json_input = st.text_area(
            "skills_data JSON (optional)",
            value='{"categories": {"Programming Languages": [{"name":"Python"},{"name":"Java"}],'
                  '"Databases":[{"name":"MySQL"},{"name":"MongoDB"}],'
                  '"Cloud & DevOps":[{"name":"Docker"},{"name":"Git"}]}}',
            height=120,
        )

        if st.button("🚀 Generate MCQ Set", type="primary", use_container_width=True):
            with st.spinner(f"Generating {n_questions} questions via Groq LLaMA… (~30–60s)"):
                try:
                    import json as _json
                    skills_data = _json.loads(skills_json_input)
                except Exception:
                    st.error("❌ Invalid JSON in skills_data. Please fix and retry.")
                    st.stop()

                sid = db.create_session(
                    title=session_title,
                    time_limit_mins=time_limit,
                )
                generator = gen.MCQGenerator()
                questions = generator.generate_mcq_set(
                    skills_data=skills_data,
                    total_questions=n_questions,
                    difficulty=difficulty_opt,
                )
                if not questions:
                    st.error("❌ Question generation failed. Check GROQ_API_KEY.")
                    st.stop()

                count = db.insert_questions(sid, questions)
                st.success(
                    f"✅ Session created! **{count} questions** stored. "
                    f"Session ID: `{sid}`"
                )
                st.session_state.session_id = sid

    with tab2:
        session = db.get_active_session()
        if not session:
            st.info("No active session. Create one above.")
        else:
            st.markdown(
                f"**{html_module.escape(session['title'])}** · "
                f"{session['question_count']} questions · "
                f"{session['time_limit_mins']} min"
            )
            st.caption(f"Session ID: `{session['session_id']}`")
            leaderboard = db.get_leaderboard(str(session["session_id"]))
            st.markdown(f"**{len(leaderboard)} submission(s) so far**")

            if leaderboard:
                import pandas as pd
                df = pd.DataFrame(leaderboard)
                df["time"]  = df["time_taken_seconds"].apply(
                    lambda x: f"{x//60}m {x%60}s" if x else "—"
                )
                df["score"] = df["score"].apply(lambda x: f"{float(x):.1f}%")
                st.dataframe(
                    df[["rank", "name", "email", "score",
                        "correct_count", "total_questions", "time"]],
                    use_container_width=True,
                    hide_index=True,
                )
            if st.button("🔄 Refresh"):
                st.rerun()

    with tab3:
        all_sessions = db.list_sessions()
        if not all_sessions:
            st.info("No sessions yet.")
        else:
            import pandas as pd
            df = pd.DataFrame(all_sessions)
            df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
            df["status"]     = df["is_active"].apply(lambda x: "🟢 Active" if x else "⚪ Inactive")
            st.dataframe(
                df[["title", "status", "question_count", "participant_count",
                    "time_limit_mins", "created_at"]],
                use_container_width=True,
                hide_index=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────────────────────────────────────

def main():
    _render_sidebar()
    mode = st.session_state.mode
    if   mode == "quiz":        _render_quiz()
    elif mode == "result":      _render_result()
    elif mode == "leaderboard": _render_leaderboard()
    elif mode == "admin":       _render_admin()
    else:                       _render_home()


if __name__ == "__main__":
    main()