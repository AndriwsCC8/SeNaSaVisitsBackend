"""SQLite en memoria con los modelos reales, solo para pruebas aisladas (nunca SQL Server real)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, create_engine, event
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.base import Base
import app.infrastructure.persistence.models  # noqa: F401  registra los modelos


@compiles(BigInteger, "sqlite")
def _bigint_as_integer(type_, compiler, **kw) -> str:
    return "INTEGER"


@compiles(DATETIME2, "sqlite")
def _datetime2_as_datetime(type_, compiler, **kw) -> str:
    return "DATETIME"


def make_session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _register(dbapi_connection, _record) -> None:
        dbapi_connection.create_function(
            "SYSUTCDATETIME", 0, lambda: datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
        )

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
