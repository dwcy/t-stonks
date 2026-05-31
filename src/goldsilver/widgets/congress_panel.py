from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models_macro import CongressTrade, PoliticianStats


_PARTY_STYLE = {
    "R": "#ff6b6b",
    "D": "#5dade2",
    "I": "#a0a0b0",
}

_CHAMBER_LABEL = {
    "HOUSE": "H",
    "SENATE": "S",
}


_NAME_SUFFIXES = (
    " Incorporated", " Corporation", " Holdings Inc", " Holdings",
    " Group Inc", " Company", " Inc", " Corp", " Co", " Ltd", " Plc",
    " LP", " LLC", " SA", " AG", " NV",
)


def _short_name(name: str, *, max_chars: int = 18) -> str:
    cleaned = name.strip().rstrip(".,&")
    for suf in _NAME_SUFFIXES:
        if cleaned.lower().endswith(suf.lower()):
            cleaned = cleaned[: -len(suf)].rstrip(" .,&")
            break
    if len(cleaned) > max_chars:
        cleaned = cleaned[: max_chars - 1].rstrip() + "…"
    return cleaned


def _format_age(seconds: int) -> str:
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        h, rem = divmod(seconds, 3600)
        m = rem // 60
        return f"{h}h" if m == 0 else f"{h}h {m}m"
    d, rem = divmod(seconds, 86400)
    h = rem // 3600
    return f"{d}d" if h == 0 else f"{d}d {h}h"


class CongressPanel(VerticalScroll):
    trades: reactive[tuple[CongressTrade, ...]] = reactive(())
    stats: reactive[tuple[PoliticianStats, ...]] = reactive(())
    returns: reactive[dict[tuple[str, str, datetime], float | None]] = reactive({})
    stale_since: reactive[datetime | None] = reactive(None)

    def __init__(
        self,
        title: str = "Congress trades",
        *,
        max_trades: int = 60,
        top_politicians: int = 3,
    ) -> None:
        super().__init__()
        self.border_title = title
        self._max_trades = max_trades
        self._top_politicians = top_politicians

    def compose(self) -> ComposeResult:
        yield Static("loading…", id="congress-body")

    def replace_data(
        self,
        trades: list[CongressTrade],
        stats: list[PoliticianStats],
        returns: dict[tuple[str, str, datetime], float | None],
    ) -> None:
        self.stale_since = None
        self.trades = tuple(trades[: self._max_trades])
        self.stats = tuple(stats)
        self.returns = dict(returns)

    def mark_stale(self, since: datetime) -> None:
        self.stale_since = since

    def watch_trades(self, _: tuple[CongressTrade, ...]) -> None:
        self._redraw()

    def watch_stats(self, _: tuple[PoliticianStats, ...]) -> None:
        self._redraw()

    def watch_returns(
        self, _: dict[tuple[str, str, datetime], float | None]
    ) -> None:
        self._redraw()

    def watch_stale_since(self, _: datetime | None) -> None:
        self._redraw()

    def _redraw(self) -> None:
        body = self.query_one("#congress-body", Static)
        if not self.trades and not self.stats:
            body.update(Text("loading…", style="#7a7a8a"))
            self.border_subtitle = ""
            return
        text = Text()
        self._render_leaderboard(text)
        if self.trades:
            text.append("\n", style="#3a3a4a")
            self._render_trades(text)
        body.update(text)
        if self.stale_since is not None:
            local = self.stale_since.astimezone().strftime("%H:%M")
            self.border_subtitle = f"stale since {local}"
        elif self.trades:
            latest = max(t.traded_at for t in self.trades).astimezone()
            self.border_subtitle = (
                f"latest {latest.strftime('%b %d')} · "
                f"mark-to-now, BUY-side only"
            )
        else:
            self.border_subtitle = ""

    def _render_leaderboard(self, text: Text) -> None:
        scored = [s for s in self.stats if s.avg_return_pct is not None]
        if not scored:
            text.append(
                "no return data yet — yfinance closes pending\n",
                style="#7a7a8a",
            )
            return
        text.append("Top 30d (avg BUY return)  ", style="bold #e0e0e8")
        text.append("\n", style="#3a3a4a")
        for s in scored[: self._top_politicians]:
            self._render_stat_row(text, s)
        if len(scored) > self._top_politicians:
            worst = scored[-1]
            if worst is not scored[self._top_politicians - 1]:
                text.append("  ⋯ worst:  ", style="#7a7a8a")
                self._render_stat_row(text, worst, indent=False)

    def _render_stat_row(
        self, text: Text, s: PoliticianStats, *, indent: bool = True
    ) -> None:
        party_style = _PARTY_STYLE.get(s.party, "#a0a0b0")
        chamber = _CHAMBER_LABEL.get(s.chamber, "?")
        if indent:
            text.append("  ", style="")
        text.append(f"{s.party} ", style=f"bold {party_style}")
        text.append(f"{s.politician:<24} ", style="#e0e0e8")
        text.append(f"[{chamber}] ", style="dim #7a7a8a")
        ret = s.avg_return_pct or 0.0
        ret_style = "#7dff8c" if ret > 0 else "#ff6b6b" if ret < 0 else "#a0a0b0"
        text.append(f"{ret:+6.1f}% ", style=f"bold {ret_style}")
        text.append(
            f" {s.trade_count:>2} trades  {s.buy_count} buys",
            style="#a0a0b0",
        )
        if s.win_rate_pct is not None:
            text.append(
                f"  win {s.win_rate_pct:.0f}%\n", style="dim #a0a0b0"
            )
        else:
            text.append("\n", style="")

    def _render_trades(self, text: Text) -> None:
        now = datetime.now(timezone.utc)
        text.append("Recent trades\n", style="bold #e0e0e8")
        for t in self.trades:
            self._render_trade(text, t, now)

    def _render_trade(
        self, text: Text, t: CongressTrade, now: datetime
    ) -> None:
        party_style = _PARTY_STYLE.get(t.party, "#a0a0b0")
        chamber = _CHAMBER_LABEL.get(t.chamber, "?")
        date_str = t.traded_at.astimezone().strftime("%m-%d")
        age = _format_age(int((now - t.traded_at).total_seconds()))
        side_style = (
            "#7dff8c" if t.side == "BUY"
            else "#ff6b6b" if t.side == "SELL"
            else "#ffd56b"
        )
        text.append(f"{date_str} ", style="#7a7a8a")
        text.append(f"{age:>6} ", style="dim #5a5a6a")
        text.append(f"{t.party} ", style=f"bold {party_style}")
        text.append(f"{t.politician:<22} ", style="#e0e0e8")
        text.append(f"[{chamber}] ", style="dim #7a7a8a")
        text.append(f"{t.ticker:<6}", style="#ffd56b")
        name = _short_name(t.asset_name) if t.asset_name else ""
        text.append(f" {name:<18}", style="dim #c0c0d0")
        text.append(f" {t.side:<5} ", style=f"bold {side_style}")
        text.append(f"{t.size_bucket:<12} ", style="#a0a0b0")
        ret = self.returns.get((t.politician, t.ticker, t.traded_at))
        if ret is None:
            text.append("   —  ", style="dim #5a5a6a")
        else:
            ret_style = (
                "#7dff8c" if ret > 0 else "#ff6b6b" if ret < 0 else "#a0a0b0"
            )
            text.append(f"{ret:+6.1f}%", style=f"bold {ret_style}")
        text.append("\n", style="")
