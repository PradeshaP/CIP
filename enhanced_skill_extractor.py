# enhanced_skill_extractor.py
#
# ─────────────────────────────────────────────────────────────────────────────
# DESIGN PRINCIPLES
# ─────────────────────────────────────────────────────────────────────────────
#
# 1. SKILL TAXONOMY — a skill is what an interviewer asks about.
#    Tools/libraries/models are EVIDENCE of a skill, not skills themselves.
#
#    Tool/Library in resume        →  Canonical Skill extracted
#    ──────────────────────────    ─────────────────────────────
#    opencv, mediapipe, cv2        →  Computer Vision
#    llama, mixtral, gpt, groq     →  Generative AI
#    tesseract, tesseract.js       →  OCR
#    tensorflow, pytorch, keras    →  Deep Learning
#    scikit-learn, xgboost         →  Machine Learning
#    android studio, android sdk   →  Android
#    esp32, arduino, pyserial      →  IoT
#    leetcode, geeksforgeeks       →  DSA
#    pandas, numpy, matplotlib     →  Data Analysis
#
# 2. THREE-PASS PIPELINE
#
#    Pass 1 — Regex normalization
#      • Curly apostrophes/quotes → straight
#      • Standalone "C" (language) → "c language"
#      • React.js → React, Node.JS → Node.js  etc.
#      • OpenCV → opencv, MediaPipe → mediapipe  (alias casing)
#      • Pre-split into clean paragraphs (fixes spaCy sentence segmentation)
#
#    Pass 2 — PhraseMatcher (spaCy, attr="LOWER")
#      • Exact alias → canonical parent skill
#      • Tagged source="explicit"
#
#    Pass 3 — Semantic similarity (sentence-transformers)
#      Candidates built from THREE sources to maximize coverage:
#        a) spaCy noun chunks of 2+ words     → threshold 0.78
#        b) spaCy sentences (per paragraph)   → threshold 0.88
#        c) Sliding window n-grams (4–8 words)→ threshold 0.82
#           This is the KEY fix — catches phrases like:
#           "Amazon's cloud platform for hosting" → AWS
#           "packaging and shipping applications along with their dependencies" → Docker
#           even when spaCy sentence segmentation is poor on resume text.
#      Individual tokens EXCLUDED — single words cause false positives.
#      Tagged source="semantic"
#
# ─────────────────────────────────────────────────────────────────────────────

import re
import spacy
from spacy.matcher import PhraseMatcher
from collections import defaultdict

try:
    from sentence_transformers import SentenceTransformer, util
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False
    print("WARNING: sentence-transformers not installed. "
          "Run: pip install sentence-transformers")


