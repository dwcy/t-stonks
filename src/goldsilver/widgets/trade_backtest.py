"""Backtest tabs for the Trade Simulator: day picker, run, and result rendering."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Label, Select, Static, TabPane

from goldsilver.data.backtest import run_backtest
from goldsilver.data.history_store import available_days
from goldsilver.data.models import GOLD, SILVER
from goldsilver.data.settings import AppSettings
from goldsilver.data.signal_strategies import STRATEGY_REGISTRY
from goldsilver.data.trade_models import SimulatorSummary, Trade

if TYPE_CHECKING:
    from goldsilver.widgets.trade_simulator import TradeSimulatorScreen


_MOMENTUM_OPTIONS = [
    (c.name, c.name) for c in STRATEGY_REGISTRY if c.kind == "momentum"
]
_RECOIL_OPTIONS = [(c.name, c.name) for c in STRATEGY_REGISTRY if c.kind == "recoil"]
_TRIGGER_OPTIONS = [("Either", "either"), ("Both", "both")]
_SELL_MODE_OPTIONS = [("Sell all", "all"), ("Percent", "percent")]


_REASON_LABEL: dict[str, str] = {
    "signal_buy": "Buy signal",
    "signal_sell": "Sell signal",
    "eod_liquidation": "End-of-day liquidation",
    "manual_reset": "Manual reset",
}

SYMBOL_LABEL: dict[str, str] = {GOLD: "Gold", SILVER: "Silver"}

_TAB_TITLE: dict[str, str] = {GOLD: "Gold History", SILVER: "Silver History"}

_TRADE_COLUMNS = (
    "Time",
    "Symbol",
    "Side",
    "Units",
    "Total units",
    "Price",
    "P/L",
    "Reason",
)
_TRADE_COL_KEYS = (
    "time",
    "symbol",
    "side",
    "units",
    "total",
    "price",
    "pnl",
    "reason",
)


def fmt_money(v: float) -> str:
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.2f}"


def fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def pnl_color(v: float) -> str:
    if v > 0.0001:
        return "#7dff8c"
    if v < -0.0001:
        return "#ff6b6b"
    return "#a0a0b0"


def describe_reason(reason: str, side: str, signals: dict[str, str]) -> str:
    if reason == "eod_liquidation":
        return "End-of-day liquidation"
    if reason == "manual_reset":
        return "Manual reset"
    firing = [
        name.capitalize()
        for name in ("momentum", "recoil")
        if signals.get(name) == side
    ]
    if firing:
        return f"{' + '.join(firing)} {side.lower()} signal"
    return _REASON_LABEL.get(reason, reason)


def trade_cells(t: Trade) -> tuple:
    local = t.ts_utc.astimezone()
    reason = describe_reason(t.reason, t.side, t.signals)
    symbol = SYMBOL_LABEL.get(t.symbol, t.symbol)
    pnl_str = fmt_money(t.realized_pnl) if t.side == "SELL" else "-"
    side_color = "#7dff8c" if t.side == "BUY" else "#ff6b6b"
    side_cell = Text(t.side, style=f"bold {side_color}")
    return (
        local.strftime("%m-%d %H:%M"),
        symbol,
        side_cell,
        f"{t.units:.4f}",
        f"{t.position_units:.4f}",
        f"${t.price:,.2f}",
        pnl_str,
        reason,
    )


def _row_key(t: Trade) -> str:
    return f"{int(t.ts_utc.timestamp())}-{t.side}-{t.reason}"


def _ids(symbol: str) -> dict[str, str]:
    key = "gold" if symbol == GOLD else "silver"
    return {
        "tab": f"sim-tab-{key}-bt",
        "day": f"bt-day-{key}",
        "mom": f"bt-mom-{key}",
        "rec": f"bt-rec-{key}",
        "trigger": f"bt-trigger-{key}",
        "sellmode": f"bt-sellmode-{key}",
        "sellpct": f"bt-sellpct-{key}",
        "buypct": f"bt-buypct-{key}",
        "run": f"bt-run-{key}",
        "stats": f"bt-stats-{key}",
        "trades": f"bt-trades-{key}",
    }


def _day_options(symbol: str) -> list[tuple[str, date]]:
    return [(d.strftime("%Y-%m-%d"), d) for d in available_days(symbol)]


def compose_backtest_pane(symbol: str, settings: AppSettings) -> ComposeResult:
    ids = _ids(symbol)
    sim = settings.simulator
    with TabPane(_TAB_TITLE[symbol], id=ids["tab"]):
        with Horizontal(classes="bt-controls"):
            yield Select(
                _day_options(symbol),
                id=ids["day"],
                prompt="Select day",
                classes="bt-day-select",
            )
            yield Button("Run", id=ids["run"], variant="primary")
        with Horizontal(classes="bt-controls"):
            yield Label("Momentum", classes="bt-label")
            yield Select(
                _MOMENTUM_OPTIONS,
                id=ids["mom"],
                value=settings.marker_momentum_strategy,
                allow_blank=False,
                classes="bt-select",
            )
            yield Label("Recoil", classes="bt-label")
            yield Select(
                _RECOIL_OPTIONS,
                id=ids["rec"],
                value=settings.marker_recoil_strategy,
                allow_blank=False,
                classes="bt-select",
            )
            yield Label("Trigger", classes="bt-label")
            yield Select(
                _TRIGGER_OPTIONS,
                id=ids["trigger"],
                value=sim.trigger_mode,
                allow_blank=False,
                classes="bt-select-sm",
            )
        with Horizontal(classes="bt-controls"):
            yield Label("Sell mode", classes="bt-label")
            yield Select(
                _SELL_MODE_OPTIONS,
                id=ids["sellmode"],
                value=sim.sell_mode,
                allow_blank=False,
                classes="bt-select-sm",
            )
            yield Label("Sell %", classes="bt-label")
            yield Input(
                value=f"{sim.sell_pct * 100:.0f}",
                id=ids["sellpct"],
                classes="bt-pct-input",
            )
            yield Label("Buy %", classes="bt-label")
            yield Input(
                value=f"{sim.buy_pct * 100:.0f}",
                id=ids["buypct"],
                classes="bt-pct-input",
            )
        yield Static("", id=ids["stats"], classes="bt-stats")
        table = DataTable(id=ids["trades"], zebra_stripes=True)
        for label, col_key in zip(_TRADE_COLUMNS, _TRADE_COL_KEYS):
            table.add_column(label, key=col_key)
        yield table


def refresh_day_options(screen: TradeSimulatorScreen, symbol: str) -> None:
    try:
        select = screen.query_one(f"#{_ids(symbol)['day']}", Select)
    except Exception:
        return
    select.set_options(_day_options(symbol))


def control_symbol(widget_id: str | None) -> str | None:
    if not widget_id or not widget_id.startswith("bt-"):
        return None
    if widget_id.endswith("-gold"):
        return GOLD
    if widget_id.endswith("-silver"):
        return SILVER
    return None


def _select_str(screen: TradeSimulatorScreen, widget_id: str) -> str | None:
    try:
        value = screen.query_one(f"#{widget_id}", Select).value
    except Exception:
        return None
    return value if isinstance(value, str) else None


def _input_pct(screen: TradeSimulatorScreen, widget_id: str) -> float | None:
    try:
        raw = screen.query_one(f"#{widget_id}", Input).value
        return float(raw) / 100.0
    except (Exception, ValueError):
        return None


async def run_and_render(screen: TradeSimulatorScreen, symbol: str) -> None:
    ids = _ids(symbol)
    try:
        day = screen.query_one(f"#{ids['day']}", Select).value
    except Exception:
        return
    if not isinstance(day, date):
        _set_static(screen, ids["stats"], Text("Pick a day first.", style="#ffd56b"))
        return
    summary = await run_backtest(
        symbol,
        day,
        screen.app._settings,  # type: ignore[attr-defined]
        momentum=_select_str(screen, ids["mom"]),
        recoil=_select_str(screen, ids["rec"]),
        trigger_mode=_select_str(screen, ids["trigger"]),
        sell_mode=_select_str(screen, ids["sellmode"]),
        sell_pct=_input_pct(screen, ids["sellpct"]),
        buy_pct=_input_pct(screen, ids["buypct"]),
    )
    _set_static(screen, ids["stats"], _stats_text(symbol, day, summary))
    try:
        table = screen.query_one(f"#{ids['trades']}", DataTable)
    except Exception:
        return
    _sync_rows(screen, symbol, table, summary)


def _sync_rows(
    screen: TradeSimulatorScreen,
    symbol: str,
    table: DataTable,
    summary: SimulatorSummary,
) -> None:
    new_rows = {_row_key(t): trade_cells(t) for t in summary.recent_trades}
    rendered: set[str] = screen._bt_rendered.setdefault(symbol, set())
    for key in list(rendered):
        if key not in new_rows:
            try:
                table.remove_row(key)
            except Exception:
                pass
            rendered.discard(key)
    for key, cells in new_rows.items():
        if key in rendered:
            for col_key, value in zip(_TRADE_COL_KEYS, cells):
                try:
                    table.update_cell(key, col_key, value)
                except Exception:
                    pass
        else:
            try:
                table.add_row(*cells, key=key)
                rendered.add(key)
            except Exception:
                pass


def _stats_text(symbol: str, day: date, s: SimulatorSummary) -> Text:
    buys = sum(h.buys for h in s.history)
    sells = sum(h.sells for h in s.history)
    pnl = s.today_realized_pnl
    return Text.assemble(
        (f"{SYMBOL_LABEL.get(symbol, symbol)} {day:%Y-%m-%d}   ", "bold #e0e0e8"),
        ("Cash ", "#a0a0b0"),
        (f"{fmt_money(s.cash)}   ", "bold #e0e0e8"),
        ("P/L ", "#a0a0b0"),
        (f"{fmt_money(pnl)} ({fmt_pct(s.today_pct)})   ", f"bold {pnl_color(pnl)}"),
        ("Buys ", "#a0a0b0"),
        (f"{buys}  ", "#e0e0e8"),
        ("Sells ", "#a0a0b0"),
        (f"{sells}", "#e0e0e8"),
    )


def _set_static(screen: TradeSimulatorScreen, widget_id: str, content) -> None:
    try:
        screen.query_one(f"#{widget_id}", Static).update(content)
    except Exception:
        pass
