"""
routers/teacher.py — 교사 검토 대시보드.

GET  /api/v1/teacher/queue              — 미처리 큐 목록
POST /api/v1/teacher/queue/{id}/action  — 승인 / 수정 / 거부
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from db import get_session
from models import Submission, GradingResult, TeacherQueue, FeedbackLog
from schemas.teacher import (
    TeacherQueueResponse,
    TeacherQueueItem,
    TeacherActionRequest,
    TeacherActionResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/teacher", tags=["teacher"])


def _verify_teacher(x_teacher_password: str = Header(default="")):
    """단순 비밀번호 인증 (MVP 한정). 헤더 없거나 틀리면 401."""
    if not x_teacher_password or x_teacher_password != settings.teacher_password:
        raise HTTPException(status_code=401, detail="교사 인증 실패")


# ── 검토 큐 목록 ────────────────────────────────────────────────

@router.get("/queue", response_model=TeacherQueueResponse)
async def get_queue(
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    """action IS NULL 항목만 반환. SLA 마감 임박 순 정렬."""
    result = await db.execute(
        select(TeacherQueue)
        .options(
            selectinload(TeacherQueue.submission).selectinload(Submission.problem),
            selectinload(TeacherQueue.submission).selectinload(Submission.grading_result),
        )
        .where(TeacherQueue.action.is_(None))
        .order_by(TeacherQueue.sla_deadline.asc())
    )
    queue_items = result.scalars().all()

    items = []
    for tq in queue_items:
        sub = tq.submission
        gr = sub.grading_result
        if not gr:
            continue
        items.append(
            TeacherQueueItem(
                queue_id=tq.id,
                submission_id=sub.id,
                problem_title=sub.problem.title,
                student_answer=sub.student_answer,
                ai_score=gr.ai_score,
                ai_explanation=gr.ai_explanation,
                trust_score=gr.trust_score,
                trust_level=gr.trust_level,
                queue_type=tq.queue_type,
                sla_deadline=tq.sla_deadline,
                queued_at=tq.queued_at,
            )
        )

    return TeacherQueueResponse(queue=items, total=len(items))


# ── 교사 액션 ────────────────────────────────────────────────

@router.post("/queue/{queue_id}/action", response_model=TeacherActionResponse)
async def submit_action(
    queue_id: int,
    body: TeacherActionRequest,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    """승인 / 수정 / 거부. 묵시적 자동 승인 없음."""
    result = await db.execute(
        select(TeacherQueue)
        .options(
            selectinload(TeacherQueue.submission).selectinload(Submission.grading_result)
        )
        .where(TeacherQueue.id == queue_id)
    )
    tq = result.scalar_one_or_none()
    if not tq:
        raise HTTPException(status_code=404, detail="큐 항목을 찾을 수 없습니다")
    if tq.action is not None:
        raise HTTPException(status_code=409, detail=f"이미 처리된 항목입니다 (action={tq.action})")

    now = datetime.now(tz=timezone.utc)
    tq.action = body.action
    tq.reviewed_at = now

    if body.action == "modify":
        tq.teacher_score = body.teacher_score
        tq.teacher_explanation = body.teacher_explanation

    # submission 상태 업데이트
    sub = tq.submission
    sub.status = "approved" if body.action in ("approve", "modify") else "rejected"

    # feedback_log 저장
    gr = sub.grading_result
    if gr:
        final_score = (
            body.teacher_score if body.action == "modify" else gr.ai_score
        )
        log = FeedbackLog(
            submission_id=sub.id,
            ai_score=gr.ai_score,
            teacher_score=final_score,
            action=body.action,
            trust_score=gr.trust_score,
            trust_level=gr.trust_level,
        )
        db.add(log)

    await db.commit()

    logger.info(
        f"교사 액션 queue_id={queue_id} action={body.action} "
        f"submission_id={sub.id}"
    )

    return TeacherActionResponse(
        queue_id=queue_id,
        action=body.action,
        reviewed_at=now,
    )
