"""Fase C: privacidad de contacto de visitantes, política de inactivos y scripts obsoletos."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.application.services.visitors import VisitorManagementService
from app.application.validators.visitors import mask_email, mask_phone
from app.infrastructure.persistence.models import Visitor
from main import app
from scripts.permission_catalog import PERMISSIONS, ROLE_PERMISSION_CODES
from tests.test_phase_a import Harness, visits_sql
from tests.test_phase_b import CatalogEnv

NOW = datetime(2026, 9, 1, 10, 0)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def synthetic_visitor() -> Visitor:
    return Visitor(
        id=1, identification="00112233445", identification_normalized="00112233445", first_name="Ana", last_name="Ejemplo",
        phone="8095550123", email="ana.ejemplo@example.test", company=None, visitor_type=None, is_active=True,
        created_at=NOW, updated_at=NOW,
    )


def visitor_harness(monkeypatch: pytest.MonkeyPatch, allowed: set[str]) -> Harness:
    harness = Harness(monkeypatch, context_branch=3, allowed=allowed)
    visitor = synthetic_visitor()
    monkeypatch.setattr(VisitorManagementService, "list_visitors", lambda self, **kw: ([visitor], 1))
    monkeypatch.setattr(VisitorManagementService, "get_visitor", lambda self, visitor_id: visitor)
    monkeypatch.setattr(VisitorManagementService, "create_visitor", lambda self, payload, actor_id, audit: visitor)
    monkeypatch.setattr(VisitorManagementService, "update_visitor", lambda self, vid, payload, actor_id, audit: visitor)
    monkeypatch.setattr(VisitorManagementService, "set_active", lambda self, vid, active, actor_id, audit: visitor)
    return harness


def all_variants(client: TestClient) -> list[dict]:
    listing = client.get("/api/visitors")
    detail = client.get("/api/visitors/1")
    created = client.post("/api/visitors", json={"first_name": "Ana", "last_name": "Ejemplo"})
    updated = client.patch("/api/visitors/1", json={"company": "X"})
    activated = client.post("/api/visitors/1/activate")
    deactivated = client.post("/api/visitors/1/deactivate")
    for response in (listing, detail, created, updated, activated, deactivated):
        assert response.status_code in (200, 201), response.text
    return [listing.json()["items"][0], detail.json(), created.json(), updated.json(), activated.json(), deactivated.json()]


OPERATIONAL = {"VIEW_VISITORS", "CREATE_VISITOR", "UPDATE_VISITOR"}


def test_contact_is_masked_everywhere_without_view_visitor_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = visitor_harness(monkeypatch, OPERATIONAL)

    for item in all_variants(harness.client):
        assert item["phone"] == "***23"
        assert item["email"] == "a***@example.test"
        assert item["contact_masked"] is True
        assert item["identification"] != "00112233445" and "*" in item["identification"]
        assert "identification_normalized" not in item


def test_contact_is_visible_with_view_visitor_contact_in_own_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = visitor_harness(monkeypatch, OPERATIONAL | {"VIEW_VISITOR_CONTACT"})

    for item in all_variants(harness.client):
        assert item["phone"] == "8095550123"
        assert item["email"] == "ana.ejemplo@example.test"
        assert item["contact_masked"] is False
    assert ("VIEW_VISITOR_CONTACT", 3) in harness.permission_calls


def test_view_visitor_contact_alone_does_not_grant_visitor_access(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = visitor_harness(monkeypatch, {"VIEW_VISITOR_CONTACT"})

    assert harness.client.get("/api/visitors").status_code == 403


def test_forged_branch_id_cannot_unlock_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = visitor_harness(monkeypatch, OPERATIONAL | {"VIEW_VISITOR_CONTACT"})

    assert harness.client.get("/api/visitors/1?branch_id=9").status_code == 403


def test_masks_keep_nulls_and_short_values_safe() -> None:
    assert mask_phone(None) is None and mask_email(None) is None
    assert mask_phone("1234") == "****"
    assert mask_email("sin-arroba") == "***"


def test_visit_and_report_payloads_do_not_contain_contact_fields() -> None:
    from app.application.dto.reports import VisitReportItem
    from app.application.dto.visits import VisitResponse, VisitVisitorResponse

    for model in (VisitVisitorResponse, VisitResponse, VisitReportItem):
        assert not {"phone", "email"} & set(model.model_fields)


def test_contact_permission_is_branch_scoped_and_not_default_for_operational_roles() -> None:
    scopes = {code: scope for code, _n, _r, _a, scope in PERMISSIONS}

    assert scopes["VIEW_VISITOR_CONTACT"] == "BRANCH"
    assert "VIEW_VISITOR_CONTACT" in ROLE_PERMISSION_CODES["SUPER_ADMIN"]
    assert "VIEW_VISITOR_CONTACT" in ROLE_PERMISSION_CODES["ADMIN"]
    assert "VIEW_VISITOR_CONTACT" not in ROLE_PERMISSION_CODES["RECEPTIONIST"]
    assert "VIEW_VISITOR_CONTACT" not in ROLE_PERMISSION_CODES["USER"]


def test_openapi_declares_contact_masked() -> None:
    schema = TestClient(app).get("/openapi.json").json()["components"]["schemas"]["VisitorResponse"]

    assert "contact_masked" in schema["properties"]
    assert "identification_normalized" not in schema["properties"]


# ---- Inactivos por catálogo ----

@pytest.mark.parametrize(
    "path, allowed, expected",
    [
        ("/api/visitor-types?include_inactive=true", {"VIEW_VISITORS"}, 403),
        ("/api/visitor-types?include_inactive=true", {"VIEW_VISITORS", "MANAGE_BRANCHES", "MANAGE_VISIT_REASONS"}, 403),
        ("/api/visitor-types?include_inactive=true", {"VIEW_VISITORS", "MANAGE_VISITOR_TYPES"}, 200),
        ("/api/visit-reasons?include_inactive=true", {"VIEW_VISITS"}, 403),
        ("/api/visit-reasons?include_inactive=true", {"VIEW_VISITS", "MANAGE_BRANCHES", "MANAGE_VISITOR_TYPES"}, 403),
        ("/api/visit-reasons?include_inactive=true", {"VIEW_VISITS", "MANAGE_VISIT_REASONS"}, 200),
        ("/api/branches?include_inactive=true", {"VIEW_VISITS", "MANAGE_VISITOR_TYPES", "MANAGE_VISIT_REASONS"}, 403),
        ("/api/branches?include_inactive=true", {"MANAGE_BRANCHES"}, 200),
        ("/api/branch-types?include_inactive=true", {"VIEW_VISITS", "MANAGE_VISITOR_TYPES"}, 403),
        ("/api/branch-types?include_inactive=true", {"MANAGE_BRANCHES"}, 200),
    ],
)
def test_include_inactive_requires_the_catalog_specific_admin_permission(monkeypatch: pytest.MonkeyPatch, path: str, allowed: set[str], expected: int) -> None:
    env = CatalogEnv(monkeypatch, allowed=allowed)

    assert env.client.get(path).status_code == expected


def test_catalog_admins_without_branch_assignment_can_list_their_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    env = CatalogEnv(monkeypatch, allowed={"MANAGE_VISITOR_TYPES", "MANAGE_VISIT_REASONS"}, with_context=False)

    assert env.codes("/api/visitor-types") == ["V1"]
    assert env.codes("/api/visit-reasons") == ["R1"]
    assert env.client.get("/api/branches").status_code == 403


def test_roles_have_no_inactive_option_and_never_list_inactive(monkeypatch: pytest.MonkeyPatch) -> None:
    env = CatalogEnv(monkeypatch, allowed={"MANAGE_USERS"}, with_context=False)

    assert env.codes("/api/roles?include_inactive=true") == ["ROLE_A"]


def test_historical_visit_queries_do_not_filter_on_inactive_catalog_entries() -> None:
    text = visits_sql()

    assert "visit_reasons.is_active" not in text
    assert "visitor_types.is_active" not in text
    assert "branches.is_active" not in text


# ---- Scripts obsoletos ----

@pytest.mark.parametrize("name", ["seed_roles", "seed_permissions", "bootstrap_user"])
def test_obsolete_scripts_refuse_to_run_and_name_current_procedure(name: str) -> None:
    import importlib

    module = importlib.import_module(f"scripts.{name}")

    with pytest.raises(SystemExit, match="seed_authorization"):
        module.main()
    assert not hasattr(module, "SessionLocal")
