"""Fase E: la búsqueda de visitantes no debe filtrar por contacto sin VIEW_VISITOR_CONTACT."""
from __future__ import annotations

import pytest

from app.application.services.visitors import VisitorManagementService
from app.infrastructure.database.session import get_db
from app.infrastructure.persistence.models import Visitor
from main import app
from tests.sqlite_support import make_session_factory
from tests.test_phase_a import Harness, RecordingSession, sql

OPERATIONAL = {"VIEW_VISITORS", "CREATE_VISITOR", "UPDATE_VISITOR"}


def teardown_function() -> None:
    app.dependency_overrides.clear()


def env(monkeypatch: pytest.MonkeyPatch, allowed: set[str]) -> Harness:
    factory = make_session_factory()
    with factory.begin() as db:
        db.add_all(
            [
                Visitor(first_name="Ana", last_name="Ejemplo", identification="001-1223344-5", identification_normalized="00112233445",
                        phone="8095550123", email="ana.ejemplo@example.test", company="Empresa Ficticia"),
                Visitor(first_name="Luis", last_name="Muestra", phone="8095559999", email="luis@example.test"),
            ]
        )

    def session():
        with factory() as db:
            yield db

    harness = Harness(monkeypatch, context_branch=3, allowed=allowed)
    app.dependency_overrides[get_db] = session
    return harness


def search(harness: Harness, term: str) -> dict:
    response = harness.client.get("/api/visitors", params={"search": term})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("term", ["5550123", "8095550123", "ana.ejemplo", "example.test", "@example"])
def test_contact_terms_find_nothing_without_contact_permission(monkeypatch: pytest.MonkeyPatch, term: str) -> None:
    body = search(env(monkeypatch, OPERATIONAL), term)

    assert body["items"] == [] and body["total"] == 0


def test_contact_search_is_indistinguishable_from_a_nonexistent_value(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = env(monkeypatch, OPERATIONAL)

    assert search(harness, "5550123") == search(harness, "no-existe-zzz")
    assert search(harness, "ana.ejemplo@example.test") == search(harness, "nadie@nada.test")


@pytest.mark.parametrize("term", ["Ana", "Ejemplo", "Ficticia", "00112233445"])
def test_unprotected_fields_remain_searchable_and_contact_stays_masked(monkeypatch: pytest.MonkeyPatch, term: str) -> None:
    body = search(env(monkeypatch, OPERATIONAL), term)

    assert body["total"] == 1
    item = body["items"][0]
    assert item["first_name"] == "Ana"
    assert item["phone"] == "***23" and item["email"] == "a***@example.test"
    assert item["contact_masked"] is True
    assert "identification_normalized" not in item


@pytest.mark.parametrize("term, expected", [("5550123", "Ana"), ("ana.ejemplo", "Ana"), ("luis@example", "Luis"), ("Ana", "Ana")])
def test_contact_permission_keeps_contact_search(monkeypatch: pytest.MonkeyPatch, term: str, expected: str) -> None:
    body = search(env(monkeypatch, OPERATIONAL | {"VIEW_VISITOR_CONTACT"}), term)

    assert [item["first_name"] for item in body["items"]] == [expected]
    assert body["items"][0]["contact_masked"] is False
    assert body["items"][0]["phone"] in {"8095550123", "8095559999"}


@pytest.mark.parametrize("allowed", [OPERATIONAL, OPERATIONAL | {"VIEW_VISITOR_CONTACT"}])
def test_forged_branch_id_is_rejected_on_search(monkeypatch: pytest.MonkeyPatch, allowed: set[str]) -> None:
    harness = env(monkeypatch, allowed)

    response = harness.client.get("/api/visitors", params={"search": "Ana", "branch_id": 9})

    assert response.status_code == 403


def test_user_without_assignment_cannot_search(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = Harness(monkeypatch, context_branch=None, allowed=OPERATIONAL | {"VIEW_VISITOR_CONTACT"})

    assert harness.client.get("/api/visitors", params={"search": "5550123"}).status_code == 403


def test_contact_permission_alone_does_not_grant_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = env(monkeypatch, {"VIEW_VISITOR_CONTACT"})

    assert harness.client.get("/api/visitors", params={"search": "5550123"}).status_code == 403


def test_query_excludes_contact_columns_unless_authorized() -> None:
    def query(include_contact: bool) -> str:
        session = RecordingSession()
        VisitorManagementService(session).list_visitors(page=1, page_size=10, search="x", include_contact=include_contact)
        return " ".join(sql(statement) for statement in session.statements)

    default = RecordingSession()
    VisitorManagementService(default).list_visitors(page=1, page_size=10, search="x")
    protected = " ".join(sql(s) for s in default.statements)
    assert "visitors.phone LIKE" not in protected and "visitors.email LIKE" not in protected
    assert "visitors.first_name LIKE" in protected and "identification_normalized LIKE" in protected
    allowed = query(True)
    assert "visitors.phone LIKE" in allowed and "visitors.email LIKE" in allowed


def test_listing_filters_and_detail_still_work(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = env(monkeypatch, OPERATIONAL)

    listing = harness.client.get("/api/visitors").json()
    assert listing["total"] == 2 and [i["first_name"] for i in listing["items"]] == ["Ana", "Luis"]
    assert harness.client.get("/api/visitors", params={"is_active": "false"}).json()["total"] == 0
    assert harness.client.get(f"/api/visitors/{listing['items'][0]['id']}").status_code == 200
    assert harness.client.get("/api/visitors/9999").status_code == 404
