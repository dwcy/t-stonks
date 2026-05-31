from __future__ import annotations

from datetime import date, datetime, time, timedelta

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models_macro import OmxSnapshot
from goldsilver.data.session import STOCKHOLM


OMX_REGULAR_CLOSE = time(17, 30)
EARLY_CLOSE_MIN_GAP_MIN = 60


class OmxStrip(Static):
    snapshot: reactive[OmxSnapshot | None] = reactive(None)
    stale_since: reactive[datetime | None] = reactive(None)

    def __init__(self) -> None:
        super().__init__("")
        self.add_class("omx-strip")

    def apply_snapshot(self, snapshot: OmxSnapshot) -> None:
        self.stale_since = None
        self.snapshot = snapshot

    def mark_stale(self, since: datetime) -> None:
        self.stale_since = since

    def watch_snapshot(self, _: OmxSnapshot | None) -> None:
        self._redraw()

    def watch_stale_since(self, _: datetime | None) -> None:
        self._redraw()

    def _redraw(self) -> None:
        snap = self.snapshot
        if snap is None:
            self.update(Text("Sthlm OMX30  loading…", style="#7a7a8a"))
            return

        date_pct: dict[date, float] = {d.date: d.change_percent for d in snap.days}
        today_stk = snap.fetched_at.astimezone(STOCKHOLM).date()
        session_date = snap.latest_session_date
        if session_date == today_stk:
            date_pct[today_stk] = snap.current_change_percent

        this_monday = today_stk - timedelta(days=today_stk.weekday())
        early_close = self._is_early_close(snap, today_stk)

        text = Text()
        today_pct = snap.current_change_percent
        dot_color = "#7dff8c" if snap.market_open else "#7a7a8a"
        text.append("● ", style=dot_color)
        text.append("OMX30", style="bold #a0a0b0")
        if snap.market_open:
            if today_pct > 0:
                day_color = "#7dff8c"
            elif today_pct < 0:
                day_color = "#ff6b6b"
            else:
                day_color = "#c0c0d0"
            text.append(f" {today_pct:+.2f}%", style=day_color)
        if snap.ytd_change_percent is not None:
            ytd = snap.ytd_change_percent
            if ytd > 0:
                ytd_color = "#7dff8c"
            elif ytd < 0:
                ytd_color = "#ff6b6b"
            else:
                ytd_color = "#c0c0d0"
            sign = "+" if ytd >= 0 else ""
            text.append(" (", style="dim #5a5a6a")
            text.append(f"YTD {sign}{ytd:.1f}%", style=ytd_color)
            text.append(")", style="dim #5a5a6a")

        for week_n in (3, 2, 1):
            week_start = this_monday - timedelta(days=7 * week_n)
            text.append("  ", style="#5a5a6a")
            self._render_past_week(text, week_start, week_n, date_pct, today_stk)

        text.append("  ", style="#5a5a6a")
        self._render_this_week(
            text,
            this_monday,
            date_pct,
            today_stk,
            session_date,
            snap.market_open,
            snap.current_change_percent,
            early_close,
        )

        if not snap.market_open and session_date == today_stk:
            if today_pct > 0:
                arrow, color = "▲", "#7dff8c"
            elif today_pct < 0:
                arrow, color = "▼", "#ff6b6b"
            else:
                arrow, color = "·", "#7a7a8a"
            text.append(f"  {arrow} {today_pct:+.2f}%", style=f"bold {color}")

        if self.stale_since is not None:
            local = self.stale_since.astimezone()
            text.append(f"  · stale {local.strftime('%H:%M')}", style="dim #ff6b6b")

        self.update(text)

    @staticmethod
    def _render_past_week(
        text: Text,
        week_start: date,
        week_n: int,
        date_pct: dict[date, float],
        today_stk: date,
    ) -> None:
        factor = 1.0
        for di in range(5):
            d = week_start + timedelta(days=di)
            if d in date_pct:
                factor *= 1.0 + date_pct[d] / 100.0
        week_pct = (factor - 1.0) * 100.0
        if week_pct > 0:
            week_color = "#7dff8c"
        elif week_pct < 0:
            week_color = "#ff6b6b"
        else:
            week_color = "#7a7a8a"
        sign = "+" if week_pct > 0 else ""

        text.append("[", style="#5a5a6a")
        text.append(f"{week_n}w ", style="dim #a0a0b0")
        text.append(f"({sign}{week_pct:.1f}%) ", style=week_color)
        for di in range(5):
            if di > 0:
                text.append(" ", style="#5a5a6a")
            d = week_start + timedelta(days=di)
            OmxStrip._render_day_symbol(text, d, date_pct, today_stk)
        text.append("]", style="#5a5a6a")

    @staticmethod
    def _render_this_week(
        text: Text,
        week_start: date,
        date_pct: dict[date, float],
        today_stk: date,
        session_date: date | None,
        market_open: bool,
        current_pct: float,
        early_close: bool,
    ) -> None:
        factor = 1.0
        for di in range(5):
            d = week_start + timedelta(days=di)
            if d in date_pct:
                factor *= 1.0 + date_pct[d] / 100.0
        week_pct = (factor - 1.0) * 100.0
        if week_pct > 0:
            week_color = "#7dff8c"
        elif week_pct < 0:
            week_color = "#ff6b6b"
        else:
            week_color = "#7a7a8a"
        sign = "+" if week_pct > 0 else ""

        text.append("this week ", style="dim #a0a0b0")
        text.append(f"({sign}{week_pct:.1f}%) ", style=week_color)
        text.append("[", style="#5a5a6a")
        for di in range(5):
            if di > 0:
                text.append(" ", style="#5a5a6a")
            d = week_start + timedelta(days=di)
            if d == today_stk and early_close:
                if current_pct > 0:
                    color = "#7dff8c"
                elif current_pct < 0:
                    color = "#ff6b6b"
                else:
                    color = "#7a7a8a"
                text.append("H", style=f"bold {color}")
            elif d == today_stk and (market_open or session_date == today_stk):
                pct = current_pct
                if pct > 0:
                    text.append("▲", style="#7dff8c")
                elif pct < 0:
                    text.append("▼", style="#ff6b6b")
                else:
                    text.append("·", style="#7a7a8a")
            else:
                OmxStrip._render_day_symbol(text, d, date_pct, today_stk)
        text.append("]", style="#5a5a6a")

    @staticmethod
    def _render_day_symbol(
        text: Text,
        d: date,
        date_pct: dict[date, float],
        today_stk: date,
    ) -> None:
        if d > today_stk:
            text.append("-", style="#5a5a6a")
            return
        if d in date_pct:
            pct = date_pct[d]
            if pct > 0:
                text.append("▲", style="#7dff8c")
            elif pct < 0:
                text.append("▼", style="#ff6b6b")
            else:
                text.append("·", style="#7a7a8a")
            return
        text.append("x", style="#5a5a6a")

    @staticmethod
    def _is_early_close(snap: OmxSnapshot, today_stk: date) -> bool:
        if snap.market_open:
            return False
        if snap.latest_session_date != today_stk:
            return False
        close_ts = snap.latest_session_close_time
        if close_ts is None:
            return False
        local = close_ts.astimezone(STOCKHOLM)
        regular = datetime.combine(today_stk, OMX_REGULAR_CLOSE, tzinfo=STOCKHOLM)
        return (regular - local).total_seconds() >= EARLY_CLOSE_MIN_GAP_MIN * 60
