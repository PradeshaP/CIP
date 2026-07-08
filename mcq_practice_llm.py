"""
mcq_practice_llm.py
────────────────────────────────────────────────────────────────────────────
LLM-Powered MCQ Practice  (NO IRT / NO Rasch)
────────────────────────────────────────────────────────────────────────────

FLOW:
  1. Domains are selected (name comes from the shared profile in session state)
  2. Picks number of questions (10–15)
  3. Groq (LLaMA-3.3-70B) generates fresh MCQs
  4. Student answers questions one by one
  5. Final score card: total correct, % score, per-domain breakdown,
     question-by-question review with explanations

GROQ MODEL : llama3-70b-8192
API KEY    : GROQ_API_KEY env variable
────────────────────────────────────────────────────────────────────────────
"""

import os
import json
import time
import html as html_module
import streamlit as st
from groq import Groq

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

GROQ_MODEL = "llama-3.1-8b-instant"

DOMAINS = {
    "Python":            "🐍",
    "DSA":               "🌲",
    "SQL":               "🗄️",
    "OOPs":              "🧱",
    "JavaScript":        "🌐",
    "Machine Learning":  "🤖",
    "DevOps":            "⚙️",
    "Operating Systems": "💻",
    "Computer Networks": "🔗",
    "DBMS":              "🗃️",
    "System Design":     "🏗️",
    "Web Development":   "🕸️",
}

SCORE_BANDS = [
    (90, 100, "Outstanding 🏆", "#16a34a", "#dcfce7"),
    (75,  89, "Excellent 🌟",   "#4f46e5", "#eef2ff"),
    (60,  74, "Good 👍",        "#0891b2", "#e0f2fe"),
    (45,  59, "Average 📘",     "#d97706", "#fef3c7"),
    (  0, 44, "Needs Work 📚",  "#dc2626", "#fee2e2"),
]

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULTS = {
    "pllm_stage":         "home",   # home | generating | quiz | results
    "pllm_domains":       [],
    "pllm_n_questions":   10,
    "pllm_questions":     [],
    "pllm_q_index":       0,
    "pllm_answers":       {},       # {q_index: selected_option}
    "pllm_temp_selected": set(),
}

def _init_state():
    for k, v in _DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

def _reset():
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

