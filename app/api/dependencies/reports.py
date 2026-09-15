from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Query, status

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.permissions import DbSession
from app.application.services.authorization import PermissionService
from app.application.services.branch_access import BranchAccessService
from app.application.services.reports import ReportScope


def get_report_scope(
    user: CurrentUser,
    db: DbSession,
    branch_id: int | None = Query(default=None),
) -> ReportScope:
    permissions = PermissionService(db)
    if permissions.has_permission(user.id, "VIEW_GLOBAL_REPORTS"):
        if branch_id is not None and not BranchAccessService(db).is_active_branch(branch_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La sucursal solicitada no existe.")
        return ReportScope(branch_id=branch_id, is_global=True)

    context = BranchAccessService(db).get_current_context(user.id)
    if context is None or not permissions.has_permission(user.id, "VIEW_REPORTS", context.branch_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para consultar reportes")
    if branch_id is not None and branch_id != context.branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene acceso a la sucursal solicitada")
    return ReportScope(branch_id=context.branch_id, is_global=False)


ReportScopeDependency = Annotated[ReportScope, Depends(get_report_scope)]
