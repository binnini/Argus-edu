"""
trust_gate.py — 채점 점수 기반 신뢰도 계산 + 교사 큐 라우팅.

변경 이력:
  - v1: HHEM × 0.6 + (1 - inconsistency_rate) × 0.4 → 실효성 낮음
  - v2 (현재): AI 채점 점수 비율 기반 단순화
    trust_score = ai_score / total_score
    High (≥ threshold 0.5): 점수 즉시 노출, score_only 큐
    Low  (< threshold 0.5): 점수 숨김, full_review 큐
    (0점이면 항상 full_review)

  할루시네이션 검증은 배치 LLM 방식으로 별도 구현 예정.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class TrustResult:
    trust_score: float
    trust_level: str         # "high" | "low"
    queue_type: str          # "score_only" | "full_review"
    score_visible: bool
    sla_deadline: datetime


def calculate_trust(
    ai_score: int,
    total_score: int,
) -> TrustResult:
    """
    채점 점수 비율로 신뢰도 결정.
    0점이면 무조건 full_review.
    """
    if total_score <= 0:
        trust_score = 0.0
    else:
        trust_score = round(ai_score / total_score, 4)

    trust_score = max(0.0, min(1.0, trust_score))
    is_high = trust_score >= settings.trust_threshold

    trust_level = "high" if is_high else "low"
    queue_type = "score_only" if is_high else "full_review"
    score_visible = is_high

    now = datetime.now(tz=timezone.utc)
    sla_hours = settings.sla_normal_hours if is_high else settings.sla_high_risk_hours
    sla_deadline = now + timedelta(hours=sla_hours)

    logger.info(
        f"신뢰도 계산: score={ai_score}/{total_score} "
        f"→ trust={trust_score:.3f} ({trust_level}), queue={queue_type}"
    )

    return TrustResult(
        trust_score=trust_score,
        trust_level=trust_level,
        queue_type=queue_type,
        score_visible=score_visible,
        sla_deadline=sla_deadline,
    )


def get_submission_response(
    trust_result: TrustResult,
    ai_score: int,
    teacher_action: str | None,
    teacher_score: int | None,
    teacher_feedback: str | None,
    ai_feedback: dict | None,
) -> dict:
    """
    /submissions/{id} 응답 생성.
    절대 제약: teacher_action이 없으면 feedback은 None (ADR-001).
    """
    if teacher_action == "approve":
        final_score = ai_score
        final_feedback = ai_feedback
        score_visible = True
    elif teacher_action == "modify":
        final_score = teacher_score if teacher_score is not None else ai_score
        if isinstance(teacher_feedback, dict):
            final_feedback = teacher_feedback
        elif teacher_feedback:
            final_feedback = {
                "student_mistakes": [],
                "correct_approach": [],
                "key_concept": teacher_feedback,
            }
        else:
            final_feedback = ai_feedback
        score_visible = True
    elif teacher_action == "reject":
        final_score = None
        final_feedback = None
        score_visible = False
    else:
        final_score = ai_score if trust_result.score_visible else None
        final_feedback = None
        score_visible = trust_result.score_visible

    return {
        "score": final_score,
        "score_visible": score_visible,
        "feedback": final_feedback,
        "teacher_approved": teacher_action in ("approve", "modify"),
        "trust_score": trust_result.trust_score,
        "trust_level": trust_result.trust_level,
    }
