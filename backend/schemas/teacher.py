from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, model_validator


class TeacherQueueItem(BaseModel):
    queue_id: int
    submission_id: int
    problem_title: str
    problem_content: str = ""
    problem_answer: str = ""
    ocr_raw_text: Optional[str] = None
    student_answer: str
    student_name: str = ""
    student_id: Optional[str] = None
    input_type: str = "text"
    image_path: Optional[str] = None
    ai_score: int
    ai_feedback: str
    trust_score: float
    trust_level: str
    queue_type: str
    sla_deadline: datetime
    queued_at: datetime
    # 배치 LLM 할루시네이션 검증 결과 (ADR-026)
    hallucination_status: str = "pending"   # pending | running | done | failed
    hallucination_score: Optional[float] = None   # 높을수록 신뢰 (done 상태에서만 유효)
    hallucination_issues: Optional[str] = None    # JSON 배열 문자열


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


class SubmissionOverviewItem(BaseModel):
    submission_id: int
    problem_id: int
    problem_title: str
    student_name: str
    student_id: Optional[str] = None
    input_type: str
    image_path: Optional[str] = None
    student_answer: Optional[str] = None
    status: str
    ai_score: Optional[int] = None
    final_score: Optional[int] = None
    trust_level: Optional[str] = None
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class SubmissionOverviewResponse(BaseModel):
    submissions: list[SubmissionOverviewItem]
    total: int
    page: int
    page_size: int
