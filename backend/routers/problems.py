"""
routers/problems.py — 교사 문제 관리 CRUD.

POST   /api/v1/teacher/problems       — 문제 생성
GET    /api/v1/teacher/problems       — 문제 목록 (soft_deleted=False)
PUT    /api/v1/teacher/problems/{id}  — 문제 수정
DELETE /api/v1/teacher/problems/{id}  — 문제 삭제 (제출 없으면 hard delete, 있으면 soft delete)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import get_session
from models import Problem, Submission
from schemas.problems import (
    ProblemCreate,
    ProblemUpdate,
    TeacherProblemItem,
    TeacherProblemListResponse,
    ProblemDeleteResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-problems"])


def _verify_teacher(x_teacher_password: str = Header(default="")) -> None:
    if not x_teacher_password or x_teacher_password != settings.teacher_password:
        raise HTTPException(status_code=401, detail="교사 인증 실패")


async def _get_submission_count(db: AsyncSession, problem_id: int) -> int:
    result = await db.execute(
        select(func.count()).where(Submission.problem_id == problem_id)
    )
    return result.scalar() or 0


@router.post("/problems", response_model=TeacherProblemItem, status_code=201)
async def create_problem(
    body: ProblemCreate,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    problem = Problem(
        title=body.title,
        content=body.content,
        answer=body.answer,
        reference_solution=body.reference_solution,
        rubric=body.rubric.model_dump(),
        domain=body.domain,
        difficulty=body.difficulty,
        soft_deleted=False,
    )
    db.add(problem)
    await db.commit()
    await db.refresh(problem)

    return TeacherProblemItem(
        id=problem.id,
        title=problem.title,
        content=problem.content,
        answer=problem.answer,
        reference_solution=problem.reference_solution,
        rubric=problem.rubric,
        domain=problem.domain or "수학2",
        difficulty=problem.difficulty or 2,
        submission_count=0,
        created_at=problem.created_at,
    )


@router.get("/problems", response_model=TeacherProblemListResponse)
async def list_teacher_problems(
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    # submission count 서브쿼리
    subq = (
        select(Submission.problem_id, func.count(Submission.id).label("cnt"))
        .group_by(Submission.problem_id)
        .subquery()
    )

    result = await db.execute(
        select(Problem, subq.c.cnt)
        .outerjoin(subq, Problem.id == subq.c.problem_id)
        .where(Problem.soft_deleted.is_(False))
        .order_by(Problem.created_at.desc())
    )
    rows = result.all()

    problems = []
    for problem, cnt in rows:
        problems.append(
            TeacherProblemItem(
                id=problem.id,
                title=problem.title,
                content=problem.content,
                answer=problem.answer,
                reference_solution=problem.reference_solution,
                rubric=problem.rubric,
                domain=problem.domain or "수학2",
                difficulty=problem.difficulty or 2,
                submission_count=cnt or 0,
                created_at=problem.created_at,
            )
        )
    return TeacherProblemListResponse(problems=problems)


@router.put("/problems/{problem_id}", response_model=TeacherProblemItem)
async def update_problem(
    problem_id: int,
    body: ProblemUpdate,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    problem = await db.get(Problem, problem_id)
    if not problem or problem.soft_deleted:
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다")

    if body.title is not None:
        problem.title = body.title
    if body.content is not None:
        problem.content = body.content
    if body.answer is not None:
        problem.answer = body.answer
    if body.reference_solution is not None:
        problem.reference_solution = body.reference_solution
    if body.rubric is not None:
        problem.rubric = body.rubric.model_dump()
    if body.domain is not None:
        problem.domain = body.domain
    if body.difficulty is not None:
        problem.difficulty = body.difficulty

    await db.commit()
    await db.refresh(problem)

    count = await _get_submission_count(db, problem_id)

    return TeacherProblemItem(
        id=problem.id,
        title=problem.title,
        content=problem.content,
        answer=problem.answer,
        reference_solution=problem.reference_solution,
        rubric=problem.rubric,
        domain=problem.domain or "수학2",
        difficulty=problem.difficulty or 2,
        submission_count=count,
        created_at=problem.created_at,
    )


@router.delete("/problems/{problem_id}", response_model=ProblemDeleteResponse)
async def delete_problem(
    problem_id: int,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    problem = await db.get(Problem, problem_id)
    if not problem or problem.soft_deleted:
        raise HTTPException(status_code=404, detail="문제를 찾을 수 없습니다")

    count = await _get_submission_count(db, problem_id)

    if count == 0:
        # 제출 없음 → 완전 삭제
        await db.delete(problem)
        await db.commit()
        return ProblemDeleteResponse(id=problem_id, deleted=True, soft_delete=False)
    else:
        # 제출 있음 → soft delete
        problem.soft_deleted = True
        await db.commit()
        return ProblemDeleteResponse(id=problem_id, deleted=True, soft_delete=True)
