"""
routers/groups.py — 그룹 및 숙제 관리 API.

GET    /api/v1/teacher/groups                       — 그룹 목록
POST   /api/v1/teacher/groups                       — 그룹 생성
DELETE /api/v1/teacher/groups/{group_id}            — 그룹 삭제
POST   /api/v1/teacher/groups/{group_id}/members    — 멤버 추가
DELETE /api/v1/teacher/groups/{group_id}/members/{student_id} — 멤버 제거
GET    /api/v1/teacher/homeworks                    — 숙제 목록
POST   /api/v1/teacher/homeworks                    — 숙제 생성
DELETE /api/v1/teacher/homeworks/{homework_id}      — 숙제 삭제
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from db import get_session
from models import Problem
from models.group import StudentGroup, GroupMember
from models.homework import Homework, HomeworkProblem
from schemas.groups import (
    GroupCreate,
    GroupResponse,
    GroupListResponse,
    GroupMemberItem,
    AddMembersRequest,
)
from schemas.homeworks import (
    HomeworkCreate,
    HomeworkResponse,
    HomeworkListResponse,
    HomeworkProblemItem,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/teacher", tags=["groups"])


def _verify_teacher(x_teacher_password: str = Header(default="")):
    """단순 비밀번호 인증 (MVP 한정). 헤더 없거나 틀리면 401."""
    if not x_teacher_password or x_teacher_password != settings.teacher_password:
        raise HTTPException(status_code=401, detail="교사 인증 실패")


# ── 그룹 목록 ────────────────────────────────────────────────

@router.get("/groups", response_model=GroupListResponse)
async def list_groups(
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    result = await db.execute(
        select(StudentGroup).options(selectinload(StudentGroup.members))
    )
    groups = result.scalars().all()
    return GroupListResponse(
        groups=[
            GroupResponse(
                id=g.id,
                name=g.name,
                created_at=g.created_at,
                members=[
                    GroupMemberItem(student_id=m.student_id, student_name=m.student_name)
                    for m in g.members
                ],
            )
            for g in groups
        ]
    )


# ── 그룹 생성 ────────────────────────────────────────────────

@router.post("/groups", response_model=GroupResponse, status_code=201)
async def create_group(
    body: GroupCreate,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    group = StudentGroup(name=body.name)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return GroupResponse(
        id=group.id,
        name=group.name,
        created_at=group.created_at,
        members=[],
    )


# ── 그룹 삭제 ────────────────────────────────────────────────

@router.delete("/groups/{group_id}", status_code=204)
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    group = await db.get(StudentGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다")
    await db.delete(group)
    await db.commit()


# ── 멤버 추가 ────────────────────────────────────────────────

@router.post("/groups/{group_id}/members", status_code=201)
async def add_members(
    group_id: int,
    body: AddMembersRequest,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    group = await db.get(StudentGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다")

    for item in body.members:
        member = GroupMember(
            group_id=group_id,
            student_id=item.student_id,
            student_name=item.student_name,
        )
        db.add(member)
    await db.commit()
    return {"ok": True}


# ── 멤버 제거 ────────────────────────────────────────────────

@router.delete("/groups/{group_id}/members/{student_id}", status_code=204)
async def remove_member(
    group_id: int,
    student_id: str,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.student_id == student_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="멤버를 찾을 수 없습니다")
    await db.delete(member)
    await db.commit()


# ── 숙제 목록 ────────────────────────────────────────────────

@router.get("/homeworks", response_model=HomeworkListResponse)
async def list_homeworks(
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    result = await db.execute(
        select(Homework).options(
            selectinload(Homework.problems).selectinload(HomeworkProblem.problem),
            selectinload(Homework.group),
        )
    )
    homeworks = result.scalars().all()
    return HomeworkListResponse(
        homeworks=[
            HomeworkResponse(
                id=hw.id,
                title=hw.title,
                group_id=hw.group_id,
                group_name=hw.group.name if hw.group else None,
                due_date=hw.due_date,
                created_at=hw.created_at,
                problems=[
                    HomeworkProblemItem(
                        problem_id=hp.problem_id,
                        problem_title=hp.problem.title if hp.problem else "",
                    )
                    for hp in hw.problems
                ],
            )
            for hw in homeworks
        ]
    )


# ── 숙제 생성 ────────────────────────────────────────────────

@router.post("/homeworks", response_model=HomeworkResponse, status_code=201)
async def create_homework(
    body: HomeworkCreate,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    # 그룹 검증
    group = None
    if body.group_id:
        group = await db.get(StudentGroup, body.group_id)
        if not group:
            raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다")

    hw = Homework(
        title=body.title,
        group_id=body.group_id,
        due_date=body.due_date,
    )
    db.add(hw)
    await db.flush()  # hw.id 확보

    problem_items = []
    for pid in body.problem_ids:
        prob = await db.get(Problem, pid)
        if not prob:
            raise HTTPException(status_code=404, detail=f"문제를 찾을 수 없습니다 (id={pid})")
        hp = HomeworkProblem(homework_id=hw.id, problem_id=pid)
        db.add(hp)
        problem_items.append(HomeworkProblemItem(problem_id=pid, problem_title=prob.title))

    await db.commit()
    await db.refresh(hw)

    return HomeworkResponse(
        id=hw.id,
        title=hw.title,
        group_id=hw.group_id,
        group_name=group.name if group else None,
        due_date=hw.due_date,
        created_at=hw.created_at,
        problems=problem_items,
    )


# ── 숙제 삭제 ────────────────────────────────────────────────

@router.delete("/homeworks/{homework_id}", status_code=204)
async def delete_homework(
    homework_id: int,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_teacher),
):
    hw = await db.get(Homework, homework_id)
    if not hw:
        raise HTTPException(status_code=404, detail="숙제를 찾을 수 없습니다")
    await db.delete(hw)
    await db.commit()
