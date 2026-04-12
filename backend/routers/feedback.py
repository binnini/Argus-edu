"""
routers/feedback.py — AI vs 교사 채점 delta 집계.

GET /api/v1/teacher/feedback/summary
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import get_session
from models import FeedbackLog
from schemas.teacher import FeedbackSummaryResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/teacher", tags=["feedback"])


def _verify_teacher(x_teacher_password: str = Header(default="")):
    if not x_teacher_password or x_teacher_password != settings.teacher_password:
        raise HTTPException(status_code=401, detail="교사 인증 실패")


@router.get("/feedback/summary", response_model=FeedbackSummaryResponse)
async def get_feedback_summary(
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    result = await db.execute(select(FeedbackLog))
    logs = result.scalars().all()

    if not logs:
        return FeedbackSummaryResponse(
            total_reviewed=0,
            approved=0,
            modified=0,
            rejected=0,
            approval_rate=0.0,
            avg_score_delta=0.0,
            low_trust_detection_precision=0.0,
        )

    approved = sum(1 for l in logs if l.action == "approve")
    modified = sum(1 for l in logs if l.action == "modify")
    rejected = sum(1 for l in logs if l.action == "reject")
    total = len(logs)

    approval_rate = (approved + modified) / total if total else 0.0

    # score_delta: modify/approve 케이스만 의미 있음
    delta_logs = [l for l in logs if l.action in ("approve", "modify")]
    avg_delta = (
        sum(abs(l.teacher_score - l.ai_score) for l in delta_logs) / len(delta_logs)
        if delta_logs else 0.0
    )

    # 할루시네이션 탐지 정밀도: 교사가 수정/거부한 케이스 중 Low 신뢰도로 분류된 비율
    flagged = [l for l in logs if l.action in ("modify", "reject")]
    low_trust_flagged = sum(1 for l in flagged if l.trust_level == "low")
    precision = low_trust_flagged / len(flagged) if flagged else 0.0

    return FeedbackSummaryResponse(
        total_reviewed=total,
        approved=approved,
        modified=modified,
        rejected=rejected,
        approval_rate=round(approval_rate, 3),
        avg_score_delta=round(avg_delta, 3),
        low_trust_detection_precision=round(precision, 3),
    )
