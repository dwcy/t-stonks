"""Regression tests for the OMX 0w day-cell arrows."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from textual.app import App, ComposeResult

from goldsilver.data.models_macro import OmxDay, OmxSnapshot
from goldsilver.widgets.omx_strip import OmxStrip

STOCKHOLM = ZoneInfo("Europe/Stockholm")


class _Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield OmxStrip()


def _overnight_snapshot() -> OmxSnapshot:
    # Thursday 2026-06-04, 06:00 (before open); last session was Wed 2026-06-03,
    # which is not yet in the daily history feed (only its live close % is known).
    fetched = datetime(2026, 6, 4, 6, 0, tzinfo=STOCKHOLM).astimezone(timezone.utc)
    history = [
        OmxDay(date=date(2026, 6, 1), close=2500.0, change_percent=-0.5),
        OmxDay(date=date(2026, 6, 2), close=2520.0, change_percent=0.8),
    ]
    return OmxSnapshot(
        days=tuple(history),
        current_price=2512.0,
        current_change_percent=-0.30,
        fetched_at=fetched,
        market_open=False,
        latest_session_date=date(2026, 6, 3),
        latest_session_close_time=datetime(2026, 6, 3, 17, 30, tzinfo=STOCKHOLM),
        ytd_change_percent=None,
    )


def _zero_week_symbols(plain: str) -> list[str]:
    segment = plain.split("0w", 1)[1].split("]", 1)[0]
    return segment.split("%) ", 1)[1].split()


@pytest.mark.asyncio
async def test_last_session_gets_arrow_today_pre_open_stays_pending() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        strip = app.query_one(OmxStrip)
        strip.apply_snapshot(_overnight_snapshot())
        await pilot.pause()
        plain = str(strip.render())

    # Mon ▼, Tue ▲, Wed ▼ (last session, injected), Thu x (today, not started), Fri -
    assert _zero_week_symbols(plain) == ["▼", "▲", "▼", "x", "-"]
