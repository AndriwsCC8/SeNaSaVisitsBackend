from __future__ import annotations

from sqlalchemy import Boolean, NVARCHAR, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from .common import TimestampMixin, primary_key


class BranchType(TimestampMixin, Base):
    __tablename__ = "branch_types"

    id: Mapped[int] = primary_key()
    code: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    description: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    branches: Mapped[list[Branch]] = relationship(back_populates="branch_type")
