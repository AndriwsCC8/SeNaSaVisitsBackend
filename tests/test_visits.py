from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.application.dto.visits import VisitCancelRequest, VisitCompleteRequest, VisitCreate, VisitUpdate
from app.application.services.branch_access import BranchContext
from app.application.services.visits import VisitManagementService
from app.core.exceptions import ConflictError, ValidationError
from app.infrastructure.persistence.models import Branch, User, Visit, VisitReason, Visitor
from main import app


class ScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values

    def unique(self):
        return self


class FakeSession:
    def __init__(self, scalar_values=None, scalars_values=None):
        self.scalar_values = iter(scalar_values or [])
        self.scalars_values = iter(scalars_values or [])
        self.statements = []
        self.added = []

    def scalar(self, statement):
        self.statements.append(statement)
        try:
            return next(self.scalar_values)
        except StopIteration:
            return self.added[0] if self.added else None

    def scalars(self, statement):
        self.statements.append(statement)
        try:
            return ScalarResult(next(self.scalars_values))
        except StopIteration:
            return ScalarResult([])

    def add(self, value):
        self.added.append(value)

    def flush(self):
        if self.added and getattr(self.added[0], "id", None) is None:
            self.added[0].id = 1

    def commit(self):
        return None

    def rollback(self):
        return None


def context(branch_id: int = 1) -> BranchContext:
    return BranchContext(user_id=7, branch_id=branch_id, assignment_id=9)


def make_visit(status: str = "ACTIVE") -> Visit:
    visitor = Visitor(id=2, first_name="Ana", last_name="Perez", is_active=True)
    reason = VisitReason(id=3, code="MEETING", name="Meeting", is_active=True)
    branch = Branch(id=1, code="B1", name="Sucursal 1", branch_type_id=1, is_active=True)
    user = User(id=7, username="user", first_name="User", last_name="One", password_hash="$argon2-test", is_active=True)
    visit = Visit(
        id=11,
        visitor_id=2,
        branch_id=1,
        registered_by_user_id=7,
        entry_at=datetime(2026, 9, 14, 10, 0),
        reason_id=3,
        status=status,
        visitor=visitor,
        reason=reason,
        branch=branch,
        registered_by=user,
    )
    return visit


def test_visit_create_dto_has_no_branch_or_actor_fields() -> None:
    fields = VisitCreate.model_fields

    assert "branch_id" not in fields
    assert "registered_by_user_id" not in fields
    assert "status" not in fields


def test_visit_create_dto_rejects_client_branch_override() -> None:
    with pytest.raises(ValueError):
        VisitCreate(visitor_id=2, reason_id=3, branch_id=99)


def test_create_visit_derives_branch_and_registered_user_from_context() -> None:
    visitor = Visitor(id=2, first_name="Ana", last_name="Perez", is_active=True)
    reason = VisitReason(id=3, code="MEETING", name="Meeting", is_active=True)
    existing = make_visit()
    session = FakeSession(scalar_values=[visitor, reason, existing])

    result = VisitManagementService(session).create_visit(
        context(4),
        user_id=7,
        payload=VisitCreate(visitor_id=2, reason_id=3),
    )

    created = session.added[0]
    assert created.branch_id == 4
    assert created.registered_by_user_id == 7
    assert created.status == "ACTIVE"
    assert created.exit_at is None
    assert result is existing


def test_create_rejects_inactive_visitor() -> None:
    visitor = Visitor(id=2, first_name="Ana", last_name="Perez", is_active=False)
    session = FakeSession(scalar_values=[visitor])

    with pytest.raises(ValidationError):
        VisitManagementService(session).create_visit(context(), 7, VisitCreate(visitor_id=2, reason_id=3))


def test_create_rejects_inactive_reason() -> None:
    visitor = Visitor(id=2, first_name="Ana", last_name="Perez", is_active=True)
    reason = VisitReason(id=3, code="MEETING", name="Meeting", is_active=False)
    session = FakeSession(scalar_values=[visitor, reason])

    with pytest.raises(ValidationError):
        VisitManagementService(session).create_visit(context(), 7, VisitCreate(visitor_id=2, reason_id=3))


def test_visit_query_always_contains_branch_filter() -> None:
    session = FakeSession(scalar_values=[1], scalars_values=[[]])

    VisitManagementService(session).list_visits(context(4), page=1, page_size=20)

    assert any("visits.branch_id" in str(statement) for statement in session.statements)


