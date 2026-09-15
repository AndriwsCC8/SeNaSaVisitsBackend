from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.permissions import DbSession
from app.application.services.authorization import PermissionService
from app.application.services.branch_access import BranchAccessService
from app.application.services.dashboard import DashboardScope


def get_dashboard_scope(user: CurrentUser, db: DbSession) -> DashboardScope:
    permissions = PermissionService(db)
    if permissions.has_permission(user.id, "VIEW_GLOBAL_REPORTS"):
        return DashboardScope(branch_id=None, is_global=True)
    context = BranchAccessService(db).get_current_context(user.id)
    if context is None or not permissions.has_permission(user.id, "VIEW_REPORTS", context.branch_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para consultar el Dashboard",
        )
    return DashboardScope(branch_id=context.branch_id, is_global=False)


DashboardScopeDependency = Annotated[DashboardScope, Depends(get_dashboard_scope)]
