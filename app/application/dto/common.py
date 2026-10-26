from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, PlainSerializer


def _serialize_utc(value: datetime) -> str:
    """SQL Server stores naive UTC; responses carry an explicit UTC indicator."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(_serialize_utc, return_type=str, when_used="json")]


class ErrorResponse(BaseModel):
    detail: str
