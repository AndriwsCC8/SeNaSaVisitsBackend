from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.responses import errors
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.branch_access import CurrentBranch, require_branch_permission
from app.api.dependencies.permissions import DbSession
from app.application.dto.visitors import VisitorCreate, VisitorListResponse, VisitorResponse, VisitorTypeResponse, VisitorUpdate
from app.application.services.visitors import VisitorManagementService
from app.application.services.audit import audit_context_from_request
from app.application.services.authorization import PermissionService
from app.application.validators.visitors import mask_email, mask_identification, mask_phone
from app.infrastructure.persistence.models import User, Visitor

router = APIRouter(prefix="/visitors", tags=["visitors"])
ViewVisitors = Annotated[User, Depends(require_branch_permission("VIEW_VISITORS"))]
CreateVisitors = Annotated[User, Depends(require_branch_permission("CREATE_VISITOR"))]
UpdateVisitors = Annotated[User, Depends(require_branch_permission("UPDATE_VISITOR"))]


def can_view_contact(user: CurrentUser, db: DbSession, context: CurrentBranch) -> bool:
    """VIEW_VISITOR_CONTACT is checked in the server-resolved branch; no other permission implies it."""
    return PermissionService(db).has_permission(user.id, "VIEW_VISITOR_CONTACT", context.branch_id)


ContactAccess = Annotated[bool, Depends(can_view_contact)]


def serialize_visitor(visitor: Visitor, contact_visible: bool) -> VisitorResponse:
    visitor_type = (
        VisitorTypeResponse(
            id=visitor.visitor_type.id,
            code=visitor.visitor_type.code,
            name=visitor.visitor_type.name,
        )
        if visitor.visitor_type is not None
        else None
    )
    return VisitorResponse(
        id=visitor.id,
        identification=mask_identification(visitor.identification),
        first_name=visitor.first_name,
        last_name=visitor.last_name,
        phone=visitor.phone if contact_visible else mask_phone(visitor.phone),
        email=visitor.email if contact_visible else mask_email(visitor.email),
        contact_masked=not contact_visible,
        company=visitor.company,
        visitor_type=visitor_type,
        is_active=visitor.is_active,
        created_at=visitor.created_at,
        updated_at=visitor.updated_at,
    )


@router.get("", response_model=VisitorListResponse, responses=errors(401, 403, 422))
def list_visitors(
    actor: ViewVisitors, contact_visible: ContactAccess,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=100),
    is_active: bool | None = None,
    visitor_type_id: int | None = None,
) -> VisitorListResponse:
    visitors, total = VisitorManagementService(db).list_visitors(
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
        visitor_type_id=visitor_type_id,
        include_contact=contact_visible,
    )
    return VisitorListResponse(
        items=[serialize_visitor(visitor, contact_visible) for visitor in visitors],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{visitor_id}", response_model=VisitorResponse, responses=errors(401, 403, 404, 422))
def get_visitor(visitor_id: int, actor: ViewVisitors, contact_visible: ContactAccess, db: DbSession) -> VisitorResponse:
    return serialize_visitor(VisitorManagementService(db).get_visitor(visitor_id), contact_visible)


@router.post("", response_model=VisitorResponse, status_code=status.HTTP_201_CREATED, responses=errors(401, 403, 404, 409, 422))
def create_visitor(payload: VisitorCreate, actor: CreateVisitors, contact_visible: ContactAccess, db: DbSession, request: Request) -> VisitorResponse:
    return serialize_visitor(VisitorManagementService(db).create_visitor(payload, actor.id, audit_context_from_request(request)), contact_visible)


@router.patch("/{visitor_id}", response_model=VisitorResponse, responses=errors(401, 403, 404, 409, 422))
def update_visitor(visitor_id: int, payload: VisitorUpdate, actor: UpdateVisitors, contact_visible: ContactAccess, db: DbSession, request: Request) -> VisitorResponse:
    return serialize_visitor(VisitorManagementService(db).update_visitor(visitor_id, payload, actor.id, audit_context_from_request(request)), contact_visible)


@router.post("/{visitor_id}/activate", response_model=VisitorResponse, responses=errors(401, 403, 404, 409, 422))
def activate_visitor(visitor_id: int, actor: UpdateVisitors, contact_visible: ContactAccess, db: DbSession, request: Request) -> VisitorResponse:
    return serialize_visitor(VisitorManagementService(db).set_active(visitor_id, True, actor.id, audit_context_from_request(request)), contact_visible)


@router.post("/{visitor_id}/deactivate", response_model=VisitorResponse, responses=errors(401, 403, 404, 409, 422))
def deactivate_visitor(visitor_id: int, actor: UpdateVisitors, contact_visible: ContactAccess, db: DbSession, request: Request) -> VisitorResponse:
    return serialize_visitor(VisitorManagementService(db).set_active(visitor_id, False, actor.id, audit_context_from_request(request)), contact_visible)
