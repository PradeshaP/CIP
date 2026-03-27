"""
answer_evaluator.py

Evaluates student answers using Groq API.

EVALUATION METHOD — LLaMA gives a Likert rating (1-5) per question:
  1 = Very Poor  — completely wrong, no understanding shown
  2 = Poor       — some relevant points but major gaps or errors
  3 = Average    — knows the basics, missing key details
  4 = Good       — solid answer, only minor gaps
  5 = Excellent  — complete, accurate, well explained

Likert → Score conversion:
  1 → 20/100
  2 → 40/100
  3 → 60/100
  4 → 80/100
  5 → 100/100

LLaMA also provides:
  - strengths        : what the student got right
  - improvements     : what is missing or wrong
  - detailed_feedback: 2-3 sentence constructive paragraph
  - correct_answer_summary: one line ideal answer
"""

import os
import json
import re
from groq import Groq
from dotenv import load_dotenv
load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# LIKERT SCALE DEFINITION
# ─────────────────────────────────────────────────────────────────────────────

LIKERT_SCALE = {
    1: {"label": "Very Poor",  "emoji": "😟", "color": "#ef4444"},
    2: {"label": "Poor",       "emoji": "😕", "color": "#f97316"},
    3: {"label": "Average",    "emoji": "😐", "color": "#eab308"},
    4: {"label": "Good",       "emoji": "🙂", "color": "#22c55e"},
    5: {"label": "Excellent",  "emoji": "😄", "color": "#10b981"},
}


# ─────────────────────────────────────────────────────────────────────────────
# ANSWER EVALUATOR
# ─────────────────────────────────────────────────────────────────────────────

