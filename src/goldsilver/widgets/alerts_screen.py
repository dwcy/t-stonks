"""Modal screen to manage price-level alerts and signal beep toggles."""

from __future__ import annotations

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Switch

from goldsilver.data.settings import AppSettings

_SYMBOL_ALIASES = {
    "XAU": "XAU",
    "GOLD": "XAU",
    "AU": "XAU",
    "XAG": "XAG",
    "SILVER": "XAG",
    "AG": "XAG",
}
_SYMBOL_LABEL = {"XAU": "Gold (XAU)", "XAG": "Silver (XAG)"}


def parse_alert_input(raw: str) -> tuple[str, float] | None:
    parts = raw.strip().upper().split()
    if len(parts) != 2:
        return None
    symbol = _SYMBOL_ALIASES.get(parts[0])
    if symbol is None:
        return None
    try:
        level = float(parts[1].replace(",", "."))
    except ValueError:
        return None
    if level <= 0:
        return None
    return symbol, level


class AlertsScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(
        self,
        settings: AppSettings,
        *,
        on_change: Callable[[], None],
    ) -> None:
        super().__init__()
        self._settings = settings
        self._on_change = on_change

    def compose(self) -> ComposeResult:
        with Container(id="alerts-dialog"):
            yield Label("Price Alerts", id="alerts-title")
            with VerticalScroll(id="alerts-body"):
                with Horizontal(classes="alert-switch-row"):
                    yield Switch(value=self._settings.beep_on_buy, id="alerts-beep-buy")
                    yield Label("Beep on BUY signal", classes="alert-switch-label")
                with Horizontal(classes="alert-switch-row"):
                    yield Switch(
                        value=self._settings.beep_on_sell, id="alerts-beep-sell"
                    )
                    yield Label("Beep on SELL signal", classes="alert-switch-label")
                yield Label("Price levels", classes="alert-section-label")
                with Vertical(id="alerts-list"):
                    for row in self._build_rows():
                        yield row
                with Horizontal(classes="alert-add-row"):
                    yield Input(
                        placeholder="e.g. XAU 2700 or XAG 36.5",
                        id="alerts-add-input",
                    )
                    yield Button("Add", id="alerts-add")
            with Horizontal(id="alerts-actions"):
                yield Button("Close", id="alerts-close")

    def _entries(self) -> list[tuple[str, float]]:
        out: list[tuple[str, float]] = []
        for symbol in ("XAU", "XAG"):
            for level in self._settings.price_alerts.get(symbol, []):
                out.append((symbol, level))
        return out

    def _build_rows(self) -> list[Horizontal]:
        entries = self._entries()
        if not entries:
            return [
                Horizontal(
                    Label("(no alerts set)", classes="alert-empty"),
                    classes="alert-row",
                )
            ]
        rows: list[Horizontal] = []
        for i, (symbol, level) in enumerate(entries):
            rows.append(
                Horizontal(
                    Label(
                        f"{_SYMBOL_LABEL[symbol]}  crosses  {level:g}",
                        classes="alert-label",
                    ),
                    Button("✕", id=f"alert-rm-{i}", classes="alert-remove"),
                    classes="alert-row",
                )
            )
        return rows

    def _refresh_rows(self) -> None:
        try:
            container = self.query_one("#alerts-list", Vertical)
        except NoMatches:
            return
        container.remove_children()
        container.mount(*self._build_rows())

    def _add_alert(self, raw: str) -> None:
        parsed = parse_alert_input(raw)
        if parsed is None:
            return
        symbol, level = parsed
        levels = self._settings.price_alerts.setdefault(symbol, [])
        if level in levels:
            return
        levels.append(level)
        levels.sort()
        self._refresh_rows()
        self._on_change()

    def _remove_alert(self, index: int) -> None:
        entries = self._entries()
        if not (0 <= index < len(entries)):
            return
        symbol, level = entries[index]
        levels = self._settings.price_alerts.get(symbol, [])
        if level in levels:
            levels.remove(level)
            if not levels:
                self._settings.price_alerts.pop(symbol, None)
            self._refresh_rows()
            self._on_change()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "alerts-beep-buy":
            self._settings.beep_on_buy = event.value
            self._on_change()
        elif event.switch.id == "alerts-beep-sell":
            self._settings.beep_on_sell = event.value
            self._on_change()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "alerts-add-input":
            self._add_alert(event.value)
            event.input.value = ""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "alerts-close":
            self.dismiss()
        elif bid == "alerts-add":
            field = self.query_one("#alerts-add-input", Input)
            self._add_alert(field.value)
            field.value = ""
        elif bid.startswith("alert-rm-"):
            try:
                self._remove_alert(int(bid[len("alert-rm-") :]))
            except ValueError:
                pass
