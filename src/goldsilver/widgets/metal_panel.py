from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.color import Color
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models import Bar, Tick
from goldsilver.data.models_macro import Signal
from goldsilver.data.signal_strategy_info import (
    INDICATOR_INFO,
    INDICATOR_PRIORITY_ORDER,
)
from goldsilver.widgets.chart import ChartKind, ChartMode, ChartZoom, PriceChart


def _rgb(color: tuple[int, int, int] | str) -> str:
    if isinstance(color, str):
        return color
    r, g, b = color
    return f"rgb({r},{g},{b})"


def _short_strategy_label(name: str) -> str:
    info = INDICATOR_INFO.get(name)
    return info.short_label if info is not None else name.split()[0]


def _priority_sorted(names: list[str]) -> list[str]:
    return sorted(
        names,
        key=lambda n: (
            INDICATOR_PRIORITY_ORDER.index(n)
            if n in INDICATOR_PRIORITY_ORDER
            else len(INDICATOR_PRIORITY_ORDER)
        ),
    )


class _ChangeRow(Static):
    """Change/indicator row that toggles a badge's description on click."""

    def __init__(
        self, *, on_indicator_click: Callable[[str], None], **kwargs: object
    ) -> None:
        super().__init__("", **kwargs)  # type: ignore[arg-type]
        self._on_indicator_click = on_indicator_click

    def on_click(self, event: events.Click) -> None:
        style = event.style
        key = style.meta.get("indicator") if style is not None else None
        if key is not None:
            self._on_indicator_click(key)
            event.stop()


