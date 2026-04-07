from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    student_answer = Column(Text, nullable=False)
    input_type = Column(String(10), default="text", nullable=False)
    ocr_raw_text = Column(Text, nullable=True)
    image_path = Column(String(500), nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), default="pending")  # pending | graded | approved | rejected

    problem = relationship("Problem", back_populates="submissions")
    grading_result = relationship("GradingResult", back_populates="submission", uselist=False)
    teacher_queue = relationship("TeacherQueue", back_populates="submission", uselist=False)
    feedback_log = relationship("FeedbackLog", back_populates="submission", uselist=False)
