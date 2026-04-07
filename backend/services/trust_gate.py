"""
trust_gate.py — 종합 신뢰도 계산 + 교사 큐 라우팅.

신뢰도 계산식 (docs/decisions.md ADR-005):
    trust_score = 0.6 * hhem_score + 0.4 * (1 - inconsistency_rate)

큐 라우팅:
    High (>= threshold) → queue_type = "score_only"  (풀이 설명만 교사 검토)
    Low  (<  threshold) → queue_type = "full_review"  (채점 + 풀이 모두 검토)
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class TrustResult:
    trust_score: float       # 종합 신뢰도 (0~1)
    trust_level: str         # "high" | "low"
    queue_type: str          # "score_only" | "full_review"
    score_visible: bool      # 채점 점수 즉시 노출 여부
    sla_deadline: datetime   # 교사 검토 SLA 마감


def calculate_trust(
    hhem_score: float,
    inconsistency_rate: float,
) -> TrustResult:
    """
    종합 신뢰도 계산 및 큐 라우팅 결정.

    Args:
        hhem_score: HHEM 팩추얼 일관성 스코어 (0~1)
        inconsistency_rate: 멀티 샘플링 불일치율 (0~1)

    Returns:
        TrustResult
    """
    trust_score = round(
        0.6 * hhem_score + 0.4 * (1.0 - inconsistency_rate),
        4,
    )
    trust_score = max(0.0, min(1.0, trust_score))  # 0~1 클리핑

    is_high = trust_score >= settings.trust_threshold

    trust_level = "high" if is_high else "low"
    queue_type = "score_only" if is_high else "full_review"
    score_visible = is_high  # High면 채점 점수 즉시 노출

    # SLA 마감 계산
    now = datetime.now(tz=timezone.utc)
    if trust_level == "low":
        sla_hours = settings.sla_high_risk_hours  # 12시간 (위험 케이스 우선)
    else:
        sla_hours = settings.sla_normal_hours      # 24시간

    sla_deadline = now + timedelta(hours=sla_hours)

    logger.info(
        f"신뢰도 계산: hhem={hhem_score:.3f}, inconsistency={inconsistency_rate:.3f} "
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
    개인화 피드백은 teacher_action == 'approve' | 'modify' 일 때만 포함.

    절대 제약: teacher_action이 없으면 feedback은 None (ADR-001).
    ai_feedback: 구조화된 피드백 dict {student_mistakes, correct_approach, key_concept}
    teacher_feedback: 교사가 수정한 피드백 (문자열 또는 dict)
    """
    if teacher_action == "approve":
        final_score = ai_score
        final_feedback = ai_feedback
        score_visible = True
    elif teacher_action == "modify":
        final_score = teacher_score if teacher_score is not None else ai_score
        # 교사 수정 피드백은 문자열로 저장되어 있으므로 key_concept으로 래핑
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
        # 교사 미검토 — 피드백 절대 노출 금지
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
