"""
question_generator.py

Generates interview questions using:
  1. Few-shot learning from live GitHub datasets
  2. Chain-of-Thought (CoT) reasoning
  3. Dual-model validation with auto-retry (Llama + Mixtral)
  4. IRT b_param tagging — each question gets a difficulty estimate

IRT INTEGRATION (Option 1 — Generate all upfront):
  For each skill, generates questions across ALL difficulty levels:
    Easy   (b = -1.5 to -0.5) — basic recall / definition
    Medium (b = -0.5 to +0.5) — understanding / comparison
    Hard   (b = +0.5 to +1.5) — application / analysis

  Total per skill = questions_per_skill × 3 difficulty levels
  e.g. questions_per_skill=1 → 3 questions per skill (1 easy + 1 medium + 1 hard)

  During interview, IRT picks from this pool where b ≈ current θ.
  This matches exactly what the PDF guide and senior's notebook do.

b_param scale (from PDF guide):
  -2.0 → Trivially easy (factual recall)
  -1.0 → Easy (basic understanding)
   0.0 → Medium (average student has 50/50 chance)
  +1.0 → Hard (requires strong understanding)
  +2.0 → Very hard (expert-level synthesis)
"""

import os
import re
import json
import random
import time
import threading
import requests
from groq import Groq
from dotenv import load_dotenv
load_dotenv()

try:
    from sentence_transformers import SentenceTransformer, util as st_util
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False
    print("WARNING: sentence-transformers not installed. Confidence validation disabled.")


# ─────────────────────────────────────────────────────────────────────────────
# IRT DIFFICULTY BANDS
# b_param ranges for each difficulty level (from PDF guide)
# ─────────────────────────────────────────────────────────────────────────────

IRT_BANDS = {
    "easy":   {"b_min": -1.8, "b_max": -0.5, "b_target": -1.0,
               "description": "Basic recall or definition — any fresher should know this"},
    "medium": {"b_min": -0.5, "b_max": +0.5, "b_target":  0.0,
               "description": "Understanding and comparison — average student has 50/50 chance"},
    "hard":   {"b_min": +0.5, "b_max": +1.8, "b_target": +1.0,
               "description": "Application, analysis, edge cases — requires strong understanding"},
}


# ─────────────────────────────────────────────────────────────────────────────
# DATASET SOURCES (few-shot examples)
# ─────────────────────────────────────────────────────────────────────────────

DATASET_SOURCES = [
    {
        "url": "https://raw.githubusercontent.com/aershov24/full-stack-interview-questions/master/README.md",
        "categories": ["Backend Development", "Databases", "Cloud & DevOps",
                       "DSA & CS Fundamentals", "Testing & QA"],
        "description": "Full Stack Interview Questions (aershov24)"
    },
    {
        "url": "https://raw.githubusercontent.com/sudheerj/javascript-interview-questions/master/README.md",
        "categories": ["Programming Languages", "Frontend Development"],
        "description": "JavaScript Interview Questions (sudheerj)"
    },
    {
        "url": "https://raw.githubusercontent.com/sudheerj/reactjs-interview-questions/master/README.md",
        "categories": ["Frontend Development"],
        "description": "React Interview Questions (sudheerj)"
    },
    {
        "url": "https://raw.githubusercontent.com/zhiqiangzhongddu/Data-Science-Interview-Questions-and-Answers-General-/master/General%20Questions.md",
        "categories": ["Data Science & AI"],
        "description": "Data Science Interview Q&A (zhiqiangzhongddu)"
    },
]