class AnswerEvaluator:

    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model  = "llama-3.3-70b-versatile"

    # ------------------------------------------------------------------ #
    #  PUBLIC: evaluate_answer                                             #
    # ------------------------------------------------------------------ #

    def evaluate_answer(
        self,
        question:     str,
        user_answer:  str,
        model_answer: str,
        skill:        str,
    ) -> dict:
        """
        LLaMA reads the question, model answer, and student answer.
        Returns a Likert rating (1-5) + detailed feedback.

        Returns:
          {
            "likert":                int   1-5
            "likert_label":          str   Very Poor / Poor / Average / Good / Excellent
            "likert_emoji":          str   😟 / 😕 / 😐 / 🙂 / 😄
            "likert_color":          str   hex color
            "total_score":           int   20/40/60/80/100
            "strengths":             list[str]
            "improvements":          list[str]
            "detailed_feedback":     str
            "correct_answer_summary":str
          }
        """
        if not user_answer or not user_answer.strip():
            return self._empty_answer_result()

        prompt = f"""You are a strict but fair technical interviewer evaluating a fresher candidate's answer.

SKILL BEING TESTED: {skill}

QUESTION:
{question}

MODEL ANSWER (ideal answer for reference):
{model_answer}

CANDIDATE'S ANSWER:
{user_answer}

════════════════════════════════════════════════════════════
EVALUATION INSTRUCTIONS
════════════════════════════════════════════════════════════
Read the candidate's answer carefully and compare it against the model answer.
Give a single Likert rating based on overall quality:

  1 = Very Poor
      - Completely wrong or irrelevant answer
      - Shows no understanding of the concept
      - Example: blank answer, totally off topic, or fundamentally incorrect

  2 = Poor
      - Has 1-2 relevant points but major gaps or errors
      - Missing the core concept
      - Shows very limited understanding

  3 = Average
      - Knows the basic concept
      - Missing important details or examples
      - Partially correct but incomplete

  4 = Good
      - Solid answer covering most key points
      - Only minor gaps or imprecision
      - Shows clear understanding

  5 = Excellent
      - Complete, accurate, and well explained
      - Covers all key points from the model answer
      - May include relevant examples or practical insight

════════════════════════════════════════════════════════════
STRICT RULES FOR FAIR EVALUATION
════════════════════════════════════════════════════════════
- Compare ONLY against the model answer — do not penalise for extra correct info
- A fresher is not expected to know everything — judge relative to the skill level
- If the answer is correct but brief → 3 or 4, not 1
- If the answer is wrong but shows some effort → 2, not 1
- Do NOT give 5 unless the answer matches the model answer closely
- Do NOT give 1 unless the answer is completely wrong or blank

Return ONLY valid JSON, no markdown, no extra text:
{{
  "likert":                <1|2|3|4|5>,
  "score":                 <0-100 exact score>,
  "strengths":             ["<specific strength 1>", "<specific strength 2>"],
  "improvements":          ["<specific improvement 1>", "<specific improvement 2>"],
  "detailed_feedback":     "<2-3 sentence constructive paragraph explaining the rating>",
  "correct_answer_summary":"<one sentence summary of what the ideal answer should cover>"
}}

IMPORTANT:
  likert and score must be consistent:
    likert 1 → score between 0-20
    likert 2 → score between 21-40
    likert 3 → score between 41-60
    likert 4 → score between 61-80
    likert 5 → score between 81-100
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role":    "system",
                        "content": (
                            "You are a strict but fair technical interviewer for campus placements. "
                            "Evaluate answers honestly and return valid JSON only, no markdown."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,   # low — consistent, fair ratings
                max_tokens=600,
            )
            raw    = self._clean_json(response.choices[0].message.content)
            result = json.loads(raw)

            likert      = int(result.get("likert", 3))
            likert      = max(1, min(5, likert))      # clamp 1-5
            total_score = int(result.get("score", 0))
            total_score = max(0, min(100, total_score)) # clamp 0-100
            scale_info  = LIKERT_SCALE[likert]

            result["likert"]        = likert
            result["likert_label"]  = scale_info["label"]
            result["likert_emoji"]  = scale_info["emoji"]
            result["likert_color"]  = scale_info["color"]
            result["total_score"]   = total_score
            result["grade"]         = scale_info["label"]
            return result

        except Exception as e:
            print(f"[AnswerEvaluator] Evaluation error: {e}")
            return self._error_result()

    # ------------------------------------------------------------------ #
    #  PUBLIC: compute_session_summary                                     #
    # ------------------------------------------------------------------ #

    def compute_session_summary(
        self,
        evaluations: list[dict],
        questions:   list[dict],
    ) -> dict:
        if not evaluations:
            return {}

        scores    = [e.get("total_score", 0) for e in evaluations]
        likerts   = [e.get("likert", 3)      for e in evaluations]
        avg_score = round(sum(scores) / len(scores), 1)
        avg_likert = round(sum(likerts) / len(likerts), 1)

        # Category averages
        category_scores: dict[str, list[int]] = {}
        for i, ev in enumerate(evaluations):
            if i < len(questions):
                cat = questions[i].get("category", "Other")
                category_scores.setdefault(cat, []).append(ev.get("total_score", 0))

        category_averages = {
            cat: round(sum(s) / len(s), 1)
            for cat, s in category_scores.items()
        }

        # Likert distribution
        likert_dist = {
            LIKERT_SCALE[i]["label"]: likerts.count(i)
            for i in range(1, 6)
        }

        # Top strengths and improvements
        strengths    = []
        improvements = []
        for e in evaluations:
            strengths.extend(e.get("strengths", []))
            improvements.extend(e.get("improvements", []))

        return {
            "total_questions":    len(evaluations),
            "average_score":      avg_score,
            "overall_grade":      self._score_to_grade(avg_score),
            "highest_score":      max(scores),
            "lowest_score":       min(scores),
            "avg_likert":         avg_likert,
            "likert_distribution":likert_dist,
            "category_averages":  category_averages,
            "top_strengths":      list(dict.fromkeys(strengths))[:5],
            "top_improvements":   list(dict.fromkeys(improvements))[:5],
        }

    # ------------------------------------------------------------------ #
    #  PRIVATE helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _score_to_grade(score: float) -> str:
        if   score >= 80: return "Excellent"
        elif score >= 60: return "Good"
        elif score >= 40: return "Average"
        elif score >= 20: return "Poor"
        else:             return "Very Poor"

    @staticmethod
    def _clean_json(text: str) -> str:
        text = text.strip()
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$",          "", text).strip()
        return text

    @staticmethod
    def _empty_answer_result() -> dict:
        return {
            "likert":                 0,
            "likert_label":           "Not Answered",
            "likert_emoji":           "⬜",
            "likert_color":           "#94a3b8",
            "total_score":            0,
            "grade":                  "Very Poor",
            "strengths":              [],
            "improvements":           ["Please provide an answer to be evaluated."],
            "detailed_feedback":      "No answer was provided.",
            "correct_answer_summary": "",
        }

    @staticmethod
    def _error_result() -> dict:
        return {
            "likert":                 0,
            "likert_label":           "Error",
            "likert_emoji":           "⚠️",
            "likert_color":           "#94a3b8",
            "total_score":            0,
            "grade":                  "Error",
            "strengths":              [],
            "improvements":           [],
            "detailed_feedback":      "Evaluation failed. Please try again.",
            "correct_answer_summary": "",
        }