"""Explicit, idempotent development bootstrap for a local test user.

Run manually with:
    python -m scripts.bootstrap_user

This module is never imported by the FastAPI startup path.
"""
from __future__ import annotations

import argparse
import getpass
import os

from sqlalchemy import select

from app.core.security import hash_password
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.persistence.models import User


def bootstrap_user(username: str, password: str, first_name: str, last_name: str, email: str | None) -> str:
    if not password:
        raise ValueError("La contraseña no puede estar vacía")

    with SessionLocal.begin() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user is not None:
            return f"Usuario existente: {user.username} (sin cambios)"

        db.add(
            User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password_hash=hash_password(password),
                is_active=True,
            )
        )
        return f"Usuario creado: {username}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea un usuario local de desarrollo de forma idempotente")
    parser.add_argument("--username", default=os.getenv("BOOTSTRAP_USERNAME", "admin"))
    parser.add_argument("--first-name", default=os.getenv("BOOTSTRAP_FIRST_NAME", "Administrador"))
    parser.add_argument("--last-name", default=os.getenv("BOOTSTRAP_LAST_NAME", "Local"))
    parser.add_argument("--email", default=os.getenv("BOOTSTRAP_EMAIL"))
    args = parser.parse_args()
    password = getpass.getpass("Contraseña del usuario de desarrollo: ")
    print(bootstrap_user(args.username, password, args.first_name, args.last_name, args.email))


if __name__ == "__main__":
    main()
