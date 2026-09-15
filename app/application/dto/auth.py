from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class BranchSummary(BaseModel):
    id: int
    code: str
    name: str


class AuthenticatedUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    first_name: str
    last_name: str
    role: str | None = None
    branch: BranchSummary | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthenticatedUserResponse
