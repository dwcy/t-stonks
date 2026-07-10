from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Label,
    RadioButton,
    RadioSet,
    Switch,
    TabbedContent,
    TabPane,
)

from goldsilver.data.settings import (
    ALLOWED_MINI_TILES,
    METALS_COLUMNS_CHOICES,
)
from goldsilver.data.signal_strategies import STRATEGY_REGISTRY
from goldsilver.widgets.chart import ChartKind
from goldsilver.widgets.minicharts_tab import MiniChartsTab


TIMEFRAME_LABELS = ("today", "5d", "1mo", "3mo")

_MINI_TILE_LABEL: dict[str, str] = {
    "USDSEK": "USD/SEK",
    "CADSEK": "CAD/SEK",
    "EURSEK": "EUR/SEK",
    "BRENT": "Oil",
    "COPPER": "Copper",
    "BTC": "BTC",
    "RATIO": "Gold/Silver ratio",
    "DXY": "Dollar Index",
    "REALYIELD": "10Y real yield",
    "FEDRATE": "Fed funds rate",
    "RIKSRATE": "Riksbank policy rate",
}


@dataclass(slots=True)
class PlotSettings:
    timeframe_index: int
    chart_kind: ChartKind
    show_dual_charts: bool
    chart_kind2: ChartKind
    show_sma: bool
    show_vwap: bool
    show_day_refs: bool
    show_news_markets: bool
    show_news_trump: bool
    show_congress_trades: bool
    show_insider_trades: bool
    show_stocktwits: bool
    show_stock_row: bool
    show_futures: bool
    gold_color_name: str
    silver_color_name: str
    metals_columns: int
    visible_signals: dict[str, bool] = field(default_factory=dict)
    marker_momentum_strategy: str = ""
    marker_recoil_strategy: str = ""
    mini_tiles: list[str] = field(default_factory=list)
    stock_tickers: list[str] = field(default_factory=list)
    extra_stock_tickers: list[str] = field(default_factory=list)
    enabled_preset_tickers: list[str] = field(default_factory=list)


class PlotSettingsScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(
        self,
        current: PlotSettings,
        *,
        on_change: Callable[[PlotSettings], None],
        on_open_math: Callable[[], None],
    ) -> None:
        super().__init__()
        self._state = current
        self._on_change = on_change
        self._on_open_math = on_open_math
        self._strategy_names = [cls.name for cls in STRATEGY_REGISTRY]
        self._momentum_names = [
            cls.name for cls in STRATEGY_REGISTRY if cls.kind == "momentum"
        ]
        self._recoil_names = [
            cls.name for cls in STRATEGY_REGISTRY if cls.kind == "recoil"
        ]

    def compose(self) -> ComposeResult:
        with Container(id="plot-settings-dialog"):
            yield Label("Settings", id="plot-settings-title")
            with TabbedContent(id="plot-settings-tabs"):
                with TabPane("General", id="settings-tab-general"):
                    with VerticalScroll(id="plot-settings-body"):
                        yield from self._general_setting_groups()
                with TabPane("Mini charts", id="settings-tab-minicharts"):
                    with VerticalScroll(id="plot-settings-minicharts"):
                        yield MiniChartsTab(self._state, emit=self._emit)
            yield Button("Close", variant="primary", id="setting-close")

    def _general_setting_groups(self) -> ComposeResult:
        with Vertical(classes="setting-group"):
            yield Label("Cards per row", classes="setting-label")
            with RadioSet(id="setting-columns"):
                for n in METALS_COLUMNS_CHOICES:
                    yield RadioButton(
                        str(n),
                        value=(n == self._state.metals_columns),
                    )
        with Vertical(classes="setting-group"):
            yield Label("Timeframe", classes="setting-label")
            with RadioSet(id="setting-timeframe"):
                for i, label in enumerate(TIMEFRAME_LABELS):
                    yield RadioButton(label, value=(i == self._state.timeframe_index))
        with Vertical(classes="setting-group"):
            yield Label("Chart kind", classes="setting-label")
            with RadioSet(id="setting-kind"):
                yield RadioButton("Line", value=(self._state.chart_kind == "line"))
                yield RadioButton("Candle", value=(self._state.chart_kind == "candle"))
        with Vertical(classes="setting-group"):
            yield Label("Duplicate charts", classes="setting-label")
            with Horizontal(classes="switch-row"):
                yield Switch(
                    value=self._state.show_dual_charts,
                    id="setting-dual",
                )
                yield Label(
                    "Add a 2nd Gold/Silver chart",
                    classes="switch-label",
                )
            yield Label("2nd chart kind", classes="sub-label")
            with RadioSet(id="setting-kind2"):
                yield RadioButton("Line", value=(self._state.chart_kind2 == "line"))
                yield RadioButton("Candle", value=(self._state.chart_kind2 == "candle"))
        with Vertical(classes="setting-group"):
            yield Label("Overlays", classes="setting-label")
            with Horizontal(classes="switch-row"):
                yield Switch(value=self._state.show_sma, id="setting-sma")
                yield Label("SMA (20 / 50)", classes="switch-label")
            with Horizontal(classes="switch-row"):
                yield Switch(value=self._state.show_vwap, id="setting-vwap")
                yield Label("VWAP", classes="switch-label")
            with Horizontal(classes="switch-row"):
                yield Switch(
                    value=self._state.show_day_refs,
                    id="setting-refs",
                )
                yield Label(
                    "Day refs (prev close, H/L)",
                    classes="switch-label",
                )
        with Vertical(classes="setting-group"):
            yield Label("Signals shown", classes="setting-label")
            for name in self._strategy_names:
                with Horizontal(classes="switch-row"):
                    yield Switch(
                        value=self._state.visible_signals.get(name, False),
                        id=self._signal_switch_id(name),
                    )
                    yield Label(name, classes="switch-label")
            yield Button(
                "Edit math…",
                variant="default",
                id="open-edit-math",
            )
        with Vertical(classes="setting-group"):
            yield Label("Chart markers", classes="setting-label")
            yield Label("Momentum source", classes="sub-label")
            with RadioSet(id="setting-marker-momentum"):
                for name in self._momentum_names:
                    yield RadioButton(
                        name,
                        value=(name == self._state.marker_momentum_strategy),
                    )
            yield Label("Recoil source", classes="sub-label")
            with RadioSet(id="setting-marker-recoil"):
                for name in self._recoil_names:
                    yield RadioButton(
                        name,
                        value=(name == self._state.marker_recoil_strategy),
                    )
        with Vertical(classes="setting-group"):
            yield Label("News feeds", classes="setting-label")
            with Horizontal(classes="switch-row"):
                yield Switch(
                    value=self._state.show_news_markets,
                    id="setting-news-markets",
                )
                yield Label("Markets news", classes="switch-label")
            with Horizontal(classes="switch-row"):
                yield Switch(
                    value=self._state.show_news_trump,
                    id="setting-news-trump",
                )
                yield Label("Trump posts", classes="switch-label")
            with Horizontal(classes="switch-row"):
                yield Switch(
                    value=self._state.show_congress_trades,
                    id="setting-congress-trades",
                )
                yield Label("Congress trades", classes="switch-label")
            with Horizontal(classes="switch-row"):
                yield Switch(
                    value=self._state.show_insider_trades,
                    id="setting-insider-trades",
                )
                yield Label(
                    "Trump Media insiders (SEC Form 4)",
                    classes="switch-label",
                )
            with Horizontal(classes="switch-row"):
                yield Switch(
                    value=self._state.show_stocktwits,
                    id="setting-stocktwits",
                )
                yield Label(
                    "StockTwits chatter",
                    classes="switch-label",
                )
            with Horizontal(classes="switch-row"):
                yield Switch(
                    value=self._state.show_futures,
                    id="setting-futures",
                )
                yield Label(
                    "Futures (termins) row",
                    classes="switch-label",
                )
        with Vertical(classes="setting-group"):
            yield Label("Mini tiles", classes="setting-label")
            with Vertical(id="mini-tiles-list"):
                for row in self._build_mini_rows():
                    yield row

    @staticmethod
    def _slug(name: str) -> str:
        return "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")

    @classmethod
    def _signal_switch_id(cls, name: str) -> str:
        return f"setting-show-{cls._slug(name)}"

    @staticmethod
    def _mini_slug(tile_id: str) -> str:
        return tile_id.lower()

    def _build_mini_rows(self) -> list[Horizontal]:
        enabled = list(self._state.mini_tiles)
        enabled_set = set(enabled)
        rows: list[Horizontal] = []
        for idx, tile_id in enumerate(enabled):
            slug = self._mini_slug(tile_id)
            rows.append(
                Horizontal(
                    Switch(value=True, id=f"setting-mini-{slug}"),
                    Label(
                        _MINI_TILE_LABEL.get(tile_id, tile_id),
                        classes="mini-tile-label",
                    ),
                    Button(
                        "▲",
                        id=f"mini-up-{slug}",
                        disabled=(idx == 0),
                        classes="mini-reorder",
                    ),
                    Button(
                        "▼",
                        id=f"mini-down-{slug}",
                        disabled=(idx == len(enabled) - 1),
                        classes="mini-reorder",
                    ),
                    classes="mini-tile-row",
                )
            )
        for tile_id in ALLOWED_MINI_TILES:
            if tile_id in enabled_set:
                continue
            slug = self._mini_slug(tile_id)
            rows.append(
                Horizontal(
                    Switch(value=False, id=f"setting-mini-{slug}"),
                    Label(
                        _MINI_TILE_LABEL.get(tile_id, tile_id),
                        classes="mini-tile-label",
                    ),
                    classes="mini-tile-row",
                )
            )
        return rows

    def _refresh_mini_rows(self) -> None:
        container = self.query_one("#mini-tiles-list", Vertical)
        container.remove_children()
        new_rows = self._build_mini_rows()
        if new_rows:
            container.mount(*new_rows)

    def _toggle_mini_tile(self, tile_id: str, enable: bool) -> None:
        current = list(self._state.mini_tiles)
        if enable and tile_id not in current:
            current.append(tile_id)
        elif not enable and tile_id in current:
            current.remove(tile_id)
        else:
            return
        self._state.mini_tiles = current
        self._refresh_mini_rows()
        self._emit()

    def _move_mini_tile(self, tile_id: str, delta: int) -> None:
        current = list(self._state.mini_tiles)
        if tile_id not in current:
            return
        idx = current.index(tile_id)
        target = idx + delta
        if target < 0 or target >= len(current):
            return
        current[idx], current[target] = current[target], current[idx]
        self._state.mini_tiles = current
        self._refresh_mini_rows()
        self._emit()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        rs_id = event.radio_set.id
        idx = event.index
        if rs_id == "setting-columns":
            n = METALS_COLUMNS_CHOICES[idx]
            if n != self._state.metals_columns:
                self._state.metals_columns = n
                self._emit()
            return
        if rs_id == "setting-timeframe":
            if idx != self._state.timeframe_index:
                self._state.timeframe_index = idx
                self._emit()
        elif rs_id == "setting-kind":
            kind: ChartKind = "line" if idx == 0 else "candle"
            if kind != self._state.chart_kind:
                self._state.chart_kind = kind
                self._emit()
        elif rs_id == "setting-kind2":
            kind2: ChartKind = "line" if idx == 0 else "candle"
            if kind2 != self._state.chart_kind2:
                self._state.chart_kind2 = kind2
                self._emit()
        elif rs_id == "setting-marker-momentum":
            name = self._momentum_names[idx]
            if name != self._state.marker_momentum_strategy:
                self._state.marker_momentum_strategy = name
                self._emit()
        elif rs_id == "setting-marker-recoil":
            name = self._recoil_names[idx]
            if name != self._state.marker_recoil_strategy:
                self._state.marker_recoil_strategy = name
                self._emit()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        sw_id = event.switch.id or ""
        v = event.value
        if sw_id == "setting-dual" and v != self._state.show_dual_charts:
            self._state.show_dual_charts = v
            self._emit()
        elif sw_id == "setting-sma" and v != self._state.show_sma:
            self._state.show_sma = v
            self._emit()
        elif sw_id == "setting-vwap" and v != self._state.show_vwap:
            self._state.show_vwap = v
            self._emit()
        elif sw_id == "setting-refs" and v != self._state.show_day_refs:
            self._state.show_day_refs = v
            self._emit()
        elif sw_id == "setting-news-markets" and v != self._state.show_news_markets:
            self._state.show_news_markets = v
            self._emit()
        elif sw_id == "setting-news-trump" and v != self._state.show_news_trump:
            self._state.show_news_trump = v
            self._emit()
        elif (
            sw_id == "setting-congress-trades" and v != self._state.show_congress_trades
        ):
            self._state.show_congress_trades = v
            self._emit()
        elif sw_id == "setting-insider-trades" and v != self._state.show_insider_trades:
            self._state.show_insider_trades = v
            self._emit()
        elif sw_id == "setting-stocktwits" and v != self._state.show_stocktwits:
            self._state.show_stocktwits = v
            self._emit()
        elif sw_id == "setting-futures" and v != self._state.show_futures:
            self._state.show_futures = v
            self._emit()
        elif sw_id.startswith("setting-show-"):
            for name in self._strategy_names:
                if self._signal_switch_id(name) == sw_id:
                    current = self._state.visible_signals.get(name, False)
                    if current != v:
                        self._state.visible_signals[name] = bool(v)
                        self._emit()
                    break
        elif sw_id.startswith("setting-mini-"):
            slug = sw_id[len("setting-mini-") :]
            for tile_id in ALLOWED_MINI_TILES:
                if self._mini_slug(tile_id) == slug:
                    self._toggle_mini_tile(tile_id, bool(v))
                    break

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "setting-close":
            self.dismiss()
        elif bid == "open-edit-math":
            self._on_open_math()
        elif bid.startswith("mini-up-") or bid.startswith("mini-down-"):
            delta = -1 if bid.startswith("mini-up-") else 1
            slug = bid.split("-", 2)[2]
            for tile_id in ALLOWED_MINI_TILES:
                if self._mini_slug(tile_id) == slug:
                    self._move_mini_tile(tile_id, delta)
                    break

    def _emit(self) -> None:
        self._on_change(self._state)
