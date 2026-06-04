from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Literal

from textual_plotext import PlotextPlot

from goldsilver.data.models import Bar


ChartKind = Literal["line", "candle"]
ChartZoom = Literal["24h", "3h", "1h"]
ChartMode = Literal["live", "history"]

ZOOM_MINUTES: dict[ChartZoom, int] = {"24h": 24 * 60, "3h": 3 * 60, "1h": 60}
ZOOM_ORDER: tuple[ChartZoom, ...] = ("24h", "3h", "1h")
BAR_RETENTION_HOURS = 25
MAX_BARS = BAR_RETENTION_HOURS * 60  # 1500 @ 1-min bucket

UP_COLOR = (125, 255, 140)
DOWN_COLOR = (255, 107, 107)
VWAP_COLOR = (180, 180, 220)
PREV_CLOSE_COLOR = (140, 140, 160)
HALFHOUR_TICK_COLOR = (90, 90, 110)
CROSSHAIR_COLOR = (180, 180, 220)
PIN_COLOR = (255, 213, 107)


@dataclass(slots=True)
class ChartViewState:
    zoom: ChartZoom = "24h"
    mode: ChartMode = "live"
    crosshair_active: bool = False
    crosshair_index: int | None = None
    pinned_indices: set[int] = field(default_factory=set)


