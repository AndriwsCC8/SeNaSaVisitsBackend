from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.permissions import DbSession, require_permission
from app.application.dto.visitors import VisitorCreate, VisitorListResponse, VisitorResponse, VisitorTypeResponse, VisitorUpdate
from app.application.services.visitors import VisitorManagementService
from app.application.services.audit import audit_context_from_request
from app.application.validators.visitors import mask_identification
from app.infrastructure.persistence.models import Visitor

router = APIRouter(prefix="/visitors", tags=["visitors"])
ViewVisitors = Annotated[object, Depends(require_permission("VIEW_VISITORS"))]
CreateVisitors = Annotated[object, Depends(require_permission("CREATE_VISITOR"))]
UpdateVisitors = Annotated[object, Depends(require_permission("UPDATE_VISITOR"))]


def serialize_visitor(visitor: Visitor) -> VisitorResponse:
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
        phone=visitor.phone,
        email=visitor.email,
        company=visitor.company,
        visitor_type=visitor_type,
        is_active=visitor.is_active,
        created_at=visitor.created_at,
        updated_at=visitor.updated_at,
    )


@router.get("", response_model=VisitorListResponse)
def list_visitors(
    actor: ViewVisitors,
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
    )
    return VisitorListResponse(
        items=[serialize_visitor(visitor) for visitor in visitors],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{visitor_id}", response_model=VisitorResponse)
def get_visitor(visitor_id: int, actor: ViewVisitors, db: DbSession) -> VisitorResponse:
    return serialize_visitor(VisitorManagementService(db).get_visitor(visitor_id))


@router.post("", response_model=VisitorResponse, status_code=status.HTTP_201_CREATED)
def create_visitor(payload: VisitorCreate, actor: CreateVisitors, db: DbSession, request: Request) -> VisitorResponse:
    return serialize_visitor(VisitorManagementService(db).create_visitor(payload, actor.id, audit_context_from_request(request)))


@router.patch("/{visitor_id}", response_model=VisitorResponse)
def update_visitor(visitor_id: int, payload: VisitorUpdate, actor: UpdateVisitors, db: DbSession, request: Request) -> VisitorResponse:
    return serialize_visitor(VisitorManagementService(db).update_visitor(visitor_id, payload, actor.id, audit_context_from_request(request)))


@router.post("/{visitor_id}/activate", response_model=VisitorResponse)
def activate_visitor(visitor_id: int, actor: UpdateVisitors, db: DbSession, request: Request) -> VisitorResponse:
    return serialize_visitor(VisitorManagementService(db).set_active(visitor_id, True, actor.id, audit_context_from_request(request)))


@router.post("/{visitor_id}/deactivate", response_model=VisitorResponse)
def deactivate_visitor(visitor_id: int, actor: UpdateVisitors, db: DbSession, request: Request) -> VisitorResponse:
    return serialize_visitor(VisitorManagementService(db).set_active(visitor_id, False, actor.id, audit_context_from_request(request)))
