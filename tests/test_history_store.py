"""Unit tests for the daily history disk archive."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import goldsilver.data.history_store as hs
from goldsilver.data.history_store import (
    available_days,
    day_path,
    load_day,
    save_day,
    split_by_day,
)
from goldsilver.data.models import GOLD, Bar

STOCKHOLM = ZoneInfo("Europe/Stockholm")


@pytest.fixture(autouse=True)
def isolated_history_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "history"
    monkeypatch.setattr(hs, "HISTORY_DIR", root)
    return root


def _bar(ts: datetime, close: float = 2000.0) -> Bar:
    return Bar(
        symbol=GOLD,
        time=ts.astimezone(timezone.utc),
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=10.0,
    )


def test_save_then_load_round_trips_bars() -> None:
    day = date(2026, 6, 3)
    base = datetime(2026, 6, 3, 10, 0, tzinfo=STOCKHOLM)
    bars = [_bar(base + timedelta(minutes=i), 2000.0 + i) for i in range(5)]

    save_day(GOLD, day, bars)

    assert load_day(GOLD, day) == bars


def test_split_by_day_groups_on_stockholm_date() -> None:
    before_midnight = _bar(datetime(2026, 6, 3, 23, 30, tzinfo=STOCKHOLM))
    after_midnight = _bar(datetime(2026, 6, 4, 0, 30, tzinfo=STOCKHOLM))

    grouped = split_by_day([before_midnight, after_midnight])

    assert set(grouped) == {date(2026, 6, 3), date(2026, 6, 4)}
    assert grouped[date(2026, 6, 3)] == [before_midnight]


def test_available_days_sorted_newest_first() -> None:
    base = datetime(2026, 6, 1, 10, 0, tzinfo=STOCKHOLM)
    save_day(GOLD, date(2026, 6, 1), [_bar(base)])
    save_day(GOLD, date(2026, 6, 3), [_bar(base)])

    assert available_days(GOLD) == [date(2026, 6, 3), date(2026, 6, 1)]


def test_load_missing_day_returns_empty() -> None:
    assert load_day(GOLD, date(2099, 1, 1)) == []


def test_corrupt_file_returns_empty() -> None:
    day = date(2026, 6, 3)
    path = day_path(GOLD, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    assert load_day(GOLD, day) == []
