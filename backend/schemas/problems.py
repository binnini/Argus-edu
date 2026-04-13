from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ProblemSummary(BaseModel):
    id: int
    title: str
    content: str
    domain: str
    difficulty: int
    total_score: int
    school_level: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ProblemDetail(BaseModel):
    id: int
    title: str
    content: str
    domain: str
    difficulty: int
    total_score: int
    school_level: Optional[str] = None
    # answer, reference_solution은 학생에게 노출 금지 — 필드 포함하지 않음

    model_config = ConfigDict(from_attributes=True)


class ProblemListResponse(BaseModel):
    problems: list[ProblemSummary]


class ProblemListPagedResponse(BaseModel):
    problems: list[ProblemSummary]
    total: int
    page: int
    page_size: int


# ── 교사용 스키마 ─────────────────────────────────────────────

class RubricStep(BaseModel):
    step: int
    description: str
    score: int


class RubricSchema(BaseModel):
    total_score: int
    steps: list[RubricStep]


class ProblemCreate(BaseModel):
    title: str
    content: str
    answer: str
    reference_solution: str
    rubric: RubricSchema
    domain: str = "수학2"
    school_level: str = ""
    difficulty: int = 2


class ProblemUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    answer: Optional[str] = None
    reference_solution: Optional[str] = None
    rubric: Optional[RubricSchema] = None
    domain: Optional[str] = None
    school_level: Optional[str] = None
    difficulty: Optional[int] = None


class TeacherProblemItem(BaseModel):
    id: int
    title: str
    content: str
    answer: str
    reference_solution: str
    rubric: dict
    domain: str
    school_level: Optional[str] = None
    difficulty: int
    submission_count: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TeacherProblemListResponse(BaseModel):
    problems: list[TeacherProblemItem]
    total: int
    page: int
    page_size: int


class ProblemDeleteResponse(BaseModel):
    id: int
    deleted: bool
    soft_delete: bool
