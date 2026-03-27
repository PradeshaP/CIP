"""
enhanced_skill_extractor.py

LLaMA-based skill extractor — replaces NLP (spaCy + sentence-transformers).

TWO THINGS EXTRACTED:
  1. Skills — mapped to taxonomy categories
  2. Projects — with technical skills used in each project

WHY LLaMA INSTEAD OF NLP:
  NLP relies on a hardcoded alias dictionary — misses anything not in the list.
  LLaMA reads the full resume with language understanding:
    "built REST APIs using Flask and deployed on EC2"
    → Flask (Backend), REST API (Backend), AWS (Cloud & DevOps)
    without needing EC2 in any alias list.

OUTPUT:
  {
    "categories": {
      "Programming Languages": [{"name": "Python", "source": "llm"}],
      "Backend Development":   [{"name": "Flask",  "source": "llm"}],
      ...
    },
    "total_skills": int,
    "projects": [
      {
        "title":       "Face Recognition Attendance System",
        "description": "Built using OpenCV and deep learning...",
        "technologies": ["Python", "OpenCV", "Deep Learning"],
        "highlights":   ["Achieved 95% accuracy", "Deployed on Raspberry Pi"],
        "skill_context": {
          "Computer Vision": "Used OpenCV and MediaPipe for face detection",
          "Deep Learning":   "Trained CNN model for face recognition"
        }
      }
    ]
  }

skill_context is the KEY addition — maps each skill to HOW it was used
in the project, so question_generator can ask targeted questions.
"""

import os
import re
import json
from groq import Groq
from dotenv import load_dotenv
load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# SKILL TAXONOMY
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_DEFINITIONS = {
    "Programming Languages": (
        "Languages the candidate writes code in. "
        "e.g. Python, Java, C++, JavaScript, TypeScript, Go, Kotlin, Swift, PHP, Dart, R"
    ),
    "Frontend Development": (
        "UI and browser-side technologies. "
        "e.g. React, Angular, Vue.js, Next.js, HTML, CSS, Bootstrap, Tailwind CSS, Redux, JavaScript"
    ),
    "Backend Development": (
        "Server-side frameworks and API technologies. "
        "e.g. Node.js, Express.js, Django, Flask, FastAPI, Spring Boot, REST API, GraphQL"
    ),
    "Databases": (
        "Databases and data storage. "
        "e.g. MySQL, PostgreSQL, MongoDB, SQLite, Redis, Firebase, SQL, DynamoDB"
    ),
    "Cloud & DevOps": (
        "Cloud platforms, deployment, CI/CD, infrastructure. "
        "e.g. AWS, Azure, Google Cloud, Docker, Kubernetes, Git, GitHub, Jenkins, CI/CD"
    ),
    "Data Science & AI": (
        "ML, DL, AI, data analysis, computer vision, NLP, and related libraries. "
        "e.g. Machine Learning, Deep Learning, Computer Vision, NLP, Generative AI, "
        "Data Analysis, OCR"
    ),
    "Mobile Development": (
        "Mobile app development. "
        "e.g. Android, iOS, React Native, Flutter"
    ),
    "IoT & Hardware": (
        "Embedded systems and hardware. "
        "e.g. IoT, Arduino, ESP32, Raspberry Pi"
    ),
    "Tools & Platforms": (
        "Developer tools and platforms. "
        "e.g. VS Code, Postman, Figma, Jira, Linux, Bash"
    ),
    "DSA & CS Fundamentals": (
        "Core CS concepts. "
        "e.g. DSA, OOP, Operating Systems, DBMS, Networking, System Design"
    ),
    "Testing & QA": (
        "Testing frameworks. "
        "e.g. Unit Testing, Selenium, API Testing, pytest, Jest, TDD"
    ),
    "Soft Skills & Methodologies": (
        "Non-technical skills. "
        "e.g. Problem Solving, Leadership, Communication, Agile, Teamwork"
    ),
}