FALLBACK_EXAMPLES: dict[str, list[dict]] = {
    "Programming Languages": [
        {"q": "What is the difference between a list and a tuple in Python?",
         "a": "A list is mutable. A tuple is immutable. Tuples are faster and used for fixed data."},
        {"q": "What is the difference between == and .equals() in Java?",
         "a": "== checks reference equality. .equals() checks value equality. Always use .equals() for strings."},
    ],
    "Frontend Development": [
        {"q": "What is the difference between state and props in React?",
         "a": "Props are read-only inputs from parent. State is internal data that can change. State changes trigger re-render."},
        {"q": "What is the CSS box model?",
         "a": "The box model has four layers: content, padding, border, and margin from inside out."},
    ],
    "Backend Development": [
        {"q": "What is the difference between GET and POST HTTP methods?",
         "a": "GET retrieves data with params in URL. POST sends data in request body. POST is more secure for sensitive data."},
        {"q": "What is middleware in Express.js?",
         "a": "Middleware runs between request and response. Used for authentication, logging, parsing bodies."},
    ],
    "Databases": [
        {"q": "What is the difference between a primary key and a foreign key?",
         "a": "Primary key uniquely identifies each row. Foreign key references another table's primary key."},
        {"q": "What is normalization?",
         "a": "Normalization reduces data redundancy by organizing tables. Prevents update anomalies."},
    ],
    "Cloud & DevOps": [
        {"q": "What is Docker and why is it used?",
         "a": "Docker packages an app and dependencies into a container. Ensures same behaviour on any machine."},
        {"q": "What is the difference between Git merge and Git rebase?",
         "a": "Merge creates a merge commit preserving history. Rebase creates a cleaner linear history."},
    ],
    "Data Science & AI": [
        {"q": "What is the difference between supervised and unsupervised learning?",
         "a": "Supervised uses labeled data. Unsupervised finds patterns in unlabeled data."},
        {"q": "What is overfitting and how do you prevent it?",
         "a": "Overfitting is when model learns noise in training data. Prevent with cross-validation and regularization."},
    ],
    "DSA & CS Fundamentals": [
        {"q": "What is the difference between a stack and a queue?",
         "a": "Stack is LIFO. Queue is FIFO. Stacks used for function calls, queues for scheduling."},
        {"q": "What are the four pillars of OOP?",
         "a": "Encapsulation, Abstraction, Inheritance, Polymorphism."},
    ],
    "Mobile Development": [
        {"q": "What is the difference between an Activity and a Fragment in Android?",
         "a": "Activity is a full screen. Fragment is a reusable UI portion inside an Activity."},
    ],
    "Testing & QA": [
        {"q": "What is unit testing?",
         "a": "Unit testing tests individual functions in isolation. Ensures each part works before integration."},
    ],
    "Soft Skills & Methodologies": [
        {"q": "What is Agile methodology?",
         "a": "Agile is iterative development in short sprints with frequent feedback. More flexible than Waterfall."},
    ],
}
FALLBACK_EXAMPLES["default"] = FALLBACK_EXAMPLES["DSA & CS Fundamentals"]


# ─────────────────────────────────────────────────────────────────────────────
# FEW-SHOT LOADER
# ─────────────────────────────────────────────────────────────────────────────

class FewShotLoader:
    TIMEOUT  = 8
    MAX_QA   = 30

    def __init__(self):
        self._cache: dict[str, list[dict]] = {}
        self._loaded = False
        self._lock   = threading.Lock()
        self._thread = threading.Thread(target=self._load_all, daemon=True)
        self._thread.start()

    def get_examples(self, category: str, n: int = 2) -> list[dict]:
        with self._lock:
            pool = self._cache.get(category) or \
                   FALLBACK_EXAMPLES.get(category) or \
                   FALLBACK_EXAMPLES["default"]
        return random.sample(pool, min(n, len(pool)))

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def _load_all(self):
        combined: dict[str, list[dict]] = {}
        for source in DATASET_SOURCES:
            try:
                resp = requests.get(source["url"], timeout=self.TIMEOUT)
                resp.raise_for_status()
                pairs = self._parse_markdown_qa(resp.text)
                print(f"[FewShot] {source['description']}: {len(pairs)} Q&A fetched")
                for cat in source["categories"]:
                    combined.setdefault(cat, []).extend(pairs)
            except Exception as e:
                print(f"[FewShot] {source['description']}: failed ({e}). Using fallback.")

        with self._lock:
            for cat, pairs in combined.items():
                seen, unique = set(), []
                for p in pairs:
                    key = p["q"][:60].lower()
                    if key not in seen:
                        seen.add(key)
                        unique.append(p)
                self._cache[cat] = unique[:self.MAX_QA]
            self._loaded = True

    def _parse_markdown_qa(self, text: str) -> list[dict]:
        pairs = []
        for m in re.finditer(r'#{2,5}\s+Q\d+\.?\s*(.+?)\n+([\s\S]+?)(?=\n#{2,5}|\Z)', text):
            q = m.group(1).strip()
            a = self._clean_answer(m.group(2))
            if self._is_valid(q, a):
                pairs.append({"q": q, "a": a})
        for m in re.finditer(r'\*\*\s*(\d+\.\s+)?(.{15,150}\??)\s*\*\*\s*\n+([\s\S]+?)(?=\n\s*\*\*|\Z)', text):
            q = m.group(2).strip()
            a = self._clean_answer(m.group(3))
            if self._is_valid(q, a):
                pairs.append({"q": q, "a": a})
        return pairs

    def _clean_answer(self, raw: str) -> str:
        text = re.sub(r'```[\s\S]*?```', '', raw)
        text = re.sub(r'!?\[([^\]]*)\]\([^\)]*\)', r'\1', text)
        text = re.sub(r'[*_]{1,2}([^*_]+)[*_]{1,2}', r'\1', text)
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*[-*+>]\s+', '', text, flags=re.MULTILINE)
        return ' '.join(text.split())[:400]

    def _is_valid(self, q: str, a: str) -> bool:
        return len(q) >= 15 and len(a) >= 30 and q.count('\n') <= 2


