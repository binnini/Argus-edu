"""
routers/submissions.py — 학생 답변 제출 + 채점 파이프라인.

POST /api/v1/submissions       — 제출 + 비동기 채점 시작
GET  /api/v1/submissions/{id}  — 결과 폴링
GET  /api/v1/problems          — 문제 목록
GET  /api/v1/problems/{id}     — 문제 상세 (answer/reference_solution 제외)
"""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db import get_session
from models import Problem, Submission, GradingResult, TeacherQueue
from schemas.problems import ProblemListResponse, ProblemSummary, ProblemDetail
from schemas.submissions import (
    SubmissionRequest,
    SubmissionCreateResponse,
    SubmissionStatusResponse,
)
from services.trust_gate import calculate_trust, get_submission_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["submissions"])


# ── 문제 조회 ────────────────────────────────────────────────

@router.get("/problems", response_model=ProblemListResponse)
async def list_problems(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Problem).order_by(Problem.id))
    problems = result.scalars().all()
    return ProblemListResponse(
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
        ]
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


# ── 답변 제출 ────────────────────────────────────────────────

@router.post("/submissions", response_model=SubmissionCreateResponse, status_code=202)
async def create_submission(
    body: SubmissionRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    # 문제 존재 확인
    problem = await db.get(Problem, body.problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다")

    # submission 생성
    submission = Submission(
        problem_id=body.problem_id,
        student_answer=body.student_answer,
        status="pending",
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    # 채점 파이프라인 비동기 실행 (응답 먼저 반환)
    asyncio.create_task(
        _run_grading_pipeline(submission.id, request.app.state)
    )

    return SubmissionCreateResponse(
        submission_id=submission.id,
        status="pending",
        message="채점이 시작되었습니다. 결과는 잠시 후 확인할 수 있습니다.",
    )


async def _run_grading_pipeline(submission_id: int, app_state) -> None:
    """채점 + 풀이 설명 + 신뢰도 게이트 파이프라인."""
    from db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            # 데이터 로드
            result = await db.execute(
                select(Submission)
                .options(selectinload(Submission.problem))
                .where(Submission.id == submission_id)
            )
            submission = result.scalar_one()
            problem = submission.problem

            grading_svc = app_state.grading_service
            explanation_svc = app_state.explanation_service
            hhem = app_state.hhem

            # 채점
            grading_out = await grading_svc.grade(
                problem_content=problem.content,
                answer=problem.answer,
                reference_solution=problem.reference_solution,
                rubric=problem.rubric,
                student_answer=submission.student_answer,
            )

            # 풀이 설명 생성
            explanation_out = await explanation_svc.generate(
                problem_content=problem.content,
                answer=problem.answer,
                reference_solution=problem.reference_solution,
            )

            # HHEM 스코어
            explanation_text = explanation_svc.format_explanation_text(
                explanation_out.steps, explanation_out.summary
            )
            hhem_result = hhem.score_explanation(
                problem.reference_solution, explanation_text
            )

            # 신뢰도 계산
            trust = calculate_trust(
                hhem_score=hhem_result.score,
                inconsistency_rate=explanation_out.inconsistency_rate,
            )

            # GradingResult 저장
            grading_record = GradingResult(
                submission_id=submission_id,
                ai_score=grading_out.total_score,
                ai_explanation=explanation_text,
                sbert_similarity=grading_out.sbert_similarity,
                hhem_score=hhem_result.score,
                inconsistency_rate=explanation_out.inconsistency_rate,
                trust_score=trust.trust_score,
                trust_level=trust.trust_level,
            )
            db.add(grading_record)

            # TeacherQueue 등록
            queue_record = TeacherQueue(
                submission_id=submission_id,
                queue_type=trust.queue_type,
                sla_deadline=trust.sla_deadline,
            )
            db.add(queue_record)

            # 상태 업데이트
            submission.status = "graded"
            await db.commit()

            logger.info(
                f"채점 완료 submission_id={submission_id} "
                f"score={grading_out.total_score} trust={trust.trust_level}"
            )

        except Exception as e:
            logger.error(f"채점 파이프라인 오류 submission_id={submission_id}: {e}")
            # 실패 시 상태를 'error'로 업데이트
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
        )
        .where(Submission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="제출을 찾을 수 없습니다")

    # 채점 미완료
    if submission.status == "pending" or not submission.grading_result:
        return SubmissionStatusResponse(
            submission_id=submission_id,
            status=submission.status,
            score=None,
            score_visible=False,
            explanation=None,
            teacher_approved=False,
            message="채점 중입니다. 잠시 후 다시 확인해주세요.",
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
    resp_data = get_submission_response(
        trust_result=trust,
        ai_score=gr.ai_score,
        teacher_action=teacher_action,
        teacher_score=tq.teacher_score if tq else None,
        teacher_explanation=tq.teacher_explanation if tq else None,
        ai_explanation=gr.ai_explanation,
    )

    # 상태 메시지
    if teacher_action is None:
        message = "교사 검토 중입니다. 풀이 설명은 검토 완료 후 확인할 수 있습니다."
    elif teacher_action == "reject":
        message = "채점이 반려되었습니다. 교사에게 문의해주세요."
    else:
        message = None

    return SubmissionStatusResponse(
        submission_id=submission_id,
        status=submission.status,
        score=resp_data["score"],
        score_visible=resp_data["score_visible"],
        explanation=resp_data["explanation"],
        teacher_approved=resp_data["teacher_approved"],
        message=message,
    )
