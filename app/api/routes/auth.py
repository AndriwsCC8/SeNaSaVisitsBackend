from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies.auth import CurrentUser
from app.application.dto.auth import (
    AuthenticatedUserResponse,
    BranchSummary,
    LoginRequest,
    LoginResponse,
)
from app.core.security import create_access_token, verify_password
from app.application.services.authorization import PermissionService
from app.application.services.audit import AuditService, audit_context_from_request
from app.infrastructure.database.session import get_db
from app.infrastructure.persistence.models import User, UserBranchAssignment, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


def invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )


def serialize_user(user: User) -> AuthenticatedUserResponse:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    active_roles = [assignment.role.code for assignment in user.user_roles if assignment.is_active and assignment.role.is_active]
    active_assignments = [
        assignment
        for assignment in user.branch_assignments
        if assignment.status == "ACTIVE"
        and assignment.valid_from <= now
        and (assignment.valid_until is None or assignment.valid_until > now)
        and assignment.branch.is_active
    ]
    active_assignment = active_assignments[0] if len(active_assignments) == 1 else None
    branch = (
        BranchSummary(
            id=active_assignment.branch.id,
            code=active_assignment.branch.code,
            name=active_assignment.branch.name,
        )
        if active_assignment is not None
        else None
    )
    return AuthenticatedUserResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        role=active_roles[0] if active_roles else None,
        branch=branch,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Credenciales inválidas"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Servicio de autenticación no disponible"},
    },
)
def login(credentials: LoginRequest, db: Annotated[Session, Depends(get_db)], request: Request) -> LoginResponse:
    try:
        user = db.scalar(
            select(User)
            .options(
                selectinload(User.user_roles).selectinload(UserRole.role),
                selectinload(User.branch_assignments).selectinload(UserBranchAssignment.branch),
            )
            .where(User.username == credentials.username)
        )
        password_is_valid = False
        if user is not None and user.is_active:
            try:
                password_is_valid = verify_password(credentials.password, user.password_hash)
            except Exception:
                password_is_valid = False
        if not password_is_valid:
            raise invalid_credentials()
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de autenticación no disponible",
            headers={"Retry-After": "5"},
        ) from None
    except (ValueError, TypeError):
        raise invalid_credentials() from None

    AuditService(db).record(actor_user_id=user.id, action="LOGIN", entity_type="User", entity_id=user.id, new_values={"user_id": user.id, "username": user.username}, **audit_context_from_request(request).__dict__)
    db.commit()
    return LoginResponse(
        access_token=create_access_token(str(user.id)),
        user=serialize_user(user),
    )


@router.get("/me", response_model=AuthenticatedUserResponse)
def current_user(user: CurrentUser) -> AuthenticatedUserResponse:
    return serialize_user(user)


@router.get("/permissions/{permission_code}")
def check_permission(
    permission_code: str,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    branch_id: int | None = Query(default=None),
) -> dict[str, bool | str]:
    """Diagnostic permission check; it grants no access by itself."""
    allowed = PermissionService(db).has_permission(user.id, permission_code, branch_id)
    return {"permission": permission_code, "allowed": allowed}
