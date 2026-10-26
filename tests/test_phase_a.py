"""Pruebas de la Fase A: aislamiento por sucursal, fechas, OpenAPI y errores controlados."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import mssql
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies.auth import get_current_user
from app.application.dto.audit import AuditLogResponse
from app.application.services.audit import AuditQueryService
from app.application.services.authorization import PermissionService
from app.application.services.branch_access import BranchAccessService, BranchContext
from app.application.services.dashboard import DashboardScope, DashboardService
from app.application.services.users import UserManagementService
from app.application.services.visitors import VisitorManagementService
from app.application.services.visits import VisitManagementService
from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.core.security import create_access_token
from app.infrastructure.database.session import get_db
from app.infrastructure.persistence.models import User
from main import app


def sql(statement: object) -> str:
    return str(statement.compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


class Result:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values

    def unique(self) -> "Result":
        return self


class RecordingSession:
    def __init__(self) -> None:
        self.statements: list[object] = []

    def scalar(self, statement: object) -> int:
        self.statements.append(statement)
        return 0

    def scalars(self, statement: object) -> Result:
        self.statements.append(statement)
        return Result([])


class Harness:
    """Replaces authentication and permission evaluation, keeping the real route dependencies."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, context_branch: int | None, allowed: set[str]) -> None:
        self.permission_calls: list[tuple[str, int | None]] = []
        user = SimpleNamespace(id=7)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: RecordingSession()
        context = None if context_branch is None else BranchContext(user_id=7, branch_id=context_branch, assignment_id=1)
        monkeypatch.setattr(BranchAccessService, "get_current_context", lambda self, user_id, at=None: context)
        monkeypatch.setattr(BranchAccessService, "is_active_branch", lambda self, branch_id: True)

        def has_permission(service: PermissionService, user_id: int, code: str, branch_id: int | None = None, at: object = None) -> bool:
            self.permission_calls.append((code, branch_id))
            return code in allowed

        monkeypatch.setattr(PermissionService, "has_permission", has_permission)
        self.client = TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


# ---- A. Sucursal y permisos globales ----

