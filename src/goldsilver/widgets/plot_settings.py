from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RadioButton, RadioSet, Switch

from goldsilver.data.settings import (
    DEFAULT_GOLD,
    DEFAULT_SILVER,
    GOLD_PRESETS,
    METALS_COLUMNS_CHOICES,
    SILVER_PRESETS,
)
from goldsilver.data.signal_strategies import STRATEGY_REGISTRY
from goldsilver.widgets.chart import ChartKind


TIMEFRAME_LABELS = ("today", "5d", "1mo", "3mo")


@dataclass(slots=True)
class PlotSettings:
    timeframe_index: int
    chart_kind: ChartKind
    show_sma: bool
    show_vwap: bool
    show_day_refs: bool
    show_news_markets: bool
    show_news_trump: bool
    show_congress_trades: bool
    show_insider_trades: bool
    show_stocktwits: bool
    gold_color_name: str
    silver_color_name: str
    metals_columns: int
    visible_signals: dict[str, bool] = field(default_factory=dict)
    marker_momentum_strategy: str = ""
    marker_recoil_strategy: str = ""


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
        self._gold_names = list(GOLD_PRESETS.keys())
        self._silver_names = list(SILVER_PRESETS.keys())
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
            with VerticalScroll(id="plot-settings-body"):
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
                            yield RadioButton(
                                label, value=(i == self._state.timeframe_index)
                            )
                with Vertical(classes="setting-group"):
                    yield Label("Chart kind", classes="setting-label")
                    with RadioSet(id="setting-kind"):
                        yield RadioButton(
                            "Line", value=(self._state.chart_kind == "line")
                        )
                        yield RadioButton(
                            "Candle", value=(self._state.chart_kind == "candle")
                        )
                with Vertical(classes="setting-group"):
                    yield Label("Overlays", classes="setting-label")
                    with Horizontal(classes="switch-row"):
                        yield Switch(
                            value=self._state.show_sma, id="setting-sma"
                        )
                        yield Label("SMA (20 / 50)", classes="switch-label")
                    with Horizontal(classes="switch-row"):
                        yield Switch(
                            value=self._state.show_vwap, id="setting-vwap"
                        )
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
                                value=self._state.visible_signals.get(
                                    name, False
                                ),
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
                                value=(
                                    name
                                    == self._state.marker_momentum_strategy
                                ),
                            )
                    yield Label("Recoil source", classes="sub-label")
                    with RadioSet(id="setting-marker-recoil"):
                        for name in self._recoil_names:
                            yield RadioButton(
                                name,
                                value=(
                                    name == self._state.marker_recoil_strategy
                                ),
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
                with Vertical(classes="setting-group"):
                    yield Label("Gold color", classes="setting-label")
                    with RadioSet(id="setting-gold-color"):
                        for name in self._gold_names:
                            yield RadioButton(
                                name,
                                value=(name == self._state.gold_color_name),
                            )
                with Vertical(classes="setting-group"):
                    yield Label("Silver color", classes="setting-label")
                    with RadioSet(id="setting-silver-color"):
                        for name in self._silver_names:
                            yield RadioButton(
                                name,
                                value=(name == self._state.silver_color_name),
                            )
            yield Button("Close", variant="primary", id="setting-close")

    @staticmethod
    def _slug(name: str) -> str:
        return "".join(
            ch.lower() if ch.isalnum() else "-" for ch in name
        ).strip("-")

    @classmethod
    def _signal_switch_id(cls, name: str) -> str:
        return f"setting-show-{cls._slug(name)}"

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
        elif rs_id == "setting-gold-color":
            name = self._gold_names[idx]
            if name != self._state.gold_color_name:
                self._state.gold_color_name = name
                self._emit()
        elif rs_id == "setting-silver-color":
            name = self._silver_names[idx]
            if name != self._state.silver_color_name:
                self._state.silver_color_name = name
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
        if sw_id == "setting-sma" and v != self._state.show_sma:
            self._state.show_sma = v
            self._emit()
        elif sw_id == "setting-vwap" and v != self._state.show_vwap:
            self._state.show_vwap = v
            self._emit()
        elif sw_id == "setting-refs" and v != self._state.show_day_refs:
            self._state.show_day_refs = v
            self._emit()
        elif (
            sw_id == "setting-news-markets"
            and v != self._state.show_news_markets
        ):
            self._state.show_news_markets = v
            self._emit()
        elif (
            sw_id == "setting-news-trump"
            and v != self._state.show_news_trump
        ):
            self._state.show_news_trump = v
            self._emit()
        elif (
            sw_id == "setting-congress-trades"
            and v != self._state.show_congress_trades
        ):
            self._state.show_congress_trades = v
            self._emit()
        elif (
            sw_id == "setting-insider-trades"
            and v != self._state.show_insider_trades
        ):
            self._state.show_insider_trades = v
            self._emit()
        elif (
            sw_id == "setting-stocktwits"
            and v != self._state.show_stocktwits
        ):
            self._state.show_stocktwits = v
            self._emit()
        elif sw_id.startswith("setting-show-"):
            for name in self._strategy_names:
                if self._signal_switch_id(name) == sw_id:
                    current = self._state.visible_signals.get(name, False)
                    if current != v:
                        self._state.visible_signals[name] = bool(v)
                        self._emit()
                    break

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "setting-close":
            self.dismiss()
        elif bid == "open-edit-math":
            self._on_open_math()

    def _emit(self) -> None:
        self._on_change(self._state)
