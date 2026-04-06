from sqlalchemy import Column, Integer, SmallInteger, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class TeacherQueue(Base):
    __tablename__ = "teacher_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), unique=True, nullable=False)
    queue_type = Column(String(20), nullable=False)  # 'score_only' | 'full_review'
    sla_deadline = Column(DateTime(timezone=True), nullable=False)
    action = Column(String(10), nullable=True)  # NULL | 'approve' | 'modify' | 'reject'
    teacher_score = Column(SmallInteger, nullable=True)
    teacher_explanation = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    queued_at = Column(DateTime(timezone=True), server_default=func.now())

    submission = relationship("Submission", back_populates="teacher_queue")
