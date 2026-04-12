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
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db import get_session
from models import Problem, Submission, GradingResult, TeacherQueue
from models.group import GroupMember
from models.homework import Homework, HomeworkProblem
from schemas.problems import ProblemListResponse, ProblemSummary, ProblemDetail, ProblemListPagedResponse
from schemas.submissions import (
    SubmissionRequest,
    SubmissionCreateResponse,
    SubmissionStatusResponse,
    SubmissionUpdateRequest,
    StudentHistoryItem,
    StudentHistoryResponse,
)
from schemas.homeworks import StudentHomeworkResponse, StudentHomeworkItem, HomeworkProblemStatus
from services.trust_gate import calculate_trust, get_submission_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["submissions"])

UPLOAD_DIR = Path("uploads")
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB


# ── 문제 조회 ────────────────────────────────────────────────

@router.get("/problems", response_model=ProblemListPagedResponse)
async def list_problems(
    db: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
):
    total_result = await db.execute(
        select(func.count()).select_from(Problem).where(Problem.soft_deleted.is_(False))
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(Problem)
        .where(Problem.soft_deleted.is_(False))
        .order_by(Problem.id)
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

    asyncio.create_task(
        _run_grading_pipeline(submission.id, request.app.state)
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
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 이미지 형식: {image.content_type}. JPEG/PNG/WEBP만 허용합니다.",
        )

    # 크기 제한
    image_bytes = await image.read()
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"이미지 크기가 너무 큽니다 ({len(image_bytes) // 1024}KB). 최대 10MB입니다.",
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

    asyncio.create_task(
        _run_grading_pipeline(
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


# ── 채점 파이프라인 ───────────────────────────────────────────

async def _run_grading_pipeline(
    submission_id: int,
    app_state,
    image_bytes: bytes | None = None,
    image_content_type: str | None = None,
) -> None:
    """채점 + 개인화 피드백 + 신뢰도 게이트 파이프라인."""
    from db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Submission)
                .options(selectinload(Submission.problem))
                .where(Submission.id == submission_id)
            )
            submission = result.scalar_one()
            problem = submission.problem

            combined_svc = app_state.combined_service
            student_answer = submission.student_answer

            # OCR (이미지 입력 시)
            if submission.input_type == "image" and image_bytes:
                ocr_svc = app_state.ocr_service
                try:
                    ocr_text = await ocr_svc.recognize(image_bytes, image_content_type or "image/jpeg")
                except Exception as e:
                    logger.error(f"OCR 실패 submission_id={submission_id}: {e}")
                    submission.status = "error"
                    await db.commit()
                    return

                existing_prefix = submission.student_answer or ""
                if existing_prefix:
                    student_answer = existing_prefix + "[풀이 과정]\n" + ocr_text
                else:
                    student_answer = ocr_text
                submission.student_answer = student_answer
                submission.ocr_raw_text = ocr_text
                await db.commit()

            # 채점 + 피드백 단일 호출
            out = await combined_svc.run(
                problem_content=problem.content,
                answer=problem.answer,
                reference_solution=problem.reference_solution,
                rubric=problem.rubric,
                student_answer=student_answer,
            )

            # 신뢰도: 점수 비율 기반
            total_score = problem.rubric.get("total_score", 1)
            trust = calculate_trust(
                ai_score=out.total_score,
                total_score=total_score,
            )

            ai_feedback_dict = {
                "student_mistakes": out.student_mistakes,
                "correct_approach": out.correct_approach,
                "key_concept": out.key_concept,
            }

            # GradingResult 저장
            grading_record = GradingResult(
                submission_id=submission_id,
                ai_score=out.total_score,
                ai_feedback=json.dumps(ai_feedback_dict, ensure_ascii=False),
                sbert_similarity=out.sbert_similarity,
                trust_score=trust.trust_score,
                trust_level=trust.trust_level,
                hallucination_status="pending",  # 배치 스케줄러가 비동기 처리
            )
            db.add(grading_record)

            queue_record = TeacherQueue(
                submission_id=submission_id,
                queue_type=trust.queue_type,
                sla_deadline=trust.sla_deadline,
            )
            db.add(queue_record)

            submission.status = "graded"
            await db.commit()

            logger.info(
                f"채점 완료 submission_id={submission_id} "
                f"score={out.total_score} trust={trust.trust_level}"
            )

        except Exception as e:
            logger.error(f"채점 파이프라인 오류 submission_id={submission_id}: {e}")
            try:
                result = await db.execute(
                    select(Submission).where(Submission.id == submission_id)
                )
                sub = result.scalar_one_or_none()
                if sub:
                    sub.status = "error"
                    await db.commit()
            except Exception:
                pass


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


# ── 제출 수정 ────────────────────────────────────────────────

@router.put("/submissions/{submission_id}", response_model=SubmissionCreateResponse, status_code=200)
async def update_submission(
    submission_id: int,
    body: SubmissionUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """
    채점 대기 중(pending/graded, 교사 미처리) 제출 답안 수정.
    수정 시 기존 채점 결과 삭제 + 재채점 시작.
    """
    result = await db.execute(
        select(Submission)
        .options(
            selectinload(Submission.grading_result),
            selectinload(Submission.teacher_queue),
        )
        .where(Submission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="제출을 찾을 수 없습니다")

    # 수정 가능 조건: pending 또는 graded, 교사 미처리
    tq = submission.teacher_queue
    if tq and tq.action is not None:
        raise HTTPException(status_code=409, detail="이미 교사가 검토한 제출은 수정할 수 없습니다")
    if submission.status not in ("pending", "graded", "error"):
        raise HTTPException(status_code=409, detail="승인 또는 거부된 제출은 수정할 수 없습니다")

    # 답안 업데이트
    if body.student_answer is not None:
        submission.student_answer = body.student_answer

    # 기존 채점 결과 + 큐 항목 삭제 (재채점 위해)
    if submission.grading_result:
        await db.delete(submission.grading_result)
    if tq:
        await db.delete(tq)

    # 상태 초기화
    submission.status = "pending"
    await db.commit()
    await db.refresh(submission)

    # 재채점 시작
    asyncio.create_task(
        _run_grading_pipeline(submission.id, request.app.state)
    )

    logger.info(f"제출 수정 + 재채점 시작 submission_id={submission_id}")

    return SubmissionCreateResponse(
        submission_id=submission.id,
        status="pending",
        message="답안이 수정되었습니다. 재채점이 시작되었습니다.",
    )


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
        return SubmissionStatusResponse(
            submission_id=submission_id,
            status=submission.status,
            score=None,
            score_visible=False,
            feedback=None,
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
    trust = TrustResult(
        trust_score=gr.trust_score,
        trust_level=gr.trust_level,
        queue_type=tq.queue_type if tq else "score_only",
        score_visible=gr.trust_level == "high",
        sla_deadline=tq.sla_deadline if tq else datetime.now(timezone.utc) + timedelta(hours=24),
    )

    teacher_action = tq.action if tq else None

    # ai_feedback: JSON 문자열 → dict
    ai_feedback_dict = None
    if gr.ai_feedback:
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

    if teacher_action is None:
        message = "교사 검토 중입니다. 피드백은 검토 완료 후 확인할 수 있습니다."
    elif teacher_action == "reject":
        message = "채점이 반려되었습니다. 교사에게 문의해주세요."
    else:
        message = None

    return SubmissionStatusResponse(
        submission_id=submission_id,
        status=submission.status,
        score=resp_data["score"],
        score_visible=resp_data["score_visible"],
        feedback=resp_data["feedback"],
        teacher_approved=resp_data["teacher_approved"],
        message=message,
        problem_title=submission.problem.title if submission.problem else None,
        problem_content=submission.problem.content if submission.problem else None,
        input_type=submission.input_type,
        ocr_raw_text=submission.ocr_raw_text,
    )


