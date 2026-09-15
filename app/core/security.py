"""Password hashing and JWT primitives used by the authentication layer."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

_password_hasher = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _password_hasher.verify(plain_password, hashed_password)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Generate a short-lived access token containing only identity claims."""
    settings = get_settings()
    issued_at = datetime.now(timezone.utc)
    expire = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "iat": issued_at,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.refresh_token_expire_minutes)
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
