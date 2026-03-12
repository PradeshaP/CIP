"""
question_generator.py

Generates interview questions using:
  1. Few-shot learning from LIVE open datasets (GitHub raw URLs, no auth needed)
  2. Chain-of-Thought (CoT) reasoning — LLM thinks before writing
  3. Dual-model validation with auto-retry (Llama + Mixtral)

DATASET SOURCES (all freely accessible, no API key required):
  - github.com/aershov24/full-stack-interview-questions   → Full Stack, JS, SQL, OOP
  - github.com/zhiqiangzhongddu/Data-Science-Interview-Questions-... → ML, DS, Stats
  - github.com/sudheerj/javascript-interview-questions   → JavaScript
  - github.com/sudheerj/reactjs-interview-questions      → React
  - github.com/Devinterview-io/python-interview-questions → Python

NOTE on Kaggle datasets:
  Kaggle requires login + API key for direct CSV download — not usable at runtime
  without credentials. These GitHub repos are the best freely-accessible alternative.

ARCHITECTURE:
  Startup  → FewShotLoader fetches + parses + caches Q&A pairs per category
  Per call → _get_few_shot_examples() samples 2 fresh examples for the prompt
  Prompt   → CoT reasoning block → final JSON output
"""

import os
import re
import json
import random
import time
import threading
import requests
from groq import Groq

try:
    from sentence_transformers import SentenceTransformer, util as st_util
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False
    print("WARNING: sentence-transformers not installed. Confidence validation disabled.")


# ─────────────────────────────────────────────────────────────────────────────
# DATASET CONFIGURATION
# Each entry: { "url": raw GitHub URL, "categories": [app category names] }
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

