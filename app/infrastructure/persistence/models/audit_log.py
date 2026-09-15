from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, NVARCHAR, String, text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from .common import primary_key


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_actor_created_at", "actor_user_id", "created_at"),
        Index("ix_audit_logs_entity_created_at", "entity_type", "entity_id", "created_at"),
        Index("ix_audit_logs_branch_created_at", "branch_id", "created_at"),
    )

    id: Mapped[int] = primary_key()
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"), nullable=True)
    action: Mapped[str] = mapped_column(NVARCHAR(60), nullable=False)
    entity_type: Mapped[str] = mapped_column(NVARCHAR(80), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="NO ACTION"), nullable=True)
    old_values: Mapped[str | None] = mapped_column(NVARCHAR(None), nullable=True)
    new_values: Mapped[str | None] = mapped_column(NVARCHAR(None), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DATETIME2(precision=3), nullable=False, server_default=text("SYSUTCDATETIME()"))

    actor: Mapped[User | None] = relationship(back_populates="audit_logs", foreign_keys=[actor_user_id])
    branch: Mapped[Branch | None] = relationship(back_populates="audit_logs")