def test_visitor_route_uses_authorized_branch_without_client_branch_id(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = Harness(monkeypatch, context_branch=3, allowed={"VIEW_VISITORS"})
    monkeypatch.setattr(VisitorManagementService, "list_visitors", lambda self, **kw: ([], 0))

    response = harness.client.get("/api/visitors")

    assert response.status_code == 200
    assert harness.permission_calls == [("VIEW_VISITORS", 3), ("VIEW_VISITOR_CONTACT", 3)]


@pytest.mark.parametrize("path", ["/api/visitors?branch_id=9", "/api/visits?branch_id=9", "/api/visits/5?branch_id=9"])
def test_manipulated_branch_id_cannot_cross_branch_isolation(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    harness = Harness(monkeypatch, context_branch=3, allowed={"VIEW_VISITORS", "VIEW_VISITS"})

    response = harness.client.get(path)

    assert response.status_code == 403
    assert harness.permission_calls == []


def test_matching_client_branch_id_is_only_a_check(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = Harness(monkeypatch, context_branch=3, allowed={"VIEW_VISITORS"})
    monkeypatch.setattr(VisitorManagementService, "list_visitors", lambda self, **kw: ([], 0))

    assert harness.client.get("/api/visitors?branch_id=3").status_code == 200


@pytest.mark.parametrize("method, path", [("get", "/api/visitors"), ("get", "/api/visitors?branch_id=3"), ("post", "/api/visits")])
def test_user_without_current_assignment_gets_no_branch_access(monkeypatch: pytest.MonkeyPatch, method: str, path: str) -> None:
    harness = Harness(monkeypatch, context_branch=None, allowed={"VIEW_VISITORS", "VIEW_VISITS", "CREATE_VISIT"})

    response = getattr(harness.client, method)(path, **({"json": {"visitor_id": 1, "reason_id": 1}} if method == "post" else {}))

    assert response.status_code == 403
    assert harness.permission_calls == []


def test_branch_user_cannot_modify_visitors_of_another_branch_context(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = Harness(monkeypatch, context_branch=3, allowed={"UPDATE_VISITOR"})

    response = harness.client.patch("/api/visitors/1?branch_id=9", json={"company": "X"})

    assert response.status_code == 403


def test_branch_permission_missing_returns_403(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = Harness(monkeypatch, context_branch=3, allowed=set())

    assert harness.client.get("/api/visitors").status_code == 403
    assert harness.permission_calls == [("VIEW_VISITORS", 3)]


def test_users_branch_filter_is_search_filter_not_authorization_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = Harness(monkeypatch, context_branch=None, allowed={"MANAGE_USERS"})
    captured: dict[str, object] = {}

    def list_users(self: object, **kwargs: object) -> tuple[list[object], int]:
        captured.update(kwargs)
        return [], 0

    monkeypatch.setattr(UserManagementService, "list_users", list_users)

    response = harness.client.get("/api/users?branch_id=99")

    assert response.status_code == 200
    assert harness.permission_calls == [("MANAGE_USERS", None)]
    assert captured["branch_id"] == 99


def test_audit_branch_filter_is_search_filter_not_authorization_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = Harness(monkeypatch, context_branch=None, allowed={"VIEW_AUDIT_LOGS"})
    captured: dict[str, object] = {}

    def list_logs(self: object, **kwargs: object) -> tuple[list[object], int]:
        captured.update(kwargs)
        return [], 0

    monkeypatch.setattr(AuditQueryService, "list_logs", list_logs)

    response = harness.client.get("/api/audit-logs?branch_id=99")

    assert response.status_code == 200
    assert harness.permission_calls == [("VIEW_AUDIT_LOGS", None)]
    assert captured["branch_id"] == 99


@pytest.mark.parametrize("path", ["/api/users?branch_id=1", "/api/audit-logs?branch_id=1"])
def test_global_routes_without_permission_return_403(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    harness = Harness(monkeypatch, context_branch=1, allowed=set())

    assert harness.client.get(path).status_code == 403


def test_branch_scoped_report_user_cannot_request_other_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = Harness(monkeypatch, context_branch=3, allowed={"VIEW_REPORTS"})

    assert harness.client.get("/api/reports/visits?branch_id=9").status_code == 403


def test_explicit_deny_prevails_over_allow_and_role() -> None:
    from tests.test_authorization import evaluation

    assert not evaluation(effects=("ALLOW", "DENY"), role_granted=True).allowed


# ---- B. CORS ----

def test_default_cors_origins_are_explicit_and_not_wildcard() -> None:
    settings = Settings(_env_file=None, database_url="x", jwt_secret_key="k" * 32)

    assert "http://localhost:5173" in settings.cors_origins_list
    assert "http://localhost:8443" in settings.cors_origins_list
    assert "http://127.0.0.1:8443" in settings.cors_origins_list
    assert "*" not in settings.cors_origins_list
    assert settings.cors_allow_credentials is False


def test_cors_origins_are_configurable_and_wildcard_is_rejected() -> None:
    settings = Settings(_env_file=None, database_url="x", jwt_secret_key="k" * 32, cors_origins=" http://a.test , http://192.0.2.10:8443 ")
    assert settings.cors_origins_list == ["http://a.test", "http://192.0.2.10:8443"]

    with pytest.raises(ValueError):
        Settings(_env_file=None, database_url="x", jwt_secret_key="k" * 32, cors_origins="http://a.test,*")


def test_cors_headers_on_simple_requests() -> None:
    client = TestClient(app)

    allowed = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    blocked = client.get("/api/health", headers={"Origin": "https://untrusted.example"})

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in allowed.headers
    assert "access-control-allow-origin" not in blocked.headers


def test_cors_preflight_allows_localhost_5173() -> None:
    response = TestClient(app).options(
        "/api/auth/login",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


# ---- C. Autenticación y errores controlados ----

def test_protected_routes_reject_missing_credentials_with_401() -> None:
    client = TestClient(app)

    for path in ("/api/users", "/api/visitors", "/api/visits", "/api/audit-logs", "/api/dashboard/summary", "/api/reports/visits"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_token_is_401_on_protected_route() -> None:
    response = TestClient(app).get("/api/users", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401


def test_valid_token_of_inactive_user_is_401() -> None:
    inactive = User(id=7, username="u", first_name="A", last_name="B", password_hash="x", is_active=False)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(scalar=lambda statement: inactive)

    response = TestClient(app).get("/api/auth/me", headers={"Authorization": f"Bearer {create_access_token('7')}"})

    assert response.status_code == 401


def test_database_failure_during_token_validation_is_safe_500_not_401() -> None:
    def broken(statement: object) -> None:
        raise SQLAlchemyError("SELECT password_hash FROM users WHERE secret")

    app.dependency_overrides[get_db] = lambda: SimpleNamespace(scalar=broken)

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/auth/me", headers={"Authorization": f"Bearer {create_access_token('7')}"}
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Ha ocurrido un error interno. Intente de nuevo más tarde."}
    assert "SELECT" not in response.text and "password_hash" not in response.text


def test_access_token_lifetime_matches_configuration() -> None:
    from app.core.config import get_settings
    from app.core.security import decode_token

    payload = decode_token(create_access_token("7"))

    assert payload["exp"] - payload["iat"] == get_settings().access_token_expire_minutes * 60


def test_openapi_security_scheme_is_http_bearer_only() -> None:
    schemes = TestClient(app).get("/openapi.json").json()["components"]["securitySchemes"]

    assert schemes["HTTPBearer"] == {"type": "http", "scheme": "bearer"}
    assert all(scheme["type"] != "oauth2" for scheme in schemes.values())


# ---- E. OpenAPI de errores ----

def test_openapi_documents_functional_errors() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    protected = [
        (path, method, operation)
        for path, item in paths.items()
        if path not in {"/", "/api/health", "/api/health/db", "/api/auth/login"}
        for method, operation in item.items()
    ]

    assert protected
    for path, method, operation in protected:
        assert "401" in operation["responses"], (method, path)
    for path in ("/api/users", "/api/visitors", "/api/visits", "/api/audit-logs", "/api/dashboard/summary", "/api/reports/visits"):
        assert "403" in paths[path]["get"]["responses"], path
    assert {"401", "403", "404", "409", "422"} <= set(paths["/api/visits/{visit_id}/complete"]["post"]["responses"])
    assert {"401", "403", "404", "409", "422"} <= set(paths["/api/users"]["post"]["responses"])
    assert {"401", "403", "404", "409", "422"} <= set(paths["/api/visitors"]["post"]["responses"])
    schema_ref = paths["/api/visitors/{visitor_id}"]["get"]["responses"]["404"]["content"]["application/json"]["schema"]["$ref"]
    assert schema_ref.endswith("/ErrorResponse")


# ---- D. Fechas ----

def audit_sql(**kwargs: object) -> str:
    session = RecordingSession()
    AuditQueryService(session).list_logs(page=1, page_size=10, **kwargs)  # type: ignore[arg-type]
    return sql(session.statements[0])


def visits_sql(**kwargs: object) -> str:
    session = RecordingSession()
    context = BranchContext(user_id=7, branch_id=1, assignment_id=1)
    VisitManagementService(session).list_visits(context, page=1, page_size=10, **kwargs)  # type: ignore[arg-type]
    return sql(session.statements[-1])


def dashboard_sql(**kwargs: object) -> str:
    filters = DashboardService._filters(DashboardScope(branch_id=1, is_global=False), kwargs.get("date_from"), kwargs.get("date_to"))  # type: ignore[arg-type]
    return " AND ".join(sql(item) for item in filters)


@pytest.mark.parametrize("build, column", [(audit_sql, "audit_logs.created_at"), (visits_sql, "visits.entry_at"), (dashboard_sql, "visits.entry_at")])
def test_all_modules_use_inclusive_start_and_exclusive_end(build, column: str) -> None:
    text = build(date_from=datetime(2026, 9, 1), date_to=datetime(2026, 9, 2))

    assert f"{column} >= '2026-09-01 00:00:00" in text
    assert f"{column} < '2026-09-02 00:00:00" in text
    assert f"{column} <=" not in text


@pytest.mark.parametrize("build", [audit_sql, visits_sql, dashboard_sql])
def test_aware_dates_are_converted_once_to_utc(build) -> None:
    local = timezone(timedelta(hours=-4))
    text = build(date_from=datetime(2026, 9, 1, 0, 0, tzinfo=local), date_to=datetime(2026, 9, 1, 20, 0, tzinfo=local))

    assert "2026-09-01 04:00:00" in text
    assert "2026-09-02 00:00:00" in text


@pytest.mark.parametrize("build", [audit_sql, visits_sql, dashboard_sql])
def test_naive_dates_are_treated_as_utc_without_shift(build) -> None:
    assert "2026-09-01 10:30:00" in build(date_from=datetime(2026, 9, 1, 10, 30))


@pytest.mark.parametrize("build", [audit_sql, visits_sql, dashboard_sql])
@pytest.mark.parametrize("start, end", [(datetime(2026, 9, 1), datetime(2026, 9, 1)), (datetime(2026, 9, 2), datetime(2026, 9, 1))])
def test_empty_or_inverted_ranges_are_rejected(build, start: datetime, end: datetime) -> None:
    with pytest.raises(ValidationError):
        build(date_from=start, date_to=end)


@pytest.mark.parametrize("build", [audit_sql, visits_sql, dashboard_sql])
def test_single_bound_filters_are_supported(build) -> None:
    assert ">=" in build(date_from=datetime(2026, 9, 1))
    assert "<" in build(date_to=datetime(2026, 9, 1))


def test_audit_route_returns_422_for_empty_range(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = Harness(monkeypatch, context_branch=None, allowed={"VIEW_AUDIT_LOGS"})

    response = harness.client.get("/api/audit-logs?date_from=2026-09-01T00:00:00Z&date_to=2026-09-01T00:00:00Z")

    assert response.status_code == 422


def test_response_timestamps_are_serialized_as_utc_iso_8601() -> None:
    def build(created_at: datetime) -> dict[str, object]:
        return AuditLogResponse(
            id=1, actor_user_id=None, action="A", entity_type="E", entity_id=None, branch_id=None,
            old_values=None, new_values=None, ip_address=None, user_agent=None, correlation_id=None,
            created_at=created_at,
        ).model_dump(mode="json")

    assert build(datetime(2026, 9, 1, 10, 0))["created_at"] == "2026-09-01T10:00:00Z"
    assert build(datetime(2026, 9, 1, 6, 0, tzinfo=timezone(timedelta(hours=-4))))["created_at"] == "2026-09-01T10:00:00Z"
