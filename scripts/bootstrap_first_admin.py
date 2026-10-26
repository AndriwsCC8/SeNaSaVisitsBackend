"""Create (or verify) the first administrator. Manual command; never runs from FastAPI startup.

Prerequisites, in order:
  1. alembic upgrade head
  2. python -m scripts.seed_authorization          (roles and permissions)
  3. python -m scripts.load_reference_data ...     (official branches; branch must exist)
  4. python -m scripts.bootstrap_first_admin ...   (this command)

The password is only requested interactively and is never logged or echoed.
"""
from __future__ import annotations

import argparse
import getpass
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.authorization import PermissionService
from app.core.security import hash_password
from app.infrastructure.persistence.models import (
    Branch,
    Permission,
    Role,
    RolePermission,
    User,
    UserBranchAssignment,
    UserRole,
)
from scripts.permission_catalog import PERMISSIONS, ROLE_PERMISSION_CODES, ROLES

logger = logging.getLogger("senasa_visits.bootstrap")

ADMIN_ROLE_CODE = "SUPER_ADMIN"


@dataclass(frozen=True)
class BootstrapResult:
    user_id: int
    branch_id: int
    created: bool


def parse_catalog_entry(value: str) -> tuple[str, str]:
    """Parse a repeatable CODE=Name command-line catalog value."""
    code, separator, name = value.partition("=")
    code = code.strip().upper()
    name = name.strip()
    if not separator or not code or not name:
        raise argparse.ArgumentTypeError("Use el formato CODIGO=Nombre, sin valores vacíos")
    if len(code) > 50 or len(name) > 120:
        raise argparse.ArgumentTypeError("El código o nombre supera la longitud máxima permitida")
    if not re.fullmatch(r"[A-Z0-9_-]+", code):
        raise argparse.ArgumentTypeError("El código solo puede contener letras, números, guion y guion bajo")
    return code, name


def validate_initial_password(password: str) -> None:
    if len(password) < 12 or not any(c.islower() for c in password) or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
        raise ValueError("La contraseña inicial debe tener al menos 12 caracteres, una minúscula, una mayúscula y un número")


def _load_catalog(db: Session) -> tuple[dict[str, Role], dict[str, Permission]]:
    roles = {role.code: role for role in db.scalars(select(Role)).all()}
    permissions = {permission.code: permission for permission in db.scalars(select(Permission)).all()}
    problems: list[str] = []
    for code, *_ in ROLES:
        if code not in roles:
            problems.append(f"falta el rol {code}")
        elif not roles[code].is_active:
            problems.append(f"el rol {code} está inactivo")
    for code, _name, _resource, _action, scope in PERMISSIONS:
        permission = permissions.get(code)
        if permission is None:
            problems.append(f"falta el permiso {code}")
        elif not permission.is_active or permission.scope != scope:
            problems.append(f"el permiso {code} está inactivo o con ámbito distinto")
    if problems:
        raise RuntimeError("Catálogo de autorización incompleto o inconsistente (ejecute scripts.seed_authorization): " + "; ".join(problems))
    return roles, permissions


def _verify_effective_permissions(db: Session, user_id: int, branch_id: int) -> None:
    """Confirm through the real authorization service that every catalog permission is effective."""
    service = PermissionService(db)
    missing = [
        code
        for code, _name, _resource, _action, scope in PERMISSIONS
        if not service.has_permission(user_id, code, branch_id if scope == "BRANCH" else None)
    ]
    if missing:
        raise RuntimeError("El administrador no obtiene permisos efectivos: " + ", ".join(missing))


def _configuration_problems(db: Session, user: User, branch: Branch, roles: dict[str, Role], permissions: dict[str, Permission]) -> list[str]:
    problems: list[str] = []
    if not user.is_active:
        problems.append("el usuario existe pero está inactivo")
    active_roles = db.scalars(select(UserRole).where(UserRole.user_id == user.id, UserRole.is_active.is_(True))).all()
    if not any(item.role_id == roles[ADMIN_ROLE_CODE].id for item in active_roles):
        problems.append(f"el usuario no tiene el rol {ADMIN_ROLE_CODE} activo")
    assignments = db.scalars(
        select(UserBranchAssignment).where(
            UserBranchAssignment.user_id == user.id,
            UserBranchAssignment.status == "ACTIVE",
            UserBranchAssignment.valid_until.is_(None),
        )
    ).all()
    if len(assignments) != 1 or assignments[0].branch_id != branch.id:
        problems.append("el usuario no tiene exactamente una asignación vigente a la sucursal indicada")
    granted = set(
        db.scalars(
            select(RolePermission.permission_id).where(
                RolePermission.role_id == roles[ADMIN_ROLE_CODE].id, RolePermission.is_active.is_(True)
            )
        ).all()
    )
    missing = sorted(code for code in ROLE_PERMISSION_CODES[ADMIN_ROLE_CODE] if permissions[code].id not in granted)
    if missing:
        problems.append("al rol SUPER_ADMIN le faltan permisos: " + ", ".join(missing))
    return problems


