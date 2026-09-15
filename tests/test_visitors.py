from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.application.dto.visitors import VisitorCreate, VisitorUpdate
from app.application.services.visitors import VisitorManagementService
from app.application.validators.visitors import mask_identification, normalize_identification, normalize_required_text, validate_email
from app.core.exceptions import ConflictError, ValidationError
from app.infrastructure.persistence.models import Visitor, VisitorType
from main import app


class ScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values

    def unique(self):
        return self


class FakeSession:
    def __init__(self, scalar_values=None, visitors=None, visitor_type=None):
        self.scalar_values = iter(scalar_values or [])
        self.visitors = visitors or []
        self.visitor_type = visitor_type
        self.statements = []
        self.added = []

    def scalar(self, statement):
        self.statements.append(statement)
        try:
            return next(self.scalar_values)
        except StopIteration:
            if self.added:
                return self.added[0]
            return self.visitor_type

    def scalars(self, statement):
        self.statements.append(statement)
        return ScalarResult(self.visitors)

    def add(self, value):
        self.added.append(value)

    def flush(self):
        if self.added and getattr(self.added[0], "id", None) is None:
            self.added[0].id = 1

    def commit(self):
        return None

    def rollback(self):
        return None


def test_identification_normalization_is_conservative_and_stable() -> None:
    assert normalize_identification("  402-123 4567  ") == "402-1234567"
    assert normalize_identification(None) is None
    assert normalize_identification("   ") is None


def test_identification_mask_never_returns_complete_value() -> None:
    value = "402-1234567"
    masked = mask_identification(value)

    assert masked != value
    assert "1234567" not in masked
    assert masked.startswith("402")
    assert masked.endswith("4567")


def test_required_text_and_email_validation() -> None:
    assert normalize_required_text("  Ana   Maria ", "El nombre") == "Ana Maria"
    assert validate_email("  person@example.com ") == "person@example.com"
    with pytest.raises(ValidationError):
        normalize_required_text("   ", "El nombre")
    with pytest.raises(ValidationError):
        validate_email("not-an-email")


def test_create_schema_never_accepts_normalized_identification() -> None:
    payload = VisitorCreate(first_name="Ana", last_name="Perez", identification="402-123")

    assert "identification_normalized" not in VisitorCreate.model_fields


def test_update_schema_never_accepts_normalized_identification() -> None:
    assert "identification_normalized" not in VisitorUpdate.model_fields


def test_visitor_model_has_no_branch_id() -> None:
    assert "branch_id" not in Visitor.__table__.columns


def test_visitor_create_stores_original_and_normalized_identification() -> None:
    session = FakeSession(visitor_type=None)
    visitor = VisitorManagementService(session).create_visitor(
        VisitorCreate(first_name=" Ana ", last_name=" Perez ", identification=" 402-123 4567 ")
    )

    created = session.added[0]
    assert created.identification == "402-123 4567"
    assert created.identification_normalized == "402-1234567"
    assert created.first_name == "Ana"
    assert visitor is not None


def test_create_without_identification_does_not_deduplicate_by_personal_fields() -> None:
    session = FakeSession(visitor_type=None)
    VisitorManagementService(session).create_visitor(
        VisitorCreate(first_name="Ana", last_name="Perez", email="person@example.com")
    )

    created = session.added[0]
    assert created.identification is None
    assert created.identification_normalized is None


def test_duplicate_identification_is_checked_in_sql() -> None:
    session = FakeSession(scalar_values=[77])

    with pytest.raises(ConflictError):
        VisitorManagementService(session).create_visitor(
            VisitorCreate(first_name="Ana", last_name="Perez", identification="402-1234567")
        )

    assert any("identification_normalized" in str(statement) for statement in session.statements)


def test_visitor_type_must_exist_and_be_active() -> None:
    inactive_type = VisitorType(id=4, code="EXTERNAL", name="Externo", is_active=False)
    session = FakeSession(visitor_type=inactive_type)

    with pytest.raises(ValidationError):
        VisitorManagementService(session).create_visitor(
            VisitorCreate(first_name="Ana", last_name="Perez", visitor_type_id=4)
        )


def test_update_can_remove_identification_and_normalized_value() -> None:
    visitor = Visitor(
        id=8,
        first_name="Ana",
        last_name="Perez",
        identification="402-1234567",
        identification_normalized="402-1234567",
        is_active=True,
    )
    session = FakeSession(scalar_values=[visitor, visitor], visitor_type=visitor)

    result = VisitorManagementService(session).update_visitor(8, VisitorUpdate(identification=None))

    assert visitor.identification is None
    assert visitor.identification_normalized is None
    assert result is visitor


def test_update_omitted_identification_does_not_clear_it() -> None:
    visitor = Visitor(
        id=8,
        first_name="Ana",
        last_name="Perez",
        identification="402-1234567",
        identification_normalized="402-1234567",
        is_active=True,
    )
    session = FakeSession(scalar_values=[visitor, visitor])

    VisitorManagementService(session).update_visitor(8, VisitorUpdate(first_name="Ana Maria"))

    assert visitor.identification == "402-1234567"
    assert visitor.identification_normalized == "402-1234567"


def test_pagination_and_search_are_expressed_in_sql() -> None:
    session = FakeSession(scalar_values=[12], visitors=[])

    visitors, total = VisitorManagementService(session).list_visitors(
        page=2,
        page_size=10,
        search="Ana",
        is_active=True,
        visitor_type_id=4,
    )

    assert visitors == []
    assert total == 12
    query_sql = str(session.statements[-1])
    assert "LIMIT" in query_sql.upper() or "OFFSET" in query_sql.upper()
    assert "identification_normalized" in query_sql
    assert "visitor_type_id" in query_sql


def test_set_active_is_soft_state() -> None:
    visitor = Visitor(id=8, first_name="Ana", last_name="Perez", is_active=True)
    session = FakeSession(scalar_values=[visitor, visitor])

    VisitorManagementService(session).set_active(8, False)

    assert visitor.is_active is False
    assert session.added == []


def test_openapi_contains_only_visitor_endpoints() -> None:
    schema = TestClient(app).get("/openapi.json").json()
    paths = {path for path in schema["paths"] if path.startswith("/api/visitors")}

    assert paths == {
        "/api/visitors",
        "/api/visitors/{visitor_id}",
        "/api/visitors/{visitor_id}/activate",
        "/api/visitors/{visitor_id}/deactivate",
    }


def test_visitor_response_does_not_expose_normalized_identification() -> None:
    from app.application.dto.visitors import VisitorResponse

    assert "identification_normalized" not in VisitorResponse.model_fields