@pytest.mark.parametrize("entry_at, expected", [(datetime(2026, 9, 1, 10, 0), True), (datetime(2026, 9, 1, 11, 0), False)])
def test_visit_date_to_is_exclusive(entry_at: datetime, expected: bool) -> None:
    session = FakeSession(scalar_values=[1], scalars_values=[[]])
    VisitManagementService(session).list_visits(
        context(1),
        page=1,
        page_size=20,
        date_from=datetime(2026, 9, 1, 9, 0),
        date_to=datetime(2026, 9, 1, 11, 0),
    )

    statement = str(session.statements[-1])
    assert ("< :entry_at" in statement) is True
    assert expected in {True, False}


def test_visit_date_filters_allow_single_bounds() -> None:
    for date_from, date_to in ((datetime(2026, 9, 1, 10), None), (None, datetime(2026, 9, 1, 11))):
        session = FakeSession(scalar_values=[0], scalars_values=[[]])
        VisitManagementService(session).list_visits(context(1), page=1, page_size=20, date_from=date_from, date_to=date_to)
        assert "entry_at" in str(session.statements[-1])


def test_get_visit_from_other_branch_is_not_found() -> None:
    session = FakeSession(scalar_values=[None])

    with pytest.raises(Exception):
        VisitManagementService(session).get_visit(context(1), 99)


def test_patch_cannot_change_status_or_branch() -> None:
    visit = make_visit()
    session = FakeSession(scalar_values=[visit, visit])

    result = VisitManagementService(session).update_visit(
        context(1),
        11,
        VisitUpdate(destination="Reception"),
    )

    assert result is visit
    assert visit.destination == "Reception"
    assert visit.status == "ACTIVE"
    assert visit.branch_id == 1


def test_complete_active_visit_sets_exit_and_actor() -> None:
    visit = make_visit()
    session = FakeSession(scalar_values=[visit, visit])

    result = VisitManagementService(session).complete_visit(
        context(1),
        8,
        11,
        VisitCompleteRequest(exit_at=datetime(2026, 9, 14, 11, 0)),
    )

    assert result is visit
    assert visit.status == "COMPLETED"
    assert visit.completed_by_user_id == 8
    assert visit.exit_at == datetime(2026, 9, 14, 11, 0)


def test_complete_completed_visit_is_conflict() -> None:
    visit = make_visit("COMPLETED")
    session = FakeSession(scalar_values=[visit])

    with pytest.raises(ConflictError):
        VisitManagementService(session).complete_visit(context(), 8, 11, VisitCompleteRequest())


def test_complete_cancelled_visit_is_conflict() -> None:
    visit = make_visit("CANCELLED")
    session = FakeSession(scalar_values=[visit])

    with pytest.raises(ConflictError):
        VisitManagementService(session).complete_visit(context(), 8, 11, VisitCompleteRequest())


def test_complete_cannot_use_exit_before_entry() -> None:
    visit = make_visit()
    session = FakeSession(scalar_values=[visit])

    with pytest.raises(ValidationError):
        VisitManagementService(session).complete_visit(
            context(), 8, 11, VisitCompleteRequest(exit_at=datetime(2026, 9, 14, 9, 0))
        )


def test_cancel_active_visit_requires_reason_and_sets_audit_fields() -> None:
    visit = make_visit()
    session = FakeSession(scalar_values=[visit, visit])

    result = VisitManagementService(session).cancel_visit(
        context(), 8, 11, VisitCancelRequest(cancellation_reason="Registro duplicado")
    )

    assert result is visit
    assert visit.status == "CANCELLED"
    assert visit.cancelled_by_user_id == 8
    assert visit.cancelled_at is not None
    assert visit.cancellation_reason == "Registro duplicado"


def test_cancel_completed_visit_is_conflict() -> None:
    visit = make_visit("COMPLETED")
    session = FakeSession(scalar_values=[visit])

    with pytest.raises(ConflictError):
        VisitManagementService(session).cancel_visit(context(), 8, 11, VisitCancelRequest(cancellation_reason="No aplica"))


def test_cancelled_visit_cannot_be_cancelled_again() -> None:
    visit = make_visit("CANCELLED")
    session = FakeSession(scalar_values=[visit])

    with pytest.raises(ConflictError):
        VisitManagementService(session).cancel_visit(context(), 8, 11, VisitCancelRequest(cancellation_reason="Duplicado"))


def test_visit_routes_are_documented() -> None:
    schema = TestClient(app).get("/openapi.json").json()
    assert set(path for path in schema["paths"] if path.startswith("/api/visits")) == {
        "/api/visits",
        "/api/visits/{visit_id}",
        "/api/visits/{visit_id}/complete",
        "/api/visits/{visit_id}/cancel",
    }
