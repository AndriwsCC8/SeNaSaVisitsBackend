"""Respuestas de error documentadas en OpenAPI (cuerpo común: {"detail": str})."""
from __future__ import annotations

from typing import Any

from app.application.dto.common import ErrorResponse

_DESCRIPTIONS = {
    401: "No autenticado: token ausente, inválido o expirado",
    403: "Autenticado sin permiso o fuera de la sucursal autorizada",
    404: "El recurso solicitado no existe en el alcance autorizado",
    409: "Conflicto con el estado actual del recurso",
    422: "Datos o filtros no válidos",
}


def errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    """Build the `responses` mapping for the given HTTP error codes."""
    result: dict[int | str, dict[str, Any]] = {}
    for code in codes:
        entry: dict[str, Any] = {"description": _DESCRIPTIONS[code]}
        if code != 422:
            entry["model"] = ErrorResponse
        result[code] = entry
    return result
