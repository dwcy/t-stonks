"""Tests for forward-looking calendar expectations: parse, merge, and store."""

from __future__ import annotations

from datetime import datetime, timezone

from goldsilver.data.calendar_actuals_store import StoredActuals
from goldsilver.data.calendar_expectations import merge_expected, parse_expected
from goldsilver.data.models_macro import CalendarEvent

_EXPECTED_COMMENT = (
    '<!-- EXPECTED: {"found": true, "forecast": "3.1%", "previous": "3.0%", '
    '"summary": "Consensus sees CPI 3.1%.", "analysis": {"gold": "bearish", '
    '"silver": "neutral", "usd": "bullish", "rationale": "A beat lifts USD."}} -->'
)


def _event() -> CalendarEvent:
    return CalendarEvent(
        source="FED",
        title="Retail Sales (Jun)",
        scheduled_time=datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc),
        importance="HIGH",
    )


def test_parse_expected_reads_forecast_and_analysis() -> None:
    figures = parse_expected(_EXPECTED_COMMENT)

    assert figures is not None
    assert figures.forecast == "3.1%"
    assert figures.analysis is not None and figures.analysis.usd == "bullish"


def test_parse_expected_returns_none_without_marker() -> None:
    assert parse_expected("no comment here") is None


def test_merge_expected_fills_forecast_without_releasing() -> None:
    figures = parse_expected(_EXPECTED_COMMENT)
    assert figures is not None

    merged = merge_expected(_event(), figures)

    assert merged.forecast == "3.1%"
    assert merged.actual is None
    assert merged.status == "SCHEDULED"


def test_merge_expected_marks_event_as_expectation() -> None:
    figures = parse_expected(_EXPECTED_COMMENT)
    assert figures is not None

    merged = merge_expected(_event(), figures)

    assert merged.is_expectation is True
    assert merged.analysis is not None and merged.analysis.surprise == "na"


def test_stored_preview_record_applies_without_releasing() -> None:
    figures = parse_expected(_EXPECTED_COMMENT)
    assert figures is not None
    preview = merge_expected(_event(), figures)
    record = StoredActuals.from_event(preview)

    applied = record.apply_to(_event())

    assert applied.forecast == "3.1%"
    assert applied.expected_summary == "Consensus sees CPI 3.1%."
    assert applied.actual is None
    assert applied.status == "SCHEDULED"


def test_stored_released_record_still_releases() -> None:
    released = _event().model_copy(
        update={"actual": "3.4%", "forecast": "3.1%", "status": "RELEASED"}
    )
    record = StoredActuals.from_event(released)

    applied = record.apply_to(_event())

    assert applied.actual == "3.4%"
    assert applied.status == "RELEASED"
