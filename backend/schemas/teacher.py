from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, model_validator


class TeacherQueueItem(BaseModel):
    queue_id: int
    submission_id: int
    problem_title: str
    student_answer: str
    ai_score: int
    ai_feedback: str
    trust_score: float
    trust_level: str
    queue_type: str
    sla_deadline: datetime
    queued_at: datetime


class TeacherQueueResponse(BaseModel):
    queue: list[TeacherQueueItem]
    total: int


class TeacherActionRequest(BaseModel):
    action: Literal["approve", "modify", "reject"]
    teacher_score: Optional[int] = None
    teacher_feedback: Optional[str] = None

    @model_validator(mode="after")
    def validate_modify_fields(self) -> "TeacherActionRequest":
        if self.action == "modify":
            if self.teacher_score is None or self.teacher_feedback is None:
                raise ValueError("modify 액션에는 teacher_score와 teacher_feedback이 필요합니다")
        return self


class TeacherActionResponse(BaseModel):
    queue_id: int
    action: str
    reviewed_at: datetime


class FeedbackSummaryResponse(BaseModel):
    total_reviewed: int
    approved: int
    modified: int
    rejected: int
    approval_rate: float
    avg_score_delta: float
    low_trust_detection_precision: float
