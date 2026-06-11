"""Settings tab for mini charts: row config, fuzzy stock search, and preset watchlist."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Input, Label, OptionList, Switch
from textual.widgets.option_list import Option

from goldsilver.data.stock_presets import PRESET_STOCKS
from goldsilver.data.symbol_search import search_symbols

if TYPE_CHECKING:
    from goldsilver.widgets.plot_settings import PlotSettings


def parse_tickers(raw: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for chunk in raw.replace(";", ",").replace(" ", ",").split(","):
        t = chunk.strip().upper()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _slug(ticker: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in ticker).strip("-")


class MiniChartsTab(Vertical):
    def __init__(self, state: PlotSettings, *, emit: Callable[[], None]) -> None:
        super().__init__(id="minicharts-tab")
        self._state = state
        self._emit = emit
        self._preset_by_slug = {_slug(t): t for t, _ in PRESET_STOCKS}

    def compose(self) -> ComposeResult:
        with Vertical(classes="setting-group"):
            yield Label("Mini charts", classes="setting-label")
            with Horizontal(classes="switch-row"):
                yield Switch(
                    value=self._state.show_stock_row,
                    id="setting-stock-row",
                )
                yield Label("Show mini charts", classes="switch-label")
            yield Label("Tickers (comma-separated)", classes="sub-label")
            yield Input(
                value=", ".join(self._state.stock_tickers),
                placeholder="LUG.TO, LUG.ST, LUMI.ST",
                id="setting-stock-tickers",
            )
        with Vertical(classes="setting-group"):
            yield Label("Watchlist (extra row below)", classes="setting-label")
            yield Label("Search stocks (Enter to search)", classes="sub-label")
            yield Input(
                placeholder="Name or ticker, e.g. Boliden",
                id="stock-search-input",
            )
            results = OptionList(id="stock-search-results")
            results.display = False
            yield results
            with Vertical(id="extra-tickers-list"):
                for row in self._build_extra_rows():
                    yield row
        with Vertical(classes="setting-group"):
            yield Label("Default presets (OMXS30 + extras)", classes="setting-label")
            yield Label("Enabled presets show in the extra row", classes="sub-label")
            with Vertical(id="preset-list"):
                enabled = set(self._state.enabled_preset_tickers)
                for ticker, name in PRESET_STOCKS:
                    yield Checkbox(
                        f"{ticker} — {name}",
                        value=(ticker in enabled),
                        id=f"preset-{_slug(ticker)}",
                        classes="preset-check",
                    )

    def _build_extra_rows(self) -> list[Horizontal]:
        rows: list[Horizontal] = []
        for ticker in self._state.extra_stock_tickers:
            rows.append(
                Horizontal(
                    Label(ticker, classes="extra-ticker-label"),
                    Button("✕", id=f"extra-rm-{_slug(ticker)}", classes="extra-rm"),
                    classes="extra-ticker-row",
                )
            )
        return rows

    def _refresh_extra_rows(self) -> None:
        container = self.query_one("#extra-tickers-list", Vertical)
        container.remove_children()
        rows = self._build_extra_rows()
        if rows:
            container.mount(*rows)

    def _add_extra_ticker(self, symbol: str) -> None:
        t = symbol.strip().upper()
        if not t or t in self._state.extra_stock_tickers:
            return
        self._state.extra_stock_tickers = [*self._state.extra_stock_tickers, t]
        self._refresh_extra_rows()
        self._emit()

    def _remove_extra_ticker(self, slug: str) -> None:
        for ticker in self._state.extra_stock_tickers:
            if _slug(ticker) == slug:
                self._state.extra_stock_tickers = [
                    t for t in self._state.extra_stock_tickers if t != ticker
                ]
                self._refresh_extra_rows()
                self._emit()
                return

    async def _run_search(self, query: str) -> None:
        results = self.query_one("#stock-search-results", OptionList)
        results.clear_options()
        results.add_option(Option("Searching…", disabled=True))
        results.display = True
        matches = await asyncio.to_thread(search_symbols, query)
        results.clear_options()
        if not matches:
            results.add_option(Option("No matches", disabled=True))
            return
        for m in matches:
            results.add_option(Option(m.label, id=m.symbol))

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if (event.switch.id or "") != "setting-stock-row":
            return
        event.stop()
        if event.value != self._state.show_stock_row:
            self._state.show_stock_row = event.value
            self._emit()

    def on_input_changed(self, event: Input.Changed) -> None:
        if (event.input.id or "") != "setting-stock-tickers":
            return
        event.stop()
        parsed = parse_tickers(event.value)
        if parsed != self._state.stock_tickers:
            self._state.stock_tickers = parsed
            self._emit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if (event.input.id or "") != "stock-search-input":
            return
        event.stop()
        query = event.value.strip()
        if query:
            self.run_worker(
                self._run_search(query), exclusive=True, group="symbol-search"
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if (event.option_list.id or "") != "stock-search-results":
            return
        event.stop()
        if event.option.id:
            self._add_extra_ticker(event.option.id)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        cb_id = event.checkbox.id or ""
        if not cb_id.startswith("preset-"):
            return
        event.stop()
        ticker = self._preset_by_slug.get(cb_id[len("preset-") :])
        if ticker is None:
            return
        enabled = list(self._state.enabled_preset_tickers)
        if event.value and ticker not in enabled:
            enabled.append(ticker)
        elif not event.value and ticker in enabled:
            enabled.remove(ticker)
        else:
            return
        self._state.enabled_preset_tickers = enabled
        self._emit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("extra-rm-"):
            event.stop()
            self._remove_extra_ticker(bid[len("extra-rm-") :])
