# enhanced_skill_extractor.py

import spacy
from spacy.matcher import PhraseMatcher
from collections import defaultdict


class EnhancedSkillExtractor:

    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except:
            raise Exception(
                "spaCy model not found. Run: python -m spacy download en_core_web_sm"
            )

        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")

        self.skills_db = self._load_skills_database()
        self.skill_to_category = {}

        self._create_patterns()

    # ---------------- SKILL DATABASE WITH ALIASES ---------------- #

    def _load_skills_database(self):
        return {

            "Programming Languages": {
                "Python": ["python", "python3"],
                "Java": ["java"],
                "C++": ["c++", "cpp"],
                "C#": ["c#", "csharp"],
                "Go": ["go", "golang"],
                "R": ["r programming", "r"]
            },

            "Frontend Development": {
                "React": ["react", "reactjs", "react.js"],
                "JavaScript": ["javascript", "js"],
                "TypeScript": ["typescript", "ts"],
                "Angular": ["angular", "angularjs"],
                "Vue.js": ["vue", "vuejs"],
                "HTML": ["html"],
                "CSS": ["css"],
                "Bootstrap": ["bootstrap"],
                "Tailwind CSS": ["tailwind", "tailwindcss"]
            },

            "Backend Development": {
                "Node.js": ["node", "nodejs", "node.js"],
                "Express.js": ["express", "expressjs"],
                "Django": ["django"],
                "Flask": ["flask"],
                "Spring Boot": ["spring boot"],
                ".NET Core": [".net core", "dotnet core"]
            },

            "Databases": {
                "MySQL": ["mysql"],
                "SQL": ["sql"],
                "PostgreSQL": ["postgresql", "postgres"],
                "MongoDB": ["mongodb", "mongo"],
                "SQLite": ["sqlite"],
                "Oracle": ["oracle db", "oracle"]
            },

            "Cloud & DevOps": {
                "AWS": ["aws", "amazon web services"],
                "Azure": ["azure", "microsoft azure"],
                "Google Cloud": ["gcp", "google cloud"],
                "Docker": ["docker"],
                "Kubernetes": ["kubernetes", "k8s"],
                "Git": ["git", "github", "gitlab"],
                "CI/CD": ["ci/cd", "continuous integration", "continuous deployment"]
            },

            "Data Science & AI": {
                "Machine Learning": ["machine learning", "ml"],
                "Deep Learning": ["deep learning", "dl"],
                "NLP": ["nlp", "natural language processing"],
                "TensorFlow": ["tensorflow", "tf"],
                "PyTorch": ["pytorch"],
                "Pandas": ["pandas"],
                "NumPy": ["numpy"],
                "Scikit-learn": ["scikit learn", "sklearn"]
            }
        }

    # ---------------- CREATE NLP PATTERNS ---------------- #

    def _create_patterns(self):
        for category, skills in self.skills_db.items():
            for skill_name, aliases in skills.items():

                self.skill_to_category[skill_name] = category

                patterns = []
                for alias in aliases:
                    patterns.append(self.nlp.make_doc(alias))

                self.matcher.add(skill_name, patterns)

    # ---------------- EXTRACT SKILLS ---------------- #

    def extract_all_skills(self, text):
        doc = self.nlp(text)
        matches = self.matcher(doc)

        categorized_skills = defaultdict(list)
        seen = set()

        for match_id, start, end in matches:
            skill_name = self.nlp.vocab.strings[match_id]

            if skill_name not in seen:
                seen.add(skill_name)

                category = self.skill_to_category.get(skill_name, "Other")

                categorized_skills[category].append({
                    "name": skill_name,
                    "source": "explicit"
                })

        # Ensure all categories exist
        formatted_output = {}
        for category in self.skills_db.keys():
            formatted_output[category] = categorized_skills.get(category, [])

        return {
            "categories": formatted_output,
            "total_skills": sum(len(v) for v in formatted_output.values())
        }
