"""Engine y fábrica de sesiones de SQLAlchemy para SQL Server."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    fast_executemany=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI que provee una sesión de base de datos por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
