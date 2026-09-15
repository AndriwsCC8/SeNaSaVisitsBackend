from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.dependencies.permissions import require_permission
from app.application.services.authorization import PermissionEvaluation, PermissionService
from app.infrastructure.persistence.models import Permission


class ScalarResult:
    def __init__(self, values: list[str]) -> None:
        self.values = values

    def all(self) -> list[str]:
        return self.values


class FakeSession:
    def __init__(self, scalar_values: list[object], effects: list[str], assignments: list[object] | None = None) -> None:
        self.scalar_values = iter(scalar_values)
        self.effects = effects
        self.assignments = assignments or []
        self.statements: list[object] = []

    def scalar(self, statement: object) -> object:
        self.statements.append(statement)
        return next(self.scalar_values)

    def scalars(self, statement: object) -> ScalarResult:
        self.statements.append(statement)
        if "user_branch_assignments" in str(statement):
            return ScalarResult(self.assignments)
        return ScalarResult(self.effects)


def assignment(branch_id: int = 3, *, active_branch: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=99,
        branch_id=branch_id,
        branch=SimpleNamespace(is_active=active_branch),
    )


def evaluation(
    *,
    user_active: bool = True,
    permission_active: bool = True,
    branch_valid: bool = True,
    assignment_valid: bool = True,
    effects: tuple[str, ...] = (),
    role_granted: bool = False,
) -> PermissionEvaluation:
    return PermissionEvaluation(
        user_active=user_active,
        permission_active=permission_active,
        branch_valid=branch_valid,
        assignment_valid=assignment_valid,
        explicit_effects=effects,
        role_granted=role_granted,
    )


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, False),
        ({"role_granted": True}, True),
        ({"effects": ("ALLOW",), "assignment_valid": True}, True),
        ({"effects": ("DENY",), "role_granted": True}, False),
        ({"effects": ("DENY", "ALLOW"), "role_granted": True}, False),
        ({"effects": ("ALLOW",), "role_granted": True, "assignment_valid": True}, True),
        ({"effects": (), "role_granted": True, "permission_active": False}, False),
        ({"effects": (), "role_granted": True, "user_active": False}, False),
        ({"effects": (), "role_granted": True, "branch_valid": False}, False),
        ({"effects": ("ALLOW",), "assignment_valid": False}, False),
    ],
)
def test_permission_precedence_and_state_rules(kwargs: dict[str, object], expected: bool) -> None:
    assert evaluation(**kwargs).allowed is expected


def test_branch_permission_requires_branch_and_assignment() -> None:
    assert not evaluation(effects=("ALLOW",), assignment_valid=False).allowed
    assert evaluation(effects=("ALLOW",), assignment_valid=True).allowed


def test_global_permission_does_not_need_physical_assignment() -> None:
    assert evaluation(effects=("ALLOW",), assignment_valid=True).allowed


def test_invalid_scope_context_is_denied() -> None:
    assert not evaluation(branch_valid=False, role_granted=True).allowed


def test_expired_and_future_rules_are_ignored_by_query_contract() -> None:
    now = datetime(2026, 9, 14)
    expired = now - timedelta(seconds=1)
    future = now + timedelta(seconds=1)
    assert expired < now < future
    assert not evaluation(effects=()).allowed


def test_service_evaluates_branch_role_permission() -> None:
    permission = Permission(id=10, code="VIEW_VISITS", scope="BRANCH", is_active=True)
    db = FakeSession([True, permission, True, 100], [], [assignment()])

    assert PermissionService(db).has_permission(7, "VIEW_VISITS", branch_id=3, at=datetime(2026, 9, 14))


def test_service_evaluates_explicit_deny_over_role() -> None:
    permission = Permission(id=10, code="VIEW_VISITS", scope="BRANCH", is_active=True)
    db = FakeSession([True, permission, True, 100], ["DENY"], [assignment()])

    assert not PermissionService(db).has_permission(7, "VIEW_VISITS", branch_id=3, at=datetime(2026, 9, 14))


def test_service_rejects_branch_permission_without_branch_id() -> None:
    permission = Permission(id=10, code="VIEW_VISITS", scope="BRANCH", is_active=True)
    db = FakeSession([True, permission], [])

    assert not PermissionService(db).has_permission(7, "VIEW_VISITS")


def test_service_rejects_global_permission_with_branch_id() -> None:
    permission = Permission(id=10, code="VIEW_GLOBAL_REPORTS", scope="GLOBAL", is_active=True)
    db = FakeSession([True, permission], [])

    assert not PermissionService(db).has_permission(7, "VIEW_GLOBAL_REPORTS", branch_id=3)


def test_service_rejects_inactive_user_permission_or_branch() -> None:
    permission = Permission(id=10, code="VIEW_VISITS", scope="BRANCH", is_active=True)
    assert not PermissionService(FakeSession([False, permission], [])).has_permission(7, "VIEW_VISITS", 3)
    assert not PermissionService(FakeSession([True, permission, False], [], [])).has_permission(7, "VIEW_VISITS", 3)


def test_service_uses_global_role_without_branch_assignment() -> None:
    permission = Permission(id=10, code="MANAGE_BRANCHES", scope="GLOBAL", is_active=True)
    db = FakeSession([True, permission, 100], [])

    assert PermissionService(db).has_permission(7, "MANAGE_BRANCHES")


def test_require_permission_returns_403_for_authenticated_user_without_access() -> None:
    dependency = require_permission("VIEW_VISITS")
    request = SimpleNamespace(path_params={})
    user = SimpleNamespace(id=7)
    permission = Permission(id=10, code="VIEW_VISITS", scope="BRANCH", is_active=True)
    db = FakeSession([True, permission, 100], [], [])

    with pytest.raises(HTTPException) as error:
        dependency(request, user, db, 3)

    assert error.value.status_code == 403
