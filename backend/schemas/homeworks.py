from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class HomeworkProblemItem(BaseModel):
    problem_id: int
    problem_title: str = ""


class HomeworkCreate(BaseModel):
    title: str
    group_id: Optional[int] = None
    due_date: Optional[datetime] = None
    problem_ids: list[int]


class HomeworkResponse(BaseModel):
    id: int
    title: str
    group_id: Optional[int]
    group_name: Optional[str]
    due_date: Optional[datetime]
    created_at: datetime
    problems: list[HomeworkProblemItem]

    class Config:
        from_attributes = True


class HomeworkListResponse(BaseModel):
    homeworks: list[HomeworkResponse]


class HomeworkProblemStatus(BaseModel):
    problem_id: int
    problem_title: str
    submitted: bool
    status: Optional[str] = None


class StudentHomeworkItem(BaseModel):
    homework_id: int
    title: str
    group_name: Optional[str]
    due_date: Optional[datetime]
    total_problems: int
    completed_problems: int
    problems: list[HomeworkProblemStatus]


class StudentHomeworkResponse(BaseModel):
    homeworks: list[StudentHomeworkItem]
