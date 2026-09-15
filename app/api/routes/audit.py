from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.permissions import DbSession, require_permission
from app.application.dto.audit import AuditLogListResponse, AuditLogResponse
from app.application.services.audit import AuditQueryService, AuditService

router = APIRouter(prefix="/audit-logs", tags=["audit"])
ViewAuditLogs = Annotated[object, Depends(require_permission("VIEW_AUDIT_LOGS"))]


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    actor: ViewAuditLogs,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    actor_user_id: int | None = None,
    action: str | None = Query(default=None, max_length=60),
    entity_type: str | None = Query(default=None, max_length=80),
    entity_id: int | None = None,
    branch_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AuditLogListResponse:
    logs, total = AuditQueryService(db).list_logs(
        page=page,
        page_size=page_size,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
    )
    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=log.id,
                actor_user_id=log.actor_user_id,
                action=log.action,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                branch_id=log.branch_id,
                old_values=AuditService.redact_serialized(log.old_values),
                new_values=AuditService.redact_serialized(log.new_values),
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                correlation_id=log.correlation_id,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
