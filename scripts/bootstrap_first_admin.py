"""Create the first authorized administrator and required starter catalogs.

This command is intentionally manual and refuses to run once any user exists.
It never runs from FastAPI startup. Use only after applying the approved Alembic head.
"""
from __future__ import annotations

import argparse
import getpass
import re
from datetime import datetime, timezone
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.persistence.models import (
    Branch,
    BranchType,
    Permission,
    Role,
    RolePermission,
    User,
    UserBranchAssignment,
    UserRole,
    VisitReason,
    VisitorType,
)
from scripts.permission_catalog import PERMISSIONS, ROLE_PERMISSION_CODES, ROLES

NamedCatalog = TypeVar("NamedCatalog", BranchType, VisitorType, VisitReason)


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
    if len(password) < 12 or not any(char.islower() for char in password) or not any(char.isupper() for char in password) or not any(char.isdigit() for char in password):
        raise ValueError("La contraseña inicial debe tener al menos 12 caracteres, una minúscula, una mayúscula y un número")


def upsert_named_catalog(db: Session, model: type[NamedCatalog], code: str, name: str) -> NamedCatalog:
    item = db.scalar(select(model).where(model.code == code))
    if item is None:
        item = model(code=code, name=name, is_active=True)
        db.add(item)
        db.flush()
    elif not item.is_active or item.name != name:
        raise ValueError(f"El catálogo {model.__tablename__}.{code} ya existe con datos diferentes o está inactivo")
    return item


def initialize_first_admin(
    db: Session,
    *,
    username: str,
    first_name: str,
    last_name: str,
    email: str | None,
    password: str,
    branch_type_code: str,
    branch_type_name: str,
    branch_code: str,
    branch_name: str,
    visitor_types: list[tuple[str, str]],
    visit_reasons: list[tuple[str, str]],
) -> tuple[int, int]:
    validate_initial_password(password)

    # On SQL Server, this table lock makes the empty-database guard serializable
    # against concurrent executions of this one-time bootstrap.
    existing_user_id = db.scalars(
        select(User.id).with_hint(User, "TABLOCKX, HOLDLOCK", dialect_name="mssql")
    ).first()
    if existing_user_id is not None:
        raise RuntimeError("El bootstrap inicial solo se permite cuando no existe ningún usuario")

    branch_type = upsert_named_catalog(db, BranchType, branch_type_code, branch_type_name)
    branch = db.scalar(select(Branch).where(Branch.code == branch_code))
    if branch is None:
        branch = Branch(code=branch_code, name=branch_name, branch_type_id=branch_type.id, is_active=True)
        db.add(branch)
        db.flush()
    elif not branch.is_active or branch.name != branch_name or branch.branch_type_id != branch_type.id:
        raise ValueError(f"La sucursal {branch_code} ya existe con datos diferentes o está inactiva")

    for code, name in visitor_types:
        upsert_named_catalog(db, VisitorType, code, name)
    for code, name in visit_reasons:
        upsert_named_catalog(db, VisitReason, code, name)

    roles: dict[str, Role] = {}
    for code, name, description in ROLES:
        role = db.scalar(select(Role).where(Role.code == code))
        if role is None:
            role = Role(code=code, name=name, description=description, is_active=True)
            db.add(role)
            db.flush()
        elif not role.is_active:
            raise ValueError(f"El rol {code} existe, pero está inactivo")
        roles[code] = role

    permissions: dict[str, Permission] = {}
    for code, name, resource, action, scope in PERMISSIONS:
        permission = db.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(
                code=code,
                name=name,
                description=name,
                resource=resource,
                action=action,
                scope=scope,
                is_active=True,
            )
            db.add(permission)
            db.flush()
        elif not permission.is_active or permission.scope != scope:
            raise ValueError(f"El permiso {code} existe inactivo o con un ámbito distinto")
        permissions[code] = permission

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

    admin_role = roles["SUPER_ADMIN"]
    db.add(UserRole(user_id=admin.id, role_id=admin_role.id, assigned_by_user_id=admin.id, is_active=True))
    db.add(
        UserBranchAssignment(
            user_id=admin.id,
            branch_id=branch.id,
            valid_from=datetime.now(timezone.utc).replace(tzinfo=None),
            valid_until=None,
            assigned_by_user_id=admin.id,
            reason="Asignación inicial del primer administrador",
            status="ACTIVE",
        )
    )

    grant_count = 0
    for role_code, permission_codes in ROLE_PERMISSION_CODES.items():
        for permission_code in sorted(permission_codes):
            existing = db.scalar(
                select(RolePermission.id).where(
                    RolePermission.role_id == roles[role_code].id,
                    RolePermission.permission_id == permissions[permission_code].id,
                    RolePermission.is_active.is_(True),
                )
            )
            if existing is None:
                db.add(
                    RolePermission(
                        role_id=roles[role_code].id,
                        permission_id=permissions[permission_code].id,
                        assigned_by_user_id=admin.id,
                        is_active=True,
                    )
                )
                grant_count += 1

    db.flush()
    return admin.id, branch.id


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicialización manual y única del primer administrador autorizado")
    parser.add_argument("--confirm-initialization", action="store_true", help="Confirma que se inicializará la base vacía")
    parser.add_argument("--username", required=True)
    parser.add_argument("--first-name", required=True)
    parser.add_argument("--last-name", required=True)
    parser.add_argument("--email")
    parser.add_argument("--branch-type", required=True, type=parse_catalog_entry, metavar="CODIGO=NOMBRE")
    parser.add_argument("--branch", required=True, type=parse_catalog_entry, metavar="CODIGO=NOMBRE")
    parser.add_argument("--visitor-type", required=True, action="append", type=parse_catalog_entry, metavar="CODIGO=NOMBRE")
    parser.add_argument("--visit-reason", required=True, action="append", type=parse_catalog_entry, metavar="CODIGO=NOMBRE")
    args = parser.parse_args()
    if not args.confirm_initialization:
        parser.error("Debe agregar --confirm-initialization para confirmar la operación única")

    password = getpass.getpass("Contraseña inicial (mínimo 12 caracteres): ")
    if password != getpass.getpass("Repita la contraseña: "):
        parser.error("Las contraseñas no coinciden")

    try:
        with SessionLocal.begin() as db:
            admin_id, branch_id = initialize_first_admin(
                db,
                username=args.username,
                first_name=args.first_name,
                last_name=args.last_name,
                email=args.email,
                password=password,
                branch_type_code=args.branch_type[0],
                branch_type_name=args.branch_type[1],
                branch_code=args.branch[0],
                branch_name=args.branch[1],
                visitor_types=args.visitor_type,
                visit_reasons=args.visit_reason,
            )
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    print(f"Inicialización completada. Usuario administrador ID={admin_id}; sucursal inicial ID={branch_id}.")
    print("Se registraron roles, permisos, asignaciones y catálogos iniciales en una sola transacción.")


if __name__ == "__main__":
    main()
