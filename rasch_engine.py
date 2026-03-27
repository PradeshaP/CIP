"""
rasch_engine.py
1-PL Rasch IRT engine — faithful to your senior's notebook (Cell 1 + Cell 3).

FORMULA:  P(correct | θ, b) = 1 / (1 + e^-(θ-b))
  θ : student ability    -3.0 to +3.0, starts 0.0
  b : question difficulty -2.0 to +2.0, from dataset

  ✅ update_theta()         — same alpha=0.3, same formula
  ✅ update_b_online()      — b drifts per response (alpha_b=0.03)
  ✅ calibrate_b()          — log-odds batch recalibration after N responses
  ✅ select_question()      — b≈θ + random tie-breaking + step-down on wrong
  ✅ fisher_info()          — Fisher information I(θ,b) = P(1-P)
  ✅ se_theta()             — Standard error of θ estimate
  ✅ SkillSession class     — mirrors StudentSession from Cell 3
"""

import math
import random


ALPHA               = 0.3     # θ learning rate
ALPHA_B             = 0.03    # b online update rate
THETA_MIN           = -3.0
THETA_MAX           =  3.0
B_MIN               = -2.0
B_MAX               =  2.0
THETA_INIT          =  0.0
CALIB_MIN_RESPONSES =  5      # recalibrate b after this many responses

PROFICIENCY_BANDS = [
    ( 1.5,  3.0, "Expert",       "#534AB7"),
    ( 0.5,  1.5, "Advanced",     "#1D9E75"),
    (-0.5,  0.5, "Intermediate", "#378ADD"),
    (-1.5, -0.5, "Beginner",     "#EF9F27"),
    (-3.0, -1.5, "Novice",       "#E24B4A"),
]


# ── Core IRT math ─────────────────────────────────────────────────────────────

def p_correct(theta: float, b: float) -> float:
    """Rasch probability of correct answer."""
    return 1.0 / (1.0 + math.exp(-(theta - b)))


def update_theta(theta: float, b: float, is_correct: bool) -> float:
    """
    Update θ after one answer.
    surprise = is_correct - P(θ, b)
    θ_new    = θ + α × surprise
    Clamped to [THETA_MIN, THETA_MAX].
    """
    p         = p_correct(theta, b)
    surprise  = int(is_correct) - p
    new_theta = theta + ALPHA * surprise
    return float(max(THETA_MIN, min(THETA_MAX, new_theta)))


def update_b_online(b: float, theta: float, is_correct: bool) -> float:
    """
    Online b update — called after every answer (from senior's Cell 1).
    If wrong  → student found it harder than b suggests → b drifts DOWN.
    If correct → student found it easier than b suggests → b drifts UP.
    grad = -(y - P)  opposite direction to θ update.
    """
    p    = p_correct(theta, b)
    grad = -(int(is_correct) - p)
    new_b = b - ALPHA_B * grad
    return float(max(B_MIN, min(B_MAX, new_b)))


def calibrate_b(response_count: int, correct_count: int) -> float | None:
    """
    Batch calibration using Rasch log-odds formula (from senior's Cell 1).
    b = -ln(p / (1-p))  where p = pass rate.
    Only runs after CALIB_MIN_RESPONSES responses.
    Returns None if not enough data yet.

    Interpretation:
      pass rate 80% → b = -1.39 (easier than initially tagged)
      pass rate 20% → b = +1.39 (harder than initially tagged)
    """
    if response_count < CALIB_MIN_RESPONSES:
        return None
    p = correct_count / response_count
    p = max(0.01, min(0.99, p))           # avoid log(0)
    b_cal = -math.log(p / (1.0 - p))
    return float(max(B_MIN, min(B_MAX, b_cal)))


def fisher_info(theta: float, b: float) -> float:
    """
    Fisher information at (θ, b).
    Peaks at b=θ where I = 0.25 (maximum information point).
    """
    p = p_correct(theta, b)
    return p * (1.0 - p)


def se_theta(responses: list[dict]) -> float:
    """
    Standard error of θ estimate (from senior's Cell 1).
    SE = 1 / sqrt(sum of Fisher information across all responses).
    Shrinks as more answers accumulate — θ estimate gets more precise.
    responses: list of dicts with 'theta_before' and 'b_used'.
    """
    if not responses:
        return 1.0
    total = sum(fisher_info(r["theta_before"], r["b_used"]) for r in responses)
    return round(1.0 / math.sqrt(total), 4) if total > 0 else 1.0


def select_question(pool: list[dict], theta: float,
                    asked_ids: set, last_correct=None) -> dict | None:
    """
    Adaptive question selection — matches senior's Cell 1 select_question().

    Logic:
      - If last answer was CORRECT (or first question):
          pick question with b closest to θ from ANY direction
      - If last answer was WRONG:
          prefer questions where b <= θ (step difficulty DOWN)
          if no easier question exists, use closest available

    Tie-breaking: adds tiny random noise (0 to 1e-4) to distance
    so equal-distance questions are not always selected in same order.
    This matches senior's: pool["dist"] + np.random.uniform(0, 1e-4, len(pool))
    """
    candidates = [q for q in pool if q["question_id"] not in asked_ids]
    if not candidates:
        return None

    if last_correct is False:
        easier = [q for q in candidates if q["b_param"] <= theta]
        if easier:
            candidates = easier

    # Distance + tiny noise for tie-breaking
    return min(
        candidates,
        key=lambda q: abs(q["b_param"] - theta) + random.uniform(0, 1e-4)
    )


