from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.catalogs import (
    BranchCatalogAccess,
    BranchTypeCatalogAccess,
    RoleCatalogAccess,
    VisitorTypeCatalogAccess,
    VisitReasonCatalogAccess,
)
from app.api.dependencies.permissions import DbSession
from app.api.responses import errors
from app.application.dto.catalogs import (
    BranchCatalogItem,
    BranchTypeCatalogItem,
    VisitorTypeCatalogItem,
    VisitReasonCatalogItem,
)
from app.application.dto.users import RoleResponse
from app.application.services.authorization import PermissionService
from app.application.services.catalogs import CatalogService

router = APIRouter(tags=["catalogs"])

_INCLUDE_INACTIVE = Query(default=False, description="Incluye registros inactivos (por defecto solo activos).")


def _require_permission(user: CurrentUser, db: DbSession, code: str) -> None:
    if not PermissionService(db).has_permission(user.id, code):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Solo {code} puede consultar registros inactivos de este catálogo")


@router.get("/branches", response_model=list[BranchCatalogItem], responses=errors(401, 403, 422))
def list_branches(
    user: CurrentUser,
    access: BranchCatalogAccess,
    db: DbSession,
    include_inactive: bool = _INCLUDE_INACTIVE,
) -> list[BranchCatalogItem]:
    """Usuarios con alcance global ven todas las sucursales; el resto solo la suya."""
    if include_inactive:
        _require_permission(user, db, "MANAGE_BRANCHES")
    branches = CatalogService(db).list_branches(branch_id=access.branch_id, include_inactive=include_inactive)
    return [BranchCatalogItem.model_validate(item) for item in branches]


@router.get("/branch-types", response_model=list[BranchTypeCatalogItem], responses=errors(401, 403, 422))
def list_branch_types(
    user: CurrentUser,
    access: BranchTypeCatalogAccess,
    db: DbSession,
    include_inactive: bool = _INCLUDE_INACTIVE,
) -> list[BranchTypeCatalogItem]:
    return [BranchTypeCatalogItem.model_validate(item) for item in CatalogService(db).list_branch_types(include_inactive=include_inactive)]


@router.get("/visitor-types", response_model=list[VisitorTypeCatalogItem], responses=errors(401, 403, 422))
def list_visitor_types(
    user: CurrentUser,
    access: VisitorTypeCatalogAccess,
    db: DbSession,
    include_inactive: bool = _INCLUDE_INACTIVE,
) -> list[VisitorTypeCatalogItem]:
    if include_inactive:
        _require_permission(user, db, "MANAGE_VISITOR_TYPES")
    return [VisitorTypeCatalogItem.model_validate(item) for item in CatalogService(db).list_visitor_types(include_inactive=include_inactive)]


@router.get("/visit-reasons", response_model=list[VisitReasonCatalogItem], responses=errors(401, 403, 422))
def list_visit_reasons(
    user: CurrentUser,
    access: VisitReasonCatalogAccess,
    db: DbSession,
    include_inactive: bool = _INCLUDE_INACTIVE,
) -> list[VisitReasonCatalogItem]:
    if include_inactive:
        _require_permission(user, db, "MANAGE_VISIT_REASONS")
    return [VisitReasonCatalogItem.model_validate(item) for item in CatalogService(db).list_visit_reasons(include_inactive=include_inactive)]


@router.get("/roles", response_model=list[RoleResponse], responses=errors(401, 403))
def list_roles(access: RoleCatalogAccess, db: DbSession) -> list[RoleResponse]:
    return [RoleResponse(id=item.id, code=item.code, name=item.name) for item in CatalogService(db).list_roles()]
