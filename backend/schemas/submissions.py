from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class SubmissionRequest(BaseModel):
    problem_id: int
    student_answer: str
    student_name: str = ""
    student_id: Optional[str] = None


class SubmissionCreateResponse(BaseModel):
    submission_id: int
    status: str
    message: str


class FeedbackMistake(BaseModel):
    step: int
    description: str


class FeedbackStep(BaseModel):
    step: int
    title: str
    content: str


class FeedbackSchema(BaseModel):
    student_mistakes: list[FeedbackMistake]
    correct_approach: list[FeedbackStep]
    key_concept: str


class SubmissionStatusResponse(BaseModel):
    submission_id: int
    status: str
    score: Optional[int]
    score_visible: bool
    feedback: Optional[FeedbackSchema]   # 교사 승인 후에만 노출
    teacher_approved: bool
    message: Optional[str]


class StudentHistoryItem(BaseModel):
    submission_id: int
    problem_title: str
    problem_domain: str
    status: str
    ai_score: Optional[int]
    final_score: Optional[int]
    input_type: str
    submitted_at: datetime


class StudentHistoryResponse(BaseModel):
    submissions: list[StudentHistoryItem]