def _inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .stApp { background: #f0f4ff; }

    .pllm-banner {
        background: linear-gradient(135deg, #0f172a 0%, #4f46e5 55%, #7c3aed 100%);
        border-radius: 16px; padding: 2rem 2.4rem; margin-bottom: 1.5rem;
    }
    .pllm-banner h1 { margin: 0 0 .3rem; font-size: 1.75rem; font-weight: 800;
        letter-spacing: -.02em; color: white; }
    .pllm-banner p  { margin: 0; font-size: .9rem; opacity: .85; color: white; }

    .pllm-card {
        background: white; border-radius: 16px; padding: 1.6rem 2rem; margin-bottom: 1.2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,.06), 0 4px 16px rgba(79,70,229,.07);
    }
    .pllm-label {
        font-size: .68rem; font-weight: 700; letter-spacing: .1em;
        text-transform: uppercase; color: #6366f1; margin-bottom: .75rem;
    }
    .pllm-prog-wrap {
        background: #e0e7ff; border-radius: 99px; height: 8px;
        overflow: hidden; margin: .5rem 0 1.4rem;
    }
    .pllm-prog-fill {
        height: 100%; border-radius: 99px;
        background: linear-gradient(90deg, #4f46e5, #7c3aed);
    }
    .pllm-q-card {
        background: white; border-radius: 14px; padding: 1.6rem 2rem;
        border-left: 5px solid #4f46e5; margin-bottom: 1.2rem;
        box-shadow: 0 2px 12px rgba(79,70,229,.09);
    }
    .pllm-q-meta {
        font-size: .7rem; font-weight: 700; color: #6366f1;
        letter-spacing: .1em; text-transform: uppercase; margin-bottom: .55rem;
    }
    .pllm-q-text {
        font-size: 1.06rem; font-weight: 600; color: #1e1b4b; line-height: 1.65;
    }
    .pllm-expl {
        background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 10px;
        padding: .8rem 1rem; font-size: .87rem; color: #3730a3; margin-top: .7rem;
    }
    .pllm-metric {
        background: white; border-radius: 14px; padding: 1.3rem 1rem;
        text-align: center; border-top: 4px solid;
        box-shadow: 0 1px 6px rgba(0,0,0,.06);
    }
    .pllm-metric-val   { font-size: 1.8rem; font-weight: 800; line-height: 1; margin-bottom: 4px; }
    .pllm-metric-label { font-size: .72rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: .07em; color: #94a3b8; }
    .pllm-bar-track {
        background: #e0e7ff; border-radius: 999px; height: 10px; overflow: hidden;
    }
    .pllm-bar-fill { height: 10px; border-radius: 999px; }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# GROQ — QUESTION GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def _build_prompt(domain: str, n: int) -> str:
    return f"""You are an expert technical interviewer for campus placements.

Generate exactly {n} multiple-choice questions on the topic "{domain}".

Rules:
- Each question must have exactly 4 options labelled a, b, c, d
- Only ONE option is correct
- All 4 options must be plausible (no obviously silly distractors)
- Questions must be factually accurate
- Cover different sub-topics within {domain}
- Mix difficulty: some easy, some medium, some hard
- Explanation must be 1-2 sentences, clear and educational

Return ONLY a valid JSON array. No markdown, no backticks, no extra text.

[
  {{
    "question_text": "...",
    "option_a": "...",
    "option_b": "...",
    "option_c": "...",
    "option_d": "...",
    "correct_option": "a",
    "explanation": "...",
    "difficulty": "easy"
  }}
]"""


def _generate_for_domain(domain: str, n: int) -> tuple:
    """Returns (list_of_questions, error_string)."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return [], "GROQ_API_KEY not found in environment variables."
    try:
        client   = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": _build_prompt(domain, n)}],
            temperature=0.7,
            max_tokens=4096,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if model wraps output
        if "```" in raw:
            parts = raw.split("```")
            for p in parts:
                p = p.strip()
                if p.startswith("json"):
                    p = p[4:].strip()
                if p.startswith("["):
                    raw = p
                    break

        questions = json.loads(raw)
        if not isinstance(questions, list):
            return [], f"Unexpected format for {domain}"

        clean = []
        for i, q in enumerate(questions):
            if not isinstance(q, dict):
                continue
            required = ["question_text", "option_a", "option_b",
                        "option_c", "option_d", "correct_option"]
            if not all(k in q for k in required):
                continue
            q["question_id"] = f"{domain}_{i}_{int(time.time())}"
            q["skill"]       = domain
            q["difficulty"]  = q.get("difficulty", "medium").lower()
            q["explanation"] = q.get("explanation", "")
            clean.append(q)

        return clean, ""

    except json.JSONDecodeError as e:
        return [], f"JSON parse error ({domain}): {e}"
    except Exception as e:
        return [], f"API error ({domain}): {e}"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _score_band(pct: int):
    for lo, hi, label, color, bg in SCORE_BANDS:
        if lo <= pct <= hi:
            return label, color, bg
    return "Needs Work 📚", "#dc2626", "#fee2e2"


def _get_student_name() -> str:
    """Pull name from the shared profile set in the sidebar."""
    return st.session_state.get("student_name", "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE: HOME
# ─────────────────────────────────────────────────────────────────────────────

def _stage_home():
    student_name = _get_student_name()

    st.markdown(f"""
    <div class="pllm-banner">
        <h1>🧠 AI-Powered MCQ Practice</h1>
        <p>Pick your domains · LLaMA 3.3-70B generates fresh questions · Get your score instantly</p>
    </div>""", unsafe_allow_html=True)

    # ── Show who is practising ────────────────────────────────────────────────
    if student_name:
        st.markdown(
            f"<div style='background:#eef2ff;border-radius:10px;padding:10px 16px;"
            f"margin-bottom:1rem;font-size:.9rem;color:#3730a3'>"
            f"👤 Practising as <b>{html_module.escape(student_name)}</b>"
            f"</div>",
            unsafe_allow_html=True)
    else:
        st.warning("⚠️ No profile found. Please save your name and email in the sidebar before continuing.")
        st.stop()

    # ── Domain selection ──────────────────────────────────────────────────────
    st.markdown('<div class="pllm-card">', unsafe_allow_html=True)
    st.markdown('<div class="pllm-label">Step 1 — Select Domains</div>',
                unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:.87rem;color:#475569;margin-bottom:.9rem'>"
        "Choose one or more domains. LLaMA will generate brand-new questions every session.</p>",
        unsafe_allow_html=True)

    domain_list  = list(DOMAINS.keys())
    cols_per_row = 4
    for row_start in range(0, len(domain_list), cols_per_row):
        row  = domain_list[row_start : row_start + cols_per_row]
        cols = st.columns(len(row))
        for col, domain in zip(cols, row):
            icon   = DOMAINS[domain]
            is_sel = domain in st.session_state.pllm_temp_selected
            label  = f"{'✓ ' if is_sel else ''}{icon} {domain}"
            with col:
                if st.button(label, key=f"dom_{domain}", use_container_width=True,
                             type="primary" if is_sel else "secondary"):
                    if is_sel:
                        st.session_state.pllm_temp_selected.discard(domain)
                    else:
                        st.session_state.pllm_temp_selected.add(domain)
                    st.rerun()

    selected = sorted(st.session_state.pllm_temp_selected)
    if selected:
        chips = " ".join(
            f'<span style="background:#eef2ff;color:#4338ca;border-radius:8px;'
            f'padding:4px 12px;font-weight:700;font-size:.82rem;'
            f'display:inline-block;margin:2px">{DOMAINS[d]} {d}</span>'
            for d in selected)
        st.markdown(f"<div style='margin-top:.8rem'><b>Selected:</b> {chips}</div>",
                    unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Question count ────────────────────────────────────────────────────────
    st.markdown('<div class="pllm-card">', unsafe_allow_html=True)
    st.markdown('<div class="pllm-label">Step 2 — Number of Questions</div>',
                unsafe_allow_html=True)

    n_sel = len(selected)
    n_questions = st.slider(
        "Total questions", min_value=10, max_value=15,
        value=st.session_state.pllm_n_questions,
        disabled=(n_sel == 0),
        help="Questions are split equally across your chosen domains.",
    )

    if n_sel > 0:
        per_d = n_questions // n_sel
        extra = n_questions - per_d * n_sel
        parts = []
        for i, d in enumerate(selected):
            n = per_d + (1 if i < extra else 0)
            parts.append(f"<b>{d}</b>: {n}q")
        st.markdown(
            "<div style='font-size:.82rem;color:#64748b;margin-top:.4rem'>"
            "Distribution — " + " &nbsp;·&nbsp; ".join(parts) + "</div>",
            unsafe_allow_html=True)

    with st.expander("📖 How it works"):
        st.markdown("""
- **LLaMA 3.3-70B** generates completely fresh questions every session — no repeats
- Questions cover different sub-topics at mixed difficulty (easy / medium / hard)
- Answer all questions one by one, then get your **score + per-domain breakdown**
- Every question shows the **correct answer + explanation** in the review
        """)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Start button ──────────────────────────────────────────────────────────
    can_start = bool(selected)
    if not selected:
        st.info("👆 Select at least one domain to begin.")

    if st.button("🚀 Generate Questions & Start",
                 type="primary", use_container_width=True, disabled=not can_start):
        st.session_state.pllm_domains     = selected
        st.session_state.pllm_n_questions = n_questions
        st.session_state.pllm_stage       = "generating"
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE: GENERATING
# ─────────────────────────────────────────────────────────────────────────────

def _stage_generating():
    domains     = st.session_state.pllm_domains
    n_questions = st.session_state.pllm_n_questions
    n_domains   = len(domains)
    per_d       = n_questions // n_domains
    extra       = n_questions - per_d * n_domains

    st.markdown("""
    <div class="pllm-banner">
        <h1>⚙️ Generating Questions…</h1>
        <p>LLaMA-3.3-70B is crafting your personalised question set — hang tight!</p>
    </div>""", unsafe_allow_html=True)

    progress = st.progress(0, text="Starting…")
    status   = st.empty()

    all_questions = []
    errors        = []

    for idx, domain in enumerate(domains):
        n_for = per_d + (1 if idx < extra else 0)
        status.info(f"🤖 Generating **{n_for}** question(s) for "
                    f"**{DOMAINS[domain]} {domain}**…")

        qs, err = _generate_for_domain(domain, n_for)

        if err or not qs:
            errors.append(err or f"No questions returned for {domain}")
            # One retry
            qs, err2 = _generate_for_domain(domain, n_for)
            if err2:
                errors.append(f"Retry failed: {err2}")

        all_questions.extend(qs)
        progress.progress((idx + 1) / n_domains,
                          text=f"✅ {domain} done — {idx+1}/{n_domains}")

    status.empty()

    if not all_questions:
        st.error("❌ Could not generate any questions.\n\n" + "\n\n".join(errors[:3]))
        if st.button("← Try Again"):
            st.session_state.pllm_stage = "home"
            st.rerun()
        return

    if errors:
        st.warning("⚠️ Some issues:\n" + "\n".join(errors[:2]))

    # Shuffle so domains are interleaved
    import random
    random.shuffle(all_questions)

    st.session_state.pllm_questions = all_questions
    st.session_state.pllm_q_index   = 0
    st.session_state.pllm_answers   = {}

    st.success(f"✅ {len(all_questions)} questions ready!")
    time.sleep(0.5)
    st.session_state.pllm_stage = "quiz"
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE: QUIZ
# ─────────────────────────────────────────────────────────────────────────────

def _stage_quiz():
    questions = st.session_state.pllm_questions
    q_index   = st.session_state.pllm_q_index
    n_total   = len(questions)

    if q_index >= n_total:
        st.session_state.pllm_stage = "results"
        st.rerun()

    q      = questions[q_index]
    pct    = int((q_index / n_total) * 100)
    diff   = q.get("difficulty", "medium")
    domain = q.get("skill", "")
    diff_color = {"easy": "#16a34a", "medium": "#d97706",
                  "hard": "#dc2626"}.get(diff, "#6366f1")

    # Banner
    st.markdown(f"""
    <div class="pllm-banner">
        <h1>📝 MCQ Practice</h1>
        <p>Question {q_index + 1} of {n_total} &nbsp;·&nbsp;
           {DOMAINS.get(domain,'')} {domain}</p>
    </div>""", unsafe_allow_html=True)

    # Progress bar
    st.markdown(
        f'<div class="pllm-prog-wrap">'
        f'<div class="pllm-prog-fill" style="width:{pct}%"></div>'
        f'</div>', unsafe_allow_html=True)

    # Domain progress pills
    domain_counts = {}
    for a_idx in st.session_state.pllm_answers:
        d = questions[a_idx].get("skill", "")
        domain_counts[d] = domain_counts.get(d, 0) + 1
    domain_total = {}
    for q_ in questions:
        d = q_.get("skill", "")
        domain_total[d] = domain_total.get(d, 0) + 1

    pills = ""
    for d in st.session_state.pllm_domains:
        asked = domain_counts.get(d, 0)
        total = domain_total.get(d, 0)
        done  = (asked >= total and total > 0)
        color = "#16a34a" if done else "#4f46e5"
        bg    = "#dcfce7" if done else "#eef2ff"
        pills += (
            f'<span style="background:{bg};color:{color};border-radius:8px;'
            f'padding:4px 11px;font-weight:700;font-size:.78rem;'
            f'margin:3px;display:inline-block">'
            f'{"✓ " if done else ""}{DOMAINS.get(d,"")} {d} ({asked}/{total})'
            f'</span>')
    st.markdown(f'<div style="margin-bottom:1rem">{pills}</div>',
                unsafe_allow_html=True)

    # Question card
    st.markdown(f"""
    <div class="pllm-q-card">
        <div class="pllm-q-meta">
            Q{q_index + 1} &nbsp;·&nbsp; {DOMAINS.get(domain,'')} {domain}
            &nbsp;·&nbsp;
            <span style="color:{diff_color}">{diff.upper()}</span>
        </div>
        <div class="pllm-q-text">{html_module.escape(q.get('question_text',''))}</div>
    </div>""", unsafe_allow_html=True)

    option_map = {
        "a": q.get("option_a", ""),
        "b": q.get("option_b", ""),
        "c": q.get("option_c", ""),
        "d": q.get("option_d", ""),
    }

    choice = st.radio(
        "Select your answer:",
        options=["a", "b", "c", "d"],
        format_func=lambda k: f"{k.upper()}.  {option_map[k]}",
        index=None,
        key=f"pllm_radio_{q_index}_{q.get('question_id','')}",
        label_visibility="collapsed",
    )

    is_last   = (q_index == n_total - 1)
    btn_label = "Submit & Finish →" if is_last else "Next Question →"

    if st.button(btn_label, type="primary",
                 use_container_width=True, disabled=(choice is None)):
        st.session_state.pllm_answers[q_index] = choice
        if is_last:
            st.session_state.pllm_stage = "results"
        else:
            st.session_state.pllm_q_index += 1
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE: RESULTS
# ─────────────────────────────────────────────────────────────────────────────

def _stage_results():
    questions    = st.session_state.pllm_questions
    answers      = st.session_state.pllm_answers
    student_name = _get_student_name() or "Student"
    domains      = st.session_state.pllm_domains

    if not questions:
        st.warning("No questions found.")
        _reset()
        st.rerun()

    # ── Compute scores ────────────────────────────────────────────────────────
    total_qs      = len(questions)
    total_correct = 0
    domain_stats  = {d: {"correct": 0, "total": 0, "qs": []} for d in domains}

    for idx, q in enumerate(questions):
        selected = answers.get(idx)
        correct  = q.get("correct_option")
        is_right = (selected == correct)
        if is_right:
            total_correct += 1
        d = q.get("skill", "")
        if d in domain_stats:
            domain_stats[d]["total"] += 1
            domain_stats[d]["correct"] += int(is_right)
            domain_stats[d]["qs"].append({
                "idx":         idx,
                "question":    q.get("question_text", ""),
                "selected":    selected,
                "correct":     correct,
                "is_correct":  is_right,
                "explanation": q.get("explanation", ""),
                "difficulty":  q.get("difficulty", "medium"),
                "options": {
                    "a": q.get("option_a",""), "b": q.get("option_b",""),
                    "c": q.get("option_c",""), "d": q.get("option_d",""),
                },
            })

    score_pct               = round(total_correct / total_qs * 100) if total_qs else 0
    band_label, band_color, band_bg = _score_band(score_pct)

    # ── Result banner ─────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1e1b4b 0%,#4338ca 60%,#7c3aed 100%);
                border-radius:16px;padding:2.2rem 2.4rem;margin-bottom:1.5rem;text-align:center">
        <div style="font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;
                    color:#a5b4fc;margin-bottom:.5rem">PRACTICE COMPLETE</div>
        <div style="font-size:1.5rem;font-weight:800;color:white;margin-bottom:1.2rem">
            {html_module.escape(student_name)}
        </div>
        <div style="display:inline-flex;flex-direction:column;align-items:center;
                    justify-content:center;width:140px;height:140px;border-radius:50%;
                    border:6px solid {band_color};background:{band_bg};margin:0 auto .9rem">
            <div style="font-size:2.6rem;font-weight:800;color:{band_color};line-height:1">
                {score_pct}%
            </div>
            <div style="font-size:.76rem;color:#64748b;margin-top:3px">
                {total_correct}/{total_qs}
            </div>
        </div>
        <br>
        <span style="display:inline-block;background:{band_bg};color:{band_color};
                     border-radius:999px;padding:7px 24px;font-weight:700;font-size:1rem;
                     margin-top:.4rem">
            {band_label}
        </span>
    </div>""", unsafe_allow_html=True)

    # ── Summary metrics ───────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    for col, (val, label, color) in zip(
        [c1, c2, c3, c4],
        [
            (str(total_qs),                    "Total Questions", "#4f46e5"),
            (str(total_correct),               "Correct",         "#16a34a"),
            (str(total_qs - total_correct),    "Wrong",           "#dc2626"),
            (f"{score_pct}%",                  "Score",           band_color),
        ]
    ):
        with col:
            st.markdown(f"""
            <div class="pllm-metric" style="border-top-color:{color}">
                <div class="pllm-metric-val" style="color:{color}">{val}</div>
                <div class="pllm-metric-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Per-domain breakdown (only when >1 domain) ────────────────────────────
    if len(domains) > 1:
        st.markdown('<div class="pllm-card">', unsafe_allow_html=True)
        st.markdown('<div class="pllm-label">Per-Domain Breakdown</div>',
                    unsafe_allow_html=True)
        for domain in domains:
            stats = domain_stats.get(domain, {"correct": 0, "total": 0})
            if stats["total"] == 0:
                continue
            d_pct = round(stats["correct"] / stats["total"] * 100)
            _, d_color, d_bg = _score_band(d_pct)
            st.markdown(f"""
            <div style="margin-bottom:1.1rem">
                <div style="display:flex;justify-content:space-between;
                            align-items:center;margin-bottom:5px">
                    <span style="font-weight:700;color:#1e1b4b;font-size:.95rem">
                        {DOMAINS.get(domain,'')} {domain}
                    </span>
                    <div style="display:flex;align-items:center;gap:10px">
                        <span style="font-size:.82rem;color:#64748b">
                            {stats['correct']}/{stats['total']} correct
                        </span>
                        <span style="background:{d_bg};color:{d_color};border-radius:999px;
                                     padding:3px 14px;font-weight:700;font-size:.82rem">
                            {d_pct}%
                        </span>
                    </div>
                </div>
                <div class="pllm-bar-track">
                    <div class="pllm-bar-fill" style="width:{d_pct}%;background:{d_color}"></div>
                </div>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Question-by-question review ───────────────────────────────────────────
    st.markdown('<div class="pllm-card">', unsafe_allow_html=True)
    st.markdown('<div class="pllm-label">Question Review</div>', unsafe_allow_html=True)

    for idx, q in enumerate(questions):
        selected   = answers.get(idx)
        correct    = q.get("correct_option")
        is_correct = (selected == correct)
        domain     = q.get("skill", "")
        diff       = q.get("difficulty", "medium")
        icon       = "✅" if is_correct else "❌"

        with st.expander(
            f"{icon} Q{idx+1} · {DOMAINS.get(domain,'')} {domain} · "
            f"{diff.upper()} · {'Correct' if is_correct else 'Wrong'}"
        ):
            st.markdown(f"**{html_module.escape(q.get('question_text',''))}**")
            st.markdown("---")

            opts = {
                "a": q.get("option_a",""), "b": q.get("option_b",""),
                "c": q.get("option_c",""), "d": q.get("option_d",""),
            }
            for k, v in opts.items():
                if k == correct and k == selected:
                    st.markdown(
                        f"<div style='background:#dcfce7;border:1.5px solid #86efac;"
                        f"border-radius:8px;padding:8px 14px;margin:4px 0;"
                        f"font-weight:600;color:#15803d'>"
                        f"✅ {k.upper()}. {html_module.escape(v)}"
                        f" &nbsp;<i>(your answer — correct)</i></div>",
                        unsafe_allow_html=True)
                elif k == correct:
                    st.markdown(
                        f"<div style='background:#dcfce7;border:1.5px solid #86efac;"
                        f"border-radius:8px;padding:8px 14px;margin:4px 0;"
                        f"font-weight:600;color:#15803d'>"
                        f"✅ {k.upper()}. {html_module.escape(v)}"
                        f" &nbsp;<i>(correct answer)</i></div>",
                        unsafe_allow_html=True)
                elif k == selected:
                    st.markdown(
                        f"<div style='background:#fee2e2;border:1.5px solid #fca5a5;"
                        f"border-radius:8px;padding:8px 14px;margin:4px 0;"
                        f"font-weight:600;color:#dc2626'>"
                        f"❌ {k.upper()}. {html_module.escape(v)}"
                        f" &nbsp;<i>(your answer)</i></div>",
                        unsafe_allow_html=True)
                else:
                    st.markdown(
                        f"<div style='background:#f8fafc;border:1px solid #e2e8f0;"
                        f"border-radius:8px;padding:8px 14px;margin:4px 0;color:#475569'>"
                        f"{k.upper()}. {html_module.escape(v)}</div>",
                        unsafe_allow_html=True)

            if q.get("explanation"):
                st.markdown(
                    f'<div class="pllm-expl">💡 {html_module.escape(q["explanation"])}</div>',
                    unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Action buttons ────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔁 Practice Again (same domains)",
                     type="primary", use_container_width=True):
            prev_domains = st.session_state.pllm_domains
            prev_n       = st.session_state.pllm_n_questions
            _reset()
            st.session_state.pllm_domains        = prev_domains
            st.session_state.pllm_n_questions    = prev_n
            st.session_state.pllm_temp_selected  = set(prev_domains)
            st.session_state.pllm_stage          = "generating"
            st.rerun()
    with col_b:
        if st.button("🏠 Choose New Domains", use_container_width=True):
            _reset()
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT  (called from main_app.py)
# ─────────────────────────────────────────────────────────────────────────────

def render_llm_mcq_practice():
    """
    Call this from main_app.py inside the MCQ Practice mode block:

        import mcq_practice_llm as pllm
        ...
        elif mode == "mcq":
            pllm.render_llm_mcq_practice()
    """
    _inject_css()
    _init_state()

    stage = st.session_state.pllm_stage
    if   stage == "home":       _stage_home()
    elif stage == "generating": _stage_generating()
    elif stage == "quiz":       _stage_quiz()
    elif stage == "results":    _stage_results()
    else:
        st.session_state.pllm_stage = "home"
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE  —  streamlit run mcq_practice_llm.py
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    st.set_page_config(
        page_title="AI MCQ Practice",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    # When run standalone, prompt for a name since there's no shared profile
    if "student_name" not in st.session_state or not st.session_state.student_name:
        st.markdown("## 🧠 AI MCQ Practice")
        name = st.text_input("Your name", placeholder="e.g. Priya S")
        if st.button("Continue →", disabled=not name.strip()):
            st.session_state.student_name = name.strip()
            st.rerun()
        st.stop()
    render_llm_mcq_practice()