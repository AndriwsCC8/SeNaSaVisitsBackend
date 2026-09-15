from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateIndex
from sqlalchemy.orm import configure_mappers

from app.infrastructure.database.base import Base
from app.infrastructure.persistence import models


EXPECTED_TABLES = {
    "branch_types",
    "branches",
    "users",
    "roles",
    "user_roles",
    "permissions",
    "role_permissions",
    "user_permissions",
    "user_branch_assignments",
    "visitors",
    "visitor_types",
    "visits",
    "visit_reasons",
    "audit_logs",
    "notifications",
}


def test_all_persistence_models_are_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert len(models.__all__) == 15


def test_relationship_mappers_configure_without_ambiguity() -> None:
    configure_mappers()


def test_historical_foreign_keys_use_no_action() -> None:
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.ondelete == "NO ACTION"


def test_required_indexes_and_constraints_are_registered() -> None:
    assignments = Base.metadata.tables["user_branch_assignments"]
    visitors = Base.metadata.tables["visitors"]
    visits = Base.metadata.tables["visits"]
    notifications = Base.metadata.tables["notifications"]

    assert "ux_assignments_active_user" in {index.name for index in assignments.indexes}
    assert "ux_visitors_identification_normalized" in {index.name for index in visitors.indexes}
    assert {"ix_visits_branch_status_entry", "ix_visits_branch_entry", "ix_visits_visitor_entry"}.issubset(
        {index.name for index in visits.indexes}
    )
    assert "ix_notifications_user_read_created" in {index.name for index in notifications.indexes}
    assert {constraint.name for constraint in assignments.constraints} >= {
        "ck_assignments_valid_dates",
        "ck_assignments_status_dates",
        "ck_assignments_status",
    }


def test_sql_server_filtered_indexes_have_mssql_where() -> None:
    assignments = Base.metadata.tables["user_branch_assignments"]
    visitors = Base.metadata.tables["visitors"]
    users = Base.metadata.tables["users"]

    filtered_indexes = {
        index.name: index.dialect_options["mssql"].get("where")
        for table in (assignments, visitors, users)
        for index in table.indexes
        if index.name in {
            "ux_assignments_active_user",
            "ux_visitors_identification_normalized",
            "ix_users_email",
            "ix_users_employee_code",
        }
    }

    assert filtered_indexes["ux_assignments_active_user"] is not None
    assert filtered_indexes["ux_visitors_identification_normalized"] is not None
    assert filtered_indexes["ix_users_email"] is not None
    assert filtered_indexes["ix_users_employee_code"] is not None

    assignment_index = next(index for index in assignments.indexes if index.name == "ux_assignments_active_user")
    ddl = str(CreateIndex(assignment_index).compile(dialect=mssql.dialect()))
    assert "WHERE valid_until IS NULL AND status = 'ACTIVE'" in ddl
