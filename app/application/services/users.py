from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.application.dto.users import UserCreate, UserTransferRequest, UserUpdate, UserAssignmentCreate
from app.application.services.audit import AuditContext, AuditService
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import hash_password
from app.infrastructure.persistence.models import Branch, Role, User, UserBranchAssignment, UserRole


class UserManagementService:
    """Transactional user, role-assignment, and branch-assignment operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_users(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
        branch_id: int | None = None,
        role_code: str | None = None,
    ) -> tuple[list[User], int]:
        now = self._utc_naive(None)
        query = select(User).options(
            selectinload(User.user_roles).selectinload(UserRole.role),
            selectinload(User.branch_assignments).selectinload(UserBranchAssignment.branch),
        )
        count_query = select(func.count(func.distinct(User.id))).select_from(User)
        filters = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(or_(User.username.like(pattern), User.first_name.like(pattern), User.last_name.like(pattern), User.employee_code.like(pattern)))
        if is_active is not None:
            filters.append(User.is_active.is_(is_active))
        if branch_id is not None:
            query = query.join(UserBranchAssignment, UserBranchAssignment.user_id == User.id)
            count_query = count_query.join(UserBranchAssignment, UserBranchAssignment.user_id == User.id)
            filters.extend(
                (
                    UserBranchAssignment.branch_id == branch_id,
                    UserBranchAssignment.status == "ACTIVE",
                    UserBranchAssignment.valid_from <= now,
                    or_(UserBranchAssignment.valid_until.is_(None), UserBranchAssignment.valid_until > now),
                )
            )
        if role_code:
            query = query.join(UserRole, UserRole.user_id == User.id).join(Role, Role.id == UserRole.role_id)
            count_query = count_query.join(UserRole, UserRole.user_id == User.id).join(Role, Role.id == UserRole.role_id)
            filters.extend((UserRole.is_active.is_(True), Role.code == role_code, Role.is_active.is_(True)))
        query = query.where(*filters).order_by(User.id).offset((page - 1) * page_size).limit(page_size)
        total = self.db.scalar(count_query.where(*filters)) or 0
        return list(self.db.scalars(query).unique().all()), total

    def get_user(self, user_id: int) -> User:
        user = self.db.scalar(
            select(User)
            .options(
                selectinload(User.user_roles).selectinload(UserRole.role),
                selectinload(User.branch_assignments).selectinload(UserBranchAssignment.branch),
            )
            .where(User.id == user_id)
        )
        if user is None:
            raise NotFoundError("El usuario solicitado no existe.")
        return user

    def create_user(self, payload: UserCreate, actor_id: int, audit: AuditContext | None = None) -> User:
        self._ensure_clean_transaction()
        try:
            with self.db.begin():
                self._ensure_unique(payload.username, payload.email, payload.employee_code)
                user = User(
                    username=payload.username,
                    email=payload.email,
                    first_name=payload.first_name,
                    last_name=payload.last_name,
                    employee_code=payload.employee_code,
                    password_hash=hash_password(payload.password),
                    is_active=True,
                )
                self.db.add(user)
                self.db.flush()
                if payload.role_code:
                    self._assign_role(user.id, payload.role_code, actor_id)
                if payload.branch_id is not None:
                    self._create_assignment(
                        user.id,
                        UserAssignmentCreate(
                            branch_id=payload.branch_id,
                            valid_from=payload.assignment_valid_from,
                        ),
                        actor_id,
                    )
                AuditService(self.db).record(
                    actor_user_id=actor_id,
                    action="CREATE_USER",
                    entity_type="User",
                    entity_id=user.id,
                    branch_id=payload.branch_id,
                    new_values={"user_id": user.id, "username": user.username, "is_active": True, "role_code": payload.role_code, "branch_id": payload.branch_id},
                    **(audit.__dict__ if audit else {}),
                )
            return self.get_user(user.id)
        except IntegrityError as exc:
            raise ConflictError("Username, email o código de empleado ya existe.") from exc

    def update_user(self, user_id: int, payload: UserUpdate, actor_id: int, audit: AuditContext | None = None) -> User:
        user = self.get_user(user_id)
        if payload.email is not None and payload.email != user.email:
            if self.db.scalar(select(User.id).where(User.email == payload.email, User.id != user_id)) is not None:
                raise ConflictError("El email ya está registrado.")
        if payload.employee_code is not None and payload.employee_code != user.employee_code:
            if self.db.scalar(select(User.id).where(User.employee_code == payload.employee_code, User.id != user_id)) is not None:
                raise ConflictError("El código de empleado ya está registrado.")
        old_values = {}
        new_values = {}
        for field in ("email", "first_name", "last_name", "employee_code"):
            value = getattr(payload, field)
            if value is not None:
                old_values[field] = getattr(user, field)
                setattr(user, field, value)
                new_values[field] = value
        if payload.role_code is not None:
            self._assign_role(user_id, payload.role_code, actor_id)
            new_values["role_code"] = payload.role_code
        AuditService(self.db).record(actor_user_id=actor_id, action="UPDATE_USER", entity_type="User", entity_id=user_id, old_values=old_values, new_values=new_values, **(audit.__dict__ if audit else {}))
        self.db.commit()
        return self.get_user(user_id)

    def set_active(self, user_id: int, active: bool, actor_id: int | None = None, audit: AuditContext | None = None) -> User:
        user = self.get_user(user_id)
        user.is_active = active
        user.deactivated_at = None if active else self._utc_naive(None)
        if actor_id is not None:
            AuditService(self.db).record(actor_user_id=actor_id, action="DEACTIVATE_USER" if not active else "UPDATE_USER", entity_type="User", entity_id=user_id, old_values={"is_active": not active}, new_values={"is_active": active}, **(audit.__dict__ if audit else {}))
        self.db.commit()
        return self.get_user(user_id)

    def create_assignment(self, user_id: int, payload: UserAssignmentCreate, actor_id: int, audit: AuditContext | None = None) -> UserBranchAssignment:
        self._ensure_clean_transaction()
        with self.db.begin():
            user = self.db.get(User, user_id)
            if user is None:
                raise NotFoundError("El usuario solicitado no existe.")
            if not user.is_active:
                raise ValidationError("No se puede asignar una sucursal a un usuario inactivo.")
            assignment = self._create_assignment(user_id, payload, actor_id)
            AuditService(self.db).record(actor_user_id=actor_id, action="ASSIGN_USER_BRANCH", entity_type="UserBranchAssignment", entity_id=assignment.id, branch_id=assignment.branch_id, new_values={"user_id": user_id, "branch_id": assignment.branch_id, "valid_from": assignment.valid_from, "valid_until": assignment.valid_until, "reason": assignment.reason}, **(audit.__dict__ if audit else {}))
        return self._get_assignment(assignment.id)

    def transfer_user(self, user_id: int, payload: UserTransferRequest, actor_id: int, audit: AuditContext | None = None) -> UserBranchAssignment:
        self._ensure_clean_transaction()
        effective_at = self._utc_naive(payload.effective_at)
        try:
            user = self.db.get(User, user_id)
            if user is None:
                raise NotFoundError("El usuario solicitado no existe.")
            if not user.is_active:
                raise ValidationError("No se puede transferir un usuario inactivo.")
            branch = self.db.scalar(select(Branch).where(Branch.id == payload.new_branch_id))
            if branch is None:
                raise NotFoundError("La sucursal solicitada no existe.")
            if not branch.is_active:
                raise ValidationError("La sucursal solicitada está inactiva.")
            assignments = list(
                self.db.scalars(
                    select(UserBranchAssignment)
                    .where(UserBranchAssignment.user_id == user_id)
                    .with_hint(UserBranchAssignment, "WITH (UPDLOCK, HOLDLOCK)", "mssql")
                ).all()
            )
            current = [assignment for assignment in assignments if self._contains(assignment, effective_at)]
            if len(current) > 1:
                raise ConflictError("El usuario tiene múltiples asignaciones vigentes.")
            if current and current[0].branch_id == payload.new_branch_id:
                raise ConflictError("El usuario ya está asignado a esa sucursal.")
            if current:
                current[0].valid_until = effective_at
                current[0].status = "ENDED"
            self._assert_no_overlap(assignments, effective_at, None)
            new_assignment = UserBranchAssignment(
                user_id=user_id,
                branch_id=payload.new_branch_id,
                valid_from=effective_at,
                valid_until=None,
                assigned_by_user_id=actor_id,
                reason=payload.reason,
                status="ACTIVE",
            )
            self.db.add(new_assignment)
            self.db.flush()
            assignment_id = new_assignment.id
            AuditService(self.db).record(actor_user_id=actor_id, action="MOVE_USER_BRANCH", entity_type="User", entity_id=user_id, branch_id=new_assignment.branch_id, old_values={"old_branch_id": current[0].branch_id if current else None}, new_values={"user_id": user_id, "new_branch_id": new_assignment.branch_id, "effective_at": effective_at, "reason": payload.reason}, **(audit.__dict__ if audit else {}))
            self.db.commit()
            return self._get_assignment(assignment_id)
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("La transferencia entra en conflicto con otra asignación.") from exc
        except Exception:
            self.db.rollback()
            raise

    def list_assignments(self, user_id: int) -> list[UserBranchAssignment]:
        if self.db.get(User, user_id) is None:
            raise NotFoundError("El usuario solicitado no existe.")
        return list(
            self.db.scalars(
                select(UserBranchAssignment)
                .options(selectinload(UserBranchAssignment.branch))
                .where(UserBranchAssignment.user_id == user_id)
                .order_by(UserBranchAssignment.valid_from.desc())
            ).all()
        )

    def _create_assignment(self, user_id: int, payload: UserAssignmentCreate, actor_id: int) -> UserBranchAssignment:
        branch = self.db.scalar(select(Branch).where(Branch.id == payload.branch_id))
        if branch is None:
            raise NotFoundError("La sucursal solicitada no existe.")
        if not branch.is_active:
            raise ValidationError("La sucursal solicitada está inactiva.")
        valid_from = self._utc_naive(payload.valid_from)
        valid_until = self._utc_naive(payload.valid_until) if payload.valid_until else None
        if valid_until is not None and valid_until <= valid_from:
            raise ValidationError("ValidUntil debe ser posterior a ValidFrom.")
        assignments = list(self.db.scalars(select(UserBranchAssignment).where(UserBranchAssignment.user_id == user_id).with_for_update()).all())
        if payload.valid_until is None and any(self._contains(item, valid_from) for item in assignments):
            raise ConflictError("El usuario ya tiene una asignación vigente.")
        self._assert_no_overlap(assignments, valid_from, valid_until)
        assignment = UserBranchAssignment(
            user_id=user_id,
            branch_id=payload.branch_id,
            valid_from=valid_from,
            valid_until=valid_until,
            assigned_by_user_id=actor_id,
            reason=payload.reason,
            status="ACTIVE" if valid_until is None else "ENDED",
        )
        self.db.add(assignment)
        self.db.flush()
        return assignment

    def _assign_role(self, user_id: int, role_code: str, actor_id: int) -> None:
        role = self.db.scalar(select(Role).where(Role.code == role_code))
        if role is None:
            raise NotFoundError("El rol solicitado no existe.")
        if not role.is_active:
            raise ValidationError("El rol solicitado está inactivo.")
        active = list(self.db.scalars(select(UserRole).where(UserRole.user_id == user_id, UserRole.is_active.is_(True))).all())
        now = self._utc_naive(None)
        for current in active:
            current.is_active = False
            current.revoked_at = now
        self.db.add(UserRole(user_id=user_id, role_id=role.id, assigned_by_user_id=actor_id, is_active=True))

    def _ensure_unique(self, username: str, email: str | None, employee_code: str | None) -> None:
        if self.db.scalar(select(User.id).where(User.username == username)) is not None:
            raise ConflictError("El username ya está registrado.")
        if email and self.db.scalar(select(User.id).where(User.email == email)) is not None:
            raise ConflictError("El email ya está registrado.")
        if employee_code and self.db.scalar(select(User.id).where(User.employee_code == employee_code)) is not None:
            raise ConflictError("El código de empleado ya está registrado.")

    def _get_assignment(self, assignment_id: int) -> UserBranchAssignment:
        assignment = self.db.scalar(select(UserBranchAssignment).options(selectinload(UserBranchAssignment.branch)).where(UserBranchAssignment.id == assignment_id))
        if assignment is None:
            raise NotFoundError("La asignación solicitada no existe.")
        return assignment

    @staticmethod
    def _contains(assignment: UserBranchAssignment, at: datetime) -> bool:
        return assignment.status == "ACTIVE" and assignment.valid_from <= at and (assignment.valid_until is None or at < assignment.valid_until)

    @staticmethod
    def _assert_no_overlap(assignments: list[UserBranchAssignment], start: datetime, end: datetime | None) -> None:
        for existing in assignments:
            existing_end = existing.valid_until
            if existing.valid_from < (end or datetime.max) and (start < existing_end if existing_end else True):
                raise ConflictError("El intervalo de asignación se solapa con el historial existente.")

    def _ensure_clean_transaction(self) -> None:
        if hasattr(self.db, "in_transaction") and self.db.in_transaction():
            self.db.commit()

    @staticmethod
    def _utc_naive(value: datetime | None) -> datetime:
        current = value or datetime.now(timezone.utc)
        if current.tzinfo is not None:
            return current.astimezone(timezone.utc).replace(tzinfo=None)
        return current
