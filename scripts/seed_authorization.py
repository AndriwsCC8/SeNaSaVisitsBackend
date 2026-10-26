"""Prepare the approved role and permission catalogs without any administrative identity.

Run manually: python -m scripts.seed_authorization
Role-permission grants are NOT created here: the schema requires an existing user in
RolePermission.assigned_by_user_id, so they are created by scripts.bootstrap_first_admin.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models import Permission, Role
from scripts.permission_catalog import PERMISSIONS, ROLES

logger = logging.getLogger("senasa_visits.bootstrap")


@dataclass(frozen=True)
class SeedResult:
    roles_created: int
    permissions_created: int


def seed_authorization_catalog(db: Session) -> SeedResult:
    """Create missing roles/permissions; abort on any existing entry that differs from the catalog."""
    conflicts: list[str] = []
    roles_to_add: list[Role] = []
    permissions_to_add: list[Permission] = []

    for code, name, description in ROLES:
        role = db.scalar(select(Role).where(Role.code == code))
        if role is None:
            roles_to_add.append(Role(code=code, name=name, description=description, is_active=True))
        elif not role.is_active:
            conflicts.append(f"El rol {code} existe pero está inactivo")

    for code, name, resource, action, scope in PERMISSIONS:
        permission = db.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permissions_to_add.append(
                Permission(code=code, name=name, description=name, resource=resource, action=action, scope=scope, is_active=True)
            )
        elif not permission.is_active or permission.scope != scope:
            conflicts.append(f"El permiso {code} existe inactivo o con un ámbito distinto al aprobado ({scope})")

    if conflicts:
        raise ValueError("; ".join(conflicts))

    db.add_all(roles_to_add)
    db.add_all(permissions_to_add)
    db.flush()
    logger.info("Catálogo de autorización: roles creados=%s, permisos creados=%s", len(roles_to_add), len(permissions_to_add))
    return SeedResult(roles_created=len(roles_to_add), permissions_created=len(permissions_to_add))


def main() -> None:
    from app.infrastructure.database.session import SessionLocal

    try:
        with SessionLocal.begin() as db:
            result = seed_authorization_catalog(db)
    except ValueError as exc:
        raise SystemExit(f"Abortado sin cambios: {exc}") from None
    print(f"Roles creados: {result.roles_created}. Permisos creados: {result.permissions_created}.")


if __name__ == "__main__":
    main()
