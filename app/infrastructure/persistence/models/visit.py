from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, NVARCHAR, text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from .common import TimestampMixin, primary_key


class Visit(TimestampMixin, Base):
    __tablename__ = "visits"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'COMPLETED', 'CANCELLED')", name="ck_visits_status"),
        CheckConstraint("exit_at IS NULL OR exit_at >= entry_at", name="ck_visits_exit_after_entry"),
        CheckConstraint("(status = 'CANCELLED' AND cancelled_by_user_id IS NOT NULL AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL) OR status <> 'CANCELLED'", name="ck_visits_cancellation_data"),
        Index("ix_visits_branch_status_entry", "branch_id", "status", "entry_at"),
        Index("ix_visits_branch_entry", "branch_id", "entry_at"),
        Index("ix_visits_visitor_entry", "visitor_id", "entry_at"),
    )

    id: Mapped[int] = primary_key()
    visitor_id: Mapped[int] = mapped_column(ForeignKey("visitors.id", ondelete="NO ACTION"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="NO ACTION"), nullable=False)
    registered_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"), nullable=False)
    entry_at: Mapped[datetime] = mapped_column(DATETIME2(precision=3), nullable=False)
    exit_at: Mapped[datetime | None] = mapped_column(DATETIME2(precision=3), nullable=True)
    reason_id: Mapped[int] = mapped_column(ForeignKey("visit_reasons.id", ondelete="NO ACTION"), nullable=False)
    destination: Mapped[str | None] = mapped_column(NVARCHAR(200), nullable=True)
    visited_person: Mapped[str | None] = mapped_column(NVARCHAR(200), nullable=True)
    status: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False)
    notes: Mapped[str | None] = mapped_column(NVARCHAR(1000), nullable=True)
    completed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"), nullable=True)
    cancelled_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DATETIME2(precision=3), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)

    visitor: Mapped[Visitor] = relationship(back_populates="visits")
    branch: Mapped[Branch] = relationship(back_populates="visits")
    registered_by: Mapped[User] = relationship(back_populates="registered_visits", foreign_keys=[registered_by_user_id])
    completed_by: Mapped[User | None] = relationship(back_populates="completed_visits", foreign_keys=[completed_by_user_id])
    cancelled_by: Mapped[User | None] = relationship(back_populates="cancelled_visits", foreign_keys=[cancelled_by_user_id])
    reason: Mapped[VisitReason] = relationship(back_populates="visits")