class MetalPanel(Vertical):
    price: reactive[float | None] = reactive(None)
    change: reactive[float] = reactive(0.0)
    change_percent: reactive[float] = reactive(0.0)
    day_high: reactive[float] = reactive(0.0)
    day_low: reactive[float] = reactive(0.0)
    updated_at: reactive[datetime | None] = reactive(None)
    expanded_indicator: reactive[str | None] = reactive(None)

    def __init__(
        self,
        symbol: str,
        label: str,
        *,
        accent_color: tuple[int, int, int] | str = "white",
        classes: str = "",
    ) -> None:
        super().__init__(classes=classes)
        self.symbol = symbol
        self._accent = _rgb(accent_color)
        self.border_title = label
        self._signals: dict[str, Signal | None] = {}
        self._visible_signals: list[str] = []
        self._stats: dict[str, float] | None = None

    def compose(self) -> ComposeResult:
        yield Static("--:--:--", id="updated", classes="updated")
        yield Static(self._render_header(), id="header", classes="header")
        yield _ChangeRow(
            on_indicator_click=self._toggle_indicator,
            id="change-row",
            classes="change-row",
        )
        yield Static("", id="indicator-detail", classes="indicator-detail")
        yield PriceChart(color=self._accent_rgb_tuple())

    def _accent_rgb_tuple(self) -> tuple[int, int, int] | str:
        if self._accent.startswith("rgb("):
            inner = self._accent[4:-1]
            r, g, b = (int(x) for x in inner.split(","))
            return (r, g, b)
        return self._accent

    def seed_history(
        self,
        bars: list[Bar],
        *,
        x_origin: datetime | None = None,
        chart_kind: ChartKind = "line",
        show_sma: bool = True,
        show_vwap: bool = False,
        show_day_refs: bool = False,
    ) -> None:
        self.query_one(PriceChart).seed(
            bars,
            x_origin=x_origin,
            kind=chart_kind,
            show_sma=show_sma,
            show_vwap=show_vwap,
            show_day_refs=show_day_refs,
        )

    def set_accent(self, rgb: tuple[int, int, int]) -> None:
        self._accent = _rgb(rgb)
        color = Color(*rgb)
        self.styles.border = ("round", color)
        self.styles.border_title_color = color
        chart = self.query_one(PriceChart)
        chart.set_color(rgb)
        self._refresh_header()
        self._refresh_change_row()

    def apply_chart_features(
        self,
        *,
        chart_kind: ChartKind,
        show_sma: bool,
        show_vwap: bool,
        show_day_refs: bool,
    ) -> None:
        self.query_one(PriceChart).apply_features(
            kind=chart_kind,
            show_sma=show_sma,
            show_vwap=show_vwap,
            show_day_refs=show_day_refs,
        )

    def set_visible_signals(self, names: list[str]) -> None:
        self._visible_signals = list(names)
        self._refresh_indicators()

    def apply_signal(self, signal: Signal) -> None:
        self._signals[signal.strategy] = signal
        if signal.strategy in self._visible_signals:
            self._refresh_indicators()

    def apply_tick(self, tick: Tick) -> None:
        self.price = tick.price
        self.change = tick.change
        self.change_percent = tick.change_percent
        self.day_high = tick.day_high
        self.day_low = tick.day_low
        self.updated_at = tick.time
        chart = self.query_one(PriceChart)
        chart.apply_session_refs(tick.prev_close, tick.day_high, tick.day_low)
        chart.add_point(tick.price, tick.time)

    def add_marker(
        self,
        price: float,
        time: datetime,
        color: tuple[int, int, int],
        *,
        heavy: bool = False,
    ) -> None:
        self.query_one(PriceChart).add_marker(price, time, color, heavy=heavy)

    def clear_markers(self) -> None:
        self.query_one(PriceChart).clear_markers()

    def set_stats(
        self,
        *,
        week_high: float,
        week_low: float,
        week_avg: float,
        month_avg: float,
        year_avg: float,
        ma200: float | None = None,
    ) -> None:
        self._stats = {
            "wh": week_high,
            "wl": week_low,
            "w": week_avg,
            "m": month_avg,
            "y": year_avg,
        }
        if ma200 is not None:
            self._stats["ma200"] = ma200
        self._refresh_header()

    def _refresh_indicators(self) -> None:
        self._refresh_change_row()

    def _toggle_indicator(self, name: str) -> None:
        self.expanded_indicator = None if self.expanded_indicator == name else name

    def watch_expanded_indicator(self, _: str | None) -> None:
        self._refresh_indicator_detail()

    def _render_indicators(self) -> Text:
        if not self._visible_signals:
            return Text("")
        text = Text()
        for i, name in enumerate(_priority_sorted(self._visible_signals)):
            if i > 0:
                text.append("  ·  ", style="#3a3a4a")
            badge_start = len(text)
            label = _short_strategy_label(name)
            sig = self._signals.get(name)
            label_color = (
                "dim #bb9af7"
                if sig is not None and sig.kind == "recoil"
                else "dim #7dcfff"
            )
            text.append(f"{label} ", style=label_color)
            if sig is None:
                text.append("warming up", style="dim #5a5a6a")
            elif sig.action == "BUY":
                text.append("▲ BUY", style="bold #7dff8c")
                text.append(f" {sig.intensity_sigma:.1f}σ", style="#7dff8c")
            elif sig.action == "SELL":
                text.append("▼ SELL", style="bold #ff6b6b")
                text.append(f" {sig.intensity_sigma:.1f}σ", style="#ff6b6b")
            else:
                text.append("· idle", style="dim #7a7a8a")
            if name in INDICATOR_INFO:
                text.stylize(Style(meta={"indicator": name}), badge_start, len(text))
        return text

    def _render_indicator_detail(self) -> Text:
        name = self.expanded_indicator
        info = INDICATOR_INFO.get(name) if name is not None else None
        if info is None:
            return Text("")
        text = Text()
        text.append(f"{name}  ", style="bold #e0e0e8")
        text.append(
            f"priority {info.priority_rank}/{len(INDICATOR_PRIORITY_ORDER)}\n",
            style="dim #7a7a8a",
        )
        text.append(f"{info.description}\n", style="#c0c0d0")
        text.append(info.rationale, style="dim #9a9aa8")
        return text

    def _refresh_indicator_detail(self) -> None:
        widget = self.query_one_optional("#indicator-detail", Static)
        if widget is not None:
            widget.update(self._render_indicator_detail())

    def set_chart_zoom(self, zoom: ChartZoom) -> None:
        self.query_one(PriceChart).set_zoom(zoom)

    def cycle_chart_zoom(self) -> None:
        self.query_one(PriceChart).cycle_zoom()

    def set_chart_mode(self, mode: ChartMode) -> None:
        self.query_one(PriceChart).set_mode(mode)

    def cycle_chart_mode(self) -> None:
        self.query_one(PriceChart).cycle_mode()

    def toggle_crosshair(self) -> None:
        self.query_one(PriceChart).toggle_crosshair()

    def move_crosshair(self, step: int) -> None:
        self.query_one(PriceChart).move_crosshair(step)

    def pin_current(self) -> None:
        self.query_one(PriceChart).pin_current()

    def clear_pins(self) -> None:
        self.query_one(PriceChart).clear_pins()

    @property
    def chart_zoom(self) -> ChartZoom:
        return self.query_one(PriceChart).zoom

    @property
    def chart_mode(self) -> ChartMode:
        return self.query_one(PriceChart).mode

    def watch_price(self, _: float | None) -> None:
        self._refresh_header()
        self._refresh_change_row()

    def watch_change(self, _: float) -> None:
        self._refresh_change_row()

    def watch_change_percent(self, _: float) -> None:
        self._refresh_change_row()

    def watch_day_high(self, _: float) -> None:
        self._refresh_header()

    def watch_day_low(self, _: float) -> None:
        self._refresh_header()

    def watch_updated_at(self, ts: datetime | None) -> None:
        widget = self.query_one_optional("#updated", Static)
        if widget is None:
            return
        if ts is None:
            widget.update(Text("--:--:--", style="dim #5a5a6a"))
            return
        local = ts.astimezone()
        widget.update(Text(local.strftime("%H:%M:%S"), style="dim #7a7a8a"))

    def _render_header(self) -> Text:
        if self.price is None:
            return Text("waiting…", style="dim #7a7a8a")
        parts: list[tuple[str, str]] = [
            (f"{self.price:,.2f} ", f"bold {self._accent}"),
            ("USD", "dim #7a7a8a"),
        ]
        if self.day_high != 0.0 or self.day_low != 0.0:
            parts.extend(
                [
                    ("   ", ""),
                    ("H ", "#7a7a8a"),
                    (f"{self.day_high:,.2f}", "#7dff8c"),
                    ("   ", ""),
                    ("L ", "#7a7a8a"),
                    (f"{self.day_low:,.2f}", "#ff6b6b"),
                ]
            )
        text = Text.assemble(*parts)
        if self._stats is not None:
            s = self._stats
            text.append("   ", style="")
            text.append("WH ", style="dim #7a7a8a")
            text.append(f"{s['wh']:,.2f}", style="#7dff8c")
            text.append("  WL ", style="dim #7a7a8a")
            text.append(f"{s['wl']:,.2f}", style="#ff6b6b")
            text.append("  W̄ ", style="dim #7a7a8a")
            text.append(f"{s['w']:,.2f}", style="#c0c0d0")
            text.append("  ·  ", style="#3a3a4a")
            text.append("M̄ ", style="dim #7a7a8a")
            text.append(f"{s['m']:,.2f}", style="#c0c0d0")
            text.append("  ·  ", style="#3a3a4a")
            text.append("Ȳ ", style="dim #7a7a8a")
            text.append(f"{s['y']:,.2f}", style="#c0c0d0")
            if "ma200" in s:
                text.append("  ·  ", style="#3a3a4a")
                text.append("MA200 ", style="dim #7a7a8a")
                text.append(f"{s['ma200']:,.2f}", style="#64c8e6")
        return text

    def _render_change_row(self) -> Text:
        if self.price is None:
            return Text("")
        change_style = "#7dff8c" if self.change >= 0 else "#ff6b6b"
        arrow = "▲" if self.change >= 0 else "▼"
        sign = "+" if self.change >= 0 else ""
        text = Text.assemble(
            (arrow, change_style),
            (f" {sign}{self.change_percent:.2f}%", change_style),
        )
        indicators = self._render_indicators()
        if indicators.plain:
            text.append("    ", style="")
            text.append_text(indicators)
        return text

    def _refresh_header(self) -> None:
        widget = self.query_one_optional("#header", Static)
        if widget is not None:
            widget.update(self._render_header())

    def _refresh_change_row(self) -> None:
        widget = self.query_one_optional("#change-row", Static)
        if widget is not None:
            widget.update(self._render_change_row())
