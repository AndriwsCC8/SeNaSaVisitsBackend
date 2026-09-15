from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.application.services.audit import AuditQueryService, AuditService
from app.core.exceptions import ForbiddenError
from app.infrastructure.persistence.models import AuditLog
from main import app


class FakeResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeSession:
    def __init__(self, scalar_values=None, logs=None):
        self.scalar_values = iter(scalar_values or [])
        self.logs = logs or []
        self.added = []
        self.statements = []

    def add(self, value):
        self.added.append(value)

    def scalar(self, statement):
        self.statements.append(statement)
        try:
            return next(self.scalar_values)
        except StopIteration:
            return 0

    def scalars(self, statement):
        self.statements.append(statement)
        return FakeResult(self.logs)


def test_audit_service_redacts_secrets_and_serializes_deterministically() -> None:
    session = FakeSession()
    event = AuditService(session).record(
        actor_user_id=7,
        action="UPDATE_USER",
        entity_type="User",
        entity_id=7,
        old_values={"username": "old", "password": "secret", "password_hash": "hash"},
        new_values={"username": "new", "access_token": "jwt", "role": "ADMIN"},
        ip_address="127.0.0.1",
        user_agent="pytest",
        correlation_id="corr-1",
    )

    assert event in session.added
    assert json.loads(event.old_values) == {"username": "old"}
    assert json.loads(event.new_values) == {"role": "ADMIN", "username": "new"}
    assert "secret" not in event.old_values
    assert "jwt" not in event.new_values
    assert "Authorization" not in (event.user_agent or "")


def test_audit_service_keeps_empty_values_null() -> None:
    event = AuditService(FakeSession()).record(
        actor_user_id=None,
        action="LOGIN",
        entity_type="User",
        old_values=None,
        new_values={},
    )

    assert event.old_values is None
    assert event.new_values is None


@pytest.mark.parametrize(
    "sensitive_key",
    [
        "password",
        "password_hash",
        "passwordHash",
        "password-hash",
        "access_token",
        "accessToken",
        "refresh_token",
        "refreshToken",
        "authorization",
        "Authorization",
        "api_key",
        "apiKey",
        "secret",
        "credentials",
    ],
)
def test_audit_service_redacts_sensitive_key_variants(sensitive_key: str) -> None:
    event = AuditService(FakeSession()).record(
        actor_user_id=7,
        action="UPDATE_USER",
        entity_type="User",
        new_values={sensitive_key: "must-not-persist", "ordinary_field": "kept"},
    )

    assert json.loads(event.new_values) == {"ordinary_field": "kept"}


def test_audit_service_keeps_normal_keys() -> None:
    event = AuditService(FakeSession()).record(
        actor_user_id=7,
        action="UPDATE_USER",
        entity_type="User",
        new_values={"password_policy": "argon2", "secretary_name": "Ana"},
    )

    assert json.loads(event.new_values) == {
        "password_policy": "argon2",
        "secretary_name": "Ana",
    }


def test_audit_query_is_paged_and_sql_filtered() -> None:
    session = FakeSession(scalar_values=[3], logs=[])

    logs, total = AuditQueryService(session).list_logs(
        page=2,
        page_size=10,
        action="CREATE_VISIT",
        entity_type="Visit",
        branch_id=4,
        date_from=datetime(2026, 1, 1),
    )

    assert logs == []
    assert total == 3
    assert any("audit_logs.branch_id" in str(statement) for statement in session.statements)
    assert any("LIMIT" in str(statement).upper() or "OFFSET" in str(statement).upper() for statement in session.statements)


def test_audit_model_has_no_application_update_or_delete_endpoint() -> None:
    schema = TestClient(app).get("/openapi.json").json()
    assert "/api/audit-logs" in schema["paths"]
    methods = set(schema["paths"]["/api/audit-logs"])
    assert methods == {"get"}


def test_audit_endpoint_requires_bearer_security() -> None:
    schema = TestClient(app).get("/openapi.json").json()
    assert schema["paths"]["/api/audit-logs"]["get"]["security"]


def test_audit_entity_is_append_only_model_without_password_fields() -> None:
    assert "password" not in AuditLog.__table__.columns
    assert "password_hash" not in AuditLog.__table__.columns
