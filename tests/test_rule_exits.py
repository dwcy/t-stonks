"""Tests for stop-loss / take-profit / trailing-stop exits in the simulator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from goldsilver.data.models import GOLD
from goldsilver.data.models_macro import Signal
from goldsilver.data.settings import SimulatorSettings
from goldsilver.data.trades_service import TradesService

_T0 = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)  # 14:00 Stockholm, open


def _sig(action: str, at: datetime) -> Signal:
    return Signal(
        symbol=GOLD,
        strategy="Test",
        kind="momentum",
        action=action,
        intensity_sigma=1.0,
        reason="test",
        at=at,
    )


async def _feed(svc: TradesService, prices: list[tuple[float, str]]) -> None:
    for i, (price, action) in enumerate(prices):
        at = _T0 + timedelta(minutes=i)
        await svc.on_signal(
            symbol=GOLD,
            price=price,
            ts_utc=at,
            mom=_sig(action, at),
            rec=None,
            last_prices={GOLD: (price, at)},
        )


def _service(**rules: float) -> TradesService:
    settings = SimulatorSettings(enabled=True, trigger_mode="either", **rules)
    return TradesService(settings, persist=False)


async def test_stop_loss_exits_full_position() -> None:
    svc = _service(stop_loss_pct=2.0)

    await _feed(svc, [(100.0, "BUY"), (99.0, "NONE"), (97.9, "NONE")])

    reasons = [t.reason for t in svc.summary({}).recent_trades]
    assert reasons == ["signal_buy", "stop_loss"]
    assert not svc.summary({}).positions


async def test_take_profit_exits_with_gain() -> None:
    svc = _service(take_profit_pct=3.0)

    await _feed(svc, [(100.0, "BUY"), (102.0, "NONE"), (103.1, "NONE")])

    trades = svc.summary({}).recent_trades
    assert [t.reason for t in trades] == ["signal_buy", "take_profit"]
    assert trades[-1].realized_pnl > 0


async def test_trailing_stop_fires_from_high_water() -> None:
    svc = _service(trailing_stop_pct=2.0)

    await _feed(
        svc,
        [(100.0, "BUY"), (105.0, "NONE"), (104.0, "NONE"), (102.8, "NONE")],
    )

    reasons = [t.reason for t in svc.summary({}).recent_trades]
    assert reasons == ["signal_buy", "trailing_stop"]


async def test_no_rules_means_no_exit() -> None:
    svc = _service()

    await _feed(svc, [(100.0, "BUY"), (90.0, "NONE"), (120.0, "NONE")])

    reasons = [t.reason for t in svc.summary({}).recent_trades]
    assert reasons == ["signal_buy"]
