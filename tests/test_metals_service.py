"""Tests for MetalsService tick assembly: live H/L tracking across the Stockholm day."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from goldsilver.data.models import GOLD
from goldsilver.data.service import MetalsService


def test_make_tick_tracks_running_high_low_within_day() -> None:
    service = MetalsService()
    at = datetime(2026, 6, 10, 20, 0, tzinfo=timezone.utc)

    service._make_tick(GOLD, 2500.0, at)
    tick = service._make_tick(GOLD, 2510.0, at + timedelta(minutes=1))

    assert tick.day_high == 2510.0
    assert tick.day_low == 2500.0


def test_make_tick_resets_high_low_after_stockholm_midnight() -> None:
    service = MetalsService()
    before_midnight = datetime(2026, 6, 10, 20, 0, tzinfo=timezone.utc)
    after_midnight = datetime(2026, 6, 10, 22, 30, tzinfo=timezone.utc)

    service._make_tick(GOLD, 2500.0, before_midnight)
    service._make_tick(GOLD, 2510.0, before_midnight + timedelta(minutes=1))
    tick = service._make_tick(GOLD, 2490.0, after_midnight)

    assert tick.day_high == 2490.0
    assert tick.day_low == 2490.0
