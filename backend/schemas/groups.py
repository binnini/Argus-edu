from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class GroupMemberItem(BaseModel):
    student_id: str
    student_name: str


class GroupCreate(BaseModel):
    name: str


class GroupResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    members: list[GroupMemberItem]

    class Config:
        from_attributes = True


class GroupListResponse(BaseModel):
    groups: list[GroupResponse]


class AddMembersRequest(BaseModel):
    members: list[GroupMemberItem]
