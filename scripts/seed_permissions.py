"""Idempotently seed the approved permission catalog. Run manually only."""
from __future__ import annotations

from sqlalchemy import select

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.persistence.models import Permission
from scripts.permission_catalog import PERMISSIONS


def main() -> None:
    with SessionLocal.begin() as db:
        for code, name, resource, action, scope in PERMISSIONS:
            permission = db.scalar(select(Permission).where(Permission.code == code))
            if permission is None:
                db.add(Permission(code=code, name=name, description=name, resource=resource, action=action, scope=scope))
    print(f"Permisos procesados: {len(PERMISSIONS)}")


if __name__ == "__main__":
    main()
