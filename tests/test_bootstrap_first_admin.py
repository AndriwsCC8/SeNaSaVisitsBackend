from __future__ import annotations

import argparse
import inspect
import logging

import pytest
from sqlalchemy import func, select

from app.application.services.authorization import PermissionService
from app.core.security import verify_password
from app.infrastructure.persistence.models import (
    Branch,
    BranchType,
    Permission,
    Role,
    RolePermission,
    User,
    UserBranchAssignment,
    UserRole,
)
from scripts import bootstrap_first_admin as bootstrap
from scripts.bootstrap_first_admin import initialize_first_admin, parse_catalog_entry, validate_initial_password
from scripts.permission_catalog import PERMISSIONS, ROLE_PERMISSION_CODES, ROLES
from scripts.seed_authorization import seed_authorization_catalog
from tests.sqlite_support import make_session_factory

PASSWORD = "Unit-Test-Pass-2026"


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def prepared_factory(*, authorization: bool = True, branch: bool = True):
    factory = make_session_factory()
    with factory.begin() as db:
        if authorization:
            seed_authorization_catalog(db)
        if branch:
            branch_type = BranchType(code="T_TEST", name="Tipo de prueba")
            db.add(branch_type)
            db.flush()
            db.add(Branch(code="B_TEST", name="Sucursal de prueba", branch_type_id=branch_type.id))
    return factory


def run_bootstrap(factory, **overrides):
    values = dict(username="admin_test", first_name="Admin", last_name="Prueba", email=None, password=PASSWORD, branch_code="B_TEST")
    values.update(overrides)
    with factory.begin() as db:
        return initialize_first_admin(db, **values)


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


# ---- Catálogo de autorización sin identidad ----

def test_seed_authorization_creates_catalog_without_users_and_is_idempotent() -> None:
    factory = make_session_factory()
    with factory.begin() as db:
        first = seed_authorization_catalog(db)
    with factory.begin() as db:
        second = seed_authorization_catalog(db)

    assert (first.roles_created, first.permissions_created) == (len(ROLES), len(PERMISSIONS))
    assert (second.roles_created, second.permissions_created) == (0, 0)
    with factory() as db:
        assert count(db, Role) == len(ROLES)
        assert count(db, Permission) == len(PERMISSIONS)
        assert count(db, User) == 0
        assert count(db, RolePermission) == 0


def test_seed_authorization_aborts_on_scope_conflict_without_writing() -> None:
    factory = make_session_factory()
    with factory.begin() as db:
        db.add(Permission(code="MANAGE_USERS", name="x", resource="users", action="manage", scope="BRANCH"))

    with pytest.raises(ValueError, match="MANAGE_USERS"):
        with factory.begin() as db:
            seed_authorization_catalog(db)

    with factory() as db:
        assert count(db, Role) == 0
        assert count(db, Permission) == 1


def test_seed_authorization_aborts_when_role_is_inactive() -> None:
    factory = make_session_factory()
    with factory.begin() as db:
        db.add(Role(code="SUPER_ADMIN", name="x", is_active=False))

    with pytest.raises(ValueError, match="SUPER_ADMIN"):
        with factory.begin() as db:
            seed_authorization_catalog(db)


# ---- Primer administrador ----

def test_first_admin_gets_every_catalog_permission_effectively(caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]) -> None:
    factory = prepared_factory()
    with caplog.at_level(logging.DEBUG):
        result = run_bootstrap(factory)

    assert result.created is True
    with factory() as db:
        admin = db.get(User, result.user_id)
        assert admin.password_hash != PASSWORD and admin.password_hash.startswith("$argon2")
        assert verify_password(PASSWORD, admin.password_hash)
        service = PermissionService(db)
        for code, _n, _r, _a, scope in PERMISSIONS:
            assert service.has_permission(admin.id, code, result.branch_id if scope == "BRANCH" else None), code
        assert count(db, UserBranchAssignment) == 1
        assert count(db, UserRole) == 1
        expected = sum(len(codes) for codes in ROLE_PERMISSION_CODES.values())
        assert count(db, RolePermission) == expected
    assert PASSWORD not in caplog.text
    captured = capsys.readouterr()
    assert PASSWORD not in captured.out + captured.err


def test_global_permissions_are_denied_for_branch_scope_and_vice_versa() -> None:
    factory = prepared_factory()
    result = run_bootstrap(factory)
    with factory() as db:
        service = PermissionService(db)
        assert not service.has_permission(result.user_id, "MANAGE_USERS", result.branch_id)
        assert not service.has_permission(result.user_id, "VIEW_VISITS")


def test_bootstrap_is_idempotent_when_already_configured() -> None:
    factory = prepared_factory()
    first = run_bootstrap(factory)
    with factory() as db:
        before = [count(db, m) for m in (User, UserRole, UserBranchAssignment, RolePermission)]

    second = run_bootstrap(factory)

    assert second.created is False and second.user_id == first.user_id
    with factory() as db:
        assert [count(db, m) for m in (User, UserRole, UserBranchAssignment, RolePermission)] == before


def test_bootstrap_requires_seeded_authorization_catalog() -> None:
    factory = prepared_factory(authorization=False)

    with pytest.raises(RuntimeError, match="seed_authorization"):
        run_bootstrap(factory)
    with factory() as db:
        assert count(db, User) == 0


@pytest.mark.parametrize("deactivate", [False, True])
def test_bootstrap_requires_existing_active_branch(deactivate: bool) -> None:
    factory = prepared_factory(branch=deactivate)
    if deactivate:
        with factory.begin() as db:
            db.scalar(select(Branch)).is_active = False

    with pytest.raises(RuntimeError, match="sucursal"):
        run_bootstrap(factory)


def test_bootstrap_refuses_when_other_users_exist() -> None:
    factory = prepared_factory()
    run_bootstrap(factory)

    with pytest.raises(RuntimeError, match="no promueve"):
        run_bootstrap(factory, username="otro_usuario")
    with factory() as db:
        assert count(db, User) == 1


def test_bootstrap_aborts_on_partial_state_without_changing_privileges() -> None:
    factory = prepared_factory()
    result = run_bootstrap(factory)
    with factory.begin() as db:
        for item in db.scalars(select(UserRole)).all():
            item.is_active = False

    with pytest.raises(RuntimeError, match="parcial o ambigua"):
        run_bootstrap(factory)
    with factory() as db:
        assert count(db, UserRole) == 1
        assert db.scalar(select(UserRole.is_active)) is False
        assert db.get(User, result.user_id).is_active is True


def test_bootstrap_rolls_back_everything_if_a_step_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = prepared_factory()

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(bootstrap, "_verify_effective_permissions", fail)
    with pytest.raises(RuntimeError, match="fallo simulado"):
        run_bootstrap(factory)

    with factory() as db:
        assert [count(db, m) for m in (User, UserRole, UserBranchAssignment, RolePermission)] == [0, 0, 0, 0]


def test_bootstrap_rejects_weak_password_before_writing() -> None:
    factory = prepared_factory()

    with pytest.raises(ValueError):
        run_bootstrap(factory, password="weak")
    with factory() as db:
        assert count(db, User) == 0


def test_bootstrap_has_no_password_argument_or_default_credentials() -> None:
    source = inspect.getsource(bootstrap)

    assert "--password" not in source
    assert "getpass.getpass" in source
