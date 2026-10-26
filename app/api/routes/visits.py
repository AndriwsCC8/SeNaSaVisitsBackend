from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.responses import errors
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.branch_access import require_branch_permission_context
from app.api.dependencies.permissions import DbSession
from app.application.dto.visits import (
    VisitCancelRequest,
    VisitCompleteRequest,
    VisitCreate,
    VisitListResponse,
    VisitReasonResponse,
    VisitResponse,
    VisitUpdate,
    VisitUserResponse,
    VisitVisitorResponse,
    VisitBranchResponse,
)
from app.application.services.branch_access import BranchContext
from app.application.services.visits import VisitManagementService
from app.application.services.audit import audit_context_from_request
from app.application.validators.visitors import mask_identification
from app.infrastructure.persistence.models import Visit

router = APIRouter(prefix="/visits", tags=["visits"])
ViewVisitsContext = Annotated[BranchContext, Depends(require_branch_permission_context("VIEW_VISITS"))]
CreateVisitContext = Annotated[BranchContext, Depends(require_branch_permission_context("CREATE_VISIT"))]
UpdateVisitContext = Annotated[BranchContext, Depends(require_branch_permission_context("UPDATE_VISIT"))]


def serialize_user(user) -> VisitUserResponse:
    return VisitUserResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )


def serialize_visit(visit: Visit) -> VisitResponse:
    return VisitResponse(
        id=visit.id,
        visitor=VisitVisitorResponse(
            id=visit.visitor.id,
            identification=mask_identification(visit.visitor.identification),
            first_name=visit.visitor.first_name,
            last_name=visit.visitor.last_name,
            company=visit.visitor.company,
        ),
        branch=VisitBranchResponse(id=visit.branch.id, code=visit.branch.code, name=visit.branch.name),
        registered_by=serialize_user(visit.registered_by),
        entry_at=visit.entry_at,
        exit_at=visit.exit_at,
        reason=VisitReasonResponse(id=visit.reason.id, code=visit.reason.code, name=visit.reason.name),
        destination=visit.destination,
        visited_person=visit.visited_person,
        status=visit.status,
        notes=visit.notes,
        created_at=visit.created_at,
        updated_at=visit.updated_at,
        completed_by=serialize_user(visit.completed_by) if visit.completed_by else None,
        cancelled_by=serialize_user(visit.cancelled_by) if visit.cancelled_by else None,
        cancelled_at=visit.cancelled_at,
        cancellation_reason=visit.cancellation_reason,
    )


@router.get("", response_model=VisitListResponse, responses=errors(401, 403, 422))
def list_visits(
    context: ViewVisitsContext,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    visitor_id: int | None = None,
    reason_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = Query(default=None, max_length=100),
) -> VisitListResponse:
    visits, total = VisitManagementService(db).list_visits(
        context,
        page=page,
        page_size=page_size,
        status=status_filter,
        visitor_id=visitor_id,
        reason_id=reason_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    return VisitListResponse(items=[serialize_visit(visit) for visit in visits], total=total, page=page, page_size=page_size)


@router.get("/{visit_id}", response_model=VisitResponse, responses=errors(401, 403, 404, 422))
def get_visit(visit_id: int, context: ViewVisitsContext, db: DbSession) -> VisitResponse:
    return serialize_visit(VisitManagementService(db).get_visit(context, visit_id))


@router.post("", response_model=VisitResponse, status_code=status.HTTP_201_CREATED, responses=errors(401, 403, 404, 409, 422))
def create_visit(
    payload: VisitCreate,
    user: CurrentUser,
    context: CreateVisitContext,
    db: DbSession,
    request: Request,
) -> VisitResponse:
    return serialize_visit(VisitManagementService(db).create_visit(context, user.id, payload, audit_context_from_request(request)))


@router.patch("/{visit_id}", response_model=VisitResponse, responses=errors(401, 403, 404, 409, 422))
def update_visit(
    visit_id: int,
    payload: VisitUpdate,
    context: UpdateVisitContext,
    db: DbSession,
    user: CurrentUser,
    request: Request,
) -> VisitResponse:
    return serialize_visit(VisitManagementService(db).update_visit(context, visit_id, payload, user.id, audit_context_from_request(request)))


@router.post("/{visit_id}/complete", response_model=VisitResponse, responses=errors(401, 403, 404, 409, 422))
def complete_visit(
    visit_id: int,
    payload: VisitCompleteRequest,
    user: CurrentUser,
    context: UpdateVisitContext,
    db: DbSession,
    request: Request,
) -> VisitResponse:
    return serialize_visit(VisitManagementService(db).complete_visit(context, user.id, visit_id, payload, audit_context_from_request(request)))


@router.post("/{visit_id}/cancel", response_model=VisitResponse, responses=errors(401, 403, 404, 409, 422))
def cancel_visit(
    visit_id: int,
    payload: VisitCancelRequest,
    user: CurrentUser,
    context: UpdateVisitContext,
    db: DbSession,
    request: Request,
) -> VisitResponse:
    return serialize_visit(VisitManagementService(db).cancel_visit(context, user.id, visit_id, payload, audit_context_from_request(request)))