def initialize_first_admin(
    db: Session,
    *,
    username: str,
    first_name: str,
    last_name: str,
    email: str | None,
    password: str,
    branch_code: str,
) -> BootstrapResult:
    """Create the first administrator, or confirm an already correct configuration (no changes)."""
    validate_initial_password(password)

    # TABLOCKX makes the "no users yet" check safe against concurrent bootstrap runs on SQL Server.
    users = db.scalars(select(User).with_hint(User, "TABLOCKX, HOLDLOCK", dialect_name="mssql")).all()
    roles, permissions = _load_catalog(db)

    branch = db.scalar(select(Branch).where(Branch.code == branch_code))
    if branch is None or not branch.is_active:
        raise RuntimeError(f"La sucursal {branch_code} no existe o está inactiva (cárguela con scripts.load_reference_data)")

    existing = next((user for user in users if user.username == username), None)
    if existing is not None:
        problems = _configuration_problems(db, existing, branch, roles, permissions)
        if problems:
            raise RuntimeError("Configuración parcial o ambigua; no se modifican privilegios automáticamente: " + "; ".join(problems))
        _verify_effective_permissions(db, existing.id, branch.id)
        logger.info("Administrador ya configurado: user_id=%s branch_id=%s (sin cambios)", existing.id, branch.id)
        return BootstrapResult(existing.id, branch.id, created=False)

    if users:
        raise RuntimeError("Ya existen usuarios y ninguno coincide con el nombre indicado; el bootstrap no promueve usuarios existentes")

    admin = User(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(admin)
    db.flush()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # SQL Server stores DATETIME2(3); truncate so the stored value never lies in the future.
    valid_from = now.replace(microsecond=now.microsecond // 1000 * 1000)
    db.add(UserRole(user_id=admin.id, role_id=roles[ADMIN_ROLE_CODE].id, assigned_by_user_id=admin.id, is_active=True))
    db.add(
        UserBranchAssignment(
            user_id=admin.id,
            branch_id=branch.id,
            valid_from=valid_from,
            valid_until=None,
            assigned_by_user_id=admin.id,
            reason="Asignación inicial del primer administrador",
            status="ACTIVE",
        )
    )
    # RolePermission requires an existing user, which is why grants are created here and not by the seed.
    for role_code, permission_codes in ROLE_PERMISSION_CODES.items():
        for permission_code in sorted(permission_codes):
            already = db.scalar(
                select(RolePermission.id).where(
                    RolePermission.role_id == roles[role_code].id,
                    RolePermission.permission_id == permissions[permission_code].id,
                    RolePermission.is_active.is_(True),
                )
            )
            if already is None:
                db.add(
                    RolePermission(
                        role_id=roles[role_code].id,
                        permission_id=permissions[permission_code].id,
                        assigned_by_user_id=admin.id,
                        is_active=True,
                    )
                )
    db.flush()
    _verify_effective_permissions(db, admin.id, branch.id)
    logger.info("Primer administrador creado: user_id=%s branch_id=%s", admin.id, branch.id)
    return BootstrapResult(admin.id, branch.id, created=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicialización manual del primer administrador autorizado")
    parser.add_argument("--confirm-initialization", action="store_true", help="Confirma la operación explícita")
    parser.add_argument("--username", required=True)
    parser.add_argument("--first-name", required=True)
    parser.add_argument("--last-name", required=True)
    parser.add_argument("--email")
    parser.add_argument("--branch-code", required=True, help="Código de una sucursal activa ya cargada")
    args = parser.parse_args()
    if not args.confirm_initialization:
        parser.error("Debe agregar --confirm-initialization para confirmar la operación")

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    password = getpass.getpass("Contraseña inicial (mínimo 12 caracteres): ")
    if password != getpass.getpass("Repita la contraseña: "):
        parser.error("Las contraseñas no coinciden")

    from app.infrastructure.database.session import SessionLocal

    try:
        with SessionLocal.begin() as db:
            result = initialize_first_admin(
                db,
                username=args.username.strip(),
                first_name=args.first_name.strip(),
                last_name=args.last_name.strip(),
                email=args.email,
                password=password,
                branch_code=args.branch_code.strip().upper(),
            )
    except (RuntimeError, ValueError) as exc:
        parser.error(f"Abortado; la transacción se revirtió. {exc}")

    state = "creado" if result.created else "ya estaba configurado (sin cambios)"
    print(f"Administrador {state}. Usuario ID={result.user_id}; sucursal ID={result.branch_id}.")


if __name__ == "__main__":
    main()
