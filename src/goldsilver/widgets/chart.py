from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from textual_plotext import PlotextPlot

from goldsilver.data.models import Bar


class PriceChart(PlotextPlot):
    DEFAULT_CSS = """
    PriceChart {
        height: 1fr;
        min-height: 8;
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
        self._times: list[datetime] = []
        self._prices: list[float] = []
        self._x_origin: datetime | None = None

    def on_mount(self) -> None:
        self._redraw()

    def seed(
        self, bars: Iterable[Bar], *, x_origin: datetime | None = None
    ) -> None:
        bars_list = list(bars)
        self._x_origin = x_origin
        self._times = [b.time for b in bars_list]
        self._prices = [b.close for b in bars_list]
        self._redraw()

    def add_point(self, price: float, time: datetime) -> None:
        if self._times:
            delta = (time - self._times[-1]).total_seconds()
            if 0 <= delta < self._bucket_seconds:
                self._times[-1] = time
                self._prices[-1] = price
                self._redraw()
                return
            if delta < 0:
                return
        self._times.append(time)
        self._prices.append(price)
        self._redraw()

    def _redraw(self) -> None:
        self.plt.clear_figure()
        if len(self._prices) < 2:
            self.refresh()
            return

        origin = self._x_origin if self._x_origin is not None else self._times[0]
        xs = [(t - origin).total_seconds() / 60.0 for t in self._times]
        self.plt.plot(xs, list(self._prices), color=self._color, marker="braille")

        span_minutes = xs[-1]
        if span_minutes <= 0:
            self.refresh()
            return

        if self._x_origin is not None:
            self.plt.xlim(0, max(span_minutes, xs[-1]))

        ticks, labels = self._compute_ticks(origin, span_minutes)
        if ticks:
            self.plt.xticks(ticks, labels)
        self.refresh()

    def _compute_ticks(
        self, origin: datetime, span_minutes: float
    ) -> tuple[list[float], list[str]]:
        origin_local = origin.astimezone()

        if span_minutes <= 24 * 60:
            step = 30.0
            label_every_minutes = 60
        elif span_minutes <= 7 * 24 * 60:
            step = 6 * 60.0
            label_every_minutes = 24 * 60
        else:
            step = 24 * 60.0
            label_every_minutes = 7 * 24 * 60

        first_offset = self._next_step_offset(origin_local, int(step))
        ticks: list[float] = []
        labels: list[str] = []
        x = first_offset
        while x <= span_minutes:
            tick_time = (origin + timedelta(minutes=x)).astimezone()
            ticks.append(x)
            minutes_from_midnight = tick_time.hour * 60 + tick_time.minute
            if minutes_from_midnight % label_every_minutes == 0:
                labels.append(tick_time.strftime("%H:%M"))
            else:
                labels.append("")
            x += step
        return ticks, labels

    @staticmethod
    def _next_step_offset(start_local: datetime, step_minutes: int) -> float:
        minutes_from_midnight = start_local.hour * 60 + start_local.minute
        remainder = minutes_from_midnight % step_minutes
        if remainder == 0 and start_local.second == 0 and start_local.microsecond == 0:
            return 0.0
        return float(step_minutes - remainder) - (
            start_local.second / 60.0 + start_local.microsecond / 60_000_000.0
        )
