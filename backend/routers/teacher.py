"""
routers/teacher.py — 교사 검토 대시보드.

GET  /api/v1/teacher/queue              — 미처리 큐 목록
POST /api/v1/teacher/queue/{id}/action  — 승인 / 수정 / 거부
GET  /api/v1/teacher/submissions        — 제출 현황 목록
GET  /api/v1/teacher/problems/{id}/submissions — 문제별 제출 목록
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from db import get_session
from models import Submission, GradingResult, TeacherQueue, FeedbackLog
from services.job_queue import queue_counts
from schemas.teacher import (
    TeacherQueueResponse,
    TeacherQueueItem,
    TeacherActionRequest,
    TeacherActionResponse,
    SubmissionOverviewItem,
    SubmissionOverviewResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/teacher", tags=["teacher"])
AUTO_APPROVE_MARKER = "__AUTO_APPROVED_BY_HALLUCINATION__"


def _verify_teacher(x_teacher_password: str = Header(default="")):
    """단순 비밀번호 인증 (MVP 한정). 헤더 없거나 틀리면 401."""
    if not x_teacher_password or x_teacher_password != settings.teacher_password:
        raise HTTPException(status_code=401, detail="교사 인증 실패")


# ── 검토 큐 목록 ────────────────────────────────────────────────

@router.get("/queue", response_model=TeacherQueueResponse)
async def get_queue(
    trust_level: Optional[str] = None,
    review_status: str = Query(
        "pending",
        description="pending|approved|modify|reject|reviewed|all",
    ),
    sort: str = Query("sla", description="sla|latest"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    """교사 검토 큐 조회. 처리 상태/정렬/신뢰도 필터 지원."""
    query = (
        select(TeacherQueue)
        .join(TeacherQueue.submission)
        .join(Submission.grading_result)
        .options(
            selectinload(TeacherQueue.submission).selectinload(Submission.problem),
            selectinload(TeacherQueue.submission).selectinload(Submission.grading_result),
        )
    )
    normalized_status = (review_status or "pending").lower().strip()
    if normalized_status == "pending":
        query = query.where(TeacherQueue.action.is_(None))
    elif normalized_status == "approved":
        query = query.where(TeacherQueue.action == "approve")
    elif normalized_status == "modify":
        query = query.where(TeacherQueue.action == "modify")
    elif normalized_status == "reject":
        query = query.where(TeacherQueue.action == "reject")
    elif normalized_status == "reviewed":
        query = query.where(TeacherQueue.action.is_not(None))
    elif normalized_status != "all":
        raise HTTPException(status_code=400, detail="review_status 값이 올바르지 않습니다")

    if trust_level:
        query = query.where(func.lower(GradingResult.trust_level) == trust_level.lower())

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar() or 0

    if sort == "latest":
        ordered = query.order_by(func.coalesce(TeacherQueue.reviewed_at, TeacherQueue.queued_at).desc())
    elif sort == "sla":
        ordered = query.order_by(TeacherQueue.sla_deadline.asc(), TeacherQueue.queued_at.asc())
    else:
        raise HTTPException(status_code=400, detail="sort 값이 올바르지 않습니다")

    result = await db.execute(ordered.offset((page - 1) * page_size).limit(page_size))
    queue_items = result.scalars().all()

    items = []
    for tq in queue_items:
        sub = tq.submission
        gr = sub.grading_result
        if not gr:
            continue
        auto_approved = tq.action == "approve" and tq.teacher_feedback == AUTO_APPROVE_MARKER
        items.append(
            TeacherQueueItem(
                queue_id=tq.id,
                submission_id=sub.id,
                problem_title=sub.problem.title,
                problem_content=sub.problem.content if sub.problem else "",
                problem_answer=sub.problem.answer if sub.problem else "",
                ocr_raw_text=sub.ocr_raw_text,
                student_answer=sub.student_answer,
                student_name=sub.student_name,
                student_id=sub.student_id,
                input_type=sub.input_type or "text",
                image_path=sub.image_path,
                ai_score=gr.ai_score,
                ai_feedback=gr.ai_feedback,
                trust_score=gr.trust_score,
                trust_level=gr.trust_level,
                queue_type=tq.queue_type,
                sla_deadline=tq.sla_deadline,
                queued_at=tq.queued_at,
                hallucination_status=gr.hallucination_status,
                hallucination_score=gr.hallucination_score,
                hallucination_issues=gr.hallucination_issues,
                feedback_status=gr.feedback_status,
                solution_status=gr.solution_status,
                action=tq.action,
                reviewed_at=tq.reviewed_at,
                auto_approved=auto_approved,
            )
        )

    return TeacherQueueResponse(queue=items, total=total, page=page, page_size=page_size)


@router.get("/queue/health")
async def get_queue_health(
    _: None = Depends(_verify_teacher),
):
    queues = await queue_counts()
    return {"queues": queues}


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
        tq.teacher_feedback = body.teacher_feedback

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


# ── 제출 현황 목록 ────────────────────────────────────────────

@router.get("/submissions", response_model=SubmissionOverviewResponse)
async def get_submissions(
    problem_id: Optional[int] = None,
    status: Optional[str] = None,
    student_name: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    query = (
        select(Submission)
        .options(
            selectinload(Submission.problem),
            selectinload(Submission.grading_result),
            selectinload(Submission.teacher_queue),
        )
        .order_by(Submission.submitted_at.desc())
    )
    if problem_id:
        query = query.where(Submission.problem_id == problem_id)
    if status:
        query = query.where(Submission.status == status)
    if student_name:
        query = query.where(Submission.student_name.ilike(f"%{student_name}%"))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    submissions = result.scalars().all()

    items = []
    for sub in submissions:
        gr = sub.grading_result
        tq = sub.teacher_queue
        final_score = None
        if tq and tq.action == "modify" and tq.teacher_score is not None:
            final_score = tq.teacher_score
        elif gr:
            final_score = gr.ai_score
        items.append(SubmissionOverviewItem(
            submission_id=sub.id,
            problem_id=sub.problem_id,
            problem_title=sub.problem.title if sub.problem else "",
            student_name=sub.student_name,
            student_id=sub.student_id,
            input_type=sub.input_type,
            image_path=sub.image_path,
            student_answer=sub.student_answer,
            status=sub.status,
            ai_score=gr.ai_score if gr else None,
            final_score=final_score,
            trust_level=gr.trust_level if gr else None,
            feedback_status=gr.feedback_status if gr else None,
            solution_status=gr.solution_status if gr else None,
            submitted_at=sub.submitted_at,
            reviewed_at=tq.reviewed_at if tq else None,
        ))
    return SubmissionOverviewResponse(submissions=items, total=total, page=page, page_size=page_size)


@router.get("/problems/{problem_id}/submissions", response_model=SubmissionOverviewResponse)
async def get_problem_submissions(
    problem_id: int,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    query = (
        select(Submission)
        .options(
            selectinload(Submission.problem),
            selectinload(Submission.grading_result),
            selectinload(Submission.teacher_queue),
        )
        .where(Submission.problem_id == problem_id)
        .order_by(Submission.submitted_at.desc())
    )

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    submissions = result.scalars().all()

    items = []
    for sub in submissions:
        gr = sub.grading_result
        tq = sub.teacher_queue
        final_score = None
        if tq and tq.action == "modify" and tq.teacher_score is not None:
            final_score = tq.teacher_score
        elif gr:
            final_score = gr.ai_score
        items.append(SubmissionOverviewItem(
            submission_id=sub.id,
            problem_id=sub.problem_id,
            problem_title=sub.problem.title if sub.problem else "",
            student_name=sub.student_name,
            student_id=sub.student_id,
            input_type=sub.input_type,
            image_path=sub.image_path,
            student_answer=sub.student_answer,
            status=sub.status,
            ai_score=gr.ai_score if gr else None,
            final_score=final_score,
            trust_level=gr.trust_level if gr else None,
            feedback_status=gr.feedback_status if gr else None,
            solution_status=gr.solution_status if gr else None,
            submitted_at=sub.submitted_at,
            reviewed_at=tq.reviewed_at if tq else None,
        ))
    return SubmissionOverviewResponse(submissions=items, total=total, page=page, page_size=page_size)
