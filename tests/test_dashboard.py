from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.application.services.dashboard import DashboardScope, DashboardService
from app.core.exceptions import ValidationError


class Row:
    def __init__(self, **values):
        self.__dict__.update(values)


class Result:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def one(self):
        return self.rows[0]


class FakeSession:
    def __init__(self, rows=None, scalar_values=None):
        self.rows = rows or []
        self.scalar_values = iter(scalar_values or [])
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)
        return Result(self.rows)

    def scalar(self, statement):
        self.statements.append(statement)
        try:
            return next(self.scalar_values)
        except StopIteration:
            return 0


def test_branch_summary_contains_scope_and_aggregates() -> None:
    session = FakeSession(rows=[Row(total_visits=10, active_visits=2, completed_visits=7, cancelled_visits=1, unique_visitors=8)])
    result = DashboardService(session).summary(DashboardScope(branch_id=3, is_global=False), date(2026, 9, 1), date(2026, 9, 15))

    assert result["scope"] == "branch"
    assert result["branch_id"] == 3
    assert result["total_visits"] == 10
    assert result["unique_visitors"] == 8
    assert any("visits.branch_id" in str(statement) for statement in session.statements)


def test_global_summary_has_no_branch_filter() -> None:
    session = FakeSession(rows=[Row(total_visits=4, active_visits=1, completed_visits=2, cancelled_visits=1, unique_visitors=3)])
    result = DashboardService(session).summary(DashboardScope(branch_id=None, is_global=True))

    assert result["scope"] == "global"
    assert result["branch_id"] is None
    assert not any("visits.branch_id" in str(statement) for statement in session.statements)


def test_daily_series_uses_sql_group_by() -> None:
    session = FakeSession(rows=[Row(visit_date=date(2026, 9, 1), total=4)])
    result = DashboardService(session).visits_by_day(DashboardScope(branch_id=3, is_global=False))

    assert result == [{"date": date(2026, 9, 1), "total": 4}]
    statement = str(session.statements[0]).upper()
    assert "GROUP BY" in statement
    assert "VISITS.BRANCH_ID" in statement


def test_status_distribution_is_aggregated_in_sql() -> None:
    session = FakeSession(rows=[Row(code="ACTIVE", total=2), Row(code="COMPLETED", total=5)])
    result = DashboardService(session).visits_by_status(DashboardScope(branch_id=3, is_global=False))

    assert result[0]["code"] == "ACTIVE"
    assert result[1]["total"] == 5
    assert "GROUP BY" in str(session.statements[0]).upper()


def test_reason_distribution_is_aggregated_in_sql() -> None:
    session = FakeSession(rows=[Row(code="MEETING", label="Meeting", total=5)])
    result = DashboardService(session).visits_by_reason(DashboardScope(branch_id=3, is_global=False))

    assert result == [{"code": "MEETING", "label": "Meeting", "total": 5}]
    assert "VISIT_REASONS" in str(session.statements[0]).upper()


def test_invalid_date_range_is_rejected() -> None:
    session = FakeSession(rows=[Row(total_visits=0, active_visits=0, completed_visits=0, cancelled_visits=0, unique_visitors=0)])

    with pytest.raises(ValidationError):
        DashboardService(session).summary(DashboardScope(branch_id=3, is_global=False), date(2026, 9, 15), date(2026, 9, 1))


def test_dashboard_date_range_uses_inclusive_start_and_exclusive_end() -> None:
    session = FakeSession(rows=[Row(total_visits=0, active_visits=0, completed_visits=0, cancelled_visits=0, unique_visitors=0)])

    DashboardService(session).summary(
        DashboardScope(branch_id=3, is_global=False),
        datetime(2026, 9, 1, 10, tzinfo=timezone.utc),
        datetime(2026, 9, 1, 11, tzinfo=timezone.utc),
    )

    statement = str(session.statements[0]).upper()
    assert "VISITS.ENTRY_AT >=" in statement
    assert "VISITS.ENTRY_AT <" in statement


def test_missing_branch_context_is_rejected() -> None:
    session = FakeSession(rows=[Row(total_visits=0, active_visits=0, completed_visits=0, cancelled_visits=0, unique_visitors=0)])

    with pytest.raises(ValidationError):
        DashboardService(session).summary(DashboardScope(branch_id=None, is_global=False))
