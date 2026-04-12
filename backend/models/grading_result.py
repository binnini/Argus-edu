from sqlalchemy import Column, Integer, SmallInteger, Float, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class GradingResult(Base):
    __tablename__ = "grading_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), unique=True, nullable=False)
    ai_score = Column(SmallInteger, nullable=False)
    ai_feedback = Column(Text, nullable=False)
    sbert_similarity = Column(Float, nullable=False)
    trust_score = Column(Float, nullable=False)
    trust_level = Column(String(10), nullable=False)  # 'high' | 'low'
    graded_at = Column(DateTime(timezone=True), server_default=func.now())

    # 배치 LLM 할루시네이션 검증 (ADR-026)
    # hallucination_status: 'pending' → 'running' → 'done' | 'failed'
    hallucination_status = Column(String(10), nullable=False, default="pending")
    hallucination_score = Column(Float, nullable=True)          # 0.0~1.0, 높을수록 신뢰
    hallucination_issues = Column(Text, nullable=True)          # JSON 배열, 문제점 목록
    hallucination_checked_at = Column(DateTime(timezone=True), nullable=True)

    submission = relationship("Submission", back_populates="grading_result")
