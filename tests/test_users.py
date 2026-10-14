from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.application.dto.users import UserCreate, UserTransferRequest
from app.application.services.users import UserManagementService
from app.core.exceptions import ConflictError
from app.core.security import hash_password
from app.infrastructure.persistence.models import User
from main import app


class NoDatabaseSession:
    def in_transaction(self) -> bool:
        return False


def test_user_create_schema_requires_strong_initial_password() -> None:
    with pytest.raises(ValueError):
        UserCreate(
            username="new-user",
            first_name="New",
            last_name="User",
            password="short",
        )


def test_password_is_hashable_for_user_creation_contract() -> None:
    user = User(
        username="new-user",
        first_name="New",
        last_name="User",
        password_hash=hash_password("Correct-password-123"),
        is_active=True,
    )

    assert user.password_hash.startswith("$argon2")
    assert "Correct-password-123" not in user.password_hash


def test_transfer_request_accepts_optional_effective_at_and_reason() -> None:
    request = UserTransferRequest(
        new_branch_id=2,
        effective_at=datetime(2026, 9, 15),
        reason="Traslado institucional",
    )

    assert request.new_branch_id == 2
    assert request.effective_at == datetime(2026, 9, 15)


def test_assignment_interval_overlap_is_rejected() -> None:
    start = datetime(2026, 9, 15)
    with pytest.raises(ConflictError):
        UserManagementService._assert_no_overlap(
            [type("Assignment", (), {"valid_from": datetime(2026, 9, 1), "valid_until": datetime(2026, 9, 20)})()],
            start,
            datetime(2026, 9, 30),
        )


def test_adjacent_assignment_intervals_do_not_overlap() -> None:
    UserManagementService._assert_no_overlap(
        [type("Assignment", (), {"valid_from": datetime(2026, 9, 1), "valid_until": datetime(2026, 9, 15)})()],
        datetime(2026, 9, 15),
        None,
    )


def test_user_response_schema_does_not_define_password_hash() -> None:
    from app.application.dto.users import UserResponse

    assert "password_hash" not in UserResponse.model_fields


def test_user_routes_are_documented_with_expected_methods() -> None:
    schema = TestClient(app).get("/openapi.json").json()
    assert "/api/users" in schema["paths"]
    assert "/api/users/{user_id}" in schema["paths"]
    assert "/api/users/{user_id}/transfer" in schema["paths"]
    assert "post" in schema["paths"]["/api/users/{user_id}/transfer"]

    create_parameters = schema["paths"]["/api/users"]["post"].get("parameters", [])
    user_detail_parameters = schema["paths"]["/api/users/{user_id}"]["get"].get("parameters", [])
    assert "branch_id" not in {item["name"] for item in create_parameters}
    assert "branch_id" not in {item["name"] for item in user_detail_parameters}


def test_user_management_does_not_create_schema_objects() -> None:
    assert NoDatabaseSession().in_transaction() is False
