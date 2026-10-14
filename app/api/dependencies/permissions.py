from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.infrastructure.database.session import get_db
from app.application.services.authorization import PermissionService
from app.infrastructure.persistence.models import User


DbSession = Annotated[Session, Depends(get_db)]


def require_permission(permission_code: str) -> Callable[..., User]:
    """Build a dependency for GLOBAL permissions, independent of query filters."""

    def dependency(user: CurrentUser, db: DbSession) -> User:
        if not PermissionService(db).has_permission(user.id, permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para realizar esta operación",
            )
        return user

    return dependency
