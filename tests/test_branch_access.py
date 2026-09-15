from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.dependencies.branch_access import get_current_branch, require_branch_permission
from app.application.services.branch_access import BranchAccessService
from app.application.services.visit_access import VisitAccessService
from app.infrastructure.persistence.models import Permission
from tests.test_authorization import FakeSession, assignment


class AssignmentSession:
    def __init__(self, assignments: list[object]) -> None:
        self.assignments = assignments
        self.statement: object | None = None

    def scalars(self, statement: object):
        self.statement = statement
        return SimpleNamespace(all=lambda: self.assignments)

    def scalar(self, statement: object):
        return True


def request_with_path(branch_id: object | None = None) -> SimpleNamespace:
    return SimpleNamespace(path_params={} if branch_id is None else {"branch_id": branch_id})


def test_current_context_resolves_one_active_assignment() -> None:
    session = AssignmentSession([assignment(1)])

    context = BranchAccessService(session).get_current_context(7, datetime(2026, 9, 14))

    assert context is not None
    assert context.user_id == 7
    assert context.branch_id == 1


def test_multiple_current_assignments_deny_instead_of_picking_one() -> None:
    session = AssignmentSession([assignment(1), assignment(2)])

    assert BranchAccessService(session).get_current_context(7, datetime(2026, 9, 14)) is None


def test_inactive_branch_denies_context() -> None:
    session = AssignmentSession([assignment(1, active_branch=False)])

    assert BranchAccessService(session).get_current_context(7, datetime(2026, 9, 14)) is None


@pytest.mark.parametrize("assignments", [[], [assignment(1)]])
def test_missing_or_non_matching_context_denies_client_branch_override(assignments: list[object]) -> None:
    user = SimpleNamespace(id=7)
    request = request_with_path(2)
    db = AssignmentSession(assignments)

    with pytest.raises(HTTPException) as error:
        get_current_branch(user, db, request, 2)

    assert error.value.status_code == 403


def test_matching_query_branch_is_accepted() -> None:
    user = SimpleNamespace(id=7)
    request = request_with_path()
    db = AssignmentSession([assignment(1)])

    context = get_current_branch(user, db, request, 1)

    assert context.branch_id == 1


def test_missing_query_branch_uses_authorized_context() -> None:
    user = SimpleNamespace(id=7)
    request = request_with_path()
    db = AssignmentSession([assignment(1)])

    context = get_current_branch(user, db, request, None)

    assert context.branch_id == 1


def test_expired_and_future_assignments_are_excluded_by_sql_predicate() -> None:
    session = AssignmentSession([])
    service = BranchAccessService(session)

    assert service.get_current_context(7, datetime(2026, 9, 14)) is None
    statement = str(session.statement)
    assert "valid_from" in statement
    assert "valid_until" in statement
    assert "status" in statement


def test_branch_permission_dependency_uses_resolved_branch_not_client_value() -> None:
    dependency = require_branch_permission("VIEW_VISITS")
    user = SimpleNamespace(id=7)
    request = request_with_path()
    permission = Permission(id=10, code="VIEW_VISITS", scope="BRANCH", is_active=True)
    db = FakeSession([True, permission, True, 100], [], [assignment(1)])

    context = BranchAccessService(db).get_current_context(7)
    assert context is not None
    assert dependency(user, db, context) is user


def test_visit_query_filters_by_authorized_branch_in_sql() -> None:
    context = SimpleNamespace(user_id=7, branch_id=1, assignment_id=99)
    statement = VisitAccessService.list_query(context)

    sql = str(statement)
    assert "visits.branch_id" in sql
    assert "WHERE" in sql
    assert "branch_id" in {column.name for column in statement.selected_columns}
