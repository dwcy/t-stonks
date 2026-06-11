"""Tests for SimulatorSummary analytics: win rate, average win/loss, max drawdown."""

from __future__ import annotations

from datetime import datetime, timezone

from goldsilver.data.models import GOLD
from goldsilver.data.settings import SimulatorSettings
from goldsilver.data.trade_models import Trade
from goldsilver.data.trades_service import TradesService


def _sell(pnl: float, minute: int) -> Trade:
    return Trade(
        trade_id=f"t{minute}",
        ts_utc=datetime(2026, 6, 10, 12, minute, tzinfo=timezone.utc),
        symbol=GOLD,
        side="SELL",
        units=1.0,
        price=100.0,
        cash_delta=100.0,
        realized_pnl=pnl,
        reason="signal_sell",
    )


def test_analytics_from_closed_trades() -> None:
    svc = TradesService(SimulatorSettings(initial_deposit=1000.0), persist=False)
    svc._trades = [_sell(30.0, 1), _sell(-10.0, 2), _sell(10.0, 3), _sell(-50.0, 4)]

    s = svc.summary({})

    assert s.win_rate == 50.0
    assert s.avg_win == 20.0
    assert s.avg_loss == -30.0
    # Equity walk: 1030 → 1020 → 1030 → 980; peak 1030, trough 980.
    assert s.max_drawdown == 50.0


def test_analytics_empty_when_no_closed_trades() -> None:
    svc = TradesService(SimulatorSettings(initial_deposit=1000.0), persist=False)

    s = svc.summary({})

    assert s.win_rate is None
    assert s.avg_win is None
    assert s.avg_loss is None
    assert s.max_drawdown == 0.0