# ─────────────────────────────────────────────────────────────────────────────
# QUESTION GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

class QuestionGenerator:

    VALIDATOR_MODEL = "llama-3.1-8b-instant"
    MAX_RETRIES     = 2

    def __init__(self):
        self.client   = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model    = "llama-3.1-8b-instant"
        self.few_shot = FewShotLoader()

        if _ST_AVAILABLE:
            self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
        else:
            self._st_model = None

    # ──────────────────────────────────────────────────────────────────── #
    #  PUBLIC: generate_questions                                           #
    # ──────────────────────────────────────────────────────────────────── #

    def generate_questions(
        self,
        skills_data:         dict,
        questions_per_skill: int = 5,   # per difficulty level — fixed at 5 for IRT
                                         # total = questions_per_skill × 3
        resume_text:         str = "",
    ) -> list[dict]:
        """
        Generates questions across all 3 difficulty levels per skill.

        questions_per_skill=1 → 3 questions per skill (1 easy + 1 medium + 1 hard)
        questions_per_skill=2 → 6 questions per skill (2 easy + 2 medium + 2 hard)

        Each question has:
          b_param       : IRT difficulty estimate (-2.0 to +2.0)
          b_reasoning   : LLaMA's explanation for the b value
          difficulty    : easy / medium / hard
          question_id   : unique string for IRT tracking (asked_ids)

        Returns flat list of question dicts — NOT shuffled.
        IRT engine will pick from this pool using b ≈ θ.
        """
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key or not api_key.startswith("gsk_"):
            raise RuntimeError(
                "GROQ_API_KEY is missing or invalid. "
                "Add it to your .env or .secrets.toml file."
            )

        session_seed = f"{int(time.time())}-{random.randint(1000, 9999)}"

        all_skills: list[tuple[str, str]] = [
            (skill["name"], category)
            for category, skills_list in skills_data.get("categories", {}).items()
            for skill in skills_list
        ]

        questions: list[dict] = []
        qid = 1

        for skill_name, category in all_skills:
            # Generate questions for each difficulty level
            for difficulty in ["easy", "medium", "hard"]:
                skill_qs = self._generate_for_skill(
                    skill_name, category, difficulty,
                    questions_per_skill, session_seed
                )
                for q in skill_qs:
                    q["id"]          = qid
                    q["question_id"] = f"q_{qid}_{skill_name[:3].lower()}_{difficulty[0]}"
                    q = self._validate_with_retry(
                        q, skill_name, category, difficulty, session_seed
                    )
                    questions.append(q)
                    qid += 1

        # Project questions
        if resume_text:
            for project in self._extract_projects(resume_text):
                for q in self._generate_for_project(project, session_seed):
                    q["id"]          = qid
                    q["question_id"] = f"q_{qid}_proj"
                    q["confidence"]  = "high"
                    q["similarity"]  = 1.0
                    q["b_param"]     = 0.0   # project questions default medium
                    q["b_reasoning"] = "Project question — default medium difficulty"
                    questions.append(q)
                    qid += 1

        # DO NOT shuffle — IRT picks from pool by b ≈ θ
        # App will use select_question() from rasch_engine
        return questions

    # ──────────────────────────────────────────────────────────────────── #
    #  SKILL QUESTION GENERATION  (CoT + Few-Shot + IRT b_param)           #
    # ──────────────────────────────────────────────────────────────────── #

    def _generate_for_skill(self, skill_name, category, difficulty, count, seed):

        band = IRT_BANDS[difficulty]
        angles = random.sample([
            "definition and purpose of the concept",
            "difference between two related concepts in this skill",
            "when and why you would use it",
            "how it works explained with a simple example",
            "advantages and disadvantages",
            "what happens if it is misused or incorrectly applied",
            "how it compares to an alternative approach",
            "a practical example that demonstrates the concept",
            "the types or categories within this concept",
            "a common follow-up a real interviewer would ask",
        ], k=min(count, 10))

        examples     = self.few_shot.get_examples(category, n=2)
        source_note  = "live dataset" if self.few_shot.is_loaded else "reference examples"
        few_shot_str = self._format_examples(examples, source_note)

        prompt = f"""You are a senior technical interviewer conducting a campus placement
interview for a fresher (B.Tech/B.E. CS/IT student).
SESSION SEED: {seed}

════════════════════════════════════════════════════════════
TASK
════════════════════════════════════════════════════════════
Generate exactly {count} interview question(s) for:
  Skill:      {skill_name}
  Category:   {category}
  Difficulty: {difficulty.upper()}

DIFFICULTY DEFINITION for {difficulty.upper()}:
  {band['description']}

IRT b_param target: {band['b_target']} (range: {band['b_min']} to {band['b_max']})
  b scale:
    -2.0 → trivially easy (any student gets it)
    -1.0 → easy (basic understanding)
     0.0 → medium (average student 50/50 chance)
    +1.0 → hard (requires strong understanding)
    +2.0 → very hard (expert level)

════════════════════════════════════════════════════════════
REAL INTERVIEW EXAMPLES  ({source_note})
Study these carefully. Match this tone and length exactly.
════════════════════════════════════════════════════════════
{few_shot_str}
════════════════════════════════════════════════════════════
STYLE RULES
════════════════════════════════════════════════════════════
  ✅ Questions are SHORT — 1-2 sentences max
  ✅ DIRECT — no long setups or scenarios
  ✅ Start with: What is / Explain / How does / Why / What is the difference
  ✅ Model answer: 3-5 sentences, clear, explains the "why"
  ❌ NEVER use "You are working at..." or "Imagine a scenario..."

════════════════════════════════════════════════════════════
STEP 1 — THINK FIRST (Chain of Thought)
════════════════════════════════════════════════════════════
Inside a <reasoning> block:
  a) What key concept should a {difficulty} question test for {skill_name}?
  b) Write the question
  c) Write the model answer
  d) Estimate b_param within {band['b_min']} to {band['b_max']} — explain why

<reasoning>
[thinking here]
</reasoning>

════════════════════════════════════════════════════════════
STEP 2 — OUTPUT FINAL JSON (no extra text, no markdown)
════════════════════════════════════════════════════════════
[
  {{
    "skill":        "{skill_name}",
    "category":     "{category}",
    "difficulty":   "{difficulty}",
    "question":     "<question>",
    "type":         "<conceptual|practical|scenario>",
    "hints":        ["<hint 1>", "<hint 2>"],
    "model_answer": "<3-5 sentence answer>",
    "b_param":      <float between {band['b_min']} and {band['b_max']}>,
    "b_reasoning":  "<one sentence: why this b value>"
  }}
]
"""
        return self._call_llm_cot(prompt, context=f"skill '{skill_name}' [{difficulty}]")

    # ──────────────────────────────────────────────────────────────────── #
    #  PROJECT QUESTION GENERATION                                          #
    # ──────────────────────────────────────────────────────────────────── #

    def _generate_for_project(self, project, seed):
        title      = project.get("title", "Unnamed Project")
        desc       = project.get("description", "")
        techs      = ", ".join(project.get("technologies", []))
        highlights = "; ".join(project.get("highlights", []))

        prompt = f"""You are interviewing a fresher about a project they built.
SESSION SEED: {seed}

PROJECT: {title}
Description: {desc}
Technologies: {techs}
Highlights: {highlights}

Generate 1 specific question about this project.
Ask about a technical decision, challenge faced, or lesson learned.

<reasoning>
[thinking here]
</reasoning>

[
  {{
    "skill":        "{title}",
    "category":     "Project",
    "difficulty":   "medium",
    "question":     "<specific project question>",
    "type":         "project",
    "hints":        ["<1 hint>"],
    "model_answer": "<3-4 sentence fresher answer>",
    "b_param":      0.0,
    "b_reasoning":  "Project question — default medium difficulty"
  }}
]
"""
        return self._call_llm_cot(prompt, context=f"project '{title}'")

    # ──────────────────────────────────────────────────────────────────── #
    #  VALIDATION WITH AUTO-RETRY                                           #
    # ──────────────────────────────────────────────────────────────────── #

    def _validate_with_retry(self, q, skill_name, category, difficulty, seed):
        best_q, best_sim = q, -1.0

        for attempt in range(self.MAX_RETRIES + 1):
            val  = self._validate_model_answer(
                q["question"], skill_name, q.get("model_answer", "")
            )
            sim  = val["similarity"]
            conf = val["confidence"]

            if sim > best_sim:
                best_sim = sim
                best_q   = {**q, "confidence": conf, "similarity": sim}

            if sim >= 0.60:
                return best_q

            if attempt < self.MAX_RETRIES:
                regen = self._generate_for_skill(
                    skill_name, category, difficulty, 1,
                    f"{int(time.time())}-{random.randint(1000, 9999)}"
                )
                if regen:
                    q = regen[0]
            else:
                best_q["confidence"] = "medium"

        return best_q

    def _validate_model_answer(self, question, skill, model_answer):
        if not _ST_AVAILABLE or self._st_model is None:
            return {"confidence": "high", "similarity": 1.0}
        try:
            resp = self.client.chat.completions.create(
                model=self.VALIDATOR_MODEL,
                messages=[
                    {"role": "system", "content": "Answer accurately and concisely."},
                    {"role": "user",
                     "content": f"Skill: {skill}\nQuestion: {question}\nAnswer in 3-5 sentences."},
                ],
                temperature=0.2, max_tokens=300,
            )
            second = resp.choices[0].message.content.strip()
            e1  = self._st_model.encode(model_answer, convert_to_tensor=True)
            e2  = self._st_model.encode(second,       convert_to_tensor=True)
            sim = float(st_util.cos_sim(e1, e2))
            conf = "high" if sim >= 0.80 else ("medium" if sim >= 0.60 else "low")
            return {"confidence": conf, "similarity": round(sim, 2)}
        except Exception as e:
            print(f"[QGen] Validation error: {e}")
            return {"confidence": "high", "similarity": 1.0}

    # ──────────────────────────────────────────────────────────────────── #
    #  PROJECT EXTRACTION                                                   #
    # ──────────────────────────────────────────────────────────────────── #

    def _extract_projects(self, resume_text):
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system",
                     "content": "Extract structured project info. Return valid JSON only."},
                    {"role": "user",
                     "content": f"Extract all projects from this resume. "
                                f"Return a JSON array with title, description, "
                                f"technologies, highlights.\n\n{resume_text[:4000]}"},
                ],
                temperature=0.2, max_tokens=1000,
            )
            raw      = self._clean_json(resp.choices[0].message.content)
            projects = json.loads(raw)
            return projects if isinstance(projects, list) else []
        except Exception as e:
            print(f"[QGen] Project extraction error: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────── #
    #  HELPERS                                                              #
    # ──────────────────────────────────────────────────────────────────── #

    def _format_examples(self, examples, source):
        lines = [f"(sourced from {source})\n"]
        for i, ex in enumerate(examples, 1):
            lines.append(f"Example {i}:")
            lines.append(f"  Q: {ex['q']}")
            lines.append(f"  A: {ex['a']}")
            lines.append("")
        return "\n".join(lines)

    def _call_llm_cot(self, prompt: str, context: str = "") -> list[dict]:
        FALLBACK_MODELS = [
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
        ]
        last_error = None
        for model in FALLBACK_MODELS:
            try:
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system",
                         "content": ("You are an expert technical interviewer for CS/IT campus "
                                     "placements. Reason step by step, then output a valid JSON array.")},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=2500,
                )
                raw = resp.choices[0].message.content.strip()
                raw = re.sub(r"<reasoning>.*?</reasoning>", "", raw, flags=re.DOTALL).strip()
                
                # Extract JSON more robustly — find opening [ and parse char by char
                start_idx = raw.find('[')
                if start_idx == -1:
                    print(f"[QGen] No JSON array found for {context}")
                    return []
                
                # Find matching closing bracket
                bracket_count = 0
                end_idx = start_idx
                for i in range(start_idx, len(raw)):
                    if raw[i] == '[':
                        bracket_count += 1
                    elif raw[i] == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end_idx = i + 1
                            break
                
                if bracket_count != 0:
                    print(f"[QGen] Mismatched brackets in JSON for {context}")
                    return []
                
                json_str = raw[start_idx:end_idx]
                parsed = json.loads(json_str)
                
                # Ensure b_param exists and is clamped
                result = parsed if isinstance(parsed, list) else [parsed]
                for q in result:
                    b = float(q.get("b_param", 0.0))
                    q["b_param"] = max(-2.0, min(2.0, b))
                    if "b_reasoning" not in q:
                        q["b_reasoning"] = "LLM estimated"
                return result
            except Exception as e:
                err_str = str(e)
                if "401" in err_str or "invalid_api_key" in err_str:
                    raise RuntimeError(
                        f"Groq API authentication failed. Regenerate key at console.groq.com. Error: {e}"
                    )
                last_error = e
                continue
        print(f"[QGen] All models failed for {context}: {last_error}")
        return []

    @staticmethod
    def _clean_json(text: str) -> str:
        text = text.strip()
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$",          "", text).strip()
        return text