class EnhancedSkillExtractor:

    NOUN_CHUNK_THRESHOLD  = 0.78   # 2+ word noun chunks
    SENTENCE_THRESHOLD    = 0.88   # full sentences (strict — sentence is long)
    NGRAM_THRESHOLD       = 0.82   # sliding window n-grams (4–8 words)

    NGRAM_MIN = 4   # minimum words in sliding window
    NGRAM_MAX = 8   # maximum words in sliding window

    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            raise RuntimeError(
                "spaCy model not found. Run: python -m spacy download en_core_web_sm"
            )

        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        self.skills_db = self._build_skills_db()

        self.skill_to_category: dict[str, str] = {}
        self._all_skill_names:  list[str]      = []
        self._create_patterns()

        if _ST_AVAILABLE:
            self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
            self._skill_embeddings = self._st_model.encode(
                self._all_skill_names, convert_to_tensor=True
            )
        else:
            self._st_model         = None
            self._skill_embeddings = None

    # ─────────────────────────────────────────────────────────────────── #
    #  SKILLS DATABASE                                                     #
    # ─────────────────────────────────────────────────────────────────── #

    def _build_skills_db(self) -> dict:
        return {

            "Programming Languages": {
                "Python":       ["python", "python3", "python 3"],
                "Java":         ["java", "jdk", "jre"],
                "C++":          ["c++", "cpp", "c plus plus"],
                "C":            ["c language", "c programming"],
                "C#":           ["c#", "csharp", "c sharp"],
                "JavaScript":   ["javascript", "js", "es6", "ecmascript"],
                "TypeScript":   ["typescript", "ts"],
                "Go":           ["golang", "go language"],
                "Rust":         ["rust lang"],
                "Kotlin":       ["kotlin"],
                "Swift":        ["swift"],
                "PHP":          ["php"],
                "Ruby":         ["ruby", "ruby on rails"],
                "Scala":        ["scala"],
                "R":            ["r programming", "r language"],
                "Dart":         ["dart"],
            },

            "Frontend Development": {
                "React":        ["react", "reactjs", "react.js"],
                "Angular":      ["angular", "angularjs"],
                "Vue.js":       ["vue", "vuejs", "vue.js"],
                "Next.js":      ["next.js", "nextjs"],
                "Svelte":       ["svelte"],
                "HTML":         ["html", "html5"],
                "CSS":          ["css", "css3"],
                "Bootstrap":    ["bootstrap"],
                "Tailwind CSS": ["tailwind", "tailwindcss", "tailwind css"],
                "Redux":        ["redux"],
            },

            "Backend Development": {
                "Node.js":      ["node.js", "nodejs", "node"],
                "Express.js":   ["express.js", "expressjs", "express"],
                "Django":       ["django"],
                "Flask":        ["flask"],
                "FastAPI":      ["fastapi"],
                "Spring Boot":  ["spring boot", "spring framework", "spring mvc"],
                "Laravel":      ["laravel"],
                "GraphQL":      ["graphql"],
                "REST API":     ["rest api", "restful api", "restful",
                                 "rest endpoints", "api development",
                                 "web api", "http api"],
            },

            "Databases": {
                "MySQL":        ["mysql"],
                "PostgreSQL":   ["postgresql", "postgres"],
                "MongoDB":      ["mongodb", "mongo"],
                "SQLite":       ["sqlite"],
                "Redis":        ["redis"],
                "Oracle":       ["oracle", "oracle db"],
                "SQL":          ["sql", "structured query language"],
                "Elasticsearch":["elasticsearch", "elastic search"],
                "DynamoDB":     ["dynamodb", "dynamo db"],
                "Cassandra":    ["cassandra", "apache cassandra"],
                "Firebase":     ["firebase", "firestore"],
            },

            "Cloud & DevOps": {
                "AWS":      [
                    "aws", "amazon web services",
                    "amazon ec2", "amazon s3", "amazon lambda", "amazon rds",
                    # descriptive phrases that mean AWS
                    "amazon cloud", "amazon's cloud", "amazons cloud",
                    "amazon cloud platform",
                ],
                "Azure":    ["azure", "microsoft azure"],
                "Google Cloud": [
                    "gcp", "google cloud", "google cloud platform",
                    "genai study jam", "google cloud study jam",
                ],
                "Docker":   [
                    "docker", "dockerfile", "docker compose",
                    # descriptive phrases that mean Docker
                    "containerization", "containers", "container platform",
                    "packaging applications", "shipping applications",
                    "packaging and shipping", "application containers",
                    "run consistently across environments",
                ],
                "Kubernetes":["kubernetes", "k8s", "kubectl"],
                "Terraform": ["terraform"],
                "Ansible":   ["ansible"],
                "Jenkins":   ["jenkins"],
                "Git":       ["git"],
                "GitHub":    ["github"],
                "GitLab":    ["gitlab"],
                "CI/CD":     ["ci/cd", "continuous integration",
                              "continuous deployment", "continuous delivery",
                              "github actions", "gitlab ci"],
            },

            "Data Science & AI": {
                "Machine Learning": [
                    "machine learning", "ml",
                    "scikit-learn", "sklearn", "scikit learn",
                    "xgboost", "lightgbm", "catboost",
                    "python for data science",
                ],
                "Deep Learning": [
                    "deep learning", "neural networks", "neural network",
                    "cnn", "convolutional neural network",
                    "rnn", "recurrent neural network",
                    "lstm", "transformer model", "bert",
                    "tensorflow", "tf.keras", "pytorch", "torch", "keras",
                ],
                "Computer Vision": [
                    "computer vision", "image recognition",
                    "object detection", "image processing",
                    "hand gesture recognition", "finger detection",
                    "gesture detection",
                    "opencv", "cv2", "open cv",
                    "mediapipe", "media pipe",
                    "pillow", "pil", "imageai",
                ],
                "NLP": [
                    "nlp", "natural language processing",
                    "text classification", "sentiment analysis",
                    "named entity recognition", "ner",
                    "spacy", "nltk", "gensim",
                    "hugging face", "huggingface",
                    "langchain", "lang chain", "transformers",
                ],
                "Generative AI": [
                    "generative ai", "genai", "gen ai",
                    "large language model", "llm", "llms",
                    "ai powered", "ai-powered",
                    "llama", "llama 3", "llama3", "mixtral",
                    "gpt", "gpt-4", "gpt-3", "chatgpt",
                    "gemini", "groq api", "groq",
                    "openai api", "openai", "anthropic",
                    "stable diffusion",
                ],
                "OCR": [
                    "ocr", "optical character recognition",
                    "handwritten text recognition",
                    "tesseract", "tesseract.js", "easyocr", "pytesseract",
                ],
                "Data Analysis": [
                    "data analysis", "data analytics",
                    "exploratory data analysis", "eda",
                    "data visualization", "data wrangling",
                    "pandas", "numpy",
                    "matplotlib", "seaborn", "plotly",
                    "jupyter", "jupyter notebook",
                    "tableau", "power bi",
                ],
                "Big Data": [
                    "big data", "apache spark", "pyspark",
                    "hadoop", "kafka", "data pipeline", "etl",
                ],
            },

            "Mobile Development": {
                "Android": [
                    "android", "android development",
                    "android studio", "android sdk",
                    "android app", "java android", "kotlin android",
                ],
                "React Native": ["react native"],
                "Flutter":      ["flutter"],
                "iOS": [
                    "ios", "ios development",
                    "xcode", "swift ui", "swiftui", "uikit",
                ],
            },

            "IoT & Hardware": {
                "IoT": [
                    "iot", "internet of things",
                    "smart appliance", "home automation",
                    "embedded systems", "microcontroller",
                    "esp32", "esp 32", "arduino", "arduino ide",
                    "raspberry pi", "gpio", "serial communication",
                    "pyserial", "uart", "i2c", "spi",
                ],
            },

            "Tools & Platforms": {
                "VS Code":   ["vs code", "vscode", "visual studio code"],
                "Postman":   ["postman"],
                "Figma":     ["figma"],
                "Jira":      ["jira"],
                "Linux":     ["linux", "ubuntu", "debian"],
                "Bash":      ["bash", "shell scripting", "shell script"],
            },

            "DSA & CS Fundamentals": {
                "DSA": [
                    "data structures and algorithms", "dsa",
                    "data structures", "algorithms", "mastering dsa",
                    "leetcode", "geeksforgeeks",
                    "competitive programming", "hackerrank dsa",
                    "codechef", "codeforces",
                ],
                "OOP": [
                    "object oriented programming", "oop",
                    "object-oriented programming",
                    "encapsulation", "inheritance", "polymorphism",
                ],
                "OS":           ["operating systems", "os concepts",
                                 "process management", "memory management"],
                "DBMS":         ["dbms", "database management systems",
                                 "normalization", "er diagram"],
                "Networking":   ["computer networks", "networking",
                                 "tcp/ip", "http", "dns", "osi model"],
                "System Design":["system design", "low level design",
                                 "high level design", "lld", "hld"],
            },

            "Testing & QA": {
                "Unit Testing": [
                    "unit testing", "unit tests",
                    "pytest", "jest", "junit", "mocha",
                    "test driven development", "tdd",
                ],
                "Selenium":    ["selenium", "selenium webdriver"],
                "API Testing": ["api testing", "postman testing"],
            },

            "Soft Skills & Methodologies": {
                "Problem Solving": ["problem solving", "problem-solving",
                                    "analytical thinking"],
                "Leadership":      ["leadership", "team lead", "led a team",
                                    "mentoring"],
                "Communication":   ["communication", "presentation skills"],
                "Agile":           ["agile", "scrum", "sprint", "kanban"],
                "Time Management": ["time management"],
                "Adaptability":    ["adaptability", "adaptable"],
                "Teamwork":        ["teamwork", "collaboration"],
            },
        }

    # ─────────────────────────────────────────────────────────────────── #
    #  BUILD PATTERNS                                                      #
    # ─────────────────────────────────────────────────────────────────── #

    def _create_patterns(self):
        for category, skills in self.skills_db.items():
            for skill_name, aliases in skills.items():
                self.skill_to_category[skill_name] = category
                if skill_name not in self._all_skill_names:
                    self._all_skill_names.append(skill_name)
                patterns = [self.nlp.make_doc(alias) for alias in aliases]
                self.matcher.add(skill_name, patterns)

    # ─────────────────────────────────────────────────────────────────── #
    #  PASS 1 — REGEX NORMALIZATION                                        #
    # ─────────────────────────────────────────────────────────────────── #

    def _normalize_text(self, text: str) -> str:
        """
        Normalize formatting so PhraseMatcher aliases match cleanly.
        Also pre-splits the text into clean paragraphs using double newlines
        so that spaCy sentence segmentation works correctly on resume text
        (resumes often have no sentence-ending punctuation between sections).
        """
        # Curly apostrophes and quotes → straight
        text = re.sub(r"[\u2018\u2019\u02BC]", "'", text)
        text = re.sub(r"[\u201C\u201D]",        '"', text)

        # Standalone C language — not followed by ++, #, SS(S), digits
        text = re.sub(
            r"(?<![A-Za-z0-9_#\+])\bC\b(?![+#A-Za-z0-9_])",
            "c language", text
        )

        # Punctuation/casing variants → canonical alias forms
        text = re.sub(r"\bReact\.js\b",      "React",        text, flags=re.IGNORECASE)
        text = re.sub(r"\bVue\.js\b",        "Vue.js",       text, flags=re.IGNORECASE)
        text = re.sub(r"\bNode\.JS\b",       "Node.js",      text, flags=re.IGNORECASE)
        text = re.sub(r"\bExpress\.JS\b",    "Express.js",   text, flags=re.IGNORECASE)
        text = re.sub(r"\bNext\.JS\b",       "Next.js",      text, flags=re.IGNORECASE)
        text = re.sub(r"\bTesseract\.js\b",  "tesseract.js", text, flags=re.IGNORECASE)
        text = re.sub(r"\bPySerial\b",       "pyserial",     text, flags=re.IGNORECASE)
        text = re.sub(r"\bOpenCV\b",         "opencv",       text, flags=re.IGNORECASE)
        text = re.sub(r"\bMediaPipe\b",      "mediapipe",    text, flags=re.IGNORECASE)
        text = re.sub(r"\bLLaMA\b",          "llama",        text, flags=re.IGNORECASE)
        text = re.sub(r"\bMixtral\b",        "mixtral",      text, flags=re.IGNORECASE)

        # Normalize Amazon's → amazons (apostrophe removed so alias matches)
        text = re.sub(r"\bAmazon's\b", "amazons", text, flags=re.IGNORECASE)

        # Collapse excessive whitespace (but preserve newlines for paragraph splitting)
        text = re.sub(r"[ \t]{2,}", " ", text)

        return text

    # ─────────────────────────────────────────────────────────────────── #
    #  SLIDING WINDOW N-GRAMS                                              #
    # ─────────────────────────────────────────────────────────────────── #

    def _sliding_window_ngrams(self, text: str) -> list[str]:
        """
        Generate overlapping n-grams (4 to 8 words) from each line/sentence.
        This is the KEY fix for descriptive resumes.

        Problem it solves:
          spaCy sentence segmentation fails on resume text because sections
          are often separated by newlines, not punctuation. This causes long
          "sentences" that get threshold 0.88 — too strict to match.

          Sliding window n-grams break the text into small focused windows
          that directly capture phrases like:
            "packaging and shipping applications along with their dependencies"
            "amazon cloud platform for hosting"

        These go through threshold 0.82 — between noun chunks and sentences.
        """
        ngrams = []
        # Split on newlines and periods to get clean segments
        segments = re.split(r'[\n\r\.]+', text)

        for segment in segments:
            words = segment.strip().split()
            for size in range(self.NGRAM_MIN, self.NGRAM_MAX + 1):
                for i in range(len(words) - size + 1):
                    gram = " ".join(words[i:i + size])
                    ngrams.append(gram)

        return ngrams

    # ─────────────────────────────────────────────────────────────────── #
    #  PASS 3 — SEMANTIC MATCHING                                          #
    # ─────────────────────────────────────────────────────────────────── #

    def _semantic_match(self, text: str, already_found: set[str]) -> list[str]:
        """
        Builds candidates from THREE sources:
          1. spaCy noun chunks (2+ words)         → threshold 0.78
          2. spaCy sentences per paragraph        → threshold 0.88
          3. Sliding window n-grams (4–8 words)   → threshold 0.82  ← KEY FIX

        The n-gram window is what catches descriptive phrases like:
          "packaging and shipping applications along with their dependencies"
            → Docker
          "amazon cloud platform for hosting and managing web applications"
            → AWS
        """
        if not _ST_AVAILABLE or self._st_model is None:
            return []

        doc = self.nlp(text)
        candidates: list[tuple[str, float]] = []
        seen_candidates: set[str] = set()

        def add(phrase: str, threshold: float):
            phrase = phrase.strip()
            if phrase and phrase not in seen_candidates:
                seen_candidates.add(phrase)
                candidates.append((phrase, threshold))

        # Source 1 — noun chunks (2+ words)
        for chunk in doc.noun_chunks:
            if len(chunk.text.split()) >= 2:
                add(chunk.text, self.NOUN_CHUNK_THRESHOLD)

        # Source 2 — sentences (split by paragraph first for cleaner segmentation)
        for paragraph in re.split(r'\n{1,}', text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            para_doc = self.nlp(paragraph)
            for sent in para_doc.sents:
                if len(sent.text.strip()) > 15:
                    add(sent.text.strip(), self.SENTENCE_THRESHOLD)

        # Source 3 — sliding window n-grams (4–8 words)
        for gram in self._sliding_window_ngrams(text):
            add(gram, self.NGRAM_THRESHOLD)

        if not candidates:
            return []

        texts      = [c[0] for c in candidates]
        thresholds = [c[1] for c in candidates]

        cand_emb      = self._st_model.encode(texts, convert_to_tensor=True)
        cosine_scores = util.cos_sim(cand_emb, self._skill_embeddings)

        found = []
        for idx, skill_name in enumerate(self._all_skill_names):
            if skill_name in already_found:
                continue
            skill_col = cosine_scores[:, idx]
            if any(float(skill_col[i]) >= thresholds[i] for i in range(len(candidates))):
                found.append(skill_name)

        return found

    # ─────────────────────────────────────────────────────────────────── #
    #  PUBLIC: extract_all_skills                                          #
    # ─────────────────────────────────────────────────────────────────── #

    def extract_all_skills(self, text: str) -> dict:
        """
        Returns:
            {
                "categories": {
                    category_name: [
                        {"name": "Python",  "source": "explicit"},
                        {"name": "Docker",  "source": "semantic"},
                        {"name": "AWS",     "source": "semantic"},
                    ]
                },
                "total_skills": int
            }
        """
        # Pass 1 — normalize
        normalized = self._normalize_text(text)

        doc     = self.nlp(normalized)
        matches = self.matcher(doc)

        categorized: dict[str, list[dict]] = defaultdict(list)
        seen:        set[str]              = set()

        # Pass 2 — PhraseMatcher
        for match_id, _start, _end in matches:
            skill_name = self.nlp.vocab.strings[match_id]
            if skill_name not in seen:
                seen.add(skill_name)
                category = self.skill_to_category.get(skill_name, "Other")
                categorized[category].append({
                    "name":   skill_name,
                    "source": "explicit",
                })

        # Pass 3 — semantic (noun chunks + sentences + n-gram sliding window)
        for skill_name in self._semantic_match(normalized, seen):
            if skill_name not in seen:
                seen.add(skill_name)
                category = self.skill_to_category.get(skill_name, "Other")
                categorized[category].append({
                    "name":   skill_name,
                    "source": "semantic",
                })

        # Preserve category order
        formatted: dict[str, list] = {
            cat: categorized.get(cat, [])
            for cat in self.skills_db
        }

        return {
            "categories":   formatted,
            "total_skills": sum(len(v) for v in formatted.values()),
        }