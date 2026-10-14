from __future__ import annotations

import argparse

import pytest

from scripts.bootstrap_first_admin import (
    initialize_first_admin,
    parse_catalog_entry,
    validate_initial_password,
)


class ExistingUserResult:
    def first(self) -> int:
        return 42


class ExistingUserSession:
    def scalars(self, statement: object) -> ExistingUserResult:
        return ExistingUserResult()


def test_catalog_entry_requires_safe_code_and_nonempty_name() -> None:
    assert parse_catalog_entry("meeting=Reunión") == ("MEETING", "Reunión")

    with pytest.raises(argparse.ArgumentTypeError):
        parse_catalog_entry("=Sin código")
    with pytest.raises(argparse.ArgumentTypeError):
        parse_catalog_entry("MOTIVO=")
    with pytest.raises(argparse.ArgumentTypeError):
        parse_catalog_entry("MOTIVO/1=No permitido")


def test_initial_password_requires_length_and_character_classes() -> None:
    validate_initial_password("ClaveInicial2026")

    with pytest.raises(ValueError):
        validate_initial_password("weakpass")


def test_first_admin_bootstrap_refuses_database_with_any_user() -> None:
    with pytest.raises(RuntimeError, match="solo se permite cuando no existe ningún usuario"):
        initialize_first_admin(
            ExistingUserSession(),  # type: ignore[arg-type]
            username="admin",
            first_name="Admin",
            last_name="Local",
            email=None,
            password="StrongPassword2026",
            branch_type_code="OFFICE",
            branch_type_name="Oficina",
            branch_code="HQ",
            branch_name="Oficina central",
            visitor_types=[("GUEST", "Visitante")],
            visit_reasons=[("MEETING", "Reunión")],
        )