from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from app.application.dto.common import UtcDatetime


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    email: str | None = Field(default=None, max_length=254)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    employee_code: str | None = Field(default=None, max_length=50)
    password: str = Field(min_length=8, max_length=256)
    role_code: str | None = Field(default=None, max_length=50)
    branch_id: int | None = None
    assignment_valid_from: datetime | None = None


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, max_length=254)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    employee_code: str | None = Field(default=None, max_length=50)
    role_code: str | None = Field(default=None, max_length=50)


class RoleResponse(BaseModel):
    id: int
    code: str
    name: str


class BranchResponse(BaseModel):
    id: int
    code: str
    name: str


class UserAssignmentResponse(BaseModel):
    id: int
    branch_id: int
    branch: BranchResponse
    valid_from: UtcDatetime
    valid_until: UtcDatetime | None
    status: str
    reason: str | None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    first_name: str
    last_name: str
    employee_code: str | None
    is_active: bool
    created_at: UtcDatetime
    updated_at: UtcDatetime
    deactivated_at: UtcDatetime | None
    roles: list[RoleResponse]
    current_assignment: UserAssignmentResponse | None


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int


class UserTransferRequest(BaseModel):
    new_branch_id: int
    effective_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)


class UserAssignmentCreate(BaseModel):
    branch_id: int
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)
