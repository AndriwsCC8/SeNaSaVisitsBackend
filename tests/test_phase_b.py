"""Fase B: carga de datos de referencia y API de catálogos."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.infrastructure.database.session import get_db
from app.infrastructure.persistence.models import Branch, BranchType, Role, VisitReason, VisitorType
from main import app
from scripts.load_reference_data import load_reference_data, parse_reference_data
from tests.sqlite_support import make_session_factory
from tests.test_phase_a import Harness

EXAMPLE = Path(__file__).resolve().parent.parent / "docs" / "examples" / "reference-data.example.json"


def teardown_function() -> None:
    app.dependency_overrides.clear()


def valid_document() -> dict:
    return {
        "branch_types": [{"code": "TIPO_A", "name": "Tipo A"}],
        "branches": [{"code": "SUC_1", "name": "Sucursal 1", "branch_type_code": "TIPO_A"}],
        "visitor_types": [{"code": "VT_1", "name": "Tipo visitante 1"}],
        "visit_reasons": [{"code": "MOT_1", "name": "Motivo 1"}],
    }


def total_rows(db) -> int:
    return sum(db.scalar(select(func.count()).select_from(model)) for model in (BranchType, Branch, VisitorType, VisitReason))


# ---- Validación del archivo ----

def test_example_template_is_valid_and_marked_as_example() -> None:
    data = parse_reference_data(json.loads(EXAMPLE.read_text(encoding="utf-8")))

    assert data.is_example is True
    assert all(item.code.startswith("EJEMPLO_") for item in data.branches)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda d: d["branches"].append(dict(d["branches"][0])), "duplicado"),
        (lambda d: d["visit_reasons"].append(dict(d["visit_reasons"][0])), "duplicado"),
        (lambda d: d["branches"][0].pop("name"), "name"),
        (lambda d: d["branches"][0].update(code="minúscula"), "código"),
        (lambda d: d["branches"][0].update(code="X" * 31), "code"),
        (lambda d: d["visit_reasons"][0].update(unexpected=1), "unexpected"),
        (lambda d: d.update(unknown_section=[]), "unknown_section"),
        (lambda d: d["branches"][0].update(name=5), "name"),
    ],
)
def test_invalid_documents_are_rejected(mutate, message: str) -> None:
    document = valid_document()
    mutate(document)

    with pytest.raises(ValueError, match=message):
        parse_reference_data(document)


# ---- Carga ----

def test_dry_run_reports_plan_without_writing() -> None:
    factory = make_session_factory()
    with factory.begin() as db:
        report = load_reference_data(db, parse_reference_data(valid_document()), dry_run=True)

    assert len(report.to_create) == 4
    with factory() as db:
        assert total_rows(db) == 0


def test_apply_creates_records_and_is_idempotent() -> None:
    factory = make_session_factory()
    data = parse_reference_data(valid_document())
    with factory.begin() as db:
        load_reference_data(db, data, dry_run=False)
    with factory.begin() as db:
        second = load_reference_data(db, data, dry_run=False)

    assert second.to_create == [] and len(second.unchanged) == 4
    with factory() as db:
        assert total_rows(db) == 4
        branch = db.scalar(select(Branch))
        assert branch.is_active and branch.branch_type_id == db.scalar(select(BranchType.id))


def test_branch_can_reference_existing_database_type() -> None:
    factory = make_session_factory()
    with factory.begin() as db:
        db.add(BranchType(code="TIPO_A", name="Tipo A"))
    document = valid_document()
    document["branch_types"] = []

    with factory.begin() as db:
        load_reference_data(db, parse_reference_data(document), dry_run=False)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Branch)) == 1


def test_branch_with_unknown_type_is_a_conflict() -> None:
    document = valid_document()
    document["branch_types"] = []
    factory = make_session_factory()

    with pytest.raises(RuntimeError, match="TIPO_A"):
        with factory.begin() as db:
            load_reference_data(db, parse_reference_data(document), dry_run=False)
    with factory() as db:
        assert total_rows(db) == 0


def test_conflict_with_existing_data_aborts_everything_without_overwriting() -> None:
    factory = make_session_factory()
    with factory.begin() as db:
        db.add(VisitorType(code="VT_1", name="Nombre institucional existente"))

    with pytest.raises(RuntimeError, match="no se sobrescribe"):
        with factory.begin() as db:
            load_reference_data(db, parse_reference_data(valid_document()), dry_run=False)

    with factory() as db:
        assert total_rows(db) == 1
        assert db.scalar(select(VisitorType.name)) == "Nombre institucional existente"


def test_inactive_existing_record_is_a_conflict() -> None:
    factory = make_session_factory()
    with factory.begin() as db:
        db.add(VisitReason(code="MOT_1", name="Motivo 1", is_active=False))

    with pytest.raises(RuntimeError, match="MOT_1"):
        with factory.begin() as db:
            load_reference_data(db, parse_reference_data(valid_document()), dry_run=True)


def test_loader_cli_refuses_example_template_with_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import load_reference_data as module

    monkeypatch.setattr("sys.argv", ["x", "--file", str(EXAMPLE), "--apply"])
    with pytest.raises(SystemExit, match="plantilla de ejemplo"):
        module.main()


def test_loader_cli_validate_only_does_not_touch_database(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from scripts import load_reference_data as module

    monkeypatch.setattr("sys.argv", ["x", "--file", str(EXAMPLE), "--validate-only"])
    module.main()

    assert "válido" in capsys.readouterr().out


# ---- API de catálogos ----

class CatalogEnv:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, allowed: set[str], with_context: bool = True) -> None:
        self.factory = make_session_factory()
        with self.factory.begin() as db:
            btype = BranchType(code="T", name="Tipo")
            inactive_type = BranchType(code="T_OLD", name="Tipo viejo", is_active=False)
            db.add_all([btype, inactive_type])
            db.flush()
            own = Branch(code="B_OWN", name="Propia", branch_type_id=btype.id)
            other = Branch(code="B_OTHER", name="Ajena", branch_type_id=btype.id)
            closed = Branch(code="B_OLD", name="Cerrada", branch_type_id=btype.id, is_active=False)
            db.add_all([own, other, closed])
            db.add_all(
                [
                    VisitorType(code="V1", name="Activo"),
                    VisitorType(code="V0", name="Inactivo", is_active=False),
                    VisitReason(code="R1", name="Motivo activo"),
                    VisitReason(code="R0", name="Motivo inactivo", is_active=False),
                    Role(code="ROLE_A", name="Rol activo", description="interno"),
                    Role(code="ROLE_I", name="Rol inactivo", is_active=False),
                ]
            )
            db.flush()
            self.own_id, self.other_id = own.id, other.id
        self.harness = Harness(monkeypatch, context_branch=self.own_id if with_context else None, allowed=allowed)

        def get_session():
            with self.factory() as db:
                yield db

        app.dependency_overrides[get_db] = get_session
        self.client = self.harness.client

    def codes(self, path: str) -> list[str]:
        response = self.client.get(path)
        assert response.status_code == 200, response.text
        return [item["code"] for item in response.json()]


def test_branch_scoped_user_only_sees_own_branch_even_with_forged_branch_id(monkeypatch: pytest.MonkeyPatch) -> None:
    env = CatalogEnv(monkeypatch, allowed={"VIEW_VISITS"})

    assert env.codes("/api/branches") == ["B_OWN"]
    assert env.codes(f"/api/branches?branch_id={env.other_id}") == ["B_OWN"]


def test_global_user_sees_all_active_branches_and_never_inactive_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    env = CatalogEnv(monkeypatch, allowed={"MANAGE_USERS"}, with_context=False)

    assert env.codes("/api/branches") == ["B_OTHER", "B_OWN"]


def test_include_inactive_branches_requires_manage_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    env = CatalogEnv(monkeypatch, allowed={"MANAGE_USERS"}, with_context=False)
    assert env.client.get("/api/branches?include_inactive=true").status_code == 403

    env = CatalogEnv(monkeypatch, allowed={"MANAGE_BRANCHES"}, with_context=False)
    assert "B_OLD" in env.codes("/api/branches?include_inactive=true")


def test_branch_response_fields_are_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    env = CatalogEnv(monkeypatch, allowed={"VIEW_VISITS"})

    item = env.client.get("/api/branches").json()[0]

    assert set(item) == {"id", "code", "name", "branch_type_id", "is_active"}


@pytest.mark.parametrize("path", ["/api/branches", "/api/branch-types", "/api/visitor-types", "/api/visit-reasons", "/api/roles"])
def test_catalogs_require_authentication(path: str) -> None:
    assert TestClient(app).get(path).status_code == 401


@pytest.mark.parametrize("path", ["/api/branches", "/api/branch-types", "/api/visitor-types", "/api/visit-reasons", "/api/roles"])
def test_catalogs_deny_users_without_any_relevant_permission(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    env = CatalogEnv(monkeypatch, allowed=set())

    assert env.client.get(path).status_code == 403


@pytest.mark.parametrize("path", ["/api/branches", "/api/visitor-types", "/api/visit-reasons"])
def test_branch_permissions_without_current_assignment_are_denied(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    env = CatalogEnv(monkeypatch, allowed={"VIEW_VISITS", "VIEW_VISITORS", "VIEW_REPORTS"}, with_context=False)

    assert env.client.get(path).status_code == 403


def test_branch_types_only_for_manage_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    env = CatalogEnv(monkeypatch, allowed={"VIEW_VISITS", "MANAGE_USERS"})
    assert env.client.get("/api/branch-types").status_code == 403

    env = CatalogEnv(monkeypatch, allowed={"MANAGE_BRANCHES"}, with_context=False)
    assert env.codes("/api/branch-types") == ["T"]
    assert set(env.codes("/api/branch-types?include_inactive=true")) == {"T", "T_OLD"}


def test_visitor_types_and_reasons_hide_inactive_unless_admin_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    env = CatalogEnv(monkeypatch, allowed={"VIEW_VISITORS", "VIEW_VISITS", "MANAGE_VISITOR_TYPES", "MANAGE_VISIT_REASONS"})

    assert env.codes("/api/visitor-types") == ["V1"]
    assert set(env.codes("/api/visitor-types?include_inactive=true")) == {"V1", "V0"}
    assert env.codes("/api/visit-reasons") == ["R1"]
    assert set(env.codes("/api/visit-reasons?include_inactive=true")) == {"R1", "R0"}
    assert set(env.client.get("/api/visitor-types").json()[0]) == {"id", "code", "name", "is_active"}


def test_visit_reasons_available_to_global_report_viewer_without_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    env = CatalogEnv(monkeypatch, allowed={"VIEW_GLOBAL_REPORTS"}, with_context=False)

    assert env.codes("/api/visit-reasons") == ["R1"]
    assert env.client.get("/api/visitor-types").status_code == 403


def test_roles_only_active_and_without_internal_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    env = CatalogEnv(monkeypatch, allowed={"MANAGE_USERS"}, with_context=False)

    body = env.client.get("/api/roles").json()

    assert [item["code"] for item in body] == ["ROLE_A"]
    assert set(body[0]) == {"id", "code", "name"}


def test_catalog_openapi_documents_errors_and_no_permissions_endpoint() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    for path in ("/api/branches", "/api/branch-types", "/api/visitor-types", "/api/visit-reasons", "/api/roles"):
        responses = paths[path]["get"]["responses"]
        assert {"200", "401", "403"} <= set(responses), path
    assert "/api/permissions" not in paths
