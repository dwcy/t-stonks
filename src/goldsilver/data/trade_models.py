"""Trade simulator domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal


TradeSide = Literal["BUY", "SELL"]
TradeReason = Literal["signal_buy", "signal_sell", "eod_liquidation", "manual_reset"]
SellMode = Literal["all", "percent"]
TriggerMode = Literal["both", "either"]
ConsensusAction = Literal["BUY", "SELL", "NONE"]


@dataclass(slots=True)
class Position:
    symbol: str
    units: float = 0.0
    avg_cost: float = 0.0

    @property
    def cost_basis(self) -> float:
        return self.units * self.avg_cost

    def market_value(self, price: float) -> float:
        return self.units * price

    def unrealized_pnl(self, price: float) -> float:
        return self.market_value(price) - self.cost_basis


@dataclass(slots=True)
class Trade:
    trade_id: str
    ts_utc: datetime
    symbol: str
    side: TradeSide
    units: float
    price: float
    cash_delta: float
    realized_pnl: float
    reason: TradeReason
    position_units: float = 0.0
    rule_snapshot: dict[str, object] = field(default_factory=dict)
    signals: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class DailyPnL:
    day: date
    realized_pnl: float
    end_cash: float


@dataclass(slots=True)
class DayHistory:
    day: date
    buys: int
    sells: int
    realized_pnl: float


@dataclass(slots=True)
class SimulatorState:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    day_start_local: date | None = None
    lifetime_realized_pnl: float = 0.0
    today_realized_pnl: float = 0.0
    last_consensus_action: dict[str, ConsensusAction] = field(default_factory=dict)
    liquidated_for_day: bool = False
    last_processed_ts: dict[str, datetime] = field(default_factory=dict)


@dataclass(slots=True)
class PositionSnapshot:
    symbol: str
    units: float
    avg_cost: float
    last_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pct: float


@dataclass(slots=True)
class SimulatorSummary:
    enabled: bool
    is_open: bool
    cash: float
    initial_deposit: float
    today_realized_pnl: float
    lifetime_realized_pnl: float
    today_pct: float
    lifetime_pct: float
    positions: tuple[PositionSnapshot, ...]
    recent_trades: tuple[Trade, ...]
    history: tuple[DayHistory, ...]
    sell_mode: SellMode
    sell_pct: float
    trigger_mode: TriggerMode
    liquidated_for_day: bool
    max_drawdown: float = 0.0
    win_rate: float | None = None
    avg_win: float | None = None
    avg_loss: float | None = None