def theta_to_proficiency(theta: float) -> dict:
    """Convert θ to proficiency score, label and color."""
    score = round(100.0 / (1.0 + math.exp(-theta)), 1)
    for lo, hi, label, color in PROFICIENCY_BANDS:
        if lo <= theta <= hi:
            return {"score": score, "label": label, "color": color}
    return {"score": score, "label": "Expert", "color": "#534AB7"}


def compute_overall_theta(skill_thetas: dict) -> float:
    """Overall θ = simple average across all skills."""
    if not skill_thetas:
        return 0.0
    return round(sum(skill_thetas.values()) / len(skill_thetas), 4)


# ── SkillSession — mirrors StudentSession from senior's Cell 3 ────────────────

class SkillSession:
  

    def __init__(self, skill: str, quiz_length: int = 15):
        self.skill        = skill
        self.quiz_length  = quiz_length
        self.theta        = THETA_INIT
        self.theta_se     = 1.0
        self.responses    = []         # list of response dicts
        self.asked_ids    = set()
        self.last_correct = None       # tracks last answer for selection

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def q_number(self) -> int:
        return len(self.responses) + 1

    @property
    def done(self) -> bool:
        return len(self.responses) >= self.quiz_length

    @property
    def correct_count(self) -> int:
        return sum(1 for r in self.responses if r["is_correct"])

    @property
    def proficiency(self) -> dict:
        return theta_to_proficiency(self.theta)

    # ── Core methods ─────────────────────────────────────────────────────

    def next_question(self, pool: list[dict]) -> dict | None:
        """Pick next question from pool using adaptive selection."""
        return select_question(pool, self.theta, self.asked_ids, self.last_correct)

    def record_answer(self, question: dict, selected_option: str) -> dict:
        """
        Record one answer — updates θ, b, SE.
        Mirrors senior's StudentSession.record_answer() from Cell 3.

        Returns full response record dict.
        """
        correct_opt = question["correct_option"]
        is_correct  = (selected_option == correct_opt)
        b_used      = float(question["b_param"])
        p_pred      = p_correct(self.theta, b_used)
        surprise    = int(is_correct) - p_pred
        theta_before = self.theta

        # ── 1. Update θ ───────────────────────────────────────────────
        self.theta = update_theta(self.theta, b_used, is_correct)
        self.last_correct = is_correct

        # ── 2. Online b update (mirrors senior Cell 3 QB write-back) ──
        b_after_online = update_b_online(b_used, theta_before, is_correct)

        # ── 3. Batch b calibration ────────────────────────────────────
        # Count how many times this question has been answered (across all sessions)
        # This is tracked in DB — passed in via question dict if available
        resp_count = question.get("response_count", 0) + 1
        corr_count = question.get("correct_count", 0) + (1 if is_correct else 0)
        b_calibrated = calibrate_b(resp_count, corr_count)
        b_final      = b_calibrated if b_calibrated is not None else b_after_online
        b_source     = "calibrated" if b_calibrated is not None else "online"

        # ── 4. Update SE(θ) ───────────────────────────────────────────
        self.asked_ids.add(question["question_id"])
        self.theta_se = se_theta(self.responses)  # before appending

        # ── 5. Build response record ──────────────────────────────────
        record = {
            "q_number":          len(self.responses) + 1,
            "question_id":       question["question_id"],
            "skill":             self.skill,
            "question_text":     question["question_text"],
            "selected_option":   selected_option,
            "correct_option":    correct_opt,
            "is_correct":        is_correct,
            "b_used":            b_used,
            "b_after_online":    b_after_online,
            "b_final":           b_final,
            "b_source":          b_source,
            "theta_before":      theta_before,
            "theta_after":       self.theta,
            "p_correct_irt":     round(p_pred, 4),
            "surprise":          round(surprise, 4),
            "proficiency_before": round(100.0 / (1.0 + math.exp(-theta_before)), 1),
            "proficiency_after":  round(100.0 / (1.0 + math.exp(-self.theta)), 1),
            "difficulty_tier":   question.get("difficulty_tier", "medium"),
            "explanation":       question.get("explanation", ""),
            "option_a":          question.get("option_a", ""),
            "option_b":          question.get("option_b", ""),
            "option_c":          question.get("option_c", ""),
            "option_d":          question.get("option_d", ""),
        }
        self.responses.append(record)
        # Update SE after appending
        self.theta_se = se_theta(self.responses)
        return record

    def summary(self) -> dict:
        """Final summary for this skill session."""
        prof = self.proficiency
        return {
            "skill":             self.skill,
            "theta_final":       self.theta,
            "theta_se":          self.theta_se,
            "proficiency_score": prof["score"],
            "proficiency_label": prof["label"],
            "proficiency_color": prof["color"],
            "questions_answered": len(self.responses),
            "questions_correct":  self.correct_count,
            "accuracy_pct":       round(self.correct_count / max(len(self.responses), 1) * 100, 1),
        }