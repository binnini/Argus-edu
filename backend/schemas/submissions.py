from typing import Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, field_validator


class SubmissionRequest(BaseModel):
    problem_id: int
    student_answer: str
    student_name: str = ""
    student_id: Optional[str] = None
    final_answer: Optional[str] = None


class SubmissionCreateResponse(BaseModel):
    submission_id: int
    status: str
    message: str


class FeedbackMistake(BaseModel):
    step: Optional[int] = None
    description: str = ""

    @field_validator("step", mode="before")
    @classmethod
    def coerce_step(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    @field_validator("description", mode="before")
    @classmethod
    def coerce_description(cls, v: Any) -> str:
        return str(v) if v is not None else ""

    model_config = {"extra": "ignore"}


class FeedbackStep(BaseModel):
    step: Optional[int] = None
    title: str = ""
    content: str = ""

    @field_validator("step", mode="before")
    @classmethod
    def coerce_step(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    model_config = {"extra": "ignore"}


class FeedbackSchema(BaseModel):
    solution_status: Optional[str] = None
    has_mistakes: bool = True
    student_mistakes: list[Union[FeedbackMistake, str]] = []
    correct_approach: list[Union[FeedbackStep, str]] = []
    key_concept: str = ""

    @field_validator("student_mistakes", mode="before")
    @classmethod
    def normalize_mistakes(cls, v: Any) -> list:
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                result.append(FeedbackMistake(description=item))
            elif isinstance(item, dict):
                result.append(FeedbackMistake(**{k: val for k, val in item.items() if k in ("step", "description")}))
            else:
                result.append(item)
        return result

    @field_validator("correct_approach", mode="before")
    @classmethod
    def normalize_approach(cls, v: Any) -> list:
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                result.append(FeedbackStep(content=item))
            elif isinstance(item, dict):
                result.append(FeedbackStep(**{k: val for k, val in item.items() if k in ("step", "title", "content")}))
            else:
                result.append(item)
        return result

    model_config = {"extra": "ignore"}


class SubmissionStatusResponse(BaseModel):
    submission_id: int
    submitted_at: Optional[datetime] = None
    status: str
    score: Optional[int]
    max_score: Optional[int] = None      # 문제 만점 (부분 정답 판별용)
    score_visible: bool
    feedback: Optional[FeedbackSchema]   # 교사 승인 또는 feedback_visible 시 노출
    feedback_visible: bool = False       # 정답+고신뢰도면 교사 승인 전에도 노출
    feedback_status: Optional[str] = None
    graded_at: Optional[datetime] = None
    feedback_completed_at: Optional[datetime] = None
    solution_status: Optional[str] = None
    hallucination_status: Optional[str] = None
    hallucination_completed_at: Optional[datetime] = None
    teacher_approved: bool
    auto_approved: bool = False
    message: Optional[str]
    problem_title: Optional[str] = None
    problem_content: Optional[str] = None
    input_type: Optional[str] = None
    ocr_raw_text: Optional[str] = None


class StudentHistoryItem(BaseModel):
    submission_id: int
    problem_title: str
    problem_domain: str
    status: str
    ai_score: Optional[int]
    final_score: Optional[int]
    input_type: str
    submitted_at: datetime
    image_path: Optional[str] = None
    student_answer: Optional[str] = None
    feedback_status: Optional[str] = None
    hallucination_status: Optional[str] = None
    auto_approved: bool = False


class StudentHistoryResponse(BaseModel):
    submissions: list[StudentHistoryItem]
