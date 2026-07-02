"""Tests for CalendarService auto-fetch of released actuals."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from goldsilver.data import calendar_actuals, calendar_service
from goldsilver.data.calendar_actuals_store import CalendarActualsStore
from goldsilver.data.calendar_service import CalendarService
from goldsilver.data.models_macro import CalendarDay, CalendarEvent, CalendarSnapshot
from goldsilver.data.settings import CalendarSettings
from goldsilver.data.session import STOCKHOLM
from goldsilver.reports.claude_runner import ClaudeResult
from goldsilver.reports.models import ReportStatus

_SAMPLE = (
    '<!-- RELEASED: {"found": true, "actual": "3.2%", "forecast": "3.1%", '
    '"previous": "3.0%", "summary": "CPI hot."} -->'
)


def _snapshot_with_passed_high() -> CalendarSnapshot:
    now = datetime.now(STOCKHOLM)
    today = now.date()
    event = CalendarEvent(
        source="FED",
        title="CPI (May)",
        scheduled_time=now - timedelta(hours=1),
        importance="HIGH",
    )
    days = [CalendarDay(date=today, bucket="today", events=(event,))]
    return CalendarSnapshot(
        days=tuple(days),
        fetched_at=datetime.now(timezone.utc),
        status="ok",
    )


@pytest.mark.asyncio
async def test_check_due_fills_passed_event(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def fake_run_claude(*_args: object, **_kwargs: object) -> ClaudeResult:
        return ClaudeResult(status=ReportStatus.SUCCESS, html=_SAMPLE)

    monkeypatch.setattr(calendar_actuals, "run_claude", fake_run_claude)
    monkeypatch.setattr(calendar_service, "find_claude", lambda: "claude")

    emitted: list[CalendarSnapshot] = []

    async def handler(snapshot: CalendarSnapshot) -> None:
        emitted.append(snapshot)

    service = CalendarService(
        handler=handler,
        actuals_settings_provider=lambda: CalendarSettings(actuals_enabled=True),
        actuals_store=CalendarActualsStore(tmp_path / "actuals.json"),
    )
    service._last_snapshot = _snapshot_with_passed_high()

    await service._check_due()

    assert len(emitted) == 1
    event = emitted[0].days[0].events[0]
    assert event.status == "RELEASED"
    assert event.actual == "3.2%"


@pytest.mark.asyncio
async def test_fetch_actuals_now_works_when_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def fake_run_claude(*_args: object, **_kwargs: object) -> ClaudeResult:
        return ClaudeResult(status=ReportStatus.SUCCESS, html=_SAMPLE)

    monkeypatch.setattr(calendar_actuals, "run_claude", fake_run_claude)
    monkeypatch.setattr(calendar_service, "find_claude", lambda: "claude")

    emitted: list[CalendarSnapshot] = []

    async def handler(snapshot: CalendarSnapshot) -> None:
        emitted.append(snapshot)

    service = CalendarService(
        handler=handler,
        actuals_settings_provider=lambda: CalendarSettings(actuals_enabled=False),
        actuals_store=CalendarActualsStore(tmp_path / "actuals.json"),
    )
    snapshot = _snapshot_with_passed_high()
    service._last_snapshot = snapshot
    event = snapshot.days[0].events[0]

    updated = await service.fetch_actuals_now(event)

    assert updated is not None
    assert updated.status == "RELEASED"
    assert len(emitted) == 1
    assert emitted[0].days[0].events[0].actual == "3.2%"


@pytest.mark.asyncio
async def test_fetch_actuals_now_passes_same_day_sibling_into_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured_prompts: list[str] = []

    async def fake_run_claude(prompt: str, **_kwargs: object) -> ClaudeResult:
        captured_prompts.append(prompt)
        return ClaudeResult(status=ReportStatus.SUCCESS, html=_SAMPLE)

    monkeypatch.setattr(calendar_actuals, "run_claude", fake_run_claude)
    monkeypatch.setattr(calendar_service, "find_claude", lambda: "claude")

    service = CalendarService(
        actuals_settings_provider=lambda: CalendarSettings(actuals_enabled=False),
        actuals_store=CalendarActualsStore(tmp_path / "actuals.json"),
    )
    now = datetime.now(STOCKHOLM)
    today = now.date()
    claims = CalendarEvent(
        source="FED",
        title="Unemployment Insurance Weekly Claims Report",
        scheduled_time=now - timedelta(hours=1),
        importance="MED",
    )
    payrolls = CalendarEvent(
        source="FED",
        title="Employment Situation",
        scheduled_time=now - timedelta(hours=1),
        importance="HIGH",
    )
    service._last_snapshot = CalendarSnapshot(
        days=(CalendarDay(date=today, bucket="today", events=(claims, payrolls)),),
        fetched_at=datetime.now(timezone.utc),
        status="ok",
    )

    await service.fetch_actuals_now(claims)

    assert len(captured_prompts) == 1
    assert "Employment Situation" in captured_prompts[0]


@pytest.mark.asyncio
async def test_check_due_passes_same_day_sibling_into_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured_prompts: list[str] = []

    async def fake_run_claude(prompt: str, **_kwargs: object) -> ClaudeResult:
        captured_prompts.append(prompt)
        return ClaudeResult(status=ReportStatus.SUCCESS, html=_SAMPLE)

    monkeypatch.setattr(calendar_actuals, "run_claude", fake_run_claude)
    monkeypatch.setattr(calendar_service, "find_claude", lambda: "claude")

    service = CalendarService(
        actuals_settings_provider=lambda: CalendarSettings(actuals_enabled=True),
        actuals_store=CalendarActualsStore(tmp_path / "actuals.json"),
    )
    now = datetime.now(STOCKHOLM)
    today = now.date()
    claims = CalendarEvent(
        source="FED",
        title="Unemployment Insurance Weekly Claims Report",
        scheduled_time=now - timedelta(hours=1),
        importance="MED",
    )
    payrolls = CalendarEvent(
        source="FED",
        title="Employment Situation",
        scheduled_time=now - timedelta(hours=1),
        importance="HIGH",
    )
    service._last_snapshot = CalendarSnapshot(
        days=(CalendarDay(date=today, bucket="today", events=(claims, payrolls)),),
        fetched_at=datetime.now(timezone.utc),
        status="ok",
    )

    await service._check_due()

    assert len(captured_prompts) == 2
    joined = "\n".join(captured_prompts)
    assert "Employment Situation" in joined
    assert "Unemployment Insurance Weekly Claims Report" in joined


@pytest.mark.asyncio
async def test_check_due_disabled_does_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(calendar_service, "find_claude", lambda: "claude")

    emitted: list[CalendarSnapshot] = []

    async def handler(snapshot: CalendarSnapshot) -> None:
        emitted.append(snapshot)

    service = CalendarService(
        handler=handler,
        actuals_settings_provider=lambda: CalendarSettings(actuals_enabled=False),
    )
    service._last_snapshot = _snapshot_with_passed_high()

    await service._check_due()

    assert emitted == []
