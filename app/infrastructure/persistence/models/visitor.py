from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from .common import TimestampMixin, primary_key


class Visitor(TimestampMixin, Base):
    __tablename__ = "visitors"
    __table_args__ = (
        Index("ux_visitors_identification_normalized", "identification_normalized", unique=True, mssql_where="identification_normalized IS NOT NULL"),
    )

    id: Mapped[int] = primary_key()
    identification: Mapped[str | None] = mapped_column(NVARCHAR(50), nullable=True)
    identification_normalized: Mapped[str | None] = mapped_column(NVARCHAR(50), nullable=True)
    first_name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    last_name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(NVARCHAR(30), nullable=True)
    email: Mapped[str | None] = mapped_column(NVARCHAR(254), nullable=True)
    company: Mapped[str | None] = mapped_column(NVARCHAR(200), nullable=True)
    visitor_type_id: Mapped[int | None] = mapped_column(ForeignKey("visitor_types.id", ondelete="NO ACTION"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    visitor_type: Mapped[VisitorType | None] = relationship(back_populates="visitors")
    visits: Mapped[list[Visit]] = relationship(back_populates="visitor")
