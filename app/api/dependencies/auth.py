from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import decode_token
from app.infrastructure.database.session import get_db
from app.infrastructure.persistence.models import User, UserBranchAssignment, UserRole


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la autenticación",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise authentication_error()
        subject = payload.get("sub")
        user_id = int(subject) if isinstance(subject, str) and subject.isdigit() else None
        if user_id is None:
            raise authentication_error()
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise authentication_error() from None

    user = db.scalar(
        select(User)
        .options(
            selectinload(User.user_roles).selectinload(UserRole.role),
            selectinload(User.branch_assignments).selectinload(UserBranchAssignment.branch),
        )
        .where(User.id == user_id)
    )
    if user is None or not user.is_active:
        raise authentication_error()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
