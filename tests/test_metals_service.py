"""Tests for MetalsService tick assembly: live H/L tracking across the Stockholm day."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from goldsilver.data.models import GOLD
from goldsilver.data.service import MetalsService, _AvanzaSession


def test_make_tick_tracks_running_high_low_within_day() -> None:
    service = MetalsService()
    at = datetime(2026, 6, 10, 20, 0, tzinfo=timezone.utc)

    service._make_tick(GOLD, 2500.0, at)
    tick = service._make_tick(GOLD, 2510.0, at + timedelta(minutes=1))

    assert tick.day_high == 2510.0
    assert tick.day_low == 2500.0


def test_make_tick_uses_avanza_baseline_for_change() -> None:
    service = MetalsService()
    service._avanza[GOLD] = _AvanzaSession(prev_close=2400.0, high=2520.0, low=2380.0)
    at = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)

    tick = service._make_tick(GOLD, 2500.0, at)

    assert tick.change == 100.0
    assert tick.change_percent == pytest.approx(100.0 / 2400.0 * 100.0)
    assert tick.day_high == 2520.0
    assert tick.day_low == 2380.0


def test_stale_due_after_four_quiet_poll_intervals() -> None:
    service = MetalsService(poll_interval_s=5.0)

    assert not service._stale_due(100.0)  # no payload ever accepted
    service._last_payload_mono = 100.0
    assert not service._stale_due(119.9)
    assert service._stale_due(120.0)
    service._stale_notified = True
    assert not service._stale_due(500.0)  # only notify once per stall


def test_make_tick_resets_high_low_after_stockholm_midnight() -> None:
    service = MetalsService()
    before_midnight = datetime(2026, 6, 10, 20, 0, tzinfo=timezone.utc)
    after_midnight = datetime(2026, 6, 10, 22, 30, tzinfo=timezone.utc)

    service._make_tick(GOLD, 2500.0, before_midnight)
    service._make_tick(GOLD, 2510.0, before_midnight + timedelta(minutes=1))
    tick = service._make_tick(GOLD, 2490.0, after_midnight)

    assert tick.day_high == 2490.0
    assert tick.day_low == 2490.0