CANONICAL_NAMES = {
    "python": "Python", "java": "Java", "c++": "C++", "cpp": "C++",
    "c language": "C", "javascript": "JavaScript", "typescript": "TypeScript",
    "golang": "Go", "go": "Go", "kotlin": "Kotlin", "swift": "Swift",
    "php": "PHP", "dart": "Dart", "scala": "Scala", "rust": "Rust",
    "react": "React", "angular": "Angular", "vue": "Vue.js", "next.js": "Next.js",
    "html": "HTML", "css": "CSS", "bootstrap": "Bootstrap",
    "tailwind": "Tailwind CSS", "redux": "Redux",
    "node.js": "Node.js", "nodejs": "Node.js", "express": "Express.js",
    "django": "Django", "flask": "Flask", "fastapi": "FastAPI",
    "spring boot": "Spring Boot", "graphql": "GraphQL", "rest api": "REST API",
    "mysql": "MySQL", "postgresql": "PostgreSQL", "mongodb": "MongoDB",
    "sqlite": "SQLite", "redis": "Redis", "firebase": "Firebase", "sql": "SQL",
    "aws": "AWS", "azure": "Azure", "google cloud": "Google Cloud", "gcp": "Google Cloud",
    "docker": "Docker", "kubernetes": "Kubernetes", "git": "Git",
    "github": "GitHub", "jenkins": "Jenkins", "ci/cd": "CI/CD",
    "machine learning": "Machine Learning", "ml": "Machine Learning",
    "deep learning": "Deep Learning", "tensorflow": "Deep Learning",
    "pytorch": "Deep Learning", "keras": "Deep Learning",
    "computer vision": "Computer Vision", "opencv": "Computer Vision",
    "mediapipe": "Computer Vision", "cv2": "Computer Vision",
    "nlp": "NLP", "natural language processing": "NLP",
    "generative ai": "Generative AI", "llm": "Generative AI", "genai": "Generative AI",
    "gpt": "Generative AI", "llama": "Generative AI",
    "ocr": "OCR", "tesseract": "OCR",
    "data analysis": "Data Analysis", "pandas": "Data Analysis",
    "numpy": "Data Analysis", "matplotlib": "Data Analysis",
    "scikit-learn": "Machine Learning", "sklearn": "Machine Learning",
    "android": "Android", "ios": "iOS", "react native": "React Native",
    "flutter": "Flutter", "iot": "IoT", "arduino": "IoT", "esp32": "IoT",
    "raspberry pi": "IoT", "vs code": "VS Code", "postman": "Postman",
    "linux": "Linux", "bash": "Bash", "dsa": "DSA", "oop": "OOP",
    "operating systems": "OS", "dbms": "DBMS", "networking": "Networking",
    "system design": "System Design", "unit testing": "Unit Testing",
    "pytest": "Unit Testing", "selenium": "Selenium",
    "problem solving": "Problem Solving", "agile": "Agile",
}

# Fallback keyword scan used if API fails
FALLBACK_KEYWORDS: dict[str, list[str]] = {
    "Programming Languages": ["python","java","c++","javascript","typescript","kotlin","swift","php","dart"],
    "Frontend Development":  ["react","angular","vue","html","css","bootstrap","tailwind"],
    "Backend Development":   ["node.js","express","django","flask","fastapi","spring boot","rest api"],
    "Databases":             ["mysql","postgresql","mongodb","sqlite","redis","sql","firebase"],
    "Cloud & DevOps":        ["aws","azure","google cloud","docker","kubernetes","git","github","jenkins"],
    "Data Science & AI":     ["machine learning","deep learning","tensorflow","pytorch","opencv",
                               "nlp","generative ai","data analysis","pandas","numpy","ocr"],
    "Mobile Development":    ["android","ios","react native","flutter"],
    "IoT & Hardware":        ["iot","arduino","esp32","raspberry pi"],
    "Tools & Platforms":     ["vs code","postman","figma","linux","bash"],
    "DSA & CS Fundamentals": ["dsa","oop","operating systems","dbms","networking","system design"],
    "Testing & QA":          ["unit testing","selenium","pytest","jest"],
    "Soft Skills & Methodologies": ["problem solving","agile","teamwork","leadership"],
}


