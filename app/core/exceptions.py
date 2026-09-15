"""Excepciones de dominio/aplicación y manejo centralizado de errores para FastAPI."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("senasa_visits")


class AppError(Exception):
    """Excepción base de la aplicación. Las capas superiores lanzan subclases de esta."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "Ha ocurrido un error inesperado."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    message = "El recurso solicitado no existe."


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message = "Los datos proporcionados no son válidos."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    message = "La operación entra en conflicto con el estado actual del recurso."


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    message = "Credenciales inválidas o no proporcionadas."


class ForbiddenError(AppError):
    """Reservada para violaciones de autorización, incluyendo aislamiento por sucursal."""

    status_code = status.HTTP_403_FORBIDDEN
    message = "No tiene permisos para acceder a este recurso."


def register_exception_handlers(app: FastAPI) -> None:
    """Registra manejadores globales de excepciones. No expone detalles internos al cliente."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Error no controlado procesando %s %s", request.method, request.url)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Ha ocurrido un error interno. Intente de nuevo más tarde."},
        )
