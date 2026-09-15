from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Index, NVARCHAR, text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from .common import primary_key


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("(is_read = 1 AND read_at IS NOT NULL) OR (is_read = 0 AND read_at IS NULL)", name="ck_notifications_read_state"),
        Index("ix_notifications_user_read_created", "user_id", "is_read", "created_at"),
    )

    id: Mapped[int] = primary_key()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"), nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="NO ACTION"), nullable=True)
    title: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    message: Mapped[str] = mapped_column(NVARCHAR(1000), nullable=False)
    type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    read_at: Mapped[datetime | None] = mapped_column(DATETIME2(precision=3), nullable=True)
    related_entity_type: Mapped[str | None] = mapped_column(NVARCHAR(80), nullable=True)
    related_entity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2(precision=3),
        nullable=False,
        server_default=text("SYSUTCDATETIME()"),
    )

    user: Mapped[User] = relationship(back_populates="notifications")
    branch: Mapped[Branch | None] = relationship(back_populates="notifications")
