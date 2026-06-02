"""Unit tests for TradesService."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from goldsilver.data.models_macro import Signal
from goldsilver.data.settings import SimulatorSettings
from goldsilver.data.trades_service import TradesService


STOCKHOLM = ZoneInfo("Europe/Stockholm")


def _sig(
    action: str, at: datetime, kind: str = "momentum", strategy: str = "m"
) -> Signal:
    return Signal(
        symbol="GOLD",
        strategy=strategy,
        kind=kind,
        action=action,
        intensity_sigma=1.0,
        reason="test",
        at=at,
    )


def _ts(h: int, m: int = 0, day: int = 2) -> datetime:
    return datetime(2026, 6, day, h, m, tzinfo=STOCKHOLM).astimezone(timezone.utc)


@pytest.mark.asyncio
async def test_edge_only_firing(isolated_trades_path: Path) -> None:
    svc = TradesService(SimulatorSettings(enabled=True, trigger_mode="either"))
    base = _ts(10)
    lp = {"GOLD": (2000.0, base)}
    for i in range(5):
        await svc.on_signal(
            symbol="GOLD",
            price=2000.0,
            ts_utc=base + timedelta(seconds=i),
            mom=_sig("BUY", base),
            rec=_sig("NONE", base, kind="recoil", strategy="r"),
            last_prices=lp,
        )
    assert len(svc._trades) == 1
    assert svc._trades[0].side == "BUY"


@pytest.mark.asyncio
async def test_buy_is_ten_percent_of_remaining_cash(isolated_trades_path: Path) -> None:
    svc = TradesService(SimulatorSettings(enabled=True, trigger_mode="either"))
    lp = {"GOLD": (2000.0, _ts(10))}
    for i, action_pair in enumerate(
        [("BUY", "NONE"), ("NONE", "NONE"), ("BUY", "NONE")]
    ):
        ts = _ts(10) + timedelta(seconds=i * 10)
        await svc.on_signal(
            symbol="GOLD",
            price=2000.0,
            ts_utc=ts,
            mom=_sig(action_pair[0], ts),
            rec=_sig(action_pair[1], ts, kind="recoil", strategy="r"),
            last_prices=lp,
        )
    assert svc._state.cash == pytest.approx(81000.0)


@pytest.mark.asyncio
async def test_sell_all_closes_position(isolated_trades_path: Path) -> None:
    svc = TradesService(
        SimulatorSettings(enabled=True, trigger_mode="either", sell_mode="all")
    )
    lp = {"GOLD": (2000.0, _ts(10))}
    await svc.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=_ts(10),
        mom=_sig("BUY", _ts(10)),
        rec=_sig("NONE", _ts(10), kind="recoil", strategy="r"),
        last_prices=lp,
    )
    ts_sell = _ts(11)
    await svc.on_signal(
        symbol="GOLD",
        price=2100.0,
        ts_utc=ts_sell,
        mom=_sig("SELL", ts_sell),
        rec=_sig("NONE", ts_sell, kind="recoil", strategy="r"),
        last_prices=lp,
    )
    assert svc._state.positions["GOLD"].units == 0.0
    assert svc._state.lifetime_realized_pnl == pytest.approx(500.0)


@pytest.mark.asyncio
async def test_sell_percent_partial(isolated_trades_path: Path) -> None:
    svc = TradesService(
        SimulatorSettings(
            enabled=True, trigger_mode="either", sell_mode="percent", sell_pct=0.25
        )
    )
    lp = {"GOLD": (2000.0, _ts(10))}
    await svc.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=_ts(10),
        mom=_sig("BUY", _ts(10)),
        rec=_sig("NONE", _ts(10), kind="recoil", strategy="r"),
        last_prices=lp,
    )
    units_held = svc._state.positions["GOLD"].units
    ts_sell = _ts(11)
    await svc.on_signal(
        symbol="GOLD",
        price=2100.0,
        ts_utc=ts_sell,
        mom=_sig("SELL", ts_sell),
        rec=_sig("NONE", ts_sell, kind="recoil", strategy="r"),
        last_prices=lp,
    )
    assert svc._state.positions["GOLD"].units == pytest.approx(units_held * 0.75)


@pytest.mark.asyncio
async def test_consensus_both_requires_agreement(isolated_trades_path: Path) -> None:
    svc = TradesService(SimulatorSettings(enabled=True, trigger_mode="both"))
    lp = {"GOLD": (2000.0, _ts(10))}
    await svc.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=_ts(10),
        mom=_sig("BUY", _ts(10)),
        rec=_sig("NONE", _ts(10), kind="recoil", strategy="r"),
        last_prices=lp,
    )
    assert len(svc._trades) == 0
    await svc.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=_ts(10) + timedelta(seconds=1),
        mom=_sig("BUY", _ts(10)),
        rec=_sig("BUY", _ts(10), kind="recoil", strategy="r"),
        last_prices=lp,
    )
    assert len(svc._trades) == 1


@pytest.mark.asyncio
async def test_either_rejects_opposing(isolated_trades_path: Path) -> None:
    svc = TradesService(SimulatorSettings(enabled=True, trigger_mode="either"))
    lp = {"GOLD": (2000.0, _ts(10))}
    await svc.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=_ts(10),
        mom=_sig("BUY", _ts(10)),
        rec=_sig("SELL", _ts(10), kind="recoil", strategy="r"),
        last_prices=lp,
    )
    assert len(svc._trades) == 0


@pytest.mark.asyncio
async def test_eod_liquidation_at_22_55(isolated_trades_path: Path) -> None:
    svc = TradesService(SimulatorSettings(enabled=True, trigger_mode="either"))
    lp = {"GOLD": (2000.0, _ts(10))}
    await svc.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=_ts(10),
        mom=_sig("BUY", _ts(10)),
        rec=_sig("NONE", _ts(10), kind="recoil", strategy="r"),
        last_prices=lp,
    )
    assert svc._state.positions["GOLD"].units > 0
    ts_close = _ts(22, 55)
    lp["GOLD"] = (2050.0, ts_close)
    await svc.on_signal(
        symbol="GOLD",
        price=2050.0,
        ts_utc=ts_close,
        mom=_sig("NONE", ts_close),
        rec=_sig("NONE", ts_close, kind="recoil", strategy="r"),
        last_prices=lp,
    )
    assert svc._state.positions["GOLD"].units == 0.0
    assert svc._state.liquidated_for_day is True
    assert any(t.reason == "eod_liquidation" for t in svc._trades)


@pytest.mark.asyncio
async def test_day_rollover_compounds_cash(isolated_trades_path: Path) -> None:
    svc = TradesService(SimulatorSettings(enabled=True, trigger_mode="either"))
    lp = {"GOLD": (2000.0, _ts(10))}
    await svc.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=_ts(10),
        mom=_sig("BUY", _ts(10)),
        rec=_sig("NONE", _ts(10), kind="recoil", strategy="r"),
        last_prices=lp,
    )
    ts_sell = _ts(11)
    await svc.on_signal(
        symbol="GOLD",
        price=2100.0,
        ts_utc=ts_sell,
        mom=_sig("SELL", ts_sell),
        rec=_sig("NONE", ts_sell, kind="recoil", strategy="r"),
        last_prices=lp,
    )
    cash_end_day1 = svc._state.cash
    assert cash_end_day1 > 100_000.0
    ts_next = _ts(8, day=3)
    lp["GOLD"] = (2000.0, ts_next)
    await svc.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=ts_next,
        mom=_sig("NONE", ts_next),
        rec=_sig("NONE", ts_next, kind="recoil", strategy="r"),
        last_prices=lp,
    )
    assert svc._state.day_start_local.isoformat() == "2026-06-03"
    assert svc._state.liquidated_for_day is False
    assert svc._state.cash == pytest.approx(cash_end_day1)
    assert svc._state.today_realized_pnl == 0.0
    assert len(svc._daily) == 1


@pytest.mark.asyncio
async def test_outside_hours_signals_ignored(isolated_trades_path: Path) -> None:
    svc = TradesService(SimulatorSettings(enabled=True, trigger_mode="either"))
    lp = {"GOLD": (2000.0, _ts(7))}
    await svc.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=_ts(7),
        mom=_sig("BUY", _ts(7)),
        rec=_sig("NONE", _ts(7), kind="recoil", strategy="r"),
        last_prices=lp,
    )
    assert len(svc._trades) == 0
    assert svc._state.cash == 100_000.0


@pytest.mark.asyncio
async def test_round_trip_persistence(isolated_trades_path: Path) -> None:
    svc1 = TradesService(SimulatorSettings(enabled=True, trigger_mode="either"))
    lp = {"GOLD": (2000.0, _ts(10))}
    await svc1.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=_ts(10),
        mom=_sig("BUY", _ts(10)),
        rec=_sig("NONE", _ts(10), kind="recoil", strategy="r"),
        last_prices=lp,
    )
    svc2 = TradesService(SimulatorSettings(enabled=True, trigger_mode="either"))
    assert svc2._state.cash == pytest.approx(svc1._state.cash)
    assert len(svc2._trades) == len(svc1._trades)
    assert svc2._state.positions["GOLD"].units == pytest.approx(
        svc1._state.positions["GOLD"].units
    )


@pytest.mark.asyncio
async def test_reset_budget(isolated_trades_path: Path) -> None:
    svc = TradesService(SimulatorSettings(enabled=True, trigger_mode="either"))
    lp = {"GOLD": (2000.0, _ts(10))}
    await svc.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=_ts(10),
        mom=_sig("BUY", _ts(10)),
        rec=_sig("NONE", _ts(10), kind="recoil", strategy="r"),
        last_prices=lp,
    )
    assert svc._state.cash < 100_000.0
    await svc.reset_budget()
    assert svc._state.cash == 100_000.0
    assert svc._trades == []
    assert svc._daily == []


@pytest.mark.asyncio
async def test_replay_is_idempotent_via_dedupe(isolated_trades_path: Path) -> None:
    svc = TradesService(SimulatorSettings(enabled=True, trigger_mode="either"))
    lp = {"GOLD": (2000.0, _ts(10))}
    await svc.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=_ts(10),
        mom=_sig("BUY", _ts(10)),
        rec=_sig("NONE", _ts(10), kind="recoil", strategy="r"),
        last_prices=lp,
    )
    cash_after_first = svc._state.cash
    assert len(svc._trades) == 1
    await svc.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=_ts(10),
        mom=_sig("BUY", _ts(10)),
        rec=_sig("NONE", _ts(10), kind="recoil", strategy="r"),
        last_prices=lp,
    )
    assert len(svc._trades) == 1
    assert svc._state.cash == cash_after_first
    earlier = _ts(10) - timedelta(seconds=30)
    await svc.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=earlier,
        mom=_sig("SELL", earlier),
        rec=_sig("NONE", earlier, kind="recoil", strategy="r"),
        last_prices=lp,
    )
    assert len(svc._trades) == 1


@pytest.mark.asyncio
async def test_enable_toggle_fires_on_enable_changed(
    isolated_trades_path: Path,
) -> None:
    calls = []

    async def on_enabled() -> None:
        calls.append(True)

    svc = TradesService(
        SimulatorSettings(enabled=False, trigger_mode="either"),
        on_enable_changed=on_enabled,
    )
    await svc.update_settings(enabled=True)
    assert calls == [True]
    await svc.update_settings(enabled=True)
    assert calls == [True]
    await svc.update_settings(enabled=False)
    assert calls == [True]
    await svc.update_settings(enabled=True)
    assert calls == [True, True]


@pytest.mark.asyncio
async def test_summary_includes_unrealized(isolated_trades_path: Path) -> None:
    svc = TradesService(SimulatorSettings(enabled=True, trigger_mode="either"))
    lp = {"GOLD": (2000.0, _ts(10))}
    await svc.on_signal(
        symbol="GOLD",
        price=2000.0,
        ts_utc=_ts(10),
        mom=_sig("BUY", _ts(10)),
        rec=_sig("NONE", _ts(10), kind="recoil", strategy="r"),
        last_prices=lp,
    )
    summary = svc.summary({"GOLD": (2100.0, _ts(11))})
    gold_snap = next(p for p in summary.positions if p.symbol == "GOLD")
    assert gold_snap.unrealized_pnl == pytest.approx(gold_snap.units * 100.0)
