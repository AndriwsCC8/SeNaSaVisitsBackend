from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from .common import TimestampMixin, primary_key


class Branch(TimestampMixin, Base):
    __tablename__ = "branches"
    __table_args__ = (
        Index("ix_branches_branch_type_id", "branch_type_id"),
    )

    id: Mapped[int] = primary_key()
    code: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    branch_type_id: Mapped[int] = mapped_column(ForeignKey("branch_types.id", ondelete="NO ACTION"), nullable=False)
    region: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    address: Mapped[str | None] = mapped_column(NVARCHAR(300), nullable=True)
    phone: Mapped[str | None] = mapped_column(NVARCHAR(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    branch_type: Mapped[BranchType] = relationship(back_populates="branches")
    user_permissions: Mapped[list[UserPermission]] = relationship(back_populates="branch")
    user_branch_assignments: Mapped[list[UserBranchAssignment]] = relationship(back_populates="branch")
    visits: Mapped[list[Visit]] = relationship(back_populates="branch")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="branch")
    notifications: Mapped[list[Notification]] = relationship(back_populates="branch")
