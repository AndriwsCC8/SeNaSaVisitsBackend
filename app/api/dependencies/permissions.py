from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.infrastructure.database.session import get_db
from app.application.services.authorization import PermissionService
from app.infrastructure.persistence.models import User


DbSession = Annotated[Session, Depends(get_db)]


def require_permission(permission_code: str) -> Callable[..., User]:
    """Build a dependency that denies authenticated users without a permission.

    A future endpoint may expose branch_id as a path or query parameter. This
    dependency reads that value only as a resource context; it never grants it.
    The authorization service validates the branch against the database.
    """

    def dependency(
        request: Request,
        user: CurrentUser,
        db: DbSession,
        branch_id: int | None = Query(default=None),
    ) -> User:
        path_branch_id = request.path_params.get("branch_id")
        if path_branch_id is not None:
            try:
                branch_id = int(path_branch_id)
            except (TypeError, ValueError):
                branch_id = None

        if not PermissionService(db).has_permission(user.id, permission_code, branch_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para realizar esta operación",
            )
        return user

    return dependency
