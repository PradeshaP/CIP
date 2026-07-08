# 🚀 Adaptive Interview Prep Platform

An AI-powered interview preparation platform that analyzes a candidate's resume and generates **personalized, adaptive interview questions** — combining LLM-based question generation with an **Item Response Theory (IRT / Rasch Model)** engine to adjust difficulty in real time based on performance.

Built with **Python, Streamlit, and PostgreSQL**.

---

## 📋 Overview

Traditional mock-interview tools ask the same static question bank to every candidate. This platform instead:

1. **Reads your resume** (PDF / DOCX / TXT) and extracts your skills and projects using NLP + semantic matching.
2. **Generates tailored questions** — conceptual, practical, scenario-based, and project-based — for each detected skill using an LLM.
3. **Adapts question difficulty on the fly** using a Rasch/IRT model: get something right, the next question gets harder; struggle, and it eases up — just like a real adaptive assessment.
4. **Scores open-ended answers automatically**, giving a 0–100 score, strengths, areas to improve, and a model answer.
5. **Tracks everything in PostgreSQL** — sessions, skill proficiency (θ), assessment history, and a unified leaderboard across modes.

---

## ✨ Features

The app runs as a single Streamlit application (`main_app.py`) with **three modes**, switchable from the sidebar:

### 🎤 AI Interview
- Upload a resume → skills/projects auto-extracted and shown as tagged pills.
- Configure number of questions per skill and whether to include project-based questions.
- Answer free-text questions one at a time; each answer is evaluated instantly by an LLM (score, strengths, improvements, model answer).
- An **IRT engine (Rasch Model)** tracks a per-category ability score (θ) and dynamically selects the next question's difficulty based on your running performance.
- Full results dashboard at the end, with per-category proficiency breakdown.

### 🧠 AI MCQ Practice
- LLM-generated multiple-choice questions for skill-based practice with instant feedback.

### 🏆 MCQ Test
- A fixed-bank timed test mode with scoring and a **leaderboard** (gold/silver/bronze ranking) across all test-takers.

### 🧮 Adaptive Difficulty Engine (IRT / Rasch Model)
- Maintains a per-skill/category ability estimate (θ).
- After each answer, updates θ based on the "surprise" between predicted and actual performance (`p_correct` vs. actual score).
- Selects the next question by matching the question's difficulty parameter (`b`) to the candidate's current θ.
- Reports live diagnostics: θ before/after, standard error of θ, and predicted probability of a correct answer.

### 🗄️ Database Layer (PostgreSQL)
- Persists user sessions, resumes-derived skills, open-ended responses, MCQ practice/test history, and a unified cross-mode leaderboard.
- See [`DATABASE_INTEGRATION.md`](./DATABASE_INTEGRATION.md) and `db_schema.sql` for schema details.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend / App | Streamlit |
| Backend logic | Python |
| Database | PostgreSQL |
| AI / NLP | LLM-based question generation & answer evaluation, semantic skill extraction |
| Adaptive testing | Custom Rasch/IRT engine (`mcq_irt/rasch_engine.py`) |

---

## 📁 Project Structure

```
├── main_app.py                 # Unified Streamlit app (entry point — 3-mode switcher)
├── enhanced_app.py              # AI Interview mode logic
├── mcq_practice_llm.py          # LLM-based MCQ practice mode
├── resume_parser.py             # Extracts text from PDF/DOCX/TXT resumes
├── enhanced_skill_extractor.py  # NLP + semantic skill/category extraction
├── question_generator.py        # LLM-based question generation per skill
├── answer_evaluator.py          # LLM-based scoring of open-ended answers
├── mcq_irt/
│   └── rasch_engine.py          # IRT/Rasch adaptive difficulty engine
├── open_ended_database.py       # DB layer — open-ended sessions/responses
├── final_database.py            # DB layer — unified/combined session records
├── test_database.py             # DB layer — MCQ test mode + leaderboard
├── db_schema.sql                 # PostgreSQL schema
├── DATABASE_INTEGRATION.md      # Database design notes
├── setup_mcq.py                  # MCQ test bank setup script
├── test_data.json                # Sample MCQ test question bank
└── requirements_enhanced.txt     # Python dependencies
```

---

## ⚙️ Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/PradeshaP/Adaptive-Interview-Prep-Platform.git
cd Adaptive-Interview-Prep-Platform
```

### 2. Install dependencies
```bash
pip install -r requirements_enhanced.txt
```

### 3. Configure environment variables
Create a `.env` file in the project root with your database and LLM API credentials, e.g.:
```
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<db_name>
GROQ_API_KEY=your_api_key_here
```

### 4. Set up the PostgreSQL database
Run the schema against your database:
```bash
psql -U <user> -d <db_name> -f db_schema.sql
```

### 5. Run the app
```bash
streamlit run main_app.py
```

The app will launch in your browser at `http://localhost:8501`.

---

## 🎯 How It Works (Flow)

1. **Sign in** with your name and email (sidebar).
2. **Upload your resume** → skills & projects are extracted and categorized.
3. **Configure your session** — choose how many questions per skill, and whether to include project-based questions.
4. **Answer questions** one at a time. Each response is:
   - Scored by an LLM-based evaluator (0–100)
   - Used to update your ability estimate (θ) for that skill category via the Rasch model
   - Used to pick the next question's difficulty
5. **View your results** — overall grade, per-skill proficiency, strengths/improvements, and IRT diagnostics.

---


---
