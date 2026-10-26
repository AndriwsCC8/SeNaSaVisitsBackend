from __future__ import annotations

from pydantic import BaseModel
from app.application.dto.common import UtcDatetime


class AuditLogResponse(BaseModel):
    id: int
    actor_user_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    branch_id: int | None
    old_values: str | None
    new_values: str | None
    ip_address: str | None
    user_agent: str | None
    correlation_id: str | None
    created_at: UtcDatetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
