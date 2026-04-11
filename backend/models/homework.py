from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class Homework(Base):
    __tablename__ = "homeworks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    group_id = Column(Integer, ForeignKey("student_groups.id", ondelete="SET NULL"), nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    group = relationship("StudentGroup", back_populates="homeworks")
    problems = relationship("HomeworkProblem", back_populates="homework", cascade="all, delete-orphan")


class HomeworkProblem(Base):
    __tablename__ = "homework_problems"
    id = Column(Integer, primary_key=True, autoincrement=True)
    homework_id = Column(Integer, ForeignKey("homeworks.id", ondelete="CASCADE"), nullable=False)
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"), nullable=False)
    homework = relationship("Homework", back_populates="problems")
    problem = relationship("Problem")
