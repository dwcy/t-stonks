"""Tests for released-figures parsing, prompt building, and the ActualsFetcher."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from goldsilver.data import calendar_actuals
from goldsilver.data.calendar_actuals import (
    ActualsFetcher,
    build_actuals_prompt,
    parse_released,
    same_day_titles,
)
from goldsilver.data.models_macro import (
    CalendarDay,
    CalendarEvent,
    CalendarSnapshot,
)
from goldsilver.reports.claude_runner import ClaudeResult
from goldsilver.reports.models import ReportStatus

STOCKHOLM = ZoneInfo("Europe/Stockholm")

_SAMPLE = (
    'prose noise\n<!-- RELEASED: {"found": true, "actual": "3.2%", '
    '"forecast": "3.1%", "previous": "3.0%", "summary": "CPI hot."} -->\n'
)


def _event() -> CalendarEvent:
    return CalendarEvent(
        source="FED",
        title="CPI (May)",
        scheduled_time=datetime(2026, 6, 10, 14, 30, tzinfo=STOCKHOLM),
        importance="HIGH",
    )


def test_parse_released_extracts_figures() -> None:
    figures = parse_released(_SAMPLE)

    assert figures is not None
    assert (figures.found, figures.actual, figures.forecast) == (True, "3.2%", "3.1%")


def test_parse_released_without_marker_returns_none() -> None:
    assert parse_released("no marker here") is None


def test_build_actuals_prompt_includes_title_and_date() -> None:
    prompt = build_actuals_prompt(_event())

    assert "CPI (May)" in prompt
    assert "2026-06-10" in prompt


def test_build_actuals_prompt_without_siblings_omits_same_day_note() -> None:
    prompt = build_actuals_prompt(_event())

    assert "scheduled the same day" not in prompt


def test_build_actuals_prompt_with_siblings_names_dominance_check() -> None:
    prompt = build_actuals_prompt(_event(), ("Employment Situation",))

    assert "Employment Situation" in prompt
    assert "scheduled the same day" in prompt


def _sibling_event(title: str, importance: str = "HIGH") -> CalendarEvent:
    return CalendarEvent(
        source="FED",
        title=title,
        scheduled_time=datetime(2026, 6, 10, 14, 30, tzinfo=STOCKHOLM),
        importance=importance,
    )


def test_same_day_titles_returns_other_fetchable_events_same_day() -> None:
    event = _event()
    sibling = _sibling_event("Employment Situation")
    other_day = _sibling_event("PPI (May)")
    low_importance = _sibling_event("Minor Release", importance="LOW")
    today = event.scheduled_time.astimezone(STOCKHOLM).date()
    snapshot = CalendarSnapshot(
        days=(
            CalendarDay(
                date=today,
                bucket="today",
                events=(event, sibling, low_importance),
            ),
            CalendarDay(
                date=today.replace(day=today.day + 1),
                bucket="upcoming",
                events=(other_day,),
            ),
        ),
        fetched_at=event.scheduled_time,
    )

    titles = same_day_titles(snapshot, event)

    assert titles == ("Employment Situation",)


@pytest.mark.asyncio
async def test_fetcher_returns_released_event(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_claude(*_args: object, **_kwargs: object) -> ClaudeResult:
        return ClaudeResult(status=ReportStatus.SUCCESS, html=_SAMPLE)

    monkeypatch.setattr(calendar_actuals, "run_claude", fake_run_claude)
    fetcher = ActualsFetcher()

    updated = await fetcher.fetch(_event())

    assert updated is not None
    assert updated.status == "RELEASED"
    assert updated.actual == "3.2%"
    assert updated.actual_summary == "CPI hot."


@pytest.mark.asyncio
async def test_fetcher_passes_same_day_events_into_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    async def fake_run_claude(prompt: str, **_kwargs: object) -> ClaudeResult:
        captured["prompt"] = prompt
        return ClaudeResult(status=ReportStatus.SUCCESS, html=_SAMPLE)

    monkeypatch.setattr(calendar_actuals, "run_claude", fake_run_claude)
    fetcher = ActualsFetcher()

    await fetcher.fetch(_event(), ("Employment Situation",))

    assert "Employment Situation" in captured["prompt"]


@pytest.mark.asyncio
async def test_fetcher_cli_missing_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_claude(*_args: object, **_kwargs: object) -> ClaudeResult:
        return ClaudeResult(status=ReportStatus.CLI_MISSING, error="no cli")

    monkeypatch.setattr(calendar_actuals, "run_claude", fake_run_claude)
    fetcher = ActualsFetcher()

    assert await fetcher.fetch(_event()) is None


@pytest.mark.asyncio
async def test_fetcher_dedupes_after_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_claude(*_args: object, **_kwargs: object) -> ClaudeResult:
        return ClaudeResult(status=ReportStatus.SUCCESS, html=_SAMPLE)

    monkeypatch.setattr(calendar_actuals, "run_claude", fake_run_claude)
    fetcher = ActualsFetcher()
    event = _event()

    first = await fetcher.fetch(event)
    second = await fetcher.fetch(event)

    assert first is not None
    assert second is None
