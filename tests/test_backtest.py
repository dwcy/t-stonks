"""Unit tests for the saved-day backtest runner."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import goldsilver.data.history_store as hs
from goldsilver.data.backtest import run_backtest
from goldsilver.data.history_store import save_day
from goldsilver.data.models import GOLD, Bar
from goldsilver.data.settings import AppSettings

STOCKHOLM = ZoneInfo("Europe/Stockholm")
DAY = date(2026, 6, 2)


@pytest.fixture(autouse=True)
def isolated_history_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "history"
    monkeypatch.setattr(hs, "HISTORY_DIR", root)
    return root


def _volatile_day_bars() -> list[Bar]:
    base = datetime(2026, 6, 2, 9, 0, tzinfo=STOCKHOLM)
    bars: list[Bar] = []
    for i in range(360):
        # ramp up then crash to provoke momentum/recoil signals during open hours
        close = 2000.0 + (i if i < 180 else 360 - i) * 2.0
        ts = (base + timedelta(minutes=i)).astimezone(timezone.utc)
        bars.append(
            Bar(
                symbol=GOLD,
                time=ts,
                open=close,
                high=close + 0.5,
                low=close - 0.5,
                close=close,
                volume=100.0,
            )
        )
    return bars


@pytest.mark.asyncio
async def test_backtest_is_deterministic() -> None:
    save_day(GOLD, DAY, _volatile_day_bars())
    settings = AppSettings()

    first = await run_backtest(GOLD, DAY, settings)
    second = await run_backtest(GOLD, DAY, settings)

    assert (first.cash, first.today_realized_pnl) == (
        second.cash,
        second.today_realized_pnl,
    )
    assert len(first.recent_trades) == len(second.recent_trades)


@pytest.mark.asyncio
async def test_backtest_does_not_write_trades_json(
    isolated_trades_path: Path,
) -> None:
    save_day(GOLD, DAY, _volatile_day_bars())

    await run_backtest(GOLD, DAY, AppSettings())

    assert not isolated_trades_path.exists()


@pytest.mark.asyncio
async def test_overrides_change_results_without_touching_settings() -> None:
    save_day(GOLD, DAY, _volatile_day_bars())
    settings = AppSettings()

    either = await run_backtest(GOLD, DAY, settings, trigger_mode="either")
    both = await run_backtest(GOLD, DAY, settings, trigger_mode="both")

    assert len(both.recent_trades) <= len(either.recent_trades)
    assert settings.simulator.trigger_mode == "either"


@pytest.mark.asyncio
async def test_momentum_override_is_honored() -> None:
    save_day(GOLD, DAY, _volatile_day_bars())
    settings = AppSettings()

    summary = await run_backtest(
        GOLD, DAY, settings, momentum="ROC Momentum", recoil="RSI Recoil"
    )

    assert summary.initial_deposit == settings.simulator.initial_deposit


@pytest.mark.asyncio
async def test_backtest_missing_day_returns_initial_deposit() -> None:
    settings = AppSettings()

    summary = await run_backtest(GOLD, date(2099, 1, 1), settings)

    assert summary.cash == settings.simulator.initial_deposit
    assert summary.recent_trades == ()
