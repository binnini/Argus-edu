"""
trust_gate.py — 채점 점수 기반 신뢰도 계산 + 교사 큐 라우팅.

정책:
  - 정답/오답(score)은 즉시 공개
  - 피드백은 아래 중 하나일 때만 공개
    1) hallucination 검증 후 trust_level == "high"
    2) 교사 승인/수정 완료
  - 채점 단계에서는 자동 승인하지 않는다.
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
    score_visible: bool      # 항상 True — 정답/오답 즉시 표시
    feedback_visible: bool   # trust_level=high 또는 교사 승인 시 공개
    auto_approve: bool       # 현재 정책상 항상 False
    sla_deadline: datetime


def calculate_trust(
    ai_score: int,
    total_score: int,
) -> TrustResult:
    """
    채점 직후 큐 라우팅 결정.

    trust_score / trust_level 은 0.0 / "low" 로 초기화.
    실제 신뢰도는 hallucination_batch.py 가 배치 완료 후 grading_results 를 갱신한다.
    채점 단계에서는 자동 승인하지 않는다.
    """
    auto_approve = False
    queue_type = "full_review"
    sla_hours = settings.sla_normal_hours

    now = datetime.now(tz=timezone.utc)
    sla_deadline = now + timedelta(hours=sla_hours)

    logger.info(
        f"큐 라우팅: ai_score={ai_score}/{total_score}, "
        f"auto_approve={auto_approve}, queue={queue_type}"
    )

    return TrustResult(
        trust_score=0.0,        # hallucination_batch 완료 후 갱신
        trust_level="low",      # hallucination_batch 완료 후 갱신
        queue_type=queue_type,
        score_visible=True,
        feedback_visible=False,
        auto_approve=auto_approve,
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
    - 교사가 처리한 경우: 교사 결과 사용
    - 처리 전: 신뢰도에 따라 score/feedback 노출 여부 결정
      * trust_level=high: 교사 승인 전에도 피드백 노출
      * trust_level=low: 교사 승인 후에만 피드백 노출
    """
    if teacher_action == "approve":
        final_score = ai_score
        final_feedback = ai_feedback
        score_visible = True
        feedback_visible = True
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
        feedback_visible = True
    elif teacher_action == "reject":
        final_score = None
        final_feedback = None
        score_visible = False
        feedback_visible = False
    else:
        # 정답/오답은 항상 즉시 공개
        final_score = ai_score
        score_visible = True
        # 고신뢰도면 피드백 즉시 공개, 저신뢰도면 교사 검토 필요
        if trust_result.feedback_visible:
            final_feedback = ai_feedback
            feedback_visible = True
        else:
            final_feedback = None
            feedback_visible = False

    return {
        "score": final_score,
        "score_visible": score_visible,
        "feedback": final_feedback,
        "feedback_visible": feedback_visible,
        "teacher_approved": teacher_action in ("approve", "modify"),
        "trust_score": trust_result.trust_score,
        "trust_level": trust_result.trust_level,
    }
