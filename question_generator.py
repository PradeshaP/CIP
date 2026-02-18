"""
question_generator.py
Generates interview questions based on extracted skills using Groq API.
"""

import os
import json
import re
from groq import Groq


class QuestionGenerator:

    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        # llama-3.3-70b-versatile: fast, free-tier friendly, great at JSON
        self.model = "llama-3.3-70b-versatile"

    # ------------------------------------------------------------------ #
    #  PUBLIC: generate questions for all extracted skills                 #
    # ------------------------------------------------------------------ #

    def generate_questions(
        self,
        skills_data: dict,
        difficulty: str = "medium",
        questions_per_skill: int = 2,
    ) -> list[dict]:
        """
        Given the output of EnhancedSkillExtractor.extract_all_skills(),
        return a flat list of question dicts:

            {
                "id":         int,
                "skill":      str,
                "category":   str,
                "difficulty": str,
                "question":   str,
                "type":       str,   # "conceptual" | "practical" | "scenario"
                "hints":      list[str],
                "model_answer": str,
            }
        """
        all_skills: list[tuple[str, str]] = []  # (skill_name, category)

        for category, skills_list in skills_data.get("categories", {}).items():
            for skill in skills_list:
                all_skills.append((skill["name"], category))

        if not all_skills:
            return []

        questions: list[dict] = []
        qid = 1

        for skill_name, category in all_skills:
            skill_questions = self._generate_for_skill(
                skill_name, category, difficulty, questions_per_skill
            )
            for q in skill_questions:
                q["id"] = qid
                questions.append(q)
                qid += 1

        return questions

    # ------------------------------------------------------------------ #
    #  PRIVATE: generate questions for a single skill                      #
    # ------------------------------------------------------------------ #

    def _generate_for_skill(
        self,
        skill_name: str,
        category: str,
        difficulty: str,
        count: int,
    ) -> list[dict]:
        prompt = f"""You are an expert technical interviewer.
Generate exactly {count} interview question(s) for the skill: **{skill_name}** (category: {category}).
Difficulty level: {difficulty}

Return ONLY a valid JSON array (no markdown, no extra text) with this exact schema for each element:
{{
  "skill": "{skill_name}",
  "category": "{category}",
  "difficulty": "{difficulty}",
  "question": "<the interview question>",
  "type": "<conceptual | practical | scenario>",
  "hints": ["<hint 1>", "<hint 2>"],
  "model_answer": "<a comprehensive model answer in 3-5 sentences>"
}}

Rules:
- Mix question types across the {count} questions.
- Make questions precise, technical, and genuinely discriminating.
- Hints should nudge without giving the answer away.
- model_answer must be thorough but concise.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a technical interview question generator. Always respond with valid JSON only, no markdown, no extra text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1500,
            )
            raw = response.choices[0].message.content.strip()
            # Strip possible markdown fences
            raw = re.sub(r"^```(?:json)?", "", raw).strip()
            raw = re.sub(r"```$", "", raw).strip()
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else [parsed]
        except Exception as e:
            print(f"[QuestionGenerator] Error for skill '{skill_name}': {e}")
            return []