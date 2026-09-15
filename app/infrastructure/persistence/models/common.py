"""Shared SQLAlchemy types and columns for SQL Server persistence models."""
from datetime import datetime

from sqlalchemy import BigInteger, Identity, text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column


UtcDateTime = DATETIME2(precision=3)


def primary_key() -> Mapped[int]:
    return mapped_column(BigInteger, Identity(), primary_key=True)


def utc_timestamp(*, nullable: bool = False) -> Mapped[datetime]:
    return mapped_column(
        DATETIME2(precision=3),
        nullable=nullable,
        server_default=text("SYSUTCDATETIME()"),
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2(precision=3),
        nullable=False,
        server_default=text("SYSUTCDATETIME()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME2(precision=3),
        nullable=False,
        server_default=text("SYSUTCDATETIME()"),
        onupdate=text("SYSUTCDATETIME()"),
    )
