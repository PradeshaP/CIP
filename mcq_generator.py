
"""
mcq_generator.py
────────────────
Generates multiple-choice questions using the Groq API (LLaMA 3.3).

Design decisions:
  • Questions are generated ONCE per session and stored in PostgreSQL.
  • All users see the exact same questions in the same order.
  • Each MCQ has 4 options (a/b/c/d), one correct answer, and an explanation.
  • Questions span multiple skill categories so the test is well-rounded.
  • Difficulty distribution: 40% easy · 40% medium · 20% hard
    (calibrated for campus placement / fresher level)

MCQ quality rules baked into the prompt:
  ✅ All 4 options are plausible — no obviously wrong distractors
  ✅ Correct answer is spread uniformly (not always 'a' or 'b')
  ✅ Question tests UNDERSTANDING, not just memorisation
  ✅ Explanation teaches WHY, not just restates the correct answer
  ✅ No "all of the above" / "none of the above" options
"""

import os
import re
import json
import random
from groq import Groq


# Difficulty distribution for a balanced MCQ set
DIFFICULTY_DISTRIBUTION = {
    "easy":   0.40,
    "medium": 0.40,
    "hard":   0.20,
}

# Category weights — how many questions per category relative to total
CATEGORY_WEIGHTS = {
    "Programming Languages":  3,
    "Frontend Development":   2,
    "Backend Development":    2,
    "Databases":              2,
    "Cloud & DevOps":         2,
    "Data Science & AI":      2,
    "AI & Vision Libraries":  1,
    "IoT & Hardware":         1,
    "Mobile Development":     1,
    "Testing & QA":           1,
    "Soft Skills & Methodologies": 1,
}


