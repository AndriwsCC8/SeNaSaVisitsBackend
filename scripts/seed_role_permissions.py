"""Idempotently assign approved permissions to roles. Run manually only."""
from __future__ import annotations

import argparse

from sqlalchemy import select

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.persistence.models import Permission, Role, RolePermission, User
from scripts.permission_catalog import ROLE_PERMISSION_CODES


def main() -> None:
    parser = argparse.ArgumentParser(description="Asigna permisos aprobados a roles existentes")
    parser.add_argument("--assigned-by-user-id", type=int, required=True)
    args = parser.parse_args()

    with SessionLocal.begin() as db:
        assigned_by = db.scalar(select(User).where(User.id == args.assigned_by_user_id, User.is_active.is_(True)))
        if assigned_by is None:
            raise SystemExit("El usuario asignador no existe o está inactivo")

        roles = {role.code: role for role in db.scalars(select(Role)).all()}
        permissions = {permission.code: permission for permission in db.scalars(select(Permission)).all()}
        missing_roles = sorted(set(ROLE_PERMISSION_CODES) - roles.keys())
        missing_permissions = sorted(
            {code for codes in ROLE_PERMISSION_CODES.values() for code in codes} - permissions.keys()
        )
        if missing_roles or missing_permissions:
            raise SystemExit(
                "Ejecuta primero seed_roles y seed_permissions. "
                f"roles faltantes={missing_roles}, permisos faltantes={missing_permissions}"
            )

        created = 0
        for role_code, permission_codes in ROLE_PERMISSION_CODES.items():
            for permission_code in sorted(permission_codes):
                role_permission = db.scalar(
                    select(RolePermission).where(
                        RolePermission.role_id == roles[role_code].id,
                        RolePermission.permission_id == permissions[permission_code].id,
                        RolePermission.is_active.is_(True),
                    )
                )
                if role_permission is None:
                    db.add(
                        RolePermission(
                            role_id=roles[role_code].id,
                            permission_id=permissions[permission_code].id,
                            assigned_by_user_id=assigned_by.id,
                            is_active=True,
                        )
                    )
                    created += 1
    print(f"Asignaciones RolePermission creadas: {created}")


if __name__ == "__main__":
    main()