# Fallback hardcoded examples — used when all URLs fail (no network, etc.)
FALLBACK_EXAMPLES: dict[str, list[dict]] = {
    "Programming Languages": [
        {"q": "What is the difference between a list and a tuple in Python?",
         "a": "A list is mutable — you can change its elements after creation. "
              "A tuple is immutable — once created its values cannot be changed. "
              "Tuples are faster and used for fixed data like coordinates."},
        {"q": "What is the difference between == and .equals() in Java?",
         "a": "== checks if two references point to the same memory location. "
              ".equals() checks if two objects have the same value. "
              "For strings always use .equals() to compare values."},
    ],
    "Frontend Development": [
        {"q": "What is the difference between state and props in React?",
         "a": "Props are read-only inputs passed from parent to child component. "
              "State is internal data managed by the component that can change over time. "
              "When state changes React re-renders the component."},
        {"q": "What is the CSS box model?",
         "a": "The box model describes rectangular boxes around HTML elements. "
              "It has four layers: content, padding, border, and margin from inside out."},
    ],
    "Backend Development": [
        {"q": "What is the difference between GET and POST HTTP methods?",
         "a": "GET retrieves data and sends parameters in the URL. "
              "POST sends data in the request body for creating or submitting data. "
              "POST is more secure for sensitive data since it is not visible in the URL."},
        {"q": "What is middleware in Express.js?",
         "a": "Middleware is a function that runs between the request and response. "
              "It can modify the request, response, or call next() to pass control forward. "
              "Used for authentication, logging, and parsing request bodies."},
    ],
    "Databases": [
        {"q": "What is the difference between a primary key and a foreign key?",
         "a": "A primary key uniquely identifies each row and cannot be null. "
              "A foreign key references the primary key of another table. "
              "It maintains relationships and referential integrity between tables."},
        {"q": "What is normalization and why is it used?",
         "a": "Normalization organizes a database to reduce data redundancy. "
              "It divides large tables into smaller related ones. "
              "It prevents update anomalies where the same data exists in multiple places."},
    ],
    "Cloud & DevOps": [
        {"q": "What is Docker and why is it used?",
         "a": "Docker packages an application and its dependencies into a container. "
              "This ensures the app runs the same way on any machine. "
              "It solves the works-on-my-machine problem."},
        {"q": "What is the difference between Git merge and Git rebase?",
         "a": "Merge combines two branches and creates a merge commit preserving history. "
              "Rebase moves commits onto another branch creating a cleaner linear history. "
              "Rebase should not be used on public shared branches."},
    ],
    "Data Science & AI": [
        {"q": "What is the difference between supervised and unsupervised learning?",
         "a": "Supervised learning trains on labeled data where the correct output is known. "
              "Unsupervised learning finds hidden patterns in unlabeled data. "
              "Clustering and dimensionality reduction are common unsupervised techniques."},
        {"q": "What is overfitting and how do you prevent it?",
         "a": "Overfitting is when a model learns training data too well including noise. "
              "It performs poorly on new unseen data. "
              "Prevention includes cross-validation regularization and adding more data."},
    ],
    "DSA & CS Fundamentals": [
        {"q": "What is the difference between a stack and a queue?",
         "a": "A stack follows LIFO — last element added is first removed. "
              "A queue follows FIFO — first element added is first removed. "
              "Stacks are used in function calls, queues in task scheduling."},
        {"q": "What are the four pillars of Object-Oriented Programming?",
         "a": "Encapsulation, Abstraction, Inheritance, and Polymorphism. "
              "Encapsulation bundles data and restricts access. "
              "Inheritance lets a class reuse properties of another class."},
        {"q": "What is the time complexity of binary search?",
         "a": "Binary search is O(log n). "
              "At each step it halves the search space by comparing with the middle element. "
              "It only works on sorted arrays."},
    ],
    "Mobile Development": [
        {"q": "What is the difference between an Activity and a Fragment in Android?",
         "a": "An Activity represents a full screen with its own lifecycle. "
              "A Fragment is a reusable portion of UI that lives inside an Activity. "
              "Fragments allow modular UI design especially on larger screens."},
    ],
    "Testing & QA": [
        {"q": "What is unit testing and why is it important?",
         "a": "Unit testing tests individual functions or components in isolation. "
              "It ensures each part works before integrating with others. "
              "Pytest and JUnit are popular frameworks."},
    ],
    "Soft Skills & Methodologies": [
        {"q": "What is Agile methodology and how is it different from Waterfall?",
         "a": "Agile is iterative — work is done in short sprints with frequent feedback. "
              "Waterfall is sequential — each phase completes before the next starts. "
              "Agile is more flexible for changing requirements."},
    ],
}
FALLBACK_EXAMPLES["default"] = FALLBACK_EXAMPLES["DSA & CS Fundamentals"]


# ─────────────────────────────────────────────────────────────────────────────
# FEW-SHOT LOADER
# Fetches datasets at startup in a background thread — non-blocking.
# Falls back to FALLBACK_EXAMPLES if any URL fails.
# ─────────────────────────────────────────────────────────────────────────────

