from sqlalchemy import Boolean, Column, Integer, SmallInteger, String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Problem(Base):
    __tablename__ = "problems"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    answer = Column(String(100), nullable=False)
    reference_solution = Column(Text, nullable=False)
    rubric = Column(JSONB, nullable=False)
    domain = Column(String(50), default="수학2")
    difficulty = Column(SmallInteger)
    source = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    soft_deleted = Column(Boolean, default=False, nullable=False, server_default="false")

    submissions = relationship("Submission", back_populates="problem")
