"""Tests for the report scheduler: boundary math and enable/no-overlap behavior."""

from __future__ import annotations

import asyncio
from datetime import datetime

from goldsilver.data.session import STOCKHOLM
from goldsilver.reports.scheduler import (
    ReportScheduler,
    seconds_until_next_boundary,
)


def _sthlm(h: int, m: int, s: int = 0) -> datetime:
    return datetime(2026, 6, 8, h, m, s, tzinfo=STOCKHOLM)


def test_hourly_boundary() -> None:
    assert seconds_until_next_boundary(_sthlm(14, 0, 0), 60) == 3600
    assert seconds_until_next_boundary(_sthlm(14, 30, 0), 60) == 1800
    assert seconds_until_next_boundary(_sthlm(14, 59, 30), 60) == 30


def test_half_hour_boundary() -> None:
    assert seconds_until_next_boundary(_sthlm(14, 10, 0), 30) == 1200
    assert seconds_until_next_boundary(_sthlm(14, 45, 0), 30) == 900


def test_boundary_never_zero() -> None:
    # Exactly on a boundary -> next full interval, not 0.
    assert seconds_until_next_boundary(_sthlm(14, 0, 0), 30) == 1800


class _FakeService:
    def __init__(self) -> None:
        self.calls = 0

    async def run_all(self):
        self.calls += 1
        return []


async def test_disabled_does_not_run(monkeypatch) -> None:
    import goldsilver.reports.scheduler as mod

    monkeypatch.setattr(mod, "seconds_until_next_boundary", lambda now, interval: 0.01)
    svc = _FakeService()
    sched = ReportScheduler(
        svc,  # type: ignore[arg-type]
        enabled=lambda: False,
        interval_minutes=lambda: 60,
    )
    task = asyncio.create_task(sched.run_loop())
    await asyncio.sleep(0.05)
    sched.request_stop()
    await asyncio.sleep(0.05)
    task.cancel()
    assert svc.calls == 0


async def test_enabled_runs_then_stops(monkeypatch) -> None:
    import goldsilver.reports.scheduler as mod

    monkeypatch.setattr(mod, "seconds_until_next_boundary", lambda now, interval: 0.01)
    svc = _FakeService()
    sched = ReportScheduler(
        svc,  # type: ignore[arg-type]
        enabled=lambda: True,
        interval_minutes=lambda: 60,
    )
    task = asyncio.create_task(sched.run_loop())
    await asyncio.sleep(0.05)
    sched.request_stop()
    await asyncio.sleep(0.05)
    task.cancel()
    assert svc.calls >= 1
