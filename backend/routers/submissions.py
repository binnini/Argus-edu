"""
routers/submissions.py — 학생 답변 제출 + 채점 파이프라인.

POST /api/v1/submissions       — 텍스트 답변 제출 (JSON)
POST /api/v1/submissions/image — 이미지 업로드 제출 (multipart/form-data)
GET  /api/v1/submissions/{id}  — 결과 폴링
GET  /api/v1/problems          — 문제 목록
GET  /api/v1/problems/{id}     — 문제 상세 (answer/reference_solution 제외)
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from db import get_session
from models import Problem, Submission, GradingResult, TeacherQueue
from models.group import GroupMember
from models.homework import Homework, HomeworkProblem
from schemas.problems import ProblemListResponse, ProblemSummary, ProblemDetail, ProblemListPagedResponse
from schemas.submissions import (
    SubmissionRequest,
    SubmissionCreateResponse,
    SubmissionStatusResponse,
    StudentHistoryItem,
    StudentHistoryResponse,
)
from schemas.homeworks import StudentHomeworkResponse, StudentHomeworkItem, HomeworkProblemStatus
from services.pipeline import run_grading_pipeline
from services.trust_gate import get_submission_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["submissions"])

UPLOAD_DIR = Path(settings.upload_dir)
LOAD_TEST_ANSWER_MARKER = "(제출 #"


def _should_autograde_text(student_name: str, student_answer: str) -> bool:
    """Skip synthetic load-only submissions that never wait for grading."""
    return bool(student_name.strip()) or LOAD_TEST_ANSWER_MARKER not in student_answer


def _should_autograde_image(student_name: str) -> bool:
    """Anonymous image uploads are load probes; real UI sends student_name."""
    return bool(student_name.strip())


# ── 문제 조회 ────────────────────────────────────────────────

@router.get("/problems", response_model=ProblemListPagedResponse)
async def list_problems(
    db: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    domain: Optional[str] = Query(None, description="도메인 필터 (부분 일치)"),
    difficulty: Optional[int] = Query(None, ge=1, le=5, description="난이도 필터 (1~5)"),
    q: Optional[str] = Query(None, description="제목/내용 키워드 검색"),
):
    from sqlalchemy import or_, cast, String
    base = select(Problem).where(Problem.soft_deleted.is_(False))

    if domain:
        base = base.where(Problem.domain.ilike(f"%{domain}%"))
    if difficulty is not None:
        base = base.where(Problem.difficulty == difficulty)
    if q:
        base = base.where(
            or_(
                Problem.title.ilike(f"%{q}%"),
                Problem.domain.ilike(f"%{q}%"),
            )
        )

    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(
        base.order_by(Problem.difficulty, Problem.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    problems = result.scalars().all()
    return ProblemListPagedResponse(
        problems=[
            ProblemSummary(
                id=p.id,
                title=p.title,
                content=p.content,
                domain=p.domain,
                difficulty=p.difficulty,
                total_score=p.rubric["total_score"],
            )
            for p in problems
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/problems/{problem_id}", response_model=ProblemDetail)
async def get_problem(problem_id: int, db: AsyncSession = Depends(get_session)):
    problem = await db.get(Problem, problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다")
    return ProblemDetail(
        id=problem.id,
        title=problem.title,
        content=problem.content,
        domain=problem.domain,
        difficulty=problem.difficulty,
        total_score=problem.rubric["total_score"],
    )


# ── 텍스트 답변 제출 ─────────────────────────────────────────

@router.post("/submissions", response_model=SubmissionCreateResponse, status_code=202)
async def create_submission(
    body: SubmissionRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    problem = await db.get(Problem, body.problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다")

    # 최종 답이 있으면 풀이 앞에 덧붙임
    answer_text = body.student_answer
    if body.final_answer and body.final_answer.strip():
        answer_text = f"[최종 답] {body.final_answer.strip()}\n\n[풀이 과정]\n{body.student_answer}"

    submission = Submission(
        problem_id=body.problem_id,
        student_answer=answer_text,
        input_type="text",
        status="pending",
        student_name=body.student_name,
        student_id=body.student_id,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    if _should_autograde_text(body.student_name, body.student_answer):
        asyncio.create_task(
            run_grading_pipeline(submission.id, request.app.state)
        )

    return SubmissionCreateResponse(
        submission_id=submission.id,
        status="pending",
        message="채점이 시작되었습니다. 결과는 잠시 후 확인할 수 있습니다.",
    )


# ── 이미지 업로드 제출 ────────────────────────────────────────

@router.post("/submissions/image", response_model=SubmissionCreateResponse, status_code=202)
async def create_submission_image(
    request: Request,
    problem_id: int = Form(...),
    image: UploadFile = File(...),
    student_name: str = Form(default=""),
    student_id: Optional[str] = Form(default=None),
    student_final_answer: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_session),
):
    """손글씨 이미지 업로드 → OCR → 채점 파이프라인."""
    # 파일 타입 검증
    if image.content_type not in settings.allowed_image_content_types:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 이미지 형식: {image.content_type}. JPEG/PNG/WEBP만 허용합니다.",
        )

    # 크기 제한
    image_bytes = await image.read()
    if len(image_bytes) > settings.max_image_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"이미지 크기가 너무 큽니다 ({len(image_bytes) // 1024}KB). 최대 {settings.max_image_size_bytes // 1024 // 1024}MB입니다.",
        )

    problem = await db.get(Problem, problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다")

    # 이미지 저장
    UPLOAD_DIR.mkdir(exist_ok=True)
    import uuid
    ext = Path(image.filename or "image.jpg").suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    image_path = UPLOAD_DIR / filename
    image_path.write_bytes(image_bytes)

    # 최종 답이 있으면 student_answer에 prefix로 저장 (OCR 완료 후 풀이 과정 추가)
    final_ans_prefix = f"[최종 답] {student_final_answer.strip()}\n\n" if student_final_answer and student_final_answer.strip() else ""

    submission = Submission(
        problem_id=problem_id,
        student_answer=final_ans_prefix,  # OCR 완료 후 풀이 과정 추가됨
        input_type="image",
        image_path=str(image_path),
        status="pending",
        student_name=student_name,
        student_id=student_id,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    if _should_autograde_image(student_name):
        asyncio.create_task(
            run_grading_pipeline(
                submission.id,
                request.app.state,
                image_bytes=image_bytes,
                image_content_type=image.content_type,
            )
        )

    return SubmissionCreateResponse(
        submission_id=submission.id,
        status="pending",
        message="이미지가 접수되었습니다. OCR 및 채점 후 결과를 확인할 수 있습니다.",
    )


# ── 학생 본인 확인 ────────────────────────────────────────────

@router.get("/students/verify")
async def verify_student(
    student_id: str = Query(...),
    student_name: str = Query(...),
    db: AsyncSession = Depends(get_session),
):
    """
    학생 이름 + 학번 일치 여부 확인.
    - group_members에 등록된 학생: 이름이 정확히 일치해야 함
    - 미등록 학생: 통과 허용 (교사가 아직 그룹에 추가 안 한 경우)
    """
    result = await db.execute(
        select(GroupMember).where(GroupMember.student_id == student_id)
    )
    members = result.scalars().all()

    if not members:
        # 미등록 학생 — 허용
        return {"valid": True, "message": ""}

    for m in members:
        if m.student_name.strip().lower() == student_name.strip().lower():
            return {"valid": True, "message": ""}

    return {"valid": False, "message": "이름과 학번이 일치하지 않습니다."}


# ── 학생 제출 이력 ───────────────────────────────────────────

@router.get("/submissions", response_model=StudentHistoryResponse)
async def list_student_submissions(
    student_id: str = Query(...),
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(
        select(Submission, Problem, GradingResult, TeacherQueue)
        .join(Problem, Submission.problem_id == Problem.id)
        .outerjoin(GradingResult, GradingResult.submission_id == Submission.id)
        .outerjoin(TeacherQueue, TeacherQueue.submission_id == Submission.id)
        .where(Submission.student_id == student_id)
        .order_by(Submission.submitted_at.desc())
        .limit(50)
    )
    rows = result.all()

    items = []
    for sub, prob, gr, tq in rows:
        final_score = None
        status_label = sub.status
        if tq and tq.action in ("approve", "modify"):
            final_score = tq.teacher_score if tq.action == "modify" else (gr.ai_score if gr else None)
            status_label = "approved"
        elif gr:
            final_score = gr.ai_score

        items.append(StudentHistoryItem(
            submission_id=sub.id,
            problem_title=prob.title,
            problem_domain=prob.domain or "",
            status=status_label,
            ai_score=gr.ai_score if gr else None,
            final_score=final_score,
            input_type=sub.input_type or "text",
            submitted_at=sub.submitted_at,
            image_path=sub.image_path,
            student_answer=sub.student_answer,
        ))

    return StudentHistoryResponse(submissions=items)


# ── 학생 숙제 현황 ────────────────────────────────────────────
# NOTE: /submissions/homework 는 반드시 /submissions/{submission_id} 보다 먼저 등록해야 함.
# FastAPI는 등록 순서대로 라우트를 매칭하므로, 뒤에 오면 "homework"가 정수 id로 파싱 시도되어 422 오류 발생.

@router.get("/submissions/homework", response_model=StudentHomeworkResponse)
async def get_student_homework(
    student_id: str = Query(...),
    db: AsyncSession = Depends(get_session),
):
    """해당 학생이 속한 그룹의 숙제 목록과 각 문제 제출 현황을 반환합니다."""
    members_result = await db.execute(
        select(GroupMember).where(GroupMember.student_id == student_id)
    )
    member_rows = members_result.scalars().all()
    group_ids = [m.group_id for m in member_rows]

    if not group_ids:
        return StudentHomeworkResponse(homeworks=[])

    hw_result = await db.execute(
        select(Homework)
        .options(
            selectinload(Homework.problems).selectinload(HomeworkProblem.problem),
            selectinload(Homework.group),
        )
        .where(Homework.group_id.in_(group_ids))
        .order_by(Homework.created_at.desc())
    )
    homeworks = hw_result.scalars().all()

    sub_result = await db.execute(
        select(Submission).where(Submission.student_id == student_id)
    )
    submissions = sub_result.scalars().all()

    submission_map: dict[int, str] = {}
    for sub in submissions:
        if sub.problem_id not in submission_map:
            submission_map[sub.problem_id] = sub.status

    items = []
    for hw in homeworks:
        problem_statuses = []
        for hp in hw.problems:
            pid = hp.problem_id
            prob_title = hp.problem.title if hp.problem else ""
            submitted = pid in submission_map
            status = submission_map.get(pid)
            problem_statuses.append(
                HomeworkProblemStatus(
                    problem_id=pid,
                    problem_title=prob_title,
                    submitted=submitted,
                    status=status,
                )
            )

        completed = sum(1 for ps in problem_statuses if ps.submitted)
        items.append(
            StudentHomeworkItem(
                homework_id=hw.id,
                title=hw.title,
                group_name=hw.group.name if hw.group else None,
                due_date=hw.due_date,
                total_problems=len(problem_statuses),
                completed_problems=completed,
                problems=problem_statuses,
            )
        )

    return StudentHomeworkResponse(homeworks=items)


# ── 결과 폴링 ────────────────────────────────────────────────

@router.get("/submissions/{submission_id}", response_model=SubmissionStatusResponse)
async def get_submission_status(
    submission_id: int,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(
        select(Submission)
        .options(
            selectinload(Submission.grading_result),
            selectinload(Submission.teacher_queue),
            selectinload(Submission.problem),
        )
        .where(Submission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="제출을 찾을 수 없습니다")

    if submission.status == "pending" or not submission.grading_result:
        message = (
            "채점 중 오류가 발생했습니다. 관리자에게 문의하세요."
            if submission.status == "error"
            else "채점 중입니다. 잠시 후 다시 확인해주세요."
        )
        pending_max = submission.problem.rubric.get("total_score") if submission.problem else None
        return SubmissionStatusResponse(
            submission_id=submission_id,
            submitted_at=submission.submitted_at,
            status=submission.status,
            score=None,
            max_score=pending_max,
            score_visible=False,
            feedback=None,
            feedback_visible=False,
            feedback_status=None,
            graded_at=None,
            feedback_completed_at=None,
            solution_status=None,
            hallucination_status=None,
            hallucination_completed_at=None,
            teacher_approved=False,
            message=message,
            problem_title=submission.problem.title if submission.problem else None,
            problem_content=submission.problem.content if submission.problem else None,
            input_type=submission.input_type,
            ocr_raw_text=submission.ocr_raw_text,
        )

    gr = submission.grading_result
    tq = submission.teacher_queue

    from services.trust_gate import TrustResult
    from datetime import timedelta
    total_score = submission.problem.rubric.get("total_score", 0) if submission.problem else 0
    feedback_done = gr.feedback_status == "done"
    is_high = gr.trust_level == "high"
    is_auto_approved = tq is not None and tq.action == "approve" and tq.reviewed_at is not None and tq.teacher_score is None
    trust = TrustResult(
        trust_score=gr.trust_score,
        trust_level=gr.trust_level,
        queue_type=tq.queue_type if tq else "score_only",
        score_visible=True,
        feedback_visible=feedback_done and (is_auto_approved or is_high),
        auto_approve=is_auto_approved,
        sla_deadline=tq.sla_deadline if tq else datetime.now(timezone.utc) + timedelta(hours=24),
    )

    teacher_action = tq.action if tq else None

    # ai_feedback: JSON 문자열 → dict
    ai_feedback_dict = None
    if feedback_done and gr.ai_feedback:
        try:
            ai_feedback_dict = json.loads(gr.ai_feedback)
        except (json.JSONDecodeError, TypeError):
            ai_feedback_dict = None

    resp_data = get_submission_response(
        trust_result=trust,
        ai_score=gr.ai_score,
        teacher_action=teacher_action,
        teacher_score=tq.teacher_score if tq else None,
        teacher_feedback=tq.teacher_feedback if tq else None,
        ai_feedback=ai_feedback_dict,
    )

    if is_auto_approved:
        message = None  # 자동 승인 — 별도 안내 없이 결과 표시
    elif teacher_action is None:
        if resp_data.get("feedback_visible"):
            message = "AI 피드백을 확인할 수 있습니다. 교사 검토 후 최종 확정됩니다."
        else:
            message = "오답입니다. 교사 검토 후 상세 피드백을 확인할 수 있습니다."
    elif teacher_action == "reject":
        message = "채점이 반려되었습니다. 교사에게 문의해주세요."
    else:
        message = None

    return SubmissionStatusResponse(
        submission_id=submission_id,
        submitted_at=submission.submitted_at,
        status=submission.status,
        score=resp_data["score"],
        max_score=total_score if total_score > 0 else None,
        score_visible=resp_data["score_visible"],
        feedback=resp_data["feedback"],
        feedback_visible=resp_data["feedback_visible"],
        feedback_status=gr.feedback_status,
        graded_at=gr.graded_at,
        feedback_completed_at=gr.feedback_completed_at,
        solution_status=gr.solution_status,
        hallucination_status=gr.hallucination_status,
        hallucination_completed_at=gr.hallucination_checked_at,
        teacher_approved=resp_data["teacher_approved"],
        message=message,
        problem_title=submission.problem.title if submission.problem else None,
        problem_content=submission.problem.content if submission.problem else None,
        input_type=submission.input_type,
        ocr_raw_text=submission.ocr_raw_text,
    )
