"""Idempotently seed the approved role catalog. Run manually only."""
from __future__ import annotations

from sqlalchemy import select

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.persistence.models import Role
from scripts.permission_catalog import ROLES


def main() -> None:
    with SessionLocal.begin() as db:
        for code, name, description in ROLES:
            role = db.scalar(select(Role).where(Role.code == code))
            if role is None:
                db.add(Role(code=code, name=name, description=description))
    print(f"Roles procesados: {len(ROLES)}")


if __name__ == "__main__":
    main()
