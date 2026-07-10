"""Tests for fetch_daily_history() parsing and DailyChange derivation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from marketcore.models import Bar
from marketcore.services import stock_service
from marketcore.widgets.daily_change_strip import compute_daily_changes


def _fake_history_df() -> pd.DataFrame:
    index = pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03"], utc=True)
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 103.0],
            "High": [102.0, 104.0, 105.0],
            "Low": [99.0, 100.5, 102.0],
            "Close": [101.0, 103.0, 104.0],
            "Volume": [1000.0, 1200.0, 1100.0],
        },
        index=index,
    )


def test_fetch_daily_history_parses_ohlcv(monkeypatch) -> None:
    class _FakeTicker:
        def __init__(self, sym: str) -> None:
            self.sym = sym

        def history(self, period: str, interval: str):
            assert interval == "1d"
            return _fake_history_df()

    monkeypatch.setattr(stock_service.yf, "Ticker", _FakeTicker)

    bars = stock_service.fetch_daily_history("NVDA")

    assert len(bars) == 3
    assert bars[0].symbol == "NVDA"
    assert bars[-1].close == 104.0
    assert all(b.time.tzinfo is not None for b in bars)


def test_fetch_daily_history_returns_empty_on_failure(monkeypatch) -> None:
    class _FailingTicker:
        def __init__(self, sym: str) -> None:
            pass

        def history(self, period: str, interval: str):
            raise RuntimeError("network down")

    monkeypatch.setattr(stock_service.yf, "Ticker", _FailingTicker)

    assert stock_service.fetch_daily_history("NVDA") == []


def _bars() -> list[Bar]:
    base = datetime(2026, 6, 1, tzinfo=timezone.utc)
    closes = [100.0, 105.0, 105.0, 100.0]
    return [
        Bar(
            symbol="X",
            time=base.replace(day=1 + i),
            open=c,
            high=c,
            low=c,
            close=c,
            volume=1.0,
        )
        for i, c in enumerate(closes)
    ]


def test_compute_daily_changes_derives_direction() -> None:
    changes = compute_daily_changes(_bars())

    assert len(changes) == 3
    assert changes[0].direction == "up"
    assert changes[1].direction == "flat"
    assert changes[2].direction == "down"


def test_compute_daily_changes_caps_at_max_days() -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [
        Bar(
            symbol="X",
            time=base + timedelta(days=i),
            open=1.0,
            high=1.0,
            low=1.0,
            close=float(100 + i),
            volume=1.0,
        )
        for i in range(50)
    ]

    changes = compute_daily_changes(bars, max_days=40)

    assert len(changes) == 40