class FewShotLoader:
    """
    Loads real interview Q&A pairs from public GitHub raw URLs.
    Runs in a background thread so it doesn't block app startup.
    Falls back to hardcoded examples if fetch fails.

    Why GitHub raw URLs, not Kaggle?
      Kaggle datasets require API key authentication.
      These GitHub repos are publicly accessible with no credentials.
    """

    TIMEOUT  = 8     # seconds per request
    MAX_QA   = 30    # max Q&A pairs to keep per category (to limit memory)

    def __init__(self):
        self._cache: dict[str, list[dict]] = {}
        self._loaded = False
        self._lock   = threading.Lock()
        # Start loading in background immediately
        self._thread = threading.Thread(target=self._load_all, daemon=True)
        self._thread.start()

    def get_examples(self, category: str, n: int = 2) -> list[dict]:
        """
        Returns n random Q&A examples for the given category.
        If background loading is still running, uses fallback immediately.
        """
        with self._lock:
            pool = self._cache.get(category) or \
                   FALLBACK_EXAMPLES.get(category) or \
                   FALLBACK_EXAMPLES["default"]
        return random.sample(pool, min(n, len(pool)))

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def _load_all(self):
        """Fetch all dataset URLs and populate the cache."""
        combined: dict[str, list[dict]] = {}

        for source in DATASET_SOURCES:
            url         = source["url"]
            categories  = source["categories"]
            description = source["description"]
            try:
                resp = requests.get(url, timeout=self.TIMEOUT)
                resp.raise_for_status()
                pairs = self._parse_markdown_qa(resp.text)
                print(f"[FewShotLoader] ✅ {description}: {len(pairs)} Q&A pairs fetched")

                for cat in categories:
                    if cat not in combined:
                        combined[cat] = []
                    combined[cat].extend(pairs)

            except Exception as e:
                print(f"[FewShotLoader] ⚠️  {description}: fetch failed ({e}). "
                      f"Using fallback examples.")

        # Deduplicate and cap per category
        with self._lock:
            for cat, pairs in combined.items():
                seen = set()
                unique = []
                for p in pairs:
                    key = p["q"][:60].lower()
                    if key not in seen:
                        seen.add(key)
                        unique.append(p)
                self._cache[cat] = unique[:self.MAX_QA]
            self._loaded = True

        loaded_cats = [c for c, v in self._cache.items() if v]
        print(f"[FewShotLoader] Loaded {len(loaded_cats)} categories from live datasets.")

    def _parse_markdown_qa(self, text: str) -> list[dict]:
        """
        Parses Q&A pairs from markdown files.
        Handles common patterns found in interview Q&A repos:

          Pattern 1 (numbered): #### Q123 What is X?\nAnswer text
          Pattern 2 (bold Q):   **What is X?**\n\nAnswer text
          Pattern 3 (heading):  ### What is X?\nAnswer text
        """
        pairs = []

        # Pattern 1 — numbered: #### Q123 question?
        for m in re.finditer(
            r'#{2,5}\s+Q\d+\.?\s*(.+?)\n+([\s\S]+?)(?=\n#{2,5}|\Z)',
            text
        ):
            q = m.group(1).strip()
            a = self._clean_answer(m.group(2))
            if self._is_valid_qa(q, a):
                pairs.append({"q": q, "a": a})

        # Pattern 2 — bold question with answer block
        for m in re.finditer(
            r'\*\*\s*(\d+\.\s+)?(.{15,150}\??)\s*\*\*\s*\n+\s*([\s\S]+?)(?=\n\s*\*\*|\Z)',
            text
        ):
            q = m.group(2).strip()
            a = self._clean_answer(m.group(3))
            if self._is_valid_qa(q, a):
                pairs.append({"q": q, "a": a})

        # Pattern 3 — heading as question
        for m in re.finditer(
            r'#{2,4}\s+(.{15,120}\?)\s*\n+([\s\S]+?)(?=\n#{2,4}|\Z)',
            text
        ):
            q = m.group(1).strip()
            a = self._clean_answer(m.group(2))
            if self._is_valid_qa(q, a):
                pairs.append({"q": q, "a": a})

        return pairs

    def _clean_answer(self, raw: str) -> str:
        """Strip markdown, code blocks, links, keep plain text answer."""
        text = re.sub(r'```[\s\S]*?```', '', raw)          # code blocks
        text = re.sub(r'`[^`]+`', lambda m: m.group()[1:-1], text)  # inline code
        text = re.sub(r'!?\[([^\]]*)\]\([^\)]*\)', r'\1', text)     # links/images
        text = re.sub(r'[*_]{1,2}([^*_]+)[*_]{1,2}', r'\1', text)  # bold/italic
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)       # headings
        text = re.sub(r'^\s*[-*+>]\s+', '', text, flags=re.MULTILINE) # bullets
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]{2,}', ' ', text)
        # Collapse to single paragraph, max 400 chars
        flat = ' '.join(text.split())
        return flat[:400]

    def _is_valid_qa(self, q: str, a: str) -> bool:
        """Basic quality filter — skip too-short, code-heavy, or non-question entries."""
        if len(q) < 15 or len(a) < 30:
            return False
        if q.count('\n') > 2:
            return False
        # Skip entries that are mostly code
        if a.count('{') + a.count('}') > 10:
            return False
        return True