class EnhancedSkillExtractor:
    """
    LLaMA-powered skill + project extractor.
    Drop-in replacement for NLP-based extractor.
    Returns same dict shape + projects list.
    """

    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not found. Add it to your .env or .secrets.toml."
            )
        self.client = Groq(api_key=api_key)
        self.model  = "llama-3.3-70b-versatile"

    # ─────────────────────────────────────────────────────────────────── #
    #  PUBLIC: extract_all_skills                                          #
    # ─────────────────────────────────────────────────────────────────── #

    def extract_all_skills(self, resume_text: str) -> dict:
        """
        Extracts skills AND projects from resume using LLaMA.

        Returns:
        {
          "categories": {
            category: [{"name": skill, "source": "llm"}]
          },
          "total_skills": int,
          "projects": [
            {
              "title":        str,
              "description":  str,
              "technologies": [str],
              "highlights":   [str],
              "skill_context": {
                skill_name: "how this skill was used in this project"
              }
            }
          ]
        }
        """
        try:
            raw = self._call_llama(resume_text)
            return self._parse_response(raw)
        except Exception as e:
            print(f"[SkillExtractor] LLaMA failed: {e}. Using fallback.")
            result = self._keyword_fallback(resume_text)
            result["projects"] = []
            return result

    # ─────────────────────────────────────────────────────────────────── #
    #  PRIVATE: LLaMA API call                                             #
    # ─────────────────────────────────────────────────────────────────── #

    def _call_llama(self, resume_text: str) -> str:
        cat_block = "\n".join(
            f"  {i+1:02d}. {cat}\n      {desc}"
            for i, (cat, desc) in enumerate(CATEGORY_DEFINITIONS.items())
        )

        prompt = f"""You are an expert technical recruiter. Read the resume below carefully.
Extract TWO things:

════════════════════════════════════════════════════
PART 1 — SKILLS
════════════════════════════════════════════════════
Map every skill to one of these categories:
{cat_block}

RULES:
1. Read the FULL resume — skills section, projects, experience, certifications.
2. Infer skills from context:
   - "built REST APIs using Flask and deployed on EC2" → Flask, REST API, AWS
   - "trained a CNN model using PyTorch" → Deep Learning, Computer Vision
3. Use canonical names: opencv/cv2/mediapipe → "Computer Vision",
   tensorflow/pytorch → "Deep Learning", scikit-learn → "Machine Learning"
4. Do NOT list tools as separate skills — map to parent skill.
5. Each skill appears ONCE across all categories.
6. Include ALL 12 categories (empty list [] if none found).

════════════════════════════════════════════════════
PART 2 — PROJECTS
════════════════════════════════════════════════════
Extract all projects from the resume.
For each project, also extract skill_context — how each technical skill
was specifically used in that project. This is used to generate
project-specific interview questions.

════════════════════════════════════════════════════
RESUME:
════════════════════════════════════════════════════
{resume_text[:6000]}

════════════════════════════════════════════════════
OUTPUT — valid JSON only, no markdown:
════════════════════════════════════════════════════
{{
  "skills": {{
    "Programming Languages":       ["Python", "Java"],
    "Frontend Development":        ["React", "HTML", "CSS"],
    "Backend Development":         ["Flask", "REST API"],
    "Databases":                   ["MySQL", "MongoDB"],
    "Cloud & DevOps":              ["AWS", "Docker", "Git"],
    "Data Science & AI":           ["Machine Learning", "Computer Vision"],
    "Mobile Development":          [],
    "IoT & Hardware":              [],
    "Tools & Platforms":           ["VS Code", "Linux"],
    "DSA & CS Fundamentals":       ["DSA", "OOP"],
    "Testing & QA":                [],
    "Soft Skills & Methodologies": ["Problem Solving", "Agile"]
  }},
  "projects": [
    {{
      "title":        "Face Recognition Attendance System",
      "description":  "Automated attendance system using face recognition",
      "technologies": ["Python", "OpenCV", "Deep Learning", "MySQL"],
      "highlights":   ["95% accuracy", "Real-time detection"],
      "skill_context": {{
        "Computer Vision": "Used OpenCV and MediaPipe for real-time face detection and landmark extraction",
        "Deep Learning":   "Trained CNN model using PyTorch for face recognition with 95% accuracy",
        "MySQL":           "Stored attendance records and student profiles in MySQL database"
      }}
    }}
  ]
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role":    "system",
                    "content": (
                        "You are an expert technical recruiter. "
                        "Extract skills and projects from resumes. "
                        "Return valid JSON only — no markdown, no extra text."
                    )
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        return response.choices[0].message.content.strip()

    # ─────────────────────────────────────────────────────────────────── #
    #  PRIVATE: parse response                                             #
    # ─────────────────────────────────────────────────────────────────── #

    def _parse_response(self, raw: str) -> dict:
        raw = re.sub(r"^```(?:json)?", "", raw.strip()).strip()
        raw = re.sub(r"```$", "", raw).strip()

        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not m:
            raise ValueError(f"No JSON found in response: {raw[:200]}")

        parsed = json.loads(m.group())

        # ── Parse skills ─────────────────────────────────────────────
        categories: dict[str, list[dict]] = {}
        raw_skills = parsed.get("skills", {})

        for category in CATEGORY_DEFINITIONS:
            skill_list = raw_skills.get(category, [])
            if not isinstance(skill_list, list):
                skill_list = []

            entries = []
            seen    = set()
            for skill in skill_list:
                if not isinstance(skill, str) or not skill.strip():
                    continue
                canonical = CANONICAL_NAMES.get(skill.strip().lower(), skill.strip())
                if canonical == canonical.lower():
                    canonical = canonical.title()
                if canonical not in seen:
                    seen.add(canonical)
                    entries.append({"name": canonical, "source": "llm"})
            categories[category] = entries

        # ── Parse projects ────────────────────────────────────────────
        raw_projects = parsed.get("projects", [])
        projects     = []

        if isinstance(raw_projects, list):
            for p in raw_projects:
                if not isinstance(p, dict):
                    continue
                projects.append({
                    "title":        p.get("title", "Unnamed Project"),
                    "description":  p.get("description", ""),
                    "technologies": p.get("technologies", []),
                    "highlights":   p.get("highlights", []),
                    "skill_context": p.get("skill_context", {}),
                })

        total = sum(len(v) for v in categories.values())
        print(f"[SkillExtractor] Extracted {total} skills, {len(projects)} projects.")

        return {
            "categories":   categories,
            "total_skills": total,
            "projects":     projects,
        }

    # ─────────────────────────────────────────────────────────────────── #
    #  PRIVATE: keyword fallback                                           #
    # ─────────────────────────────────────────────────────────────────── #

    def _keyword_fallback(self, text: str) -> dict:
        text_lower = text.lower()
        result: dict[str, list[dict]] = {}

        for category in CATEGORY_DEFINITIONS:
            keywords = FALLBACK_KEYWORDS.get(category, [])
            found, seen = [], set()
            for kw in keywords:
                if kw in text_lower:
                    canonical = CANONICAL_NAMES.get(kw, kw.title())
                    if canonical not in seen:
                        seen.add(canonical)
                        found.append({"name": canonical, "source": "fallback"})
            result[category] = found

        total = sum(len(v) for v in result.values())
        print(f"[SkillExtractor] Fallback: {total} skills.")
        return {"categories": result, "total_skills": total}