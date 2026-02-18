"""
enhanced_app.py  –  Resume → Skills → AI Interview → Evaluation
"""

import os
import streamlit as st
from enhanced_skill_extractor import EnhancedSkillExtractor
from resume_parser import ResumeParser
from question_generator import QuestionGenerator
from answer_evaluator import AnswerEvaluator

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
.skill-pill-cat {
    display: inline-block; padding: 2px 10px; margin: 2px; border-radius: 4px;
    font-size: 0.68rem; font-weight: 700; background: #f0fdf4;
    color: #16a34a; border: 1px solid #bbf7d0;
    text-transform: uppercase; letter-spacing: 0.06em;
}

.q-card {
    background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
    border: 1.5px solid #c7d2fe; border-radius: 14px;
    padding: 1.4rem 1.6rem; margin-bottom: 1rem;
}
.q-meta { display: flex; gap: 8px; flex-wrap: wrap; font-size: 0.72rem; margin-bottom: 0.8rem; }
.q-meta span { padding: 3px 10px; border-radius: 999px; font-weight: 600; }
.q-num  { background: #4f46e5; color: white; }
.q-skill { background: #7c3aed; color: white; }
.q-text { font-size: 1.05rem; color: #1e1b4b; font-weight: 600; line-height: 1.65; }

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
    return {"easy":("#16a34a","#f0fdf4","#bbf7d0"),
            "medium":("#d97706","#fffbeb","#fde68a"),
            "hard":("#dc2626","#fef2f2","#fecaca")}.get(d, ("#64748b","#f8fafc","#e2e8f0"))

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
    "stage":"upload", "skills_data":None, "questions":[],
    "answers":{}, "evaluations":{}, "q_index":0,
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
        <p>Upload your resume · We extract your skills · AI asks the tough questions · You get scored</p>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Step 1 — Upload Resume</div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader("PDF, DOCX or TXT", type=["pdf","docx","txt"])

    if uploaded_file:
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
            with st.spinner("Analysing resume with NLP…"):
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
                        st.session_state.stage = "configure"
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
        <p>Review what we found in your resume, then configure your interview session</p>
    </div>""", unsafe_allow_html=True)

    skills_data  = st.session_state.skills_data
    total_skills = skills_data["total_skills"]

    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Skills Found</div>', unsafe_allow_html=True)
    st.markdown(f"<p style='font-size:0.9rem;color:#475569;margin-bottom:1rem'>"
                f"<b style='color:#1e1b4b'>{total_skills} skills</b> detected</p>",
                unsafe_allow_html=True)
    for category, skills_list in skills_data["categories"].items():
        if skills_list:
            pills = " ".join(f'<span class="skill-pill">{s["name"]}</span>' for s in skills_list)
            st.markdown(
                f'<div style="margin-bottom:0.9rem">'
                f'<span class="skill-pill-cat">{category}</span>'
                f'<div style="margin-top:6px">{pills}</div></div>',
                unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Interview Settings</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        difficulty = st.selectbox("Difficulty Level", ["easy","medium","hard"],
                                  index=1, format_func=str.capitalize)
    with col2:
        q_per_skill = st.slider("Questions per Skill", 1, 3, 2)

    estimated = total_skills * q_per_skill
    st.markdown(f"""
    <div style="background:#eef2ff;border:1.5px solid #c7d2fe;border-radius:10px;
                padding:12px 18px;margin:1rem 0;display:flex;align-items:center;gap:10px">
        <span style="font-size:1.2rem">📋</span>
        <span style="font-size:0.9rem;color:#3730a3">
            <b>{estimated} questions</b> will be generated for this session
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
                with st.spinner(f"AI is generating {estimated} questions…"):
                    questions = question_gen.generate_questions(
                        skills_data, difficulty=difficulty, questions_per_skill=q_per_skill)
                if questions:
                    st.session_state.questions   = questions
                    st.session_state.q_index     = 0
                    st.session_state.answers     = {}
                    st.session_state.evaluations = {}
                    st.session_state.stage       = "interview"
                    st.rerun()
                else:
                    st.error("Failed to generate questions. Check your Groq API key.")
    st.markdown('</div>', unsafe_allow_html=True)


# ================================================================== #
#  STAGE 3 – INTERVIEW                                                 #
# ================================================================== #

elif st.session_state.stage == "interview":
    questions = st.session_state.questions
    q_index   = st.session_state.q_index
    total     = len(questions)

    if not questions:
        st.warning("No questions available."); st.stop()

    q = questions[q_index]

    st.markdown("""
    <div class="page-banner">
        <h1>Technical Interview</h1>
        <p>Answer each question thoroughly — you'll get instant AI feedback after each submission</p>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    progress_bar(q_index, total)

    dc, dc_bg, dc_border = diff_badge(q.get("difficulty","medium"))
    type_icon = {"conceptual":"💡","practical":"🔧","scenario":"🎬"}.get(q.get("type",""),"❓")

    st.markdown(f"""
    <div class="q-card">
        <div class="q-meta">
            <span class="q-num">Q{q_index+1}</span>
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

    if q.get("hints"):
        if st.checkbox("💡 Show a hint", key=f"hint_{q_index}"):
            hints_html = "".join(f"<li style='margin-bottom:4px'>{h}</li>" for h in q["hints"])
            st.markdown(
                f'<div class="hint-box"><b>Hints:</b>'
                f'<ul style="margin:6px 0 0;padding-left:1.3rem">{hints_html}</ul></div>',
                unsafe_allow_html=True)

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    prev_answer = st.session_state.answers.get(q_index, "")
    answer = st.text_area("Your Answer", value=prev_answer, height=180,
                          placeholder="Write your answer here — be as detailed as possible…",
                          key=f"ans_{q_index}")

    col_prev, col_submit, col_next = st.columns([1, 2, 1])
    with col_prev:
        if q_index > 0:
            if st.button("← Previous", use_container_width=True):
                st.session_state.q_index -= 1; st.rerun()
    with col_submit:
        already_done = q_index in st.session_state.evaluations
        lbl = "Re-evaluate ↺" if already_done else "Submit & Evaluate →"
        if st.button(lbl, type="primary", use_container_width=True):
            if not answer.strip():
                st.warning("Please write an answer first.")
            else:
                st.session_state.answers[q_index] = answer
                with st.spinner("AI is evaluating your answer…"):
                    result = answer_eval.evaluate_answer(
                        question=q["question"], user_answer=answer,
                        model_answer=q.get("model_answer",""),
                        skill=q.get("skill",""), difficulty=q.get("difficulty","medium"))
                st.session_state.evaluations[q_index] = result
                st.rerun()
    with col_next:
        if q_index < total - 1:
            if st.button("Next →", use_container_width=True):
                if q_index not in st.session_state.evaluations and answer.strip():
                    st.session_state.answers[q_index] = answer
                st.session_state.q_index += 1; st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    if q_index in st.session_state.evaluations:
        ev = st.session_state.evaluations[q_index]
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Your Feedback</div>', unsafe_allow_html=True)

        col_sc, col_bd = st.columns([1, 2])
        with col_sc:
            render_score(ev["total_score"], ev["grade"])
        with col_bd:
            render_breakdown(ev.get("breakdown", {}))

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
                <div style="background:#eef2ff;border:1.5px solid #c7d2fe;border-radius:10px;
                            padding:12px 16px;margin-top:10px">
                    <b style="color:#4338ca">Ideal Answer:</b>
                    <span style="color:#1e1b4b"> {ev['correct_answer_summary']}</span>
                </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    answered = len(st.session_state.evaluations)
    if answered > 0:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px">
            <div>
                <div style="font-weight:700;color:#1e1b4b">Ready to see your results?</div>
                <div style="font-size:0.82rem;color:#6b7280">{answered} of {total} questions answered</div>
            </div>
        </div>""", unsafe_allow_html=True)
        if st.button(f"View Full Results ({answered}/{total}) →", type="primary", use_container_width=True):
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

    answered_qs = sorted(evaluations.keys())
    ev_list     = [evaluations[i] for i in answered_qs]
    q_list      = [questions[i]   for i in answered_qs]
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
        with st.expander(
            f"Q{answered_qs[idx]+1}  ·  {q.get('skill','')}  ·  "
            f"{ev['total_score']}/100  ·  {ev['grade']}"
        ):
            st.markdown(f"**Question:** {q.get('question','')}")
            st.markdown(f"**Your Answer:** {st.session_state.answers.get(answered_qs[idx],'—')}")
            st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
            col_sc, col_bd = st.columns([1, 2])
            with col_sc:
                render_score(ev["total_score"], ev["grade"])
            with col_bd:
                render_breakdown(ev.get("breakdown", {}))
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