# ─────────────────────────────────────────────────────────────────────────────
# QUESTION GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

class QuestionGenerator:

    VALIDATOR_MODEL = "mixtral-8x7b-32768"
    MAX_RETRIES     = 2

    def __init__(self):
        self.client     = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model      = "llama-3.3-70b-versatile"
        self.few_shot   = FewShotLoader()   # starts background fetch immediately

        if _ST_AVAILABLE:
            self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
        else:
            self._st_model = None

    # ──────────────────────────────────────────────────────────────────── #
    #  PUBLIC                                                               #
    # ──────────────────────────────────────────────────────────────────── #

    def generate_questions(
        self,
        skills_data:         dict,
        difficulty:          str = "medium",
        questions_per_skill: int = 2,
        resume_text:         str = "",
    ) -> list[dict]:

        session_seed = f"{int(time.time())}-{random.randint(1000, 9999)}"

        all_skills: list[tuple[str, str]] = [
            (skill["name"], category)
            for category, skills_list in skills_data.get("categories", {}).items()
            for skill in skills_list
        ]

        questions: list[dict] = []
        qid = 1

        for skill_name, category in all_skills:
            skill_qs = self._generate_for_skill(
                skill_name, category, difficulty, questions_per_skill, session_seed
            )
            for q in skill_qs:
                q["id"] = qid
                q = self._validate_with_retry(q, skill_name, category, difficulty, session_seed)
                questions.append(q)
                qid += 1

        if resume_text:
            for project in self._extract_projects(resume_text):
                for q in self._generate_for_project(project, difficulty, session_seed):
                    q["id"]         = qid
                    q["confidence"] = "high"
                    q["similarity"] = 1.0
                    questions.append(q)
                    qid += 1

        random.shuffle(questions)
        for i, q in enumerate(questions, 1):
            q["id"] = i

        return questions

    # ──────────────────────────────────────────────────────────────────── #
    #  SKILL QUESTION GENERATION  (CoT + Live Few-Shot)                    #
    # ──────────────────────────────────────────────────────────────────── #

    def _generate_for_skill(self, skill_name, category, difficulty, count, seed):

        angles = random.sample([
            "definition and purpose of the concept",
            "difference between two related concepts in this skill",
            "when and why you would use it",
            "how it works explained with a simple example",
            "advantages and disadvantages",
            "what happens if it is misused or incorrectly applied",
            "how it compares to an alternative approach",
            "a follow-up a real interviewer would naturally ask next",
            "a practical example that demonstrates the concept",
            "the types or categories within this concept",
        ], k=min(count, 10))

        # Get live examples from fetched datasets (or fallback)
        examples     = self.few_shot.get_examples(category, n=2)
        source_note  = "live dataset" if self.few_shot.is_loaded else "reference examples"
        few_shot_str = self._format_examples(examples, source_note)

        prompt = f"""You are a senior technical interviewer at a software company conducting
a campus placement interview for a fresher (B.Tech/B.E. CS/IT student).
SESSION SEED: {seed}

════════════════════════════════════════════════════════════
TASK
════════════════════════════════════════════════════════════
Generate exactly {count} interview question(s) for:
  Skill:      {skill_name}
  Category:   {category}
  Difficulty: {difficulty}
  Angle(s):   {", ".join(angles[:count])}

════════════════════════════════════════════════════════════
REAL INTERVIEW EXAMPLES  ({source_note})
Study these carefully. Your output must match this tone and length.
════════════════════════════════════════════════════════════
{few_shot_str}
════════════════════════════════════════════════════════════
STYLE RULES  (derived from real interview Q&A datasets)
════════════════════════════════════════════════════════════
  ✅ Questions are SHORT — 1 sentence or 2 short sentences max
  ✅ Questions are DIRECT — no long setups or scenarios
  ✅ Start with: What is / What are / Explain / How does /
     What is the difference between / When would you use / Why is / Give an example of
  ✅ Answers are 3-5 sentences — clear, structured, explain the "why" not just "what"
  ❌ NEVER start with "You are working at..." or "Imagine a scenario..."
  ❌ NEVER write questions longer than 2 sentences

════════════════════════════════════════════════════════════
STEP 1 — THINK FIRST  (Chain of Thought)
════════════════════════════════════════════════════════════
Reason inside a <reasoning> block:
  a) What key concept must a fresher know about {skill_name}?
  b) Which angle best tests it?
  c) Write a BAD version first (scenario/too long/vague).
  d) What makes it bad?
  e) Rewrite as a GOOD question matching the examples above.
  f) Write a model answer in 3-5 sentences.
  g) Write 2 hints that guide without giving away the answer.

<reasoning>
[thinking here — one block per question]
</reasoning>

════════════════════════════════════════════════════════════
STEP 2 — OUTPUT FINAL JSON  (no extra text, no markdown)
════════════════════════════════════════════════════════════
[
  {{
    "skill":        "{skill_name}",
    "category":     "{category}",
    "difficulty":   "{difficulty}",
    "question":     "<final question from step e>",
    "type":         "<conceptual | practical | scenario>",
    "hints":        ["<hint 1>", "<hint 2>"],
    "model_answer": "<answer from step f>"
  }}
]
"""
        return self._call_llm_cot(prompt, context=f"skill '{skill_name}'")

    # ──────────────────────────────────────────────────────────────────── #
    #  PROJECT QUESTION GENERATION  (CoT + Few-Shot)                       #
    # ──────────────────────────────────────────────────────────────────── #

    def _generate_for_project(self, project, difficulty, seed):
        title      = project.get("title", "Unnamed Project")
        desc       = project.get("description", "")
        techs      = ", ".join(project.get("technologies", []))
        highlights = "; ".join(project.get("highlights", []))

        project_examples = """Example 1:
  Q: Why did you choose React over plain JavaScript for the frontend?
  A: React makes it easy to build reusable components and manage state. Without React,
     updating the DOM manually for dynamic content like live quiz scores would be complex.

Example 2:
  Q: How did you handle errors when the external API returned no data?
  A: I wrapped the API call in a try-except block. The app shows a user-friendly message
     instead of crashing, and falls back to cached data from the database."""

        prompt = f"""You are interviewing a fresher about a project they built.
SESSION SEED: {seed}

PROJECT: {title}
Description: {desc}
Technologies: {techs}
Highlights: {highlights}

════════════════════════════════════════════════════════════
PROJECT INTERVIEW EXAMPLES
════════════════════════════════════════════════════════════
{project_examples}

════════════════════════════════════════════════════════════
STEP 1 — THINK FIRST  (Chain of Thought)
════════════════════════════════════════════════════════════
For each of the 2 questions, reason inside <reasoning>:
  a) Most revealing thing to ask about THIS project?
  b) Bad version — too generic, could be any project.
  c) Why is it bad?
  d) Good version — specific to the project above, short, direct.
  e) Strong fresher answer (3-4 sentences).
  f) 1 hint.

<reasoning>
[thinking here]
</reasoning>

════════════════════════════════════════════════════════════
STEP 2 — OUTPUT FINAL JSON
════════════════════════════════════════════════════════════
[
  {{
    "skill":        "{title}",
    "category":     "Project",
    "difficulty":   "{difficulty}",
    "question":     "<specific project question>",
    "type":         "project",
    "hints":        ["<1 hint>"],
    "model_answer": "<3-4 sentence fresher answer>"
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
            val  = self._validate_model_answer(q["question"], skill_name,
                                               q.get("model_answer", ""))
            sim  = val["similarity"]
            conf = val["confidence"]

            if sim > best_sim:
                best_sim = sim
                best_q   = {**q, "confidence": conf, "similarity": sim}

            if sim >= 0.60:
                print(f"[QGen] '{skill_name}' attempt {attempt+1}: "
                      f"sim={sim:.2f} ({conf}) ✅")
                return best_q

            if attempt < self.MAX_RETRIES:
                print(f"[QGen] '{skill_name}' attempt {attempt+1}: "
                      f"sim={sim:.2f} < 0.60 → regenerating…")
                regen = self._generate_for_skill(
                    skill_name, category, difficulty, 1,
                    f"{int(time.time())}-{random.randint(1000, 9999)}"
                )
                if regen:
                    q = regen[0]
            else:
                print(f"[QGen] '{skill_name}': retries exhausted. "
                      f"Best sim={best_sim:.2f}. Tagging 'medium'.")
                best_q["confidence"] = "medium"

        return best_q

    def _validate_model_answer(self, question, skill, model_answer):
        if not _ST_AVAILABLE or self._st_model is None:
            return {"confidence": "high", "similarity": 1.0}
        try:
            resp = self.client.chat.completions.create(
                model=self.VALIDATOR_MODEL,
                messages=[
                    {"role": "system",
                     "content": "Answer accurately and concisely."},
                    {"role": "user",
                     "content": f"Skill: {skill}\nQuestion: {question}\n\n"
                                f"Answer in 3-5 sentences."},
                ],
                temperature=0.2, max_tokens=300,
            )
            second = resp.choices[0].message.content.strip()
            e1 = self._st_model.encode(model_answer, convert_to_tensor=True)
            e2 = self._st_model.encode(second,       convert_to_tensor=True)
            sim = float(st_util.cos_sim(e1, e2))
            conf = "high" if sim >= 0.80 else ("medium" if sim >= 0.60 else "low")
            return {"confidence": conf, "similarity": round(sim, 2)}
        except Exception as e:
            print(f"[QGen] Validation error (non-critical): {e}")
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
            raw = self._clean_json(resp.choices[0].message.content)
            projects = json.loads(raw)
            return projects if isinstance(projects, list) else []
        except Exception as e:
            print(f"[QGen] Project extraction error: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────── #
    #  HELPERS                                                              #
    # ──────────────────────────────────────────────────────────────────── #

    def _format_examples(self, examples: list[dict], source: str) -> str:
        lines = [f"(sourced from {source})\n"]
        for i, ex in enumerate(examples, 1):
            lines.append(f"Example {i}:")
            lines.append(f"  Q: {ex['q']}")
            lines.append(f"  A: {ex['a']}")
            lines.append("")
        return "\n".join(lines)

    def _call_llm_cot(self, prompt: str, context: str = "") -> list[dict]:
        """CoT call — allows <reasoning> block before the JSON array."""
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
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
            m   = re.search(r"\[.*\]", raw, flags=re.DOTALL)
            if not m:
                print(f"[QGen] No JSON found for {context}")
                return []
            parsed = json.loads(m.group())
            return parsed if isinstance(parsed, list) else [parsed]
        except Exception as e:
            print(f"[QGen] CoT error for {context}: {e}")
            return []

    def _call_llm(self, prompt: str, context: str = "") -> list[dict]:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system",
                     "content": "Return valid JSON only, no markdown."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5, max_tokens=1800,
            )
            raw    = self._clean_json(resp.choices[0].message.content)
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else [parsed]
        except Exception as e:
            print(f"[QGen] Error for {context}: {e}")
            return []

    @staticmethod
    def _clean_json(text: str) -> str:
        text = text.strip()
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$",          "", text).strip()
        return text