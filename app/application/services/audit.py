from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.infrastructure.persistence.models import AuditLog

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "secret",
    "api_key",
    "credentials",
}
NORMALIZED_SENSITIVE_KEYS = {
    key.replace("_", "").replace("-", "")
    for key in SENSITIVE_KEYS
}


@dataclass(frozen=True)
class AuditContext:
    ip_address: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None


def audit_context_from_request(request) -> AuditContext:
    return AuditContext(
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        correlation_id=request.headers.get("x-correlation-id"),
    )


class AuditService:
    """Append-only application service for redacted audit events."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        actor_user_id: int | None,
        action: str,
        entity_type: str,
        entity_id: int | None = None,
        branch_id: int | None = None,
        old_values: Mapping[str, Any] | None = None,
        new_values: Mapping[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        correlation_id: str | None = None,
    ) -> AuditLog:
        if len(action) > 60 or len(entity_type) > 80:
            raise ValidationError("Los datos de auditoría exceden la longitud permitida.")
        event = AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            branch_id=branch_id,
            old_values=self._serialize(old_values),
            new_values=self._serialize(new_values),
            ip_address=(ip_address or "")[:45] or None,
            user_agent=(user_agent or "")[:500] or None,
            correlation_id=(correlation_id or "")[:100] or None,
        )
        self.db.add(event)
        return event

    @staticmethod
    def _serialize(values: Mapping[str, Any] | None) -> str | None:
        if not values:
            return None
        safe = AuditService._redact(dict(values))
        if not safe:
            return None
        return json.dumps(safe, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=AuditService._json_default)

    @staticmethod
    def _redact(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): AuditService._redact(item)
                for key, item in value.items()
                if AuditService._normalize_key(key) not in NORMALIZED_SENSITIVE_KEYS
            }
        if isinstance(value, list):
            return [AuditService._redact(item) for item in value]
        return value

    @staticmethod
    def _json_default(value: Any) -> str:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _normalize_key(key: Any) -> str:
        return str(key).lower().replace("_", "").replace("-", "")

    @staticmethod
    def redact_serialized(value: str | None) -> str | None:
        if not value:
            return None
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return None
        return AuditService._serialize(parsed if isinstance(parsed, Mapping) else {"value": parsed})


class AuditQueryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_logs(
        self,
        *,
        page: int,
        page_size: int,
        actor_user_id: int | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        branch_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[AuditLog], int]:
        if date_from is not None:
            date_from = self._utc_naive(date_from)
        if date_to is not None:
            date_to = self._utc_naive(date_to)
        if date_from is not None and date_to is not None and date_from >= date_to:
            raise ValidationError("date_to debe ser posterior a date_from; el límite superior es exclusivo.")
        filters = []
        if actor_user_id is not None:
            filters.append(AuditLog.actor_user_id == actor_user_id)
        if action:
            filters.append(AuditLog.action == action)
        if entity_type:
            filters.append(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            filters.append(AuditLog.entity_id == entity_id)
        if branch_id is not None:
            filters.append(AuditLog.branch_id == branch_id)
        if date_from is not None:
            filters.append(AuditLog.created_at >= date_from)
        if date_to is not None:
            filters.append(AuditLog.created_at < date_to)
        total = self.db.scalar(select(func.count(AuditLog.id)).where(*filters)) or 0
        logs = list(
            self.db.scalars(
                select(AuditLog)
                .where(*filters)
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return logs, total

    @staticmethod
    def _utc_naive(value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
