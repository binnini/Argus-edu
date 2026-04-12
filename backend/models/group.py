from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class StudentGroup(Base):
    __tablename__ = "student_groups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    homeworks = relationship("Homework", back_populates="group")


class GroupMember(Base):
    __tablename__ = "group_members"
    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("student_groups.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(String(20), nullable=False)
    student_name = Column(String(50), nullable=False, default="")
    group = relationship("StudentGroup", back_populates="members")
