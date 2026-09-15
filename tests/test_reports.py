from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.api.dependencies.reports import ReportScope
from app.application.dto.reports import ReportGroupBy, VisitReportFilters
from app.application.services.reports import ReportService
from app.core.exceptions import ValidationError


class Row:
    def __init__(self, **values):
        self.__dict__.update(values)


class Result:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


def detailed_row():
    return Row(
        id=1,
        entry_at=datetime(2026, 9, 1, 10, tzinfo=timezone.utc),
        exit_at=None,
        status="ACTIVE",
        destination="Recepción",
        visited_person="Ana",
        notes=None,
        completed_by_user_id=None,
        cancelled_by_user_id=None,
        cancelled_at=None,
        cancellation_reason=None,
        visitor_id=2,
        identification="402-1234567",
        visitor_first_name="Carlos",
        visitor_last_name="Perez",
        company="Empresa",
        branch_id=3,
        branch_code="B3",
        branch_name="Sucursal 3",
        reason_id=4,
        reason_code="MEETING",
        reason_name="Meeting",
        registered_by_id=7,
        username="admin",
        registered_first_name="Admin",
        registered_last_name="User",
    )


class FakeSession:
    def __init__(self, *, scalar_values=None, rows=None):
        self.scalar_values = iter(scalar_values or [])
        self.rows = rows or []
        self.statements = []

    def scalar(self, statement):
        self.statements.append(statement)
        try:
            return next(self.scalar_values)
        except StopIteration:
            return 0

    def execute(self, statement):
        self.statements.append(statement)
        return Result(self.rows)


def test_branch_report_filters_sql_by_authorized_branch() -> None:
    session = FakeSession(scalar_values=[1], rows=[detailed_row()])
    items, total = ReportService(session).detailed_visits(
        ReportScope(branch_id=3, is_global=False),
        VisitReportFilters(status="ACTIVE"),
        page=1,
        page_size=25,
    )

    assert total == 1
    assert items[0]["branch"]["id"] == 3
    assert any("visits.branch_id" in str(statement) for statement in session.statements)


def test_global_report_can_filter_by_branch_in_sql() -> None:
    session = FakeSession(scalar_values=[2], rows=[])
    ReportService(session).detailed_visits(
        ReportScope(branch_id=5, is_global=True),
        VisitReportFilters(branch_id=5),
        page=1,
        page_size=10,
    )

    assert any("visits.branch_id" in str(statement) for statement in session.statements)


def test_report_does_not_accept_invalid_date_range() -> None:
    session = FakeSession()
    with pytest.raises(ValidationError):
        ReportService(session).detailed_visits(
            ReportScope(branch_id=3, is_global=False),
            VisitReportFilters(
                date_from=datetime(2026, 10, 1, tzinfo=timezone.utc),
                date_to=datetime(2026, 9, 1, tzinfo=timezone.utc),
            ),
            page=1,
            page_size=25,
        )


def test_report_date_range_uses_inclusive_start_and_exclusive_end() -> None:
    session = FakeSession(scalar_values=[0], rows=[])
    ReportService(session).detailed_visits(
        ReportScope(branch_id=3, is_global=False),
        VisitReportFilters(
            date_from=datetime(2026, 9, 1, 10, tzinfo=timezone.utc),
            date_to=datetime(2026, 9, 1, 11, tzinfo=timezone.utc),
        ),
        page=1,
        page_size=25,
    )

    statement = " ".join(str(item) for item in session.statements).upper()
    assert "VISITS.ENTRY_AT >=" in statement
    assert "VISITS.ENTRY_AT <" in statement


def test_report_item_masks_identification() -> None:
    session = FakeSession(scalar_values=[1], rows=[detailed_row()])
    items, _ = ReportService(session).detailed_visits(
        ReportScope(branch_id=3, is_global=False),
        VisitReportFilters(),
        page=1,
        page_size=25,
    )

    assert items[0]["visitor"]["identification"] != "402-1234567"
    assert "identification_normalized" not in items[0]["visitor"]


def test_status_summary_uses_group_by() -> None:
    session = FakeSession(rows=[Row(code="ACTIVE", label="ACTIVE", total=4)])
    result = ReportService(session).grouped_visits(
        ReportScope(branch_id=3, is_global=False),
        VisitReportFilters(),
        ReportGroupBy.STATUS,
    )

    assert result == [{"code": "ACTIVE", "label": "ACTIVE", "total": 4}]
    assert "GROUP BY" in str(session.statements[0]).upper()


def test_branch_grouping_requires_global_scope() -> None:
    with pytest.raises(ValidationError):
        ReportService(FakeSession()).grouped_visits(
            ReportScope(branch_id=3, is_global=False),
            VisitReportFilters(),
            ReportGroupBy.BRANCH,
        )