class MCQGenerator:

    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model  = "llama-3.3-70b-versatile"

    # ──────────────────────────────────────────────────────────────────── #
    #  PUBLIC                                                               #
    # ──────────────────────────────────────────────────────────────────── #

    def generate_mcq_set(
        self,
        skills_data:   dict,
        total_questions: int  = 20,
        difficulty:    str   = "mixed",  # "easy"|"medium"|"hard"|"mixed"
    ) -> list[dict]:
        """
        Generate a complete MCQ set.

        Args:
            skills_data    : same format as enhanced_skill_extractor output
                             { "categories": { cat: [ {"name":..., "source":...} ] } }
            total_questions: how many questions (10–30 recommended)
            difficulty     : "mixed" = distribution from DIFFICULTY_DISTRIBUTION

        Returns:
            List of dicts, each with:
            {
                question_text, option_a, option_b, option_c, option_d,
                correct_option, explanation, skill, category, difficulty
            }
        """
        # Determine which skills are available
        available: dict[str, list[str]] = {}
        for cat, skill_list in skills_data.get("categories", {}).items():
            names = [s["name"] for s in skill_list]
            if names:
                available[cat] = names

        if not available:
            print("[MCQGenerator] No skills found in skills_data.")
            return []

        # Allocate questions per category
        allocation = self._allocate_questions(available, total_questions)
        print(f"[MCQGenerator] Question allocation: {allocation}")

        # Generate in batches per category
        all_questions: list[dict] = []
        for cat, (skills, count) in allocation.items():
            if count == 0:
                continue
            print(f"[MCQGenerator] Generating {count} question(s) for [{cat}]…")
            qs = self._generate_for_category(
                category=cat,
                skills=skills,
                count=count,
                difficulty=difficulty,
            )
            all_questions.extend(qs)

        # Shuffle so categories are interleaved (not all Python then all React)
        random.shuffle(all_questions)

        # Trim to exactly total_questions (generation may over/under-produce)
        all_questions = all_questions[:total_questions]

        # Final quality check
        valid = [q for q in all_questions if self._is_valid_mcq(q)]
        print(f"[MCQGenerator] Generated {len(valid)} valid questions "
              f"(requested {total_questions}).")
        return valid

    # ──────────────────────────────────────────────────────────────────── #
    #  ALLOCATION                                                           #
    # ──────────────────────────────────────────────────────────────────── #

    def _allocate_questions(
        self,
        available: dict[str, list[str]],
        total:     int,
    ) -> dict[str, tuple[list[str], int]]:
        """
        Distribute `total` questions across available categories
        using CATEGORY_WEIGHTS as relative weights.
        Returns { category: (skill_names_list, question_count) }
        """
        # Filter weights to only available categories
        weights = {
            cat: CATEGORY_WEIGHTS.get(cat, 1)
            for cat in available
        }
        total_weight = sum(weights.values()) or 1

        allocation: dict[str, tuple[list[str], int]] = {}
        assigned  = 0

        cats_sorted = sorted(weights.items(), key=lambda x: -x[1])
        for i, (cat, w) in enumerate(cats_sorted):
            # Last category gets remaining questions
            if i == len(cats_sorted) - 1:
                count = total - assigned
            else:
                count = max(1, round((w / total_weight) * total))

            count      = min(count, total - assigned)
            assigned  += count
            allocation[cat] = (available[cat], count)

            if assigned >= total:
                break

        return allocation

    # ──────────────────────────────────────────────────────────────────── #
    #  GENERATION PROMPT                                                    #
    # ──────────────────────────────────────────────────────────────────── #

    def _generate_for_category(
        self,
        category:   str,
        skills:     list[str],
        count:      int,
        difficulty: str,
    ) -> list[dict]:
        """Generate MCQs for a specific category via Groq API."""

        # Build difficulty instruction
        if difficulty == "mixed":
            easy_n   = max(1, round(count * DIFFICULTY_DISTRIBUTION["easy"]))
            medium_n = max(1, round(count * DIFFICULTY_DISTRIBUTION["medium"]))
            hard_n   = max(0, count - easy_n - medium_n)
            diff_instr = (
                f"Generate a mix: approximately {easy_n} easy, "
                f"{medium_n} medium, {hard_n} hard questions."
            )
        else:
            diff_instr = f"All questions should be {difficulty} difficulty."

        skills_str = ", ".join(skills[:8])  # cap to avoid token overflow

        prompt = f"""You are a senior technical interviewer creating a multiple-choice question bank
for a campus placement exam for B.Tech / B.E. Computer Science students.

════════════════════════════════════════════════════════════
TASK
════════════════════════════════════════════════════════════
Generate exactly {count} MCQ(s) for category: {category}
Skills to cover (pick the most important ones): {skills_str}
Difficulty: {diff_instr}

════════════════════════════════════════════════════════════
STRICT MCQ QUALITY RULES
════════════════════════════════════════════════════════════
  ✅ Each question tests UNDERSTANDING, not memorisation of definitions
  ✅ All 4 options must be plausible — avoid obviously wrong distractors
  ✅ The correct answer must be spread across a, b, c, d — do NOT always use 'a' or 'b'
  ✅ Explanation must teach WHY the answer is correct AND why others are wrong
  ✅ Questions use patterns like:
       "What happens when...", "Which of the following correctly...",
       "What is the output of...", "Why does...", "Which approach is best when..."
  ❌ NEVER use "All of the above" or "None of the above" as an option
  ❌ NEVER make the correct answer obvious from the question phrasing
  ❌ NEVER repeat question patterns within the same batch

════════════════════════════════════════════════════════════
DIFFICULTY GUIDE
════════════════════════════════════════════════════════════
  Easy   → Tests basic concept: "What does X mean?" or "Which syntax is correct?"
  Medium → Tests applied understanding: "When would you use X?" or "What happens if?"
  Hard   → Tests edge cases or internals: "What is the output?" or "Which is faster and why?"

════════════════════════════════════════════════════════════
OUTPUT FORMAT — valid JSON array ONLY, no extra text
════════════════════════════════════════════════════════════
[
  {{
    "question_text":  "<clear, specific question>",
    "option_a":       "<plausible option>",
    "option_b":       "<plausible option>",
    "option_c":       "<plausible option>",
    "option_d":       "<plausible option>",
    "correct_option": "<a|b|c|d>",
    "explanation":    "<2-3 sentences: why correct, why others are wrong>",
    "skill":          "<specific skill name from: {skills_str}>",
    "category":       "{category}",
    "difficulty":     "<easy|medium|hard>"
  }}
]
"""

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role":    "system",
                        "content": (
                            "You are an expert MCQ creator for CS/IT campus exams. "
                            "Always return valid JSON only — no markdown, no extra text."
                        )
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,   # some variety but not too wild for MCQs
                max_tokens=3000,
            )
            raw    = self._clean_json(resp.choices[0].message.content)
            parsed = json.loads(raw)
            result = parsed if isinstance(parsed, list) else [parsed]
            return result

        except Exception as e:
            print(f"[MCQGenerator] Error for [{category}]: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────── #
    #  VALIDATION                                                           #
    # ──────────────────────────────────────────────────────────────────── #

    def _is_valid_mcq(self, q: dict) -> bool:
        required = [
            "question_text", "option_a", "option_b",
            "option_c", "option_d", "correct_option",
        ]
        for field in required:
            if not q.get(field):
                return False
        if q["correct_option"].lower() not in ("a", "b", "c", "d"):
            return False
        if len(q["question_text"]) < 15:
            return False
        # Reject "all/none of the above"
        options = [q.get(f"option_{o}", "").lower() for o in "abcd"]
        if any("all of the above" in o or "none of the above" in o for o in options):
            return False
        return True

    @staticmethod
    def _clean_json(text: str) -> str:
        text = text.strip()
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$",          "", text).strip()
        # Extract first JSON array
        m = re.search(r"\[.*\]", text, flags=re.DOTALL)
        return m.group() if m else text