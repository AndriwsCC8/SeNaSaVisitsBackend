from __future__ import annotations

import re

from app.core.exceptions import ValidationError


def normalize_identification(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", "", value.strip()).upper()
    return normalized or None


def mask_identification(value: str | None) -> str | None:
    if value is None:
        return None
    compact = value.strip()
    if len(compact) <= 4:
        return "*" * len(compact)
    visible_prefix = compact[:3]
    visible_suffix = compact[-4:]
    return f"{visible_prefix}{'*' * max(3, len(compact) - 7)}{visible_suffix}"


def normalize_required_text(value: str, field_name: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValidationError(f"{field_name} no puede estar vacío.")
    return normalized


def validate_email(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
        raise ValidationError("El email proporcionado no es válido.")
    return normalized


def mask_phone(value: str | None) -> str | None:
    """Keep only the last two digits; short values are fully masked."""
    if not value:
        return None
    compact = value.strip()
    return "*" * len(compact) if len(compact) <= 4 else "***" + compact[-2:]


def mask_email(value: str | None) -> str | None:
    """Keep the first character and the domain."""
    if not value:
        return None
    local, separator, domain = value.strip().partition("@")
    if not separator or not local:
        return "***"
    return f"{local[0]}***@{domain}"
