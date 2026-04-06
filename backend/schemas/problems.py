from pydantic import BaseModel


class ProblemSummary(BaseModel):
    id: int
    title: str
    content: str
    domain: str
    difficulty: int
    total_score: int

    model_config = {"from_attributes": True}


class ProblemDetail(BaseModel):
    id: int
    title: str
    content: str
    domain: str
    difficulty: int
    total_score: int
    # answer, reference_solution은 학생에게 노출 금지 — 필드 포함하지 않음

    model_config = {"from_attributes": True}


class ProblemListResponse(BaseModel):
    problems: list[ProblemSummary]
