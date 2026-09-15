from __future__ import annotations

from sqlalchemy import Boolean, Index, NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from .common import TimestampMixin, primary_key


class VisitorType(TimestampMixin, Base):
    __tablename__ = "visitor_types"
    __table_args__ = (Index("ix_visitor_types_code", "code", unique=True),)

    id: Mapped[int] = primary_key()
    code: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    description: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    visitors: Mapped[list[Visitor]] = relationship(back_populates="visitor_type")
