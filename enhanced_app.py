"""
enhanced_app.py  –  Resume → Skills → AI Interview → Evaluation
Improvements:
  1. Skills extracted via phrase-match + semantic similarity (sentence-transformers)
  2. Questions generated for skills AND projects found in the resume
  3. Questions are dynamic – different every run (session seed + high temperature)
  4. Each question's model answer validated by a second AI model (Mixtral)
     Confidence badge shown to student on every question
"""
import os
import streamlit as st
from enhanced_skill_extractor import EnhancedSkillExtractor
from resume_parser import ResumeParser
from question_generator import QuestionGenerator
from answer_evaluator import AnswerEvaluator, LIKERT_SCALE
import rasch_engine as irt

st.set_page_config(
    page_title="AI Interview Coach",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
.stApp { background: #f0f4ff; }

section[data-testid="stSidebar"] { background: #1e1b4b !important; border-right: none; }
section[data-testid="stSidebar"] * { color: #c7d2fe !important; }
section[data-testid="stSidebar"] .stButton button {
    background: #4f46e5 !important; color: white !important;
    border: none !important; border-radius: 8px !important;
}
.main .block-container { background: transparent; padding: 2rem 2.5rem; max-width: 1000px; }

.page-banner {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%);
    border-radius: 16px; padding: 2rem 2.4rem; margin-bottom: 1.5rem; color: white;
}
.page-banner h1 { margin: 0 0 0.3rem; font-size: 1.7rem; font-weight: 800;
    letter-spacing: -0.02em; color: white; }
.page-banner p { margin: 0; font-size: 0.92rem; opacity: 0.85; color: white; }

.content-card {
    background: white; border-radius: 16px; padding: 1.8rem 2rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(79,70,229,0.07);
}
.section-label {
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #6366f1; margin-bottom: 0.7rem;
}

.skill-pill {
    display: inline-block; padding: 4px 13px; margin: 3px; border-radius: 999px;
    font-size: 0.78rem; font-weight: 600; background: #eef2ff;
    color: #4338ca; border: 1px solid #c7d2fe;
}
.skill-pill-semantic {
    display: inline-block; padding: 4px 13px; margin: 3px; border-radius: 999px;
    font-size: 0.78rem; font-weight: 600; background: #fdf4ff;
    color: #7e22ce; border: 1px dashed #d8b4fe;
}
.skill-pill-cat {
    display: inline-block; padding: 2px 10px; margin: 2px; border-radius: 4px;
    font-size: 0.68rem; font-weight: 700; background: #f0fdf4;
    color: #16a34a; border: 1px solid #bbf7d0;
    text-transform: uppercase; letter-spacing: 0.06em;
}
.skill-pill-project {
    display: inline-block; padding: 2px 10px; margin: 2px; border-radius: 4px;
    font-size: 0.68rem; font-weight: 700; background: #fff7ed;
    color: #c2410c; border: 1px solid #fdba74;
    text-transform: uppercase; letter-spacing: 0.06em;
}

.q-card {
    background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
    border: 1.5px solid #c7d2fe; border-radius: 14px;
    padding: 1.4rem 1.6rem; margin-bottom: 0.6rem;
}
.q-meta { display: flex; gap: 8px; flex-wrap: wrap; font-size: 0.72rem; margin-bottom: 0.8rem; }
.q-meta span { padding: 3px 10px; border-radius: 999px; font-weight: 600; }
.q-num  { background: #4f46e5; color: white; }
.q-skill { background: #7c3aed; color: white; }
.q-text { font-size: 1.05rem; color: #1e1b4b; font-weight: 600; line-height: 1.65; }

.confidence-badge {
    border-radius: 8px; padding: 8px 14px; margin-bottom: 1rem;
    font-size: 0.82rem; font-weight: 600;
    display: flex; align-items: center; gap: 8px;
}
.confidence-high   { background: #f0fdf4; border: 1px solid #bbf7d0; color: #16a34a; }
.confidence-medium { background: #fffbeb; border: 1px solid #fde68a; color: #d97706; }
.confidence-low    { background: #fef2f2; border: 1px solid #fecaca; color: #dc2626; }

.progress-bar-wrap { background: #e0e7ff; border-radius: 999px; height: 6px;
    margin-bottom: 1.2rem; overflow: hidden; }
.progress-bar-fill { background: linear-gradient(90deg, #4f46e5, #a855f7);
    height: 6px; border-radius: 999px; }
.q-counter { font-size: 0.8rem; font-weight: 600; color: #6366f1; margin-bottom: 0.4rem; }

.score-wrap { text-align: center; padding: 1rem 0.5rem; }
.score-ring {
    width: 110px; height: 110px; border-radius: 50%;
    display: inline-flex; flex-direction: column;
    align-items: center; justify-content: center; margin-bottom: 0.5rem;
}
.score-num { font-size: 2.2rem; font-weight: 800; letter-spacing: -0.04em; line-height: 1; }
.score-denom { font-size: 0.72rem; color: #94a3b8; }
.grade-badge {
    display: inline-block; padding: 4px 16px; border-radius: 999px;
    font-size: 0.78rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
}

.rubric-row { margin-bottom: 12px; }
.rubric-label { display: flex; justify-content: space-between;
    font-size: 0.8rem; color: #475569; margin-bottom: 4px; font-weight: 500; }
.rubric-track { background: #e2e8f0; border-radius: 999px; height: 8px; overflow: hidden; }
.rubric-fill { height: 8px; border-radius: 999px; }

.fb-strength {
    display: flex; align-items: flex-start; gap: 8px;
    background: #f0fdf4; border: 1px solid #bbf7d0;
    padding: 9px 13px; margin: 5px 0; border-radius: 10px;
    font-size: 0.84rem; color: #166534; font-weight: 500;
}
.fb-improve {
    display: flex; align-items: flex-start; gap: 8px;
    background: #fffbeb; border: 1px solid #fde68a;
    padding: 9px 13px; margin: 5px 0; border-radius: 10px;
    font-size: 0.84rem; color: #92400e; font-weight: 500;
}
.hint-box {
    background: #fffbeb; border: 1.5px dashed #fbbf24;
    border-radius: 10px; padding: 12px 16px;
    font-size: 0.84rem; color: #78350f; margin-top: 8px;
}

.metric-card {
    background: white; border-radius: 14px; padding: 1.3rem 1rem; text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 12px rgba(79,70,229,0.08);
    border-top: 4px solid;
}
.metric-val { font-size: 1.9rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1; margin-bottom: 4px; }
.metric-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.08em; color: #94a3b8; }

.cat-row { margin-bottom: 14px; }
.cat-row-label { display: flex; justify-content: space-between;
    font-size: 0.85rem; font-weight: 600; color: #1e1b4b; margin-bottom: 5px; }
.cat-track { background: #e0e7ff; border-radius: 999px; height: 10px; overflow: hidden; }
.cat-fill { height: 10px; border-radius: 999px; }
.section-divider { border: none; border-top: 1.5px solid #e0e7ff; margin: 1.2rem 0; }

.legend-box {
    display:flex; gap:16px; flex-wrap:wrap; align-items:center;
    font-size:0.76rem; color:#475569; margin-bottom:1rem;
    background:#f8fafc; border-radius:10px; padding:10px 14px;
    border:1px solid #e2e8f0;
}

.likert-container { margin: 1rem 0 0.5rem; }
.likert-label { font-size: 0.82rem; font-weight: 600; color: #374151; margin-bottom: 0.5rem; }
.likert-hint  { font-size: 0.78rem; color: #6b7280; margin-top: 0.25rem; }
.calibration-box {
    border-radius: 10px; padding: 10px 16px; margin-top: 0.8rem;
    font-size: 0.85rem; display: flex; align-items: flex-start; gap: 10px;
}
.calibration-accurate   { background: #f0fdf4; border: 1.5px solid #86efac; color: #15803d; }
.calibration-over       { background: #fff7ed; border: 1.5px solid #fdba74; color: #c2410c; }
.calibration-under      { background: #eff6ff; border: 1.5px solid #93c5fd; color: #1d4ed8; }
.calibration-close      { background: #f0fdf4; border: 1.5px solid #86efac; color: #15803d; }
.calibration-default    { background: #f8fafc; border: 1.5px solid #e2e8f0; color: #475569; }
.score-split { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 4px; }
.score-base  { font-size: 0.75rem; color: #6b7280; }
.score-self  { font-size: 0.75rem; color: #7c3aed; font-weight: 600; }

</style>
""", unsafe_allow_html=True)


# ── Loaders ──────────────────────────────────────────────────────── #

@st.cache_resource
def load_parsers():
    return EnhancedSkillExtractor(), ResumeParser()

@st.cache_resource
def load_ai_tools():
    return QuestionGenerator(), AnswerEvaluator()

skill_extractor, resume_parser = load_parsers()
question_gen, answer_eval      = load_ai_tools()


# ── Helpers ──────────────────────────────────────────────────────── #

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
    """Renders confidence badge below each non-project question card."""
    # Project questions are subjective — no badge needed
    if q.get("type") == "project":
        return

    confidence = q.get("confidence", "high")
    similarity = q.get("similarity", 1.0)

    conf_map = {
        "high":   ("✅", "confidence-high",
                   "Both AI models agree — answer is reliable"),
        "medium": ("⚠️", "confidence-medium",
                   "Models partially agreed — verify key points if unsure"),
        "low":    ("🔴", "confidence-low",
                   "Models disagreed — please verify this answer with your textbook"),
    }
    icon, css, message = conf_map.get(confidence, conf_map["high"])

    st.markdown(
        f'<div class="confidence-badge {css}">'
        f'{icon}&nbsp;<b>Answer confidence: {confidence.upper()}</b>'
        f'&nbsp;·&nbsp;Agreement score: {similarity}'
        f'&nbsp;·&nbsp;{message}'
        f'</div>',
        unsafe_allow_html=True
    )

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

def render_breakdown(breakdown):
    items = [
        ("technical_accuracy","Technical Accuracy",40),
        ("completeness",      "Completeness",      30),
        ("clarity",           "Clarity",           20),
        ("practical_insight", "Practical Insight", 10),
    ]
    for key, label, max_val in items:
        val = breakdown.get(key, 0)
        pct = int((val / max_val) * 100) if max_val else 0
        color = "#16a34a" if pct >= 70 else ("#f59e0b" if pct >= 40 else "#ef4444")
        st.markdown(f"""
        <div class="rubric-row">
            <div class="rubric-label">
                <span>{label}</span>
                <span style="font-weight:700;color:{color}">{val}/{max_val}</span>
            </div>
            <div class="rubric-track">
                <div class="rubric-fill" style="width:{pct}%;background:{color}"></div>
            </div>
        </div>""", unsafe_allow_html=True)

def progress_bar(current, total):
    pct = int(((current) / total) * 100) if total else 0
    st.markdown(f"""
    <div class="q-counter">Question {current + 1} of {total}</div>
    <div class="progress-bar-wrap">
        <div class="progress-bar-fill" style="width:{pct}%"></div>
    </div>""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────── #

defaults = {
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
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Sidebar ───────────────────────────────────────────────────────── #

with st.sidebar:
    st.markdown("""
    <div style="padding:0.5rem 0 1.2rem">
        <div style="font-size:1.3rem;font-weight:800;color:white;letter-spacing:-0.02em">
            🚀 Interview Coach
        </div>
        <div style="font-size:0.75rem;color:#a5b4fc;margin-top:3px">AI-powered resume interviewer</div>
    </div>""", unsafe_allow_html=True)

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

    st.markdown("<hr style='border-color:#312e81;margin:1rem 0'>", unsafe_allow_html=True)

    if st.session_state.stage == "interview" and st.session_state.questions:
        total = len(st.session_state.questions)
        done  = len(st.session_state.evaluations)
        pct   = int(done / total * 100)
        st.markdown(f"""
        <div style="margin-bottom:0.8rem">
            <div style="display:flex;justify-content:space-between;
                        font-size:0.76rem;color:#a5b4fc;margin-bottom:6px">
                <span>Progress</span><span>{done}/{total} answered</span>
            </div>
            <div style="background:#312e81;border-radius:999px;height:6px">
                <div style="width:{pct}%;background:#a5b4fc;height:6px;border-radius:999px"></div>
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#312e81;margin:1rem 0'>", unsafe_allow_html=True)
    if st.button("↺  Start Over", use_container_width=True):
        for k, v in defaults.items():
            st.session_state[k] = v
        st.rerun()


# ================================================================== #
#  STAGE 1 – UPLOAD                                                    #
# ================================================================== #

if st.session_state.stage == "upload":
    st.markdown("""
    <div class="page-banner">
        <h1>AI Interview Coach</h1>
        <p>Upload your resume · Skills + projects extracted · AI asks the tough questions · You get scored</p>
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


# ================================================================== #
#  STAGE 2 – CONFIGURE                                                 #
# ================================================================== #

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
        <span><span class="skill-pill-semantic">Skill</span> &nbsp;keyword fallback (API unavailable)</span>
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
    # Pool is fixed at 5 per difficulty level = 15 per skill
    q_per_level = 5

    answers_per_skill = st.slider(
        "Questions per skill", min_value=5, max_value=15, value=9, step=1,
        help="IRT adaptively picks from a pool of 15 questions (5 easy + 5 medium + 5 hard) per skill."
    )

    include_projects = st.checkbox(
        "🗂️  Include project-based questions (extracted from resume)",
        value=True
    )

    pool_size = total_skills * 15  # fixed: 5×3 per skill
    estimated = total_skills * answers_per_skill
    proj_note = " + project questions" if include_projects else ""
    st.markdown(f"""
    <div style="background:#eef2ff;border:1.5px solid #c7d2fe;border-radius:10px;
                padding:12px 18px;margin:1rem 0;display:flex;align-items:center;gap:10px">
        <span style="font-size:1.2rem">📋</span>
        <span style="font-size:0.9rem;color:#3730a3">
            <b>Pool: {pool_size} questions generated</b> (5 easy + 5 medium + 5 hard per skill) · <b>Student answers: {estimated}</b> (IRT adaptive){proj_note}
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
                        st.session_state.resume_text if include_projects else ""
                    )
                    questions      = []
                    gen_error      = None
                    try:
                        questions = question_gen.generate_questions(
                            skills_data,
                            questions_per_skill=q_per_level,
                            resume_text=resume_text_for_projects,
                        )
                    except RuntimeError as e:
                        gen_error = str(e)
                    except Exception as e:
                        gen_error = f"Unexpected error: {e}"

                if gen_error:
                    st.error(f"❌ Question generation failed:\n\n{gen_error}")
                    st.info("💡 Fix: Go to console.groq.com → API Keys → create a new key → update your .env or .secrets.toml file.")
                elif questions:
                    # Build IRT pool per category
                    # {category: [question dicts with b_param]}
                    cat_pool = {}
                    for q in questions:
                        cat = q.get("category", "Other")
                        cat_pool.setdefault(cat, []).append(q)

                    st.session_state.questions        = questions
                    st.session_state.q_index          = 0
                    st.session_state.answers          = {}
                    st.session_state.evaluations      = {}
                    st.session_state.cat_pool         = cat_pool
                    st.session_state.category_thetas  = {
                        cat: irt.THETA_INIT for cat in cat_pool
                    }
                    st.session_state.category_asked   = {
                        cat: set() for cat in cat_pool
                    }
                    st.session_state.category_responses = {
                        cat: [] for cat in cat_pool
                    }
                    st.session_state.answers_per_skill = answers_per_skill
                    st.session_state.stage            = "interview"
                    st.rerun()
                else:
                    st.error("❌ No questions were generated. This usually means the model returned empty output.")
                    st.info("💡 Try reducing 'Questions per Skill' to 1, or check your internet connection.")
    st.markdown('</div>', unsafe_allow_html=True)


# ================================================================== #
#  STAGE 3 – INTERVIEW                                                 #
# ================================================================== #

elif st.session_state.stage == "interview":
    questions         = st.session_state.questions
    q_index           = st.session_state.q_index
    answers_per_skill = st.session_state.get("answers_per_skill", 9)
    cat_pool          = st.session_state.get("cat_pool", {})
    cat_thetas        = st.session_state.get("category_thetas", {})
    cat_asked         = st.session_state.get("category_asked", {})

    # Total questions student should answer
    total = len(cat_pool) * answers_per_skill

    if not questions:
        st.warning("No questions available."); st.stop()

    # ── IRT Question Selection ────────────────────────────────────────
    # Pick next question from pool where b ≈ current θ for that category
    # Cycles through categories to ensure all skills are covered
    answered_count = len(st.session_state.evaluations)

    # Determine which category to pick from next (round-robin across categories)
    cats_list    = list(cat_pool.keys())
    n_cats       = len(cats_list)
    current_cat  = cats_list[answered_count % n_cats] if n_cats > 0 else None

    # Count answered questions per category using q_uid keys
    cat_answer_counts = {}
    q_uid_to_cat = {
        q.get("question_id", str(i)): q.get("category", "Other")
        for i, q in enumerate(questions)
    }
    for q_uid_key in st.session_state.evaluations:
        cat_of_q = q_uid_to_cat.get(q_uid_key, "Other")
        cat_answer_counts[cat_of_q] = cat_answer_counts.get(cat_of_q, 0) + 1

    # Find a category that still needs answers
    # Use stored current question if available (persists across reruns within same question)
    stored_q   = st.session_state.get("current_q_irt")
    stored_cat = st.session_state.get("current_cat_irt")

    # Check if stored question is still valid (not yet answered)
    if stored_q and stored_q.get("question_id") not in st.session_state.evaluations:
        q           = stored_q
        current_cat = stored_cat
    else:
        # Pick new question
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
                # Store so it persists on rerun
                st.session_state.current_q_irt   = q
                st.session_state.current_cat_irt = current_cat
                break

    # All categories answered enough questions → go to results
    if q is None:
        st.session_state.stage = "results"
        st.rerun()

    st.markdown("""
    <div class="page-banner">
        <h1>Technical Interview</h1>
        <p>Answer each question thoroughly — you'll get instant AI feedback after each submission</p>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    progress_bar(answered_count, total)

    dc, dc_bg, dc_border = diff_badge(q.get("difficulty","medium"))
    type_icon = {
        "conceptual": "💡",
        "practical":  "🔧",
        "scenario":   "🎬",
        "project":    "🗂️",
    }.get(q.get("type",""), "❓")

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

    # ── Confidence badge — shown below every non-project question ── #
    render_confidence_badge(q)

    if q.get("hints"):
        if st.checkbox("💡 Show a hint", key=f"hint_{q.get('question_id', q_index)}"):
            hints_html = "".join(f"<li style='margin-bottom:4px'>{h}</li>" for h in q["hints"])
            st.markdown(
                f'<div class="hint-box"><b>Hints:</b>'
                f'<ul style="margin:6px 0 0;padding-left:1.3rem">{hints_html}</ul></div>',
                unsafe_allow_html=True)

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    q_uid = q.get("question_id", str(q_index))
    prev_answer = st.session_state.answers.get(q_uid, "")
    answer = st.text_area("Your Answer", value=prev_answer, height=180,
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
                        model_answer=q.get("model_answer",""),
                        skill=q.get("skill",""))
                st.session_state.evaluations[q_uid] = result

                # ── IRT θ update ──────────────────────────────────────
                cat        = current_cat or q.get("category", "Other")
                b_param    = float(q.get("b_param", 0.0))
                score      = result.get("total_score", 0)
                frac_correct = score / 100.0   # fractional correct (0.0-1.0)

                if cat in st.session_state.get("category_thetas", {}):
                    theta_before = st.session_state.category_thetas[cat]
                    p_pred       = irt.p_correct(theta_before, b_param)
                    surprise     = frac_correct - p_pred
                    theta_after  = float(
                        max(irt.THETA_MIN,
                            min(irt.THETA_MAX,
                                theta_before + irt.ALPHA * surprise))
                    )
                    st.session_state.category_thetas[cat] = theta_after

                    # Track response for SE calculation
                    st.session_state.category_responses[cat].append({
                        "theta_before": theta_before,
                        "b_used":       b_param,
                        "frac_correct": frac_correct,
                        "surprise":     surprise,
                        "theta_after":  theta_after,
                    })
                    # Mark question as asked in IRT pool
                    st.session_state.category_asked[cat].add(q_uid)

                    result["irt"] = {
                        "theta_before":  round(theta_before, 3),
                        "theta_after":   round(theta_after, 3),
                        "b_param":       b_param,
                        "p_correct_irt": round(p_pred, 3),
                        "surprise":      round(surprise, 3),
                        "proficiency":   irt.theta_to_proficiency(theta_after),
                        "se":            irt.se_theta(
                                            st.session_state.category_responses[cat]
                                         ),
                    }
                    st.session_state.evaluations[q_uid] = result

                # Do NOT rerun — stay on this page to show feedback
                # User clicks "Next Question →" to move forward
    with col_next:
        if st.button("Next Question →", use_container_width=True,
                     type="primary" if q_uid in st.session_state.evaluations else "secondary"):
            # Clear stored question so IRT picks a new one
            st.session_state.current_q_irt   = None
            st.session_state.current_cat_irt = None
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    if q_uid in st.session_state.evaluations:
        ev      = st.session_state.evaluations[q_uid]
        likert  = ev.get("likert", 0)
        emoji   = ev.get("likert_emoji", "")
        label   = ev.get("likert_label", "")
        color   = ev.get("likert_color", "#64748b")
        score   = ev.get("total_score", 0)

        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Your Feedback</div>', unsafe_allow_html=True)

        # ── Likert rating display ─────────────────────────────────── #
        st.markdown(f'''
        <div style="display:flex;align-items:center;gap:20px;
                    background:#f8fafc;border-radius:12px;padding:1rem 1.4rem;
                    border:2px solid {color};margin-bottom:1rem">
            <div style="font-size:2.5rem">{emoji}</div>
            <div>
                <div style="font-size:0.75rem;color:#64748b;font-weight:600;
                            letter-spacing:0.08em;text-transform:uppercase">
                    AI Rating
                </div>
                <div style="font-size:1.4rem;font-weight:800;color:{color}">
                    {likert}/5 — {label}
                </div>
                <div style="font-size:0.82rem;color:#64748b;margin-top:2px">
                    Score: {score}/100
                </div>
            </div>
            <div style="margin-left:auto;display:flex;gap:6px">
                {" ".join([
                    f'<span style="font-size:1.4rem;opacity:{1.0 if i <= likert else 0.2}">⭐</span>'
                    for i in range(1, 6)
                ])}
            </div>
        </div>''', unsafe_allow_html=True)

        # ── Strengths and Improvements ───────────────────────────── #
        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
        col_s, col_i = st.columns(2)
        with col_s:
            st.markdown('<div class="section-label">💪 Strengths</div>', unsafe_allow_html=True)
            for s in ev.get("strengths", []):
                st.markdown(f'<div class="fb-strength"><span>✓</span> {s}</div>',
                            unsafe_allow_html=True)
        with col_i:
            st.markdown('<div class="section-label">📈 To Improve</div>', unsafe_allow_html=True)
            for imp in ev.get("improvements", []):
                st.markdown(f'<div class="fb-improve"><span>→</span> {imp}</div>',
                            unsafe_allow_html=True)

        # ── Detailed feedback ────────────────────────────────────── #
        with st.expander("📝 Read detailed feedback"):
            st.write(ev.get("detailed_feedback", ""))
            if ev.get("correct_answer_summary"):
                st.markdown(f"""
                <div style="background:#eef2ff;border:1.5px solid #c7d2fe;
                            border-radius:10px;padding:12px 16px;margin-top:10px">
                    <b style="color:#4338ca">Ideal Answer:</b>
                    <span style="color:#1e1b4b"> {ev['correct_answer_summary']}</span>
                </div>""", unsafe_allow_html=True)

        # ── IRT ability update display ───────────────────────── #
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
                <span style="color:{color};font-weight:700">
                    {arrow} {abs(dth):.3f}
                </span>
                &nbsp;·&nbsp;
                <span style="background:{color};color:white;
                             border-radius:4px;padding:1px 8px;font-size:0.78rem">
                    {prof['label']}
                </span>
                &nbsp;·&nbsp;
                SE(θ) = {se:.3f}
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


# ================================================================== #
#  STAGE 4 – RESULTS                                                   #
# ================================================================== #

elif st.session_state.stage == "results":
    questions   = st.session_state.questions
    evaluations = st.session_state.evaluations

    if not evaluations:
        st.info("No answers evaluated yet."); st.stop()

    # evaluations keyed by question_id (q_uid)
    ev_list = list(evaluations.values())
    # match questions to evaluations by question_id
    q_uid_to_q = {q.get("question_id", str(i)): q for i, q in enumerate(questions)}
    q_list = [q_uid_to_q.get(uid, {}) for uid in evaluations.keys()]
    summary     = answer_eval.compute_session_summary(ev_list, q_list)

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

    # ── IRT Proficiency Section ──────────────────────────────────── #
    cat_thetas = st.session_state.get("category_thetas", {})
    cat_responses = st.session_state.get("category_responses", {})
    if cat_thetas:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">🧠 Skill Proficiency (IRT)</div>',
                    unsafe_allow_html=True)

        overall_theta = irt.compute_overall_theta(cat_thetas)
        overall_prof  = irt.theta_to_proficiency(overall_theta)
        oc, obg       = overall_prof["color"], "#f8fafc"

        st.markdown(f"""
        <div style="background:#f0f4ff;border-radius:10px;
                    padding:0.8rem 1.2rem;margin-bottom:1rem;
                    border-left:4px solid {oc}">
            <b>Overall θ = {overall_theta:+.3f}</b>
            &nbsp;→&nbsp;
            <span style="background:{oc};color:white;border-radius:4px;
                         padding:2px 10px;font-size:0.82rem;font-weight:700">
                {overall_prof['label']}
            </span>
            &nbsp;·&nbsp;
            <span style="font-size:0.82rem;color:#64748b">
                {overall_prof['score']:.1f}% proficiency
            </span>
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
                    <div style="font-size:0.82rem;font-weight:700;color:#1e1b4b;
                                margin-bottom:6px">{cat.split()[0]}</div>
                    <div style="font-size:1.4rem;font-weight:800;color:{color}">
                        {prof['score']:.0f}%
                    </div>
                    <div style="background:{color};color:white;border-radius:4px;
                                padding:2px 8px;font-size:0.72rem;font-weight:700;
                                display:inline-block;margin:4px 0">
                        {prof['label']}
                    </div>
                    <div style="font-size:0.72rem;color:#94a3b8;margin-top:4px">
                        θ = {theta:+.3f} · SE = {se:.2f}
                    </div>
                    <div style="font-size:0.72rem;color:#94a3b8">
                        {n_ans} question(s) answered
                    </div>
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

    # ── Likert self-assessment summary ───────────────────────────── #
    if summary.get("likert_submitted", 0) > 0:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">📊 Self-Assessment Calibration</div>', unsafe_allow_html=True)
        lc1, lc2, lc3, lc4 = st.columns(4)
        avg_ss = summary.get("avg_self_assessment", 0)
        with lc1:
            st.markdown(f'''<div class="metric-card" style="border-top-color:#7c3aed">
                <div class="metric-val" style="color:#7c3aed">{avg_ss}/10</div>
                <div class="metric-label">Avg Self-Score</div></div>''', unsafe_allow_html=True)
        with lc2:
            st.markdown(f'''<div class="metric-card" style="border-top-color:#16a34a">
                <div class="metric-val" style="color:#16a34a">{summary["accurate_count"]}</div>
                <div class="metric-label">Accurate ✅</div></div>''', unsafe_allow_html=True)
        with lc3:
            st.markdown(f'''<div class="metric-card" style="border-top-color:#d97706">
                <div class="metric-val" style="color:#d97706">{summary["overconfident_count"]}</div>
                <div class="metric-label">Overconfident ⚠️</div></div>''', unsafe_allow_html=True)
        with lc4:
            st.markdown(f'''<div class="metric-card" style="border-top-color:#3b82f6">
                <div class="metric-val" style="color:#3b82f6">{summary["underconfident_count"]}</div>
                <div class="metric-label">Underconfident 💡</div></div>''', unsafe_allow_html=True)
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
            f"{conf_icon} {confidence.capitalize()} confidence"
        ):
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
                for i in range(1, 6)
            ])
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
            col_a, col_b = st.columns(2)
            with col_a:
                for s in ev.get("strengths", []):
                    st.markdown(f'<div class="fb-strength"><span>✓</span> {s}</div>', unsafe_allow_html=True)
            with col_b:
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
        for k, v in defaults.items():
            st.session_state[k] = v
        st.rerun()