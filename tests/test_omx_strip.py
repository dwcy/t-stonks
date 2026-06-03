"""Regression test for the OMX 0w today-cell arrow."""

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
    # Thursday 2026-06-04, 06:00 (before open); last session was Wed 2026-06-03.
    fetched = datetime(2026, 6, 4, 6, 0, tzinfo=STOCKHOLM).astimezone(timezone.utc)
    this_week = [
        OmxDay(date=date(2026, 6, 1), close=2500.0, change_percent=0.0),
        OmxDay(date=date(2026, 6, 2), close=2500.0, change_percent=0.0),
        OmxDay(date=date(2026, 6, 3), close=2500.0, change_percent=0.0),
    ]
    return OmxSnapshot(
        days=tuple(this_week),
        current_price=2510.0,
        current_change_percent=0.40,
        fetched_at=fetched,
        market_open=False,
        latest_session_date=date(2026, 6, 3),
        latest_session_close_time=datetime(2026, 6, 3, 17, 30, tzinfo=STOCKHOLM),
        ytd_change_percent=None,
    )


@pytest.mark.asyncio
async def test_today_cell_shows_arrow_when_last_session_was_yesterday() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        strip = app.query_one(OmxStrip)
        strip.apply_snapshot(_overnight_snapshot())
        await pilot.pause()
        plain = str(strip.render())

    assert "0w" in plain
    assert "▲" in plain
