from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.application.services.branch_access import BranchAccessService, BranchContext
from app.infrastructure.database.session import get_db
from app.infrastructure.persistence.models import User


DbSession = Annotated[Session, Depends(get_db)]


def branch_access_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tiene una sucursal autorizada para esta operación",
    )


def get_current_branch(
    user: CurrentUser,
    db: DbSession,
    request: Request,
    branch_id: int | None = Query(default=None),
) -> BranchContext:
    """Resolve the assigned branch; a client branch_id can only be checked."""
    context = BranchAccessService(db).get_current_context(user.id)
    if context is None:
        raise branch_access_error()

    path_branch_id = request.path_params.get("branch_id")
    requested_branch_id = branch_id
    if path_branch_id is not None:
        try:
            requested_branch_id = int(path_branch_id)
        except (TypeError, ValueError):
            raise branch_access_error() from None

    if requested_branch_id is not None and requested_branch_id != context.branch_id:
        raise branch_access_error()
    return context


CurrentBranch = Annotated[BranchContext, Depends(get_current_branch)]


def require_branch_permission(permission_code: str) -> Callable[..., User]:
    """Require a BRANCH permission within the user's resolved branch context."""

    def dependency(
        user: CurrentUser,
        db: DbSession,
        context: CurrentBranch,
    ) -> User:
        from app.application.services.authorization import PermissionService

        if not PermissionService(db).has_permission(user.id, permission_code, context.branch_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para realizar esta operación en esta sucursal",
            )
        return user

    return dependency


def require_branch_permission_context(permission_code: str) -> Callable[..., BranchContext]:
    """Require a branch permission and return the authorized branch context."""

    def dependency(
        user: CurrentUser,
        db: DbSession,
        context: CurrentBranch,
    ) -> BranchContext:
        from app.application.services.authorization import PermissionService

        if not PermissionService(db).has_permission(user.id, permission_code, context.branch_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para realizar esta operación en esta sucursal",
            )
        return context

    return dependency
