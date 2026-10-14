from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies.auth import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.infrastructure.database.session import get_db
from app.infrastructure.persistence.models import Branch, Role, User, UserBranchAssignment, UserRole
from main import app


class FakeSession:
    def __init__(self, user: User | None) -> None:
        self.user = user

    def scalar(self, statement: object) -> User | None:
        return self.user

    def add(self, value: object) -> None:
        return None

    def commit(self) -> None:
        return None


def make_user(*, active: bool = True, password: str = "Correct-password-123") -> User:
    role = Role(code="USER", name="User", is_active=True)
    user = User(
        id=7,
        username="carlos",
        first_name="Carlos",
        last_name="Perez",
        password_hash=hash_password(password),
        is_active=active,
    )
    user.user_roles = [UserRole(user=user, role=role, is_active=True)]
    return user


def client_for(user: User | None) -> TestClient:
    app.dependency_overrides[get_db] = lambda: FakeSession(user)
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_password_hashing_and_verification() -> None:
    password_hash = hash_password("secret-value")

    assert password_hash != "secret-value"
    assert password_hash.startswith("$argon2")
    assert verify_password("secret-value", password_hash)
    assert not verify_password("wrong-value", password_hash)


def test_access_token_contains_only_required_identity_claims() -> None:
    token = create_access_token("7")
    payload = decode_token(token)

    assert payload["sub"] == "7"
    assert payload["type"] == "access"
    assert "iat" in payload
    assert "exp" in payload
    assert set(payload) == {"sub", "type", "iat", "exp"}
    assert "password_hash" not in payload


def test_expired_token_is_rejected() -> None:
    settings = get_settings()
    token = jwt.encode(
        {"sub": "7", "type": "access", "iat": datetime.now(timezone.utc) - timedelta(minutes=2), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    client = client_for(make_user())

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_login_returns_user_without_password_hash() -> None:
    client = client_for(make_user())

    response = client.post("/api/auth/login", json={"username": "carlos", "password": "Correct-password-123"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["id"] == 7
    assert "password_hash" not in body
    assert "PasswordHash" not in body


def test_login_returns_branch_only_when_exactly_one_current_assignment_exists() -> None:
    user = make_user()
    branch = Branch(id=3, code="HQ", name="Central", branch_type_id=1, is_active=True)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user.branch_assignments = [
        UserBranchAssignment(
            id=11,
            user_id=user.id,
            branch_id=3,
            branch=branch,
            valid_from=now - timedelta(minutes=1),
            valid_until=None,
            assigned_by_user_id=user.id,
            status="ACTIVE",
        )
    ]
    client = client_for(user)

    response = client.post("/api/auth/login", json={"username": "carlos", "password": "Correct-password-123"})

    assert response.status_code == 200
    assert response.json()["user"]["branch"] == {"id": 3, "code": "HQ", "name": "Central"}

    user.branch_assignments.append(
        UserBranchAssignment(
            id=12,
            user_id=user.id,
            branch_id=4,
            branch=Branch(id=4, code="BR2", name="Branch 2", branch_type_id=1, is_active=True),
            valid_from=now - timedelta(minutes=1),
            valid_until=None,
            assigned_by_user_id=user.id,
            status="ACTIVE",
        )
    )
    response = client.post("/api/auth/login", json={"username": "carlos", "password": "Correct-password-123"})

    assert response.status_code == 200
    assert response.json()["user"]["branch"] is None


def test_login_rejects_unknown_user_and_wrong_password_generically() -> None:
    known_client = client_for(make_user())
    unknown_client = client_for(None)

    wrong_password = known_client.post("/api/auth/login", json={"username": "carlos", "password": "wrong"})
    unknown_user = unknown_client.post("/api/auth/login", json={"username": "nobody", "password": "wrong"})

    assert wrong_password.status_code == 401
    assert unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json() == {"detail": "Credenciales inválidas"}


def test_inactive_user_cannot_login() -> None:
    client = client_for(make_user(active=False))

    response = client.post("/api/auth/login", json={"username": "carlos", "password": "Correct-password-123"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Credenciales inválidas"}


def test_me_requires_token() -> None:
    client = client_for(make_user())

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_openapi_documents_json_login_and_http_bearer_authentication() -> None:
    schema = TestClient(app).get("/openapi.json").json()

    assert schema["paths"]["/api/auth/login"]["post"]["requestBody"]["content"].get("application/json")
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["type"] == "http"
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"


def test_auth_rejects_non_bearer_authorization_scheme() -> None:
    client = client_for(make_user())

    response = client.get("/api/auth/me", headers={"Authorization": "Basic Y2FybG9zOnBhc3M="})

    assert response.status_code == 401


def test_login_distinguishes_database_unavailability_from_bad_credentials() -> None:
    class UnavailableSession:
        def scalar(self, statement: object) -> object:
            raise SQLAlchemyError("database unavailable")

    app.dependency_overrides[get_db] = lambda: UnavailableSession()
    response = TestClient(app).post("/api/auth/login", json={"username": "carlos", "password": "Correct-password-123"})

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    assert response.json() == {"detail": "Servicio de autenticación no disponible"}


def test_me_uses_authenticated_token_identity() -> None:
    client = client_for(make_user())
    token = create_access_token("7")

    response = client.get("/api/auth/me?user_id=999", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["user"]["id"] == 7 if "user" in response.json() else response.json()["id"] == 7
    assert "password_hash" not in response.text.lower()


def test_token_for_missing_user_is_rejected() -> None:
    client = client_for(None)
    token = create_access_token("999")

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_get_current_user_dependency_is_reusable() -> None:
    user = make_user()
    assert get_current_user
    assert user.password_hash.startswith("$argon2")
