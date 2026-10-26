from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.permissions import DbSession
from app.application.services.authorization import PermissionService
from app.application.services.branch_access import BranchAccessService


@dataclass(frozen=True)
class CatalogAccess:
    """Authorization result; branch_id is server-resolved and never taken from the client."""

    is_global: bool
    branch_id: int | None


def require_catalog_access(global_codes: tuple[str, ...], branch_codes: tuple[str, ...]) -> Callable[..., CatalogAccess]:
    """Grant access through any GLOBAL permission, or any BRANCH permission in the user's own branch."""

    def dependency(user: CurrentUser, db: DbSession) -> CatalogAccess:
        permissions = PermissionService(db)
        if any(permissions.has_permission(user.id, code) for code in global_codes):
            return CatalogAccess(is_global=True, branch_id=None)
        context = BranchAccessService(db).get_current_context(user.id)
        if context is not None and any(permissions.has_permission(user.id, code, context.branch_id) for code in branch_codes):
            return CatalogAccess(is_global=False, branch_id=context.branch_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para consultar este catálogo")

    return dependency


BranchCatalogAccess = Annotated[
    CatalogAccess,
    Depends(
        require_catalog_access(
            ("MANAGE_BRANCHES", "MANAGE_USERS", "ASSIGN_USER_BRANCH", "MOVE_USER_BRANCH", "VIEW_GLOBAL_REPORTS", "VIEW_AUDIT_LOGS"),
            ("VIEW_VISITS", "CREATE_VISIT", "UPDATE_VISIT", "VIEW_VISITORS", "VIEW_REPORTS"),
        )
    ),
]
BranchTypeCatalogAccess = Annotated[CatalogAccess, Depends(require_catalog_access(("MANAGE_BRANCHES",), ()))]
VisitorTypeCatalogAccess = Annotated[
    CatalogAccess,
    Depends(require_catalog_access(("MANAGE_VISITOR_TYPES",), ("VIEW_VISITORS", "CREATE_VISITOR", "UPDATE_VISITOR", "VIEW_VISITS", "CREATE_VISIT"))),
]
VisitReasonCatalogAccess = Annotated[
    CatalogAccess,
    Depends(require_catalog_access(("VIEW_GLOBAL_REPORTS", "MANAGE_VISIT_REASONS"), ("VIEW_VISITS", "CREATE_VISIT", "UPDATE_VISIT", "VIEW_REPORTS"))),
]
RoleCatalogAccess = Annotated[CatalogAccess, Depends(require_catalog_access(("MANAGE_USERS",), ()))]
