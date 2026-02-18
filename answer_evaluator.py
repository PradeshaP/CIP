"""
answer_evaluator.py
Evaluates user answers to interview questions using Groq API.
"""

import os
import json
import re
from groq import Groq
from dotenv import load_dotenv
load_dotenv()

class AnswerEvaluator:

    SCORING_RUBRIC = {
        "technical_accuracy": 40,
        "completeness":        30,
        "clarity":             20,
        "practical_insight":   10,
    }

    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"

    # ------------------------------------------------------------------ #
    #  PUBLIC: evaluate a single answer                                    #
    # ------------------------------------------------------------------ #

    def evaluate_answer(
        self,
        question: str,
        user_answer: str,
        model_answer: str,
        skill: str,
        difficulty: str = "medium",
    ) -> dict:
        """
        Returns:
            {
                "total_score":        int (0–100),
                "grade":              str ("Excellent" | "Good" | "Average" | "Needs Improvement"),
                "breakdown": {
                    "technical_accuracy": int,
                    "completeness":       int,
                    "clarity":            int,
                    "practical_insight":  int,
                },
                "strengths":          list[str],
                "improvements":       list[str],
                "detailed_feedback":  str,
                "correct_answer_summary": str,
            }
        """
        if not user_answer or not user_answer.strip():
            return self._empty_answer_result()

        prompt = f"""You are a strict but fair technical interviewer evaluating a candidate's answer.

SKILL BEING TESTED: {skill}
DIFFICULTY: {difficulty}

QUESTION:
{question}

MODEL ANSWER (ground truth):
{model_answer}

CANDIDATE'S ANSWER:
{user_answer}

Evaluate using this rubric (max points shown):
- technical_accuracy : {self.SCORING_RUBRIC['technical_accuracy']} pts  (factual correctness)
- completeness       : {self.SCORING_RUBRIC['completeness']} pts  (key points covered)
- clarity            : {self.SCORING_RUBRIC['clarity']} pts  (explanation quality)
- practical_insight  : {self.SCORING_RUBRIC['practical_insight']} pts  (real-world awareness)

Return ONLY a valid JSON object (no markdown, no extra text):
{{
  "breakdown": {{
    "technical_accuracy": <0-{self.SCORING_RUBRIC['technical_accuracy']}>,
    "completeness":       <0-{self.SCORING_RUBRIC['completeness']}>,
    "clarity":            <0-{self.SCORING_RUBRIC['clarity']}>,
    "practical_insight":  <0-{self.SCORING_RUBRIC['practical_insight']}>
  }},
  "strengths":              ["<point 1>", "<point 2>"],
  "improvements":           ["<point 1>", "<point 2>"],
  "detailed_feedback":      "<2-3 sentence constructive paragraph>",
  "correct_answer_summary": "<one sentence summary of the ideal answer>"
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a strict but fair technical interviewer. Always respond with valid JSON only, no markdown, no extra text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=800,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"^```(?:json)?", "", raw).strip()
            raw = re.sub(r"```$", "", raw).strip()
            result = json.loads(raw)

            breakdown = result.get("breakdown", {})
            total = sum(breakdown.values())
            result["total_score"] = total
            result["grade"] = self._score_to_grade(total)
            return result

        except Exception as e:
            print(f"[AnswerEvaluator] Evaluation error: {e}")
            return self._error_result()

    # ------------------------------------------------------------------ #
    #  PUBLIC: evaluate ALL answers and compute session summary            #
    # ------------------------------------------------------------------ #

    def compute_session_summary(self, evaluations: list[dict], questions: list[dict]) -> dict:
        """
        Takes a list of evaluation results and their corresponding questions.
        Returns an overall session report.
        """
        if not evaluations:
            return {}

        scores = [e.get("total_score", 0) for e in evaluations]
        avg_score = round(sum(scores) / len(scores), 1)

        category_scores: dict[str, list[int]] = {}
        for i, evaluation in enumerate(evaluations):
            if i < len(questions):
                cat = questions[i].get("category", "Other")
                category_scores.setdefault(cat, []).append(
                    evaluation.get("total_score", 0)
                )

        category_averages = {
            cat: round(sum(s) / len(s), 1)
            for cat, s in category_scores.items()
        }

        strengths = []
        improvements = []
        for e in evaluations:
            strengths.extend(e.get("strengths", []))
            improvements.extend(e.get("improvements", []))

        return {
            "total_questions":   len(evaluations),
            "average_score":     avg_score,
            "overall_grade":     self._score_to_grade(avg_score),
            "highest_score":     max(scores),
            "lowest_score":      min(scores),
            "category_averages": category_averages,
            "top_strengths":     list(dict.fromkeys(strengths))[:5],
            "top_improvements":  list(dict.fromkeys(improvements))[:5],
        }

    # ------------------------------------------------------------------ #
    #  PRIVATE helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _score_to_grade(score: float) -> str:
        if score >= 85:
            return "Excellent"
        if score >= 70:
            return "Good"
        if score >= 50:
            return "Average"
        return "Needs Improvement"

    @staticmethod
    def _empty_answer_result() -> dict:
        return {
            "total_score": 0,
            "grade": "Needs Improvement",
            "breakdown": {
                "technical_accuracy": 0,
                "completeness": 0,
                "clarity": 0,
                "practical_insight": 0,
            },
            "strengths": [],
            "improvements": ["Please provide an answer to be evaluated."],
            "detailed_feedback": "No answer was provided.",
            "correct_answer_summary": "",
        }

    @staticmethod
    def _error_result() -> dict:
        return {
            "total_score": 0,
            "grade": "Error",
            "breakdown": {},
            "strengths": [],
            "improvements": [],
            "detailed_feedback": "Evaluation failed. Please try again.",
            "correct_answer_summary": "",
        }