from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.responses import errors
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.permissions import DbSession, require_permission
from app.application.dto.users import (
    BranchResponse,
    RoleResponse,
    UserAssignmentCreate,
    UserAssignmentResponse,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserTransferRequest,
    UserUpdate,
)
from app.application.services.authorization import PermissionService
from app.application.services.audit import audit_context_from_request
from app.application.services.users import UserManagementService
from app.core.exceptions import ForbiddenError
from app.infrastructure.persistence.models import User

router = APIRouter(prefix="/users", tags=["users"])
ManageUsers = Annotated[User, Depends(require_permission("MANAGE_USERS"))]
AssignBranches = Annotated[User, Depends(require_permission("ASSIGN_USER_BRANCH"))]
MoveBranches = Annotated[User, Depends(require_permission("MOVE_USER_BRANCH"))]


def serialize_assignment(assignment) -> UserAssignmentResponse:
    return UserAssignmentResponse(
        id=assignment.id,
        branch_id=assignment.branch_id,
        branch=BranchResponse(id=assignment.branch.id, code=assignment.branch.code, name=assignment.branch.name),
        valid_from=assignment.valid_from,
        valid_until=assignment.valid_until,
        status=assignment.status,
        reason=assignment.reason,
    )


def serialize_user(user: User) -> UserResponse:
    active_roles = [
        RoleResponse(id=assignment.role.id, code=assignment.role.code, name=assignment.role.name)
        for assignment in user.user_roles
        if assignment.is_active and assignment.role.is_active
    ]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    current_matches = [
        assignment
        for assignment in user.branch_assignments
        if assignment.status == "ACTIVE"
        and assignment.valid_from <= now
        and (assignment.valid_until is None or now < assignment.valid_until)
        and assignment.branch.is_active
    ]
    current = current_matches[0] if len(current_matches) == 1 else None
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        employee_code=user.employee_code,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        deactivated_at=user.deactivated_at,
        roles=active_roles,
        current_assignment=serialize_assignment(current) if current else None,
    )


def require_global_permission(actor_id: int, permission_code: str, db: Session) -> None:
    if not PermissionService(db).has_permission(actor_id, permission_code):
        raise ForbiddenError("No tiene el permiso requerido para esta operación.")


@router.get("", response_model=UserListResponse, responses=errors(401, 403, 422))
def list_users(
    actor: ManageUsers,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=100),
    is_active: bool | None = None,
    branch_id: int | None = None,
    role_code: str | None = Query(default=None, max_length=50),
) -> UserListResponse:
    users, total = UserManagementService(db).list_users(
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
        branch_id=branch_id,
        role_code=role_code,
    )
    return UserListResponse(items=[serialize_user(user) for user in users], total=total, page=page, page_size=page_size)


@router.get("/{user_id}", response_model=UserResponse, responses=errors(401, 403, 404, 422))
def get_user(user_id: int, actor: ManageUsers, db: DbSession) -> UserResponse:
    return serialize_user(UserManagementService(db).get_user(user_id))


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED, responses=errors(401, 403, 404, 409, 422))
def create_user(payload: UserCreate, actor: ManageUsers, db: DbSession, request: Request) -> UserResponse:
    if payload.branch_id is not None:
        require_global_permission(actor.id, "ASSIGN_USER_BRANCH", db)
    return serialize_user(UserManagementService(db).create_user(payload, actor.id, audit_context_from_request(request)))


@router.patch("/{user_id}", response_model=UserResponse, responses=errors(401, 403, 404, 409, 422))
def update_user(user_id: int, payload: UserUpdate, actor: ManageUsers, db: DbSession, request: Request) -> UserResponse:
    return serialize_user(UserManagementService(db).update_user(user_id, payload, actor.id, audit_context_from_request(request)))


@router.post("/{user_id}/activate", response_model=UserResponse, responses=errors(401, 403, 404, 409, 422))
def activate_user(user_id: int, actor: ManageUsers, db: DbSession, request: Request) -> UserResponse:
    return serialize_user(UserManagementService(db).set_active(user_id, True, actor.id, audit_context_from_request(request)))


@router.post("/{user_id}/deactivate", response_model=UserResponse, responses=errors(401, 403, 404, 409, 422))
def deactivate_user(user_id: int, actor: ManageUsers, db: DbSession, request: Request) -> UserResponse:
    return serialize_user(UserManagementService(db).set_active(user_id, False, actor.id, audit_context_from_request(request)))


@router.get("/{user_id}/assignments", response_model=list[UserAssignmentResponse], responses=errors(401, 403, 404, 422))
def list_assignments(user_id: int, actor: ManageUsers, db: DbSession) -> list[UserAssignmentResponse]:
    return [serialize_assignment(item) for item in UserManagementService(db).list_assignments(user_id)]


@router.post("/{user_id}/assignments", response_model=UserAssignmentResponse, status_code=status.HTTP_201_CREATED, responses=errors(401, 403, 404, 409, 422))
def create_assignment(user_id: int, payload: UserAssignmentCreate, actor: AssignBranches, db: DbSession, request: Request) -> UserAssignmentResponse:
    return serialize_assignment(UserManagementService(db).create_assignment(user_id, payload, actor.id, audit_context_from_request(request)))


@router.post("/{user_id}/transfer", response_model=UserAssignmentResponse, responses=errors(401, 403, 404, 409, 422))
def transfer_user(user_id: int, payload: UserTransferRequest, actor: MoveBranches, db: DbSession, request: Request) -> UserAssignmentResponse:
    return serialize_assignment(UserManagementService(db).transfer_user(user_id, payload, actor.id, audit_context_from_request(request)))


@router.get("/{user_id}/roles", response_model=list[RoleResponse], responses=errors(401, 403, 404, 422))
def list_user_roles(user_id: int, actor: ManageUsers, db: DbSession) -> list[RoleResponse]:
    user = UserManagementService(db).get_user(user_id)
    return [
        RoleResponse(id=item.role.id, code=item.role.code, name=item.role.name)
        for item in user.user_roles
        if item.is_active and item.role.is_active
    ]
