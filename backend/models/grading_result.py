from sqlalchemy import Column, Integer, SmallInteger, Float, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class GradingResult(Base):
    __tablename__ = "grading_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), unique=True, nullable=False)
    ai_score = Column(SmallInteger, nullable=False)
    ai_explanation = Column(Text, nullable=False)
    sbert_similarity = Column(Float, nullable=False)
    hhem_score = Column(Float, nullable=False)
    inconsistency_rate = Column(Float, nullable=False)
    trust_score = Column(Float, nullable=False)
    trust_level = Column(String(10), nullable=False)  # 'high' | 'low'
    graded_at = Column(DateTime(timezone=True), server_default=func.now())

    submission = relationship("Submission", back_populates="grading_result")
