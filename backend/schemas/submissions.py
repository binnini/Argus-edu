from typing import Optional
from pydantic import BaseModel


class SubmissionRequest(BaseModel):
    problem_id: int
    student_answer: str


class SubmissionCreateResponse(BaseModel):
    submission_id: int
    status: str
    message: str


class SubmissionStatusResponse(BaseModel):
    submission_id: int
    status: str
    score: Optional[int]
    score_visible: bool
    explanation: Optional[str]
    teacher_approved: bool
    message: Optional[str]
