"""Trade simulator engine and JSON persistence."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Any

from goldsilver.data.models_macro import Signal
from goldsilver.data.settings import SimulatorSettings, trades_path
from goldsilver.data.trade_models import (
    ConsensusAction,
    DailyPnL,
    DayHistory,
    Position,
    PositionSnapshot,
    SimulatorState,
    SimulatorSummary,
    Trade,
    TradeReason,
)
from goldsilver.data.trading_hours import is_open, to_local

SettingsPersister = Callable[[], Awaitable[None] | None]
EnableChangedCallback = Callable[[], Awaitable[None] | None]

_MIN_BUY_USD = 1.0
_TRADE_CAP = 5000


class TradesService:
    def __init__(
        self,
        settings: SimulatorSettings,
        *,
        settings_persister: SettingsPersister | None = None,
        on_enable_changed: EnableChangedCallback | None = None,
    ) -> None:
        self._settings = settings
        self._settings_persister = settings_persister
        self._on_enable_changed = on_enable_changed
        self._state = SimulatorState(cash=settings.initial_deposit)
        self._trades: list[Trade] = []
        self._daily: list[DailyPnL] = []
        self._lock = asyncio.Lock()
        self._load()

    async def on_signal(
        self,
        *,
        symbol: str,
        price: float,
        ts_utc: datetime,
        mom: Signal | None,
        rec: Signal | None,
        last_prices: dict[str, tuple[float, datetime]],
    ) -> None:
        async with self._lock:
            seen = self._state.last_processed_ts.get(symbol)
            if seen is not None and ts_utc <= seen:
                return
            now_local = to_local(ts_utc)
            self._check_clock(now_local, last_prices)
            consensus = self._consensus_action(mom, rec)
            prev = self._state.last_consensus_action.get(symbol, "NONE")
            self._state.last_consensus_action[symbol] = consensus
            if is_open(now_local) and consensus != "NONE" and prev != consensus:
                rule_snap = self._rule_snapshot()
                sig_snap = {
                    "momentum": mom.action if mom is not None else "NONE",
                    "recoil": rec.action if rec is not None else "NONE",
                    "momentum_strategy": mom.strategy if mom is not None else "",
                    "recoil_strategy": rec.strategy if rec is not None else "",
                }
                trade: Trade | None
                if consensus == "BUY":
                    trade = self._execute_buy(
                        symbol, price, ts_utc, rule_snap, sig_snap
                    )
                else:
                    trade = self._execute_sell(
                        symbol, price, ts_utc, "signal_sell", rule_snap, sig_snap
                    )
                if trade is not None:
                    self._trades.append(trade)
            self._state.last_processed_ts[symbol] = ts_utc
            await asyncio.to_thread(self._persist)

    async def liquidate_now(
        self, last_prices: dict[str, tuple[float, datetime]]
    ) -> None:
        async with self._lock:
            now_local = to_local(datetime.now(timezone.utc))
            self._liquidate_positions(now_local, last_prices, forced=True)
            await asyncio.to_thread(self._persist)

    async def reset_budget(self) -> None:
        async with self._lock:
            self._state = SimulatorState(cash=self._settings.initial_deposit)
            self._trades.clear()
            self._daily.clear()
            await asyncio.to_thread(self._persist)

    def summary(
        self,
        last_prices: dict[str, tuple[float, datetime]] | None = None,
    ) -> SimulatorSummary:
        prices = last_prices or {}
        now_local = to_local(datetime.now(timezone.utc))
        positions_snap: list[PositionSnapshot] = []
        for symbol, pos in self._state.positions.items():
            if pos.units <= 0.0:
                continue
            price_info = prices.get(symbol)
            last_p = price_info[0] if price_info is not None else pos.avg_cost
            mv = pos.units * last_p
            unr = mv - pos.cost_basis
            unr_pct = (unr / pos.cost_basis * 100.0) if pos.cost_basis > 0 else 0.0
            positions_snap.append(
                PositionSnapshot(
                    symbol, pos.units, pos.avg_cost, last_p, mv, unr, unr_pct
                )
            )
        init = self._settings.initial_deposit
        today_pct = (self._state.today_realized_pnl / init * 100.0) if init > 0 else 0.0
        lifetime_pct = (
            (self._state.lifetime_realized_pnl / init * 100.0) if init > 0 else 0.0
        )
        return SimulatorSummary(
            enabled=self._settings.enabled,
            is_open=is_open(now_local),
            cash=self._state.cash,
            initial_deposit=init,
            today_realized_pnl=self._state.today_realized_pnl,
            lifetime_realized_pnl=self._state.lifetime_realized_pnl,
            today_pct=today_pct,
            lifetime_pct=lifetime_pct,
            positions=tuple(positions_snap),
            recent_trades=tuple(self._trades[-50:]),
            history=self._build_history(),
            sell_mode=self._settings.sell_mode,
            sell_pct=self._settings.sell_pct,
            trigger_mode=self._settings.trigger_mode,
            liquidated_for_day=self._state.liquidated_for_day,
        )

    def _build_history(self) -> tuple[DayHistory, ...]:
        buys: dict[date, int] = {}
        sells: dict[date, int] = {}
        for t in self._trades:
            day = to_local(t.ts_utc).date()
            if t.side == "BUY":
                buys[day] = buys.get(day, 0) + 1
            else:
                sells[day] = sells.get(day, 0) + 1
        pnl_by_day: dict[date, float] = {d.day: d.realized_pnl for d in self._daily}
        days = set(buys) | set(sells) | set(pnl_by_day)
        rows = [
            DayHistory(
                day=d,
                buys=buys.get(d, 0),
                sells=sells.get(d, 0),
                realized_pnl=pnl_by_day.get(d, 0.0),
            )
            for d in sorted(days)
        ]
        return tuple(rows)

    async def update_settings(self, **changes: Any) -> None:
        async with self._lock:
            trigger_changed = (
                "trigger_mode" in changes
                and changes["trigger_mode"] != self._settings.trigger_mode
            )
            was_enabled = self._settings.enabled
            for k, v in changes.items():
                if hasattr(self._settings, k):
                    setattr(self._settings, k, v)
            self._settings.__post_init__()
            if trigger_changed:
                self._state.last_consensus_action.clear()
            now_enabled = self._settings.enabled
        if self._settings_persister is not None:
            result = self._settings_persister()
            if asyncio.iscoroutine(result):
                await result
        if now_enabled and not was_enabled and self._on_enable_changed is not None:
            result = self._on_enable_changed()
            if asyncio.iscoroutine(result):
                await result

    @property
    def settings(self) -> SimulatorSettings:
        return self._settings

    def _consensus_action(
        self, mom: Signal | None, rec: Signal | None
    ) -> ConsensusAction:
        a_mom = mom.action if mom is not None else "NONE"
        a_rec = rec.action if rec is not None else "NONE"
        if self._settings.trigger_mode == "both":
            if a_mom == "BUY" and a_rec == "BUY":
                return "BUY"
            if a_mom == "SELL" and a_rec == "SELL":
                return "SELL"
            return "NONE"
        actions = {a_mom, a_rec}
        if "BUY" in actions and "SELL" in actions:
            return "NONE"
        if "BUY" in actions:
            return "BUY"
        if "SELL" in actions:
            return "SELL"
        return "NONE"

    def _check_clock(
        self,
        now_local: datetime,
        last_prices: dict[str, tuple[float, datetime]],
    ) -> None:
        today = now_local.date()
        if self._state.day_start_local is None:
            self._state.day_start_local = today
        elif today != self._state.day_start_local:
            self._daily.append(
                DailyPnL(
                    day=self._state.day_start_local,
                    realized_pnl=self._state.today_realized_pnl,
                    end_cash=self._state.cash,
                )
            )
            self._state.today_realized_pnl = 0.0
            self._state.day_start_local = today
            self._state.liquidated_for_day = False
        if not is_open(now_local) and not self._state.liquidated_for_day:
            self._liquidate_positions(now_local, last_prices, forced=False)
            self._state.liquidated_for_day = True

    def _liquidate_positions(
        self,
        now_local: datetime,
        last_prices: dict[str, tuple[float, datetime]],
        *,
        forced: bool,
    ) -> None:
        ts_utc = now_local.astimezone(timezone.utc)
        rule_snap = self._rule_snapshot()
        for symbol, pos in list(self._state.positions.items()):
            if pos.units <= 0.0:
                continue
            price_info = last_prices.get(symbol)
            if price_info is None:
                continue
            price = price_info[0]
            trade = self._execute_sell_units(
                symbol=symbol,
                units=pos.units,
                price=price,
                ts_utc=ts_utc,
                reason="eod_liquidation",
                rule_snap=rule_snap,
                signals={"forced": "true" if forced else "false"},
            )
            if trade is not None:
                self._trades.append(trade)

    def _execute_buy(
        self,
        symbol: str,
        price: float,
        ts_utc: datetime,
        rule_snap: dict[str, object],
        sig_snap: dict[str, str],
    ) -> Trade | None:
        if price <= 0.0:
            return None
        spend = self._state.cash * self._settings.buy_pct
        if spend < _MIN_BUY_USD:
            return None
        units = spend / price
        cost = units * price
        pos = self._state.positions.get(symbol) or Position(symbol=symbol)
        new_units = pos.units + units
        new_cost_basis = pos.cost_basis + cost
        pos.avg_cost = new_cost_basis / new_units if new_units > 0 else 0.0
        pos.units = new_units
        self._state.positions[symbol] = pos
        self._state.cash -= cost
        return Trade(
            trade_id=str(uuid.uuid4()),
            ts_utc=ts_utc,
            symbol=symbol,
            side="BUY",
            units=units,
            price=price,
            cash_delta=-cost,
            realized_pnl=0.0,
            reason="signal_buy",
            position_units=new_units,
            rule_snapshot=rule_snap,
            signals=sig_snap,
        )

    def _execute_sell(
        self,
        symbol: str,
        price: float,
        ts_utc: datetime,
        reason: TradeReason,
        rule_snap: dict[str, object],
        sig_snap: dict[str, str],
    ) -> Trade | None:
        pos = self._state.positions.get(symbol)
        if pos is None or pos.units <= 0.0:
            return None
        if self._settings.sell_mode == "all":
            units = pos.units
        else:
            units = pos.units * self._settings.sell_pct
        return self._execute_sell_units(
            symbol=symbol,
            units=units,
            price=price,
            ts_utc=ts_utc,
            reason=reason,
            rule_snap=rule_snap,
            signals=sig_snap,
        )

    def _execute_sell_units(
        self,
        *,
        symbol: str,
        units: float,
        price: float,
        ts_utc: datetime,
        reason: TradeReason,
        rule_snap: dict[str, object],
        signals: dict[str, str],
    ) -> Trade | None:
        pos = self._state.positions.get(symbol)
        if pos is None or pos.units <= 0.0 or units <= 0.0 or price <= 0.0:
            return None
        units = min(units, pos.units)
        proceeds = units * price
        cost = units * pos.avg_cost
        realized = proceeds - cost
        pos.units -= units
        if pos.units < 1e-9:
            pos.units = 0.0
            pos.avg_cost = 0.0
        self._state.positions[symbol] = pos
        self._state.cash += proceeds
        self._state.today_realized_pnl += realized
        self._state.lifetime_realized_pnl += realized
        return Trade(
            trade_id=str(uuid.uuid4()),
            ts_utc=ts_utc,
            symbol=symbol,
            side="SELL",
            units=units,
            price=price,
            cash_delta=proceeds,
            realized_pnl=realized,
            reason=reason,
            position_units=pos.units,
            rule_snapshot=rule_snap,
            signals=signals,
        )

    def _rule_snapshot(self) -> dict[str, object]:
        return {
            "buy_pct": self._settings.buy_pct,
            "sell_mode": self._settings.sell_mode,
            "sell_pct": self._settings.sell_pct,
            "trigger_mode": self._settings.trigger_mode,
            "initial_deposit": self._settings.initial_deposit,
        }

    def _persist(self) -> None:
        path = trades_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "state": _state_to_dict(self._state),
            "trades": [_trade_to_dict(t) for t in self._trades[-_TRADE_CAP:]],
            "daily": [_daily_to_dict(d) for d in self._daily],
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load(self) -> None:
        path = trades_path()
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, dict):
            return
        try:
            self._state = _state_from_dict(
                raw.get("state", {}), self._settings.initial_deposit
            )
            self._trades = [
                _trade_from_dict(t)
                for t in raw.get("trades", [])
                if isinstance(t, dict)
            ]
            self._daily = [
                _daily_from_dict(d) for d in raw.get("daily", []) if isinstance(d, dict)
            ]
        except (ValueError, KeyError, TypeError):
            self._state = SimulatorState(cash=self._settings.initial_deposit)
            self._trades = []
            self._daily = []


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
