from sqlalchemy import Column, Integer, SmallInteger, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class FeedbackLog(Base):
    __tablename__ = "feedback_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    ai_score = Column(SmallInteger, nullable=False)
    teacher_score = Column(SmallInteger, nullable=False)
    # score_delta: GENERATED ALWAYS AS (teacher_score - ai_score) STORED
    # SQLAlchemy에서 컬럼 정의만 선언 (마이그레이션 SQL에서 GENERATED 설정)
    score_delta = Column(SmallInteger, nullable=True)
    action = Column(String(10), nullable=False)  # 'approve' | 'modify' | 'reject'
    trust_score = Column(Float, nullable=False)
    trust_level = Column(String(10), nullable=False)
    logged_at = Column(DateTime(timezone=True), server_default=func.now())

    submission = relationship("Submission", back_populates="feedback_log")
