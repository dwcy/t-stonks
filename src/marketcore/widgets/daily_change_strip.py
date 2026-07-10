"""Small widget rendering the last N trading days as up/down arrow + % change."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from marketcore.models import Bar, DailyChange
from marketcore.widgets.format import DOWN_COLOR, FLAT_COLOR, UP_COLOR

MAX_DAYS = 40


def compute_daily_changes(
    bars: list[Bar], *, max_days: int = MAX_DAYS
) -> list[DailyChange]:
    """Day-over-day % change per bar close, most recent `max_days` entries."""
    changes: list[DailyChange] = []
    for i in range(1, len(bars)):
        prev = bars[i - 1].close
        curr = bars[i].close
        pct = (curr - prev) / prev * 100.0 if prev else 0.0
        direction = "flat" if abs(pct) < 0.01 else ("up" if pct > 0 else "down")
        changes.append(
            DailyChange(
                date=bars[i].time.date(),
                close=curr,
                change_percent=pct,
                direction=direction,
            )
        )
    return changes[-max_days:]


class DailyChangeStrip(Static):
    def __init__(self) -> None:
        super().__init__("")
        self.add_class("daily-change-strip")

    def apply_changes(self, changes: list[DailyChange]) -> None:
        self.update(self._build_text(changes))

    @staticmethod
    def _build_text(changes: list[DailyChange]) -> Text:
        if not changes:
            return Text("No daily history available.", style=FLAT_COLOR)
        text = Text()
        for i, change in enumerate(changes):
            if i > 0:
                text.append("  ")
            if change.direction == "up":
                arrow, color = "▲", UP_COLOR
            elif change.direction == "down":
                arrow, color = "▼", DOWN_COLOR
            else:
                arrow, color = "▬", FLAT_COLOR
            sign = "+" if change.change_percent > 0 else ""
            text.append(f"{arrow}{sign}{change.change_percent:.1f}%", style=color)
        return text