class PriceChart(PlotextPlot):
    DEFAULT_CSS = """
    PriceChart {
        height: 16;
    }
    """

    def __init__(
        self,
        *,
        color: tuple[int, int, int] | str = "white",
        bucket_seconds: float = 60.0,
    ) -> None:
        super().__init__()
        self.theme = "clear"
        self._color = color
        self._bucket_seconds = bucket_seconds
        self._bars: list[Bar] = []
        self._x_origin: datetime | None = None
        self._kind: ChartKind = "line"
        self._show_sma: bool = True
        self._show_vwap: bool = False
        self._show_day_refs: bool = False
        self._prev_close: float | None = None
        self._sess_high: float | None = None
        self._sess_low: float | None = None
        self._markers: list[tuple[datetime, float, tuple[int, int, int], bool]] = []
        self._view = ChartViewState()

    @property
    def zoom(self) -> ChartZoom:
        return self._view.zoom

    @property
    def mode(self) -> ChartMode:
        return self._view.mode

    def on_mount(self) -> None:
        self._redraw()
        self.set_interval(1.0, self._clock_tick)

    def _clock_tick(self) -> None:
        if self._view.mode == "live" and len(self._bars) >= 2:
            self._redraw()

    def seed(
        self,
        bars: Iterable[Bar],
        *,
        x_origin: datetime | None = None,
        kind: ChartKind = "line",
        show_sma: bool = True,
        show_vwap: bool = False,
        show_day_refs: bool = False,
    ) -> None:
        self._bars = list(bars)
        self._x_origin = x_origin
        self._kind = kind
        self._show_sma = show_sma
        self._show_vwap = show_vwap
        self._show_day_refs = show_day_refs
        if not show_day_refs:
            self._prev_close = self._sess_high = self._sess_low = None
        self._view.crosshair_active = False
        self._view.crosshair_index = None
        self._view.pinned_indices.clear()
        self._trim_bars()
        self._redraw()

    def _trim_bars(self) -> None:
        if len(self._bars) > MAX_BARS:
            del self._bars[: len(self._bars) - MAX_BARS]

    def set_color(self, color: tuple[int, int, int] | str) -> None:
        self._color = color
        self._redraw()

    def apply_features(
        self,
        *,
        kind: ChartKind,
        show_sma: bool,
        show_vwap: bool,
        show_day_refs: bool,
    ) -> None:
        self._kind = kind
        self._show_sma = show_sma
        self._show_vwap = show_vwap
        self._show_day_refs = show_day_refs
        if not show_day_refs:
            self._prev_close = self._sess_high = self._sess_low = None
        self._redraw()

    def apply_session_refs(
        self, prev_close: float, day_high: float, day_low: float
    ) -> None:
        if not self._show_day_refs:
            return
        self._prev_close = prev_close
        self._sess_high = day_high
        self._sess_low = day_low
        self._redraw()

    def add_marker(
        self,
        price: float,
        time: datetime,
        color: tuple[int, int, int],
        *,
        heavy: bool = False,
    ) -> None:
        self._markers.append((time, price, color, heavy))
        if len(self._markers) > 200:
            self._markers = self._markers[-200:]
        self._redraw()

    def clear_markers(self) -> None:
        self._markers = []
        self._redraw()

    def add_point(self, price: float, time: datetime) -> None:
        if self._kind != "line" or self._view.mode != "live":
            return
        if self._bars:
            last = self._bars[-1]
            delta = (time - last.time).total_seconds()
            if 0 <= delta < self._bucket_seconds:
                self._bars[-1] = _live_bar(last.symbol, time, price, last)
                self._redraw()
                return
            if delta < 0:
                return
            symbol = last.symbol
        else:
            symbol = ""
        self._bars.append(
            Bar(
                symbol=symbol,
                time=time,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=0.0,
            )
        )
        self._trim_bars()
        self._redraw()

    def set_zoom(self, zoom: ChartZoom) -> None:
        if zoom not in ZOOM_MINUTES:
            return
        if self._view.mode != "live":
            return
        self._view.zoom = zoom
        self._redraw()

    def cycle_zoom(self) -> None:
        if self._view.mode != "live":
            return
        i = ZOOM_ORDER.index(self._view.zoom)
        self._view.zoom = ZOOM_ORDER[(i + 1) % len(ZOOM_ORDER)]
        self._redraw()

    def set_mode(self, mode: ChartMode) -> None:
        if mode not in ("live", "history"):
            return
        if mode == self._view.mode:
            return
        self._view.mode = mode
        if mode == "history":
            self._view.crosshair_active = False
            self._view.crosshair_index = None
        self._redraw()

    def cycle_mode(self) -> None:
        self.set_mode("history" if self._view.mode == "live" else "live")

    def activate_crosshair(self) -> None:
        if self._view.mode != "live" or len(self._bars) < 2:
            return
        self._view.crosshair_active = True
        if self._view.crosshair_index is None:
            self._view.crosshair_index = len(self._bars) - 1
        self._redraw()

    def dismiss_crosshair(self) -> None:
        if not self._view.crosshair_active:
            return
        self._view.crosshair_active = False
        self._redraw()

    def toggle_crosshair(self) -> None:
        if self._view.crosshair_active:
            self.dismiss_crosshair()
        else:
            self.activate_crosshair()

    def move_crosshair(self, step: int) -> None:
        if not self._view.crosshair_active or not self._bars:
            return
        idx = self._view.crosshair_index
        if idx is None:
            idx = len(self._bars) - 1
        idx = max(0, min(len(self._bars) - 1, idx + step))
        self._view.crosshair_index = idx
        self._redraw()

    def pin_current(self) -> None:
        if not self._view.crosshair_active:
            return
        idx = self._view.crosshair_index
        if idx is None:
            return
        if idx in self._view.pinned_indices:
            self._view.pinned_indices.discard(idx)
        else:
            self._view.pinned_indices.add(idx)
        self._redraw()

    def clear_pins(self) -> None:
        if not self._view.pinned_indices:
            return
        self._view.pinned_indices.clear()
        self._redraw()

    def on_mouse_scroll_up(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._view.mode != "live":
            return
        i = ZOOM_ORDER.index(self._view.zoom)
        if i + 1 < len(ZOOM_ORDER):
            self._view.zoom = ZOOM_ORDER[i + 1]
            self._redraw()
        event.stop()

    def on_mouse_scroll_down(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._view.mode != "live":
            return
        i = ZOOM_ORDER.index(self._view.zoom)
        if i > 0:
            self._view.zoom = ZOOM_ORDER[i - 1]
            self._redraw()
        event.stop()

    def _redraw(self) -> None:
        self.plt.clear_figure()
        self.border_subtitle = None
        if len(self._bars) < 2:
            self.refresh()
            return

        origin = self._bars[0].time
        xs = [(b.time - origin).total_seconds() / 60.0 for b in self._bars]
        closes = [b.close for b in self._bars]
        span_minutes = xs[-1]
        if span_minutes <= 0:
            self.refresh()
            return

        if self._view.mode == "live":
            window = ZOOM_MINUTES[self._view.zoom]
            now = datetime.now(timezone.utc)
            if origin.tzinfo is None:
                now = now.replace(tzinfo=None)
            now_offset = (now - origin).total_seconds() / 60.0
            xmax = max(span_minutes, now_offset)
            xmin = max(0.0, xmax - window)
        else:
            xmin = 0.0
            xmax = span_minutes

        i_start, i_end = _visible_slice(xs, xmin, xmax)
        v_xs = xs[i_start:i_end]
        v_bars = self._bars[i_start:i_end]
        v_closes = closes[i_start:i_end]

        if self._kind == "candle" and v_bars:
            self.plt.candlestick(
                v_xs,
                {
                    "Open": [b.open for b in v_bars],
                    "High": [b.high for b in v_bars],
                    "Low": [b.low for b in v_bars],
                    "Close": v_closes,
                },
                colors=[UP_COLOR, DOWN_COLOR],
            )
        elif v_xs:
            self.plt.plot(v_xs, v_closes, color=self._color, marker="braille")

        if self._show_sma:
            for period, dim in ((20, 0.75), (50, 0.50)):
                if len(closes) >= period:
                    sma = _rolling_mean(closes, period)
                    sma_xs = xs[period - 1 :]
                    j_start, j_end = _visible_slice(sma_xs, xmin, xmax)
                    if j_end > j_start:
                        self.plt.plot(
                            sma_xs[j_start:j_end],
                            sma[j_start:j_end],
                            color=_dim_rgb(self._color, dim),
                            marker="braille",
                        )

        if self._show_vwap:
            vwap = _vwap(closes, [b.volume for b in self._bars])
            if vwap:
                v_vwap = vwap[i_start:i_end]
                if v_xs:
                    self.plt.plot(v_xs, v_vwap, color=VWAP_COLOR, marker="braille")

        if self._show_day_refs:
            if self._prev_close is not None:
                self.plt.hline(self._prev_close, color=PREV_CLOSE_COLOR)
            if self._sess_high is not None:
                self.plt.hline(self._sess_high, color=UP_COLOR)
            if self._sess_low is not None:
                self.plt.hline(self._sess_low, color=DOWN_COLOR)

        if self._markers:
            visible_start = self._bars[0].time
            visible_end = self._bars[-1].time
            by_group: dict[
                tuple[tuple[int, int, int], bool],
                tuple[list[float], list[float]],
            ] = {}
            for time, price, color, heavy in self._markers:
                if not (visible_start <= time <= visible_end):
                    continue
                mx = (time - origin).total_seconds() / 60.0
                if not (xmin <= mx <= xmax):
                    continue
                key = (color, heavy)
                by_group.setdefault(key, ([], []))
                by_group[key][0].append(mx)
                by_group[key][1].append(price)
            for (color, heavy), (mxs, mys) in by_group.items():
                self.plt.scatter(
                    mxs,
                    mys,
                    color=color,
                    marker="●" if heavy else "braille",
                )

        self.plt.xlim(xmin, xmax)
        y_lo, y_hi = self._visible_ylim(v_bars, v_closes)
        if y_lo is not None and y_hi is not None:
            self.plt.ylim(y_lo, y_hi)

        halfhour_xs, halfhour_ys = self._halfhour_marks(
            origin, xs, closes, xmin, xmax, y_lo
        )
        if halfhour_xs:
            self.plt.scatter(
                halfhour_xs,
                halfhour_ys,
                color=HALFHOUR_TICK_COLOR,
                marker="|",
            )

        if self._view.mode == "live" and self._view.crosshair_active:
            idx = self._view.crosshair_index
            if idx is not None and 0 <= idx < len(self._bars):
                cx = xs[idx]
                if xmin <= cx <= xmax:
                    self.plt.vline(cx, color=CROSSHAIR_COLOR)
                    local = self._bars[idx].time.astimezone()
                    self.border_subtitle = (
                        f"{local.strftime('%H:%M:%S')}  {self._bars[idx].close:.2f}"
                    )

        if self._view.pinned_indices:
            pin_xs: list[float] = []
            pin_ys: list[float] = []
            for idx in self._view.pinned_indices:
                if 0 <= idx < len(self._bars):
                    px = xs[idx]
                    if xmin <= px <= xmax:
                        pin_xs.append(px)
                        pin_ys.append(self._bars[idx].close)
            if pin_xs:
                self.plt.scatter(pin_xs, pin_ys, color=PIN_COLOR, marker="●")

        ticks, labels = self._compute_ticks(origin, xmin, xmax)
        if ticks:
            self.plt.xticks(ticks, labels)
        self.refresh()

    def _halfhour_marks(
        self,
        origin: datetime,
        xs: list[float],
        closes: list[float],
        xmin: float,
        xmax: float,
        y_floor: float | None,
    ) -> tuple[list[float], list[float]]:
        if not closes:
            return [], []
        if self._view.mode == "history":
            return [], []
        if self._view.zoom == "1h":
            step = 15
        else:
            step = 30
        ymin = y_floor if y_floor is not None else min(closes)
        origin_local = origin.astimezone()
        first = self._next_step_offset(origin_local, step)
        out_x: list[float] = []
        out_y: list[float] = []
        x = first
        while x <= xmax:
            if x >= xmin:
                tick_time = (origin + timedelta(minutes=x)).astimezone()
                mins = tick_time.hour * 60 + tick_time.minute
                if mins % 60 != 0:
                    out_x.append(x)
                    out_y.append(ymin)
            x += step
        return out_x, out_y

    def _visible_ylim(
        self, v_bars: list[Bar], v_closes: list[float]
    ) -> tuple[float | None, float | None]:
        if not v_bars:
            return None, None
        if self._kind == "candle":
            lo = min(b.low for b in v_bars)
            hi = max(b.high for b in v_bars)
        else:
            lo = min(v_closes)
            hi = max(v_closes)
        if self._show_day_refs:
            for ref in (self._prev_close, self._sess_high, self._sess_low):
                if ref is not None:
                    lo = min(lo, ref)
                    hi = max(hi, ref)
        if hi == lo:
            margin = max(abs(hi) * 0.001, 0.01)
        else:
            margin = (hi - lo) * 0.05
        return lo - margin, hi + margin

    def _compute_ticks(
        self, origin: datetime, xmin: float, xmax: float
    ) -> tuple[list[float], list[str]]:
        origin_local = origin.astimezone()
        span = xmax - xmin
        if self._view.mode == "history":
            if span <= 24 * 60:
                step = 60.0
            elif span <= 7 * 24 * 60:
                step = 6 * 60.0
            else:
                step = 24 * 60.0
        elif self._view.zoom == "1h":
            step = 60.0
        else:
            step = self._live_hour_step(span)

        first_offset = self._next_step_offset(origin_local, int(step))
        if first_offset < xmin:
            skips = int((xmin - first_offset) // step) + 1
            first_offset += skips * step
        ticks: list[float] = []
        labels: list[str] = []
        x = first_offset
        while x <= xmax:
            tick_time = (origin + timedelta(minutes=x)).astimezone()
            ticks.append(x)
            if self._view.mode == "history":
                labels.append(tick_time.strftime("%H:%M"))
            elif self._view.zoom == "1h":
                labels.append(tick_time.strftime("%H:%M"))
            else:
                labels.append(tick_time.strftime("%H"))
            x += step
        return ticks, labels

    def _live_hour_step(self, span: float) -> float:
        cols = self.content_size.width or self.size.width or 80
        avail = max(20, cols - 10)
        max_labels = max(2, avail // 5)
        hours = span / 60.0
        for mult in (1, 2, 3, 4, 6, 12):
            if hours / mult <= max_labels:
                return mult * 60.0
        return 24 * 60.0

    @staticmethod
    def _next_step_offset(start_local: datetime, step_minutes: int) -> float:
        minutes_from_midnight = start_local.hour * 60 + start_local.minute
        remainder = minutes_from_midnight % step_minutes
        if remainder == 0 and start_local.second == 0 and start_local.microsecond == 0:
            return 0.0
        return float(step_minutes - remainder) - (
            start_local.second / 60.0 + start_local.microsecond / 60_000_000.0
        )


def _visible_slice(xs: list[float], xmin: float, xmax: float) -> tuple[int, int]:
    if not xs:
        return 0, 0
    i_start = 0
    while i_start < len(xs) and xs[i_start] < xmin:
        i_start += 1
    if i_start > 0:
        i_start -= 1
    i_end = i_start
    while i_end < len(xs) and xs[i_end] <= xmax:
        i_end += 1
    if i_end < len(xs):
        i_end += 1
    return i_start, i_end


def _live_bar(symbol: str, time: datetime, price: float, prev: Bar) -> Bar:
    return Bar(
        symbol=symbol,
        time=time,
        open=prev.open,
        high=max(prev.high, price),
        low=min(prev.low, price),
        close=price,
        volume=prev.volume,
    )


def _rolling_mean(values: list[float], period: int) -> list[float]:
    out: list[float] = []
    window_sum = sum(values[:period])
    out.append(window_sum / period)
    for i in range(period, len(values)):
        window_sum += values[i] - values[i - period]
        out.append(window_sum / period)
    return out


def _vwap(closes: list[float], volumes: list[float]) -> list[float]:
    out: list[float] = []
    cum_pv = 0.0
    cum_v = 0.0
    last: float | None = None
    for c, v in zip(closes, volumes):
        if v > 0:
            cum_pv += c * v
            cum_v += v
            last = cum_pv / cum_v
        elif last is None:
            last = c
        out.append(last)
    return out


def _dim_rgb(
    color: tuple[int, int, int] | str, factor: float
) -> tuple[int, int, int] | str:
    if isinstance(color, str):
        return color
    r, g, b = color
    return (
        max(0, min(255, int(r * factor))),
        max(0, min(255, int(g * factor))),
        max(0, min(255, int(b * factor))),
    )
