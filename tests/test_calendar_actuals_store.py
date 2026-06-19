"""Tests for the calendar actuals disk store and its overlay onto fresh snapshots."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from goldsilver.data import calendar_service
from goldsilver.data.calendar_actuals_store import CalendarActualsStore
from goldsilver.data.calendar_service import CalendarService
from goldsilver.data.models_macro import (
    CalendarDay,
    CalendarEvent,
    CalendarSnapshot,
    EventAnalysis,
)
from goldsilver.data.session import STOCKHOLM


def _event(title: str = "ECB monetary policy decision") -> CalendarEvent:
    return CalendarEvent(
        source="ECB",
        title=title,
        scheduled_time=datetime(2026, 6, 11, 12, 15, tzinfo=timezone.utc),
        importance="HIGH",
    )


def _released(event: CalendarEvent) -> CalendarEvent:
    return event.model_copy(
        update={
            "actual": "hold 2.15%",
            "forecast": "hold",
            "actual_summary": "ECB held the deposit rate at 2.15%.",
            "analysis": EventAnalysis(surprise="inline", rationale="As expected."),
            "status": "RELEASED",
        }
    )


def _snapshot(event: CalendarEvent) -> CalendarSnapshot:
    day = CalendarDay(
        date=event.scheduled_time.astimezone(STOCKHOLM).date(),
        bucket="today",
        events=(event,),
    )
    return CalendarSnapshot(
        days=(day,),
        fetched_at=datetime.now(timezone.utc),
        status="ok",
    )


def test_store_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "actuals.json"
    store = CalendarActualsStore(path)
    store.put(_released(_event()))

    reloaded = CalendarActualsStore(path)
    reloaded.load()
    record = reloaded.get(_event())

    assert record is not None
    assert record.actual == "hold 2.15%"
    assert record.analysis is not None
    assert record.analysis.surprise == "inline"


def test_store_tolerates_missing_and_corrupt_file(tmp_path: Path) -> None:
    missing = CalendarActualsStore(tmp_path / "nope.json")
    missing.load()

    corrupt_path = tmp_path / "bad.json"
    corrupt_path.write_text("{not json", encoding="utf-8")
    corrupt = CalendarActualsStore(corrupt_path)
    corrupt.load()

    assert missing.get(_event()) is None
    assert corrupt.get(_event()) is None


def test_apply_overlays_stored_actuals_onto_fresh_snapshot(tmp_path: Path) -> None:
    store = CalendarActualsStore(tmp_path / "actuals.json")
    store.put(_released(_event()))
    fresh = _snapshot(_event())

    overlaid = store.apply(fresh)
    event = overlaid.days[0].events[0]

    assert event.status == "RELEASED"
    assert event.actual == "hold 2.15%"
    assert event.actual_summary == "ECB held the deposit rate at 2.15%."


def test_apply_leaves_unknown_events_untouched(tmp_path: Path) -> None:
    store = CalendarActualsStore(tmp_path / "actuals.json")
    store.put(_released(_event("CPI (May)")))
    fresh = _snapshot(_event())

    overlaid = store.apply(fresh)

    assert overlaid.days[0].events[0].status == "SCHEDULED"


def test_prune_drops_only_stale_records(tmp_path: Path) -> None:
    store = CalendarActualsStore(tmp_path / "actuals.json")
    old = _event("Old release").model_copy(
        update={"scheduled_time": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)}
    )
    store.put(_released(old))
    store.put(_released(_event()))

    removed = store.prune(datetime(2026, 6, 11, tzinfo=timezone.utc), 30)

    assert removed == 1
    assert store.get(old) is None
    assert store.get(_event()) is not None


@pytest.mark.asyncio
async def test_refresh_no_longer_wipes_released_figures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    event = _event().model_copy(
        update={"scheduled_time": datetime.now(timezone.utc) + timedelta(days=1)}
    )
    store = CalendarActualsStore(tmp_path / "actuals.json")
    store.put(_released(event))
    monkeypatch.setattr(
        calendar_service, "load_static_events", lambda _start, _end: [event]
    )

    emitted: list[CalendarSnapshot] = []

    async def handler(snapshot: CalendarSnapshot) -> None:
        emitted.append(snapshot)

    service = CalendarService(handler=handler, fred_key="", actuals_store=store)
    await service.refresh_now()

    events = [e for day in emitted[0].days for e in day.events]
    assert events
    assert all(e.status == "RELEASED" and e.actual == "hold 2.15%" for e in events)


@pytest.mark.asyncio
async def test_successful_fetch_persists_record_to_disk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from goldsilver.data import calendar_actuals
    from goldsilver.reports.claude_runner import ClaudeResult
    from goldsilver.reports.models import ReportStatus

    sample = (
        '<!-- RELEASED: {"found": true, "actual": "hold 2.15%", "forecast": "hold", '
        '"previous": "2.15%", "summary": "ECB held."} -->'
    )

    async def fake_run_claude(*_args: object, **_kwargs: object) -> ClaudeResult:
        return ClaudeResult(status=ReportStatus.SUCCESS, html=sample)

    monkeypatch.setattr(calendar_actuals, "run_claude", fake_run_claude)
    monkeypatch.setattr(calendar_service, "find_claude", lambda: "claude")

    event = _event()
    path = tmp_path / "actuals.json"
    service = CalendarService(actuals_store=CalendarActualsStore(path))
    service._last_snapshot = _snapshot(event)
    await service.fetch_actuals_now(event)

    reloaded = CalendarActualsStore(path)
    reloaded.load()
    record = reloaded.get(event)

    assert record is not None
    assert record.actual == "hold 2.15%"


@pytest.mark.asyncio
async def test_fetch_actuals_now_serves_from_store_without_claude(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    event = _event()
    path = tmp_path / "actuals.json"
    CalendarActualsStore(path).put(_released(event))
    restarted = CalendarActualsStore(path)
    restarted.load()
    monkeypatch.setattr(calendar_service, "find_claude", lambda: None)

    service = CalendarService(actuals_store=restarted)
    service._last_snapshot = _snapshot(event)

    updated = await service.fetch_actuals_now(event)

    assert updated is not None
    assert updated.status == "RELEASED"
    assert updated.actual == "hold 2.15%"
