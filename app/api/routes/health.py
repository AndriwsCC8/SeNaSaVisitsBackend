"""Endpoint de verificación de estado de la API."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.infrastructure.database.session import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "service": settings.app_name}


@router.get("/health/db", response_model=None)
def database_health_check() -> dict[str, str] | JSONResponse:
    settings = get_settings()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "api": "ok",
                "database": "unavailable",
                "service": settings.app_name,
            },
        )

    return {
        "status": "ok",
        "api": "ok",
        "database": "ok",
        "service": settings.app_name,
    }
