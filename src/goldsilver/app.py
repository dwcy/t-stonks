from __future__ import annotations

import sys
from datetime import datetime, timezone

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static

from goldsilver.data import MetalsService
from goldsilver.data.models import GOLD, SILVER, Bar, Tick
from goldsilver.data.service import POLL_INTERVAL_S
from goldsilver.data.session import stockholm_midnight_utc
from goldsilver.widgets import MetalPanel


GOLD_COLOR = (255, 213, 107)
SILVER_COLOR = (208, 208, 224)

TIMEFRAMES: list[tuple[str, str, str, str | None]] = [
    ("today", "2d", "1m", "today"),
    ("5d", "5d", "5m", None),
    ("1mo", "1mo", "1h", None),
    ("3mo", "3mo", "1d", None),
]

STATUS_STYLES = {
    "starting": "#7a7a8a",
    "connecting": "#ffd56b",
    "connected": "#7dff8c",
    "reconnecting": "#ff9b6b",
}


class GoldSilverApp(App[None]):
    CSS_PATH = "styles/app.tcss"
    TITLE = "gold & silver"
    SUB_TITLE = (
        f"live spot via goldprice.org; H/L + ref close via Avanza "
        f"(interval: {POLL_INTERVAL_S:g}s)"
    )

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("t", "toggle_timeframe", "Timeframe"),
        Binding("r", "reconnect", "Reconnect"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._panels: dict[str, MetalPanel] = {}
        self._service = MetalsService(
            tick_handler=self._on_tick,
            status_handler=self._on_status,
        )
        self._connection_status = "starting"
        self._last_tick_at: datetime | None = None
        self._timeframe_index = 0

    @property
    def _timeframe_label(self) -> str:
        return TIMEFRAMES[self._timeframe_index][0]

    @property
    def _timeframe_period(self) -> str:
        return TIMEFRAMES[self._timeframe_index][1]

    @property
    def _timeframe_interval(self) -> str:
        return TIMEFRAMES[self._timeframe_index][2]

    @property
    def _timeframe_filter(self) -> str | None:
        return TIMEFRAMES[self._timeframe_index][3]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="metals"):
            gold = MetalPanel(
                GOLD, "GOLD", accent_color=GOLD_COLOR, classes="-gold"
            )
            silver = MetalPanel(
                SILVER, "SILVER", accent_color=SILVER_COLOR, classes="-silver"
            )
            self._panels[GOLD] = gold
            self._panels[SILVER] = silver
            yield gold
            yield silver
        yield Static("", id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        self._refresh_status_bar()
        self._service.start()
        self._seed_all()

    async def on_unmount(self) -> None:
        await self._service.stop()

    def _seed_all(self) -> None:
        for symbol, panel in self._panels.items():
            self.run_worker(
                self._seed_panel(symbol, panel),
                exclusive=False,
                group=f"seed-{symbol}",
            )

    async def _seed_panel(self, symbol: str, panel: MetalPanel) -> None:
        try:
            bars = await self._service.fetch_history(
                symbol,
                period=self._timeframe_period,
                interval=self._timeframe_interval,
            )
        except Exception:
            return
        x_origin: datetime | None = None
        if self._timeframe_filter == "today":
            bars = _filter_to_stockholm_today(bars)
            x_origin = stockholm_midnight_utc()
        panel.seed_history(bars, x_origin=x_origin)

    async def _on_tick(self, tick: Tick) -> None:
        self._last_tick_at = tick.time
        panel = self._panels.get(tick.symbol)
        if panel is not None:
            panel.apply_tick(tick)
        self._refresh_status_bar()

    async def _on_status(self, status: str) -> None:
        self._connection_status = status
        self._refresh_status_bar()

    def _refresh_status_bar(self) -> None:
        try:
            bar = self.query_one("#status-bar", Static)
        except Exception:
            return
        style = STATUS_STYLES.get(self._connection_status, "#7a7a8a")
        if self._last_tick_at is None:
            ago = "no ticks yet"
        else:
            local = self._last_tick_at.astimezone()
            ago = f"last tick {local.strftime('%H:%M:%S')}"
        bar.update(
            Text.assemble(
                ("● ", style),
                (f"{self._connection_status:<13}", style),
                ("  ·  ", "#3a3a4a"),
                (f"timeframe {self._timeframe_label:<3}", "#a0a0b0"),
                ("  ·  ", "#3a3a4a"),
                (ago, "#a0a0b0"),
            )
        )

    async def action_toggle_timeframe(self) -> None:
        self._timeframe_index = (self._timeframe_index + 1) % len(TIMEFRAMES)
        self._refresh_status_bar()
        self._seed_all()

    async def action_reconnect(self) -> None:
        self._connection_status = "reconnecting"
        self._refresh_status_bar()
        await self._service.stop()
        self._service.start()


def _filter_to_stockholm_today(bars: list[Bar]) -> list[Bar]:
    midnight = stockholm_midnight_utc()
    return [b for b in bars if b.time.astimezone(timezone.utc) >= midnight]


def main() -> None:
    if not sys.stdout.isatty():
        print("ok")
        return
    GoldSilverApp().run()


if __name__ == "__main__":
    main()
