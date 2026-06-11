from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models_macro import InsiderTrade
from goldsilver.widgets.format import format_age


_CODE_LABEL = {
    "P": "Purchase (open mkt)",
    "S": "Sale (open mkt)",
    "F": "Tax withhold",
    "M": "Option exercise",
    "A": "Grant/award",
    "G": "Gift",
    "C": "Conversion",
    "D": "Sale to issuer",
    "X": "Option exercise",
    "V": "Voluntary",
    "I": "Discretionary",
    "J": "Other",
    "K": "Equity swap",
    "U": "Tender",
    "W": "Acq from will",
    "Z": "In trust",
    "H": "Expiration",
    "E": "Expiration short",
    "O": "Out-of-money exer.",
    "L": "Small acq.",
}


def _format_value(value: float | None) -> str:
    if value is None:
        return "      —"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:.0f}"


def _is_trump(name: str) -> bool:
    return "trump" in name.lower()


class InsiderPanel(VerticalScroll):
    trades: reactive[tuple[InsiderTrade, ...]] = reactive(())
    stale_since: reactive[datetime | None] = reactive(None)

    def __init__(
        self,
        title: str = "Trump Media insider filings (SEC Form 4)",
        *,
        max_trades: int = 40,
    ) -> None:
        super().__init__()
        self.border_title = title
        self._max_trades = max_trades

    def compose(self) -> ComposeResult:
        yield Static("loading…", id="insider-body")

    def replace_trades(self, trades: list[InsiderTrade]) -> None:
        self.stale_since = None
        self.trades = tuple(trades[: self._max_trades])

    def mark_stale(self, since: datetime) -> None:
        self.stale_since = since

    def watch_trades(self, _: tuple[InsiderTrade, ...]) -> None:
        self._redraw()

    def watch_stale_since(self, _: datetime | None) -> None:
        self._redraw()

    def _redraw(self) -> None:
        body = self.query_one("#insider-body", Static)
        if not self.trades:
            body.update(Text("loading…", style="#7a7a8a"))
            self.border_subtitle = ""
            return
        text = Text()
        trump_count = sum(1 for t in self.trades if _is_trump(t.insider_name))
        buys = sum(1 for t in self.trades if t.side == "BUY")
        sells = sum(1 for t in self.trades if t.side == "SELL")
        text.append("DJT ", style="bold #bb9af7")
        text.append(
            f"{len(self.trades)} filings · {buys} acq · {sells} disp",
            style="#a0a0b0",
        )
        if trump_count > 0:
            text.append(
                f"  ·  {trump_count} by Trump",
                style="bold #ffd56b",
            )
        text.append("\n", style="")
        now = datetime.now(timezone.utc)
        for t in self.trades:
            self._render_trade(text, t, now)
        body.update(text)
        latest = max(t.transaction_date for t in self.trades).astimezone()
        marker = f"latest {latest.strftime('%b %d')}"
        if self.stale_since is not None:
            local = self.stale_since.astimezone().strftime("%H:%M")
            marker = f"stale since {local}"
        self.border_subtitle = marker

    def _render_trade(self, text: Text, t: InsiderTrade, now: datetime) -> None:
        is_trump = _is_trump(t.insider_name)
        name_style = "bold #ffd56b" if is_trump else "#e0e0e8"
        side_style = (
            "#7dff8c"
            if t.side == "BUY"
            else "#ff6b6b"
            if t.side == "SELL"
            else "#a0a0b0"
        )
        date_str = t.transaction_date.astimezone().strftime("%m-%d")
        age = format_age(int((now - t.transaction_date).total_seconds()))
        shares = f"{int(t.shares):>9,}" if t.shares is not None else "        —"
        price = (
            f"${t.price_per_share:>6.2f}"
            if t.price_per_share is not None
            else "      —"
        )
        value_str = _format_value(t.value_usd)
        code_label = _CODE_LABEL.get(t.code, t.code)
        prefix = "★ " if is_trump else "  "
        text.append(prefix, style="bold #ffd56b" if is_trump else "")
        text.append(f"{date_str} ", style="#7a7a8a")
        text.append(f"{age:>6} ", style="dim #5a5a6a")
        text.append(f"{t.insider_name:<22} ", style=name_style)
        text.append(f"{t.side:<4} ", style=f"bold {side_style}")
        text.append(f"{t.code} ", style="dim #c0c0d0")
        text.append(f"{shares} sh ", style="#a0a0b0")
        text.append(f"@ {price} ", style="dim #c0c0d0")
        text.append(f"= {value_str:>8}  ", style="bold #e0e0e8")
        role = t.insider_role[:22] if t.insider_role else ""
        text.append(role, style="dim #7a7a8a")
        text.append(f"  ({code_label})\n", style="dim #5a5a6a")
