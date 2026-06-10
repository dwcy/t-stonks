"""JSON persistence for the trade simulator: (de)serialize state, trades, and daily P/L."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from goldsilver.data.trade_models import (
    ConsensusAction,
    DailyPnL,
    Position,
    SimulatorState,
    Trade,
)
from goldsilver.fsutil import atomic_write_text


def save_trades(
    path: Path,
    state: SimulatorState,
    trades: list[Trade],
    daily: list[DailyPnL],
    trade_cap: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": 1,
        "state": _state_to_dict(state),
        "trades": [_trade_to_dict(t) for t in trades[-trade_cap:]],
        "daily": [_daily_to_dict(d) for d in daily],
    }
    atomic_write_text(path, json.dumps(data, indent=2))


def load_trades(
    path: Path, default_cash: float
) -> tuple[SimulatorState, list[Trade], list[DailyPnL]] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        state = _state_from_dict(raw.get("state", {}), default_cash)
        trades = [
            _trade_from_dict(t) for t in raw.get("trades", []) if isinstance(t, dict)
        ]
        daily = [
            _daily_from_dict(d) for d in raw.get("daily", []) if isinstance(d, dict)
        ]
    except (ValueError, KeyError, TypeError):
        return SimulatorState(cash=default_cash), [], []
    return state, trades, daily


def _state_to_dict(s: SimulatorState) -> dict[str, Any]:
    return {
        "cash": s.cash,
        "positions": {sym: asdict(p) for sym, p in s.positions.items()},
        "day_start_local": s.day_start_local.isoformat() if s.day_start_local else None,
        "lifetime_realized_pnl": s.lifetime_realized_pnl,
        "today_realized_pnl": s.today_realized_pnl,
        "last_consensus_action": dict(s.last_consensus_action),
        "liquidated_for_day": s.liquidated_for_day,
        "last_processed_ts": {
            sym: ts.isoformat() for sym, ts in s.last_processed_ts.items()
        },
    }


def _state_from_dict(d: dict[str, Any], default_cash: float) -> SimulatorState:
    positions: dict[str, Position] = {}
    raw_positions = d.get("positions", {})
    if isinstance(raw_positions, dict):
        for sym, payload in raw_positions.items():
            if not isinstance(payload, dict):
                continue
            positions[sym] = Position(
                symbol=str(payload.get("symbol", sym)),
                units=float(payload.get("units", 0.0)),
                avg_cost=float(payload.get("avg_cost", 0.0)),
            )
    day_raw = d.get("day_start_local")
    day_val: date | None = None
    if isinstance(day_raw, str):
        try:
            day_val = date.fromisoformat(day_raw)
        except ValueError:
            day_val = None
    last_action_raw = d.get("last_consensus_action", {})
    last_action: dict[str, ConsensusAction] = {}
    if isinstance(last_action_raw, dict):
        for k, v in last_action_raw.items():
            if v in ("BUY", "SELL", "NONE"):
                last_action[str(k)] = v
    last_ts_raw = d.get("last_processed_ts", {})
    last_ts: dict[str, datetime] = {}
    if isinstance(last_ts_raw, dict):
        for k, v in last_ts_raw.items():
            if not isinstance(v, str):
                continue
            try:
                parsed = datetime.fromisoformat(v)
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            last_ts[str(k)] = parsed
    return SimulatorState(
        cash=float(d.get("cash", default_cash)),
        positions=positions,
        day_start_local=day_val,
        lifetime_realized_pnl=float(d.get("lifetime_realized_pnl", 0.0)),
        today_realized_pnl=float(d.get("today_realized_pnl", 0.0)),
        last_consensus_action=last_action,
        liquidated_for_day=bool(d.get("liquidated_for_day", False)),
        last_processed_ts=last_ts,
    )


def _trade_to_dict(t: Trade) -> dict[str, Any]:
    return {
        "trade_id": t.trade_id,
        "ts_utc": t.ts_utc.isoformat(),
        "symbol": t.symbol,
        "side": t.side,
        "units": t.units,
        "price": t.price,
        "cash_delta": t.cash_delta,
        "realized_pnl": t.realized_pnl,
        "reason": t.reason,
        "position_units": t.position_units,
        "rule_snapshot": t.rule_snapshot,
        "signals": t.signals,
    }


def _trade_from_dict(d: dict[str, Any]) -> Trade:
    ts = d.get("ts_utc")
    if isinstance(ts, str):
        ts_dt = datetime.fromisoformat(ts)
    else:
        ts_dt = datetime.now(timezone.utc)
    if ts_dt.tzinfo is None:
        ts_dt = ts_dt.replace(tzinfo=timezone.utc)
    return Trade(
        trade_id=str(d.get("trade_id", str(uuid.uuid4()))),
        ts_utc=ts_dt,
        symbol=str(d.get("symbol", "")),
        side=d.get("side") if d.get("side") in ("BUY", "SELL") else "BUY",
        units=float(d.get("units", 0.0)),
        price=float(d.get("price", 0.0)),
        cash_delta=float(d.get("cash_delta", 0.0)),
        realized_pnl=float(d.get("realized_pnl", 0.0)),
        reason=d.get("reason")
        if d.get("reason")
        in ("signal_buy", "signal_sell", "eod_liquidation", "manual_reset")
        else "signal_buy",
        position_units=float(d.get("position_units", 0.0)),
        rule_snapshot=d.get("rule_snapshot")
        if isinstance(d.get("rule_snapshot"), dict)
        else {},
        signals=d.get("signals") if isinstance(d.get("signals"), dict) else {},
    )


def _daily_to_dict(d: DailyPnL) -> dict[str, Any]:
    return {
        "day": d.day.isoformat(),
        "realized_pnl": d.realized_pnl,
        "end_cash": d.end_cash,
    }


def _daily_from_dict(d: dict[str, Any]) -> DailyPnL:
    day_raw = d.get("day")
    day_val = date.fromisoformat(day_raw) if isinstance(day_raw, str) else date.today()
    return DailyPnL(
        day=day_val,
        realized_pnl=float(d.get("realized_pnl", 0.0)),
        end_cash=float(d.get("end_cash", 0.0)),
    